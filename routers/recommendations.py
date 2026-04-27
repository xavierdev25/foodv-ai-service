import logging
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.schemas import RecommendationRequest, RecommendationResponse
from services.ollama_service import get_recommendations_with_fallback, check_ollama_health, list_ollama_models
from services.cache_service import get_cached, set_cached

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/recommendations", response_model=RecommendationResponse)
@limiter.limit("10/minute")
def recommend(request_http: Request, request: RecommendationRequest):
    try:
        logger.info(
            f"Recomendaciones para usuario {request.user_id} "
            f"con {len(request.available_products)} productos"
        )

        # Intentar desde caché
        products_raw = [p.model_dump() for p in request.available_products]
        cached = get_cached(request.user_id, products_raw)
        if cached:
            return RecommendationResponse(**cached)

        # Generar con Ollama o Groq
        result = get_recommendations_with_fallback(request)

        # Guardar en caché
        set_cached(request.user_id, products_raw, result.model_dump())

        logger.info(f"Recomendaciones generadas: {len(result.recommendations)}")
        return result

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error inesperado: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generando recomendaciones: {exc}")


@router.get("/health/ollama")
def ollama_health():
    try:
        result = check_ollama_health()
        return {"ollama": "ok", "model": result["model"], "available": True}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/models")
def get_models():
    try:
        models = list_ollama_models()
        return {"models": models}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Error conectando con Ollama: {exc}")
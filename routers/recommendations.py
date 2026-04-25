import logging

from fastapi import APIRouter, HTTPException

from models.schemas import RecommendationRequest, RecommendationResponse
from services.ollama_service import get_recommendations, check_ollama_health, list_ollama_models

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/recommendations", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest):
    try:
        logger.info(
            f"Generando recomendaciones para usuario {request.user_id} "
            f"con {len(request.available_products)} productos"
        )
        result = get_recommendations(request)
        logger.info(f"Recomendaciones generadas: {len(result.recommendations)} productos")
        return result
    except ValueError as exc:
        logger.warning(f"Error de validación: {exc}")
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        logger.error(f"Error de runtime: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error inesperado generando recomendaciones: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generando recomendaciones: {exc}")


@router.get("/health/ollama")
def ollama_health():
    """Verifica que Ollama esté corriendo y que el modelo phi3 esté disponible."""
    try:
        result = check_ollama_health()
        return {"ollama": "ok", "model": result["model"], "available": True}
    except RuntimeError as exc:
        logger.error(f"Ollama health check fallido: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error inesperado en health check: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error verificando Ollama: {exc}")


@router.get("/models")
def get_models():
    """Lista los modelos disponibles en Ollama."""
    try:
        models = list_ollama_models()
        return {"models": models}
    except Exception as exc:
        logger.error(f"Error listando modelos: {exc}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Error conectando con Ollama: {exc}")
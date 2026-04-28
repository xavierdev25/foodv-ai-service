"""Endpoints de recomendaciones.

Diseño:

- Handler `async` con `run_in_threadpool` para los servicios sync.
- Rate limit aplicado **realmente** vía decorador (per IP+API key).
- Cache key incluye TODOS los inputs relevantes.
- Errores nunca exponen el mensaje interno crudo: se devuelve un
  `error_id` correlacionable con los logs.
- Endpoint `/models` eliminado (filtraba info de infraestructura).
"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from config import RATE_LIMIT_RECOMMENDATIONS
from models.schemas import (
    OllamaHealthResponse,
    RecommendationRequest,
    RecommendationResponse,
)

from services.cache_service import get_cache_service
from services.logging_filter import hash_user_id
from services.ollama_service import check_ollama_health
from services.orchestrator import AllProvidersFailedError, LLMOrchestrator
from services.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_orchestrator(request: Request) -> LLMOrchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Servicio no inicializado")
    return orchestrator


@router.post("/recommendations", response_model=RecommendationResponse)
@limiter.limit(RATE_LIMIT_RECOMMENDATIONS)
async def recommend(
    request: Request,
    body: RecommendationRequest,
) -> RecommendationResponse:
    err_id = uuid4().hex[:12]
    uid_hash = hash_user_id(body.user_id)

    try:
        logger.info(
            "Recomendaciones request uid=%s products=%d max=%d",
            uid_hash,
            len(body.available_products),
            body.max_recommendations,
        )

        cache = get_cache_service()
        cache_key = cache.make_key(
            user_id=body.user_id,
            product_ids=[p.id for p in body.available_products],
            restrictions=[r.value for r in body.restrictions],
            preferences=body.preferences,
            max_recommendations=body.max_recommendations,
        )

        cached = await run_in_threadpool(cache.get, cache_key)
        if cached:
            logger.info("Cache HIT uid=%s", uid_hash)
            try:
                return RecommendationResponse(**cached)
            except ValidationError:
                logger.warning("Cache corrupto para key=%s, regenerando", cache_key)

        orchestrator = _get_orchestrator(request)
        result = await run_in_threadpool(orchestrator.execute, body)

        await run_in_threadpool(cache.set, cache_key, result.model_dump())

        logger.info(
            "Recomendaciones generadas uid=%s count=%d source=%s",
            uid_hash,
            len(result.recommendations),
            result.generated_by,
        )
        return result

    except AllProvidersFailedError:
        logger.error("[%s] Todos los proveedores LLM fallaron uid=%s", err_id, uid_hash)
        raise HTTPException(
            status_code=503,
            detail={"error_id": err_id, "message": "Servicio de IA temporalmente no disponible"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[%s] Error inesperado uid=%s: %s", err_id, uid_hash, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error_id": err_id, "message": "Error interno"},
        )


@router.get("/health/ollama", response_model=OllamaHealthResponse)
async def ollama_health() -> OllamaHealthResponse:
    try:
        result = await run_in_threadpool(check_ollama_health)
    except RuntimeError as exc:
        logger.warning("Health Ollama DOWN: %s", exc)
        raise HTTPException(status_code=503, detail="Ollama no disponible")
    return OllamaHealthResponse(ollama="ok", model=result["model"], available=True)

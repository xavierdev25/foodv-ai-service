"""FastAPI app principal.

Responsabilidades:

- Wire-up de middlewares (auth con `hmac.compare_digest`, CORS, rate limit).
- Bootstrap del orquestador LLM con la cadena de proveedores.
- Health checks: `/health` (liveness, público) y `/health/ready` (readiness).
- Documentación deshabilitada en producción.
"""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from config import (
    ALLOWED_ORIGINS,
    API_SECRET_KEY,
    GROQ_API_KEY,
    IS_PRODUCTION,
    OLLAMA_MODEL,
)
from models.schemas import ReadinessResponse
from routers import recommendations
from services.cache_service import get_cache_service
from services.groq_service import GroqProvider
from services.logging_filter import install_secret_filter
from services.ollama_service import OllamaProvider, check_ollama_health
from services.orchestrator import LLMOrchestrator
from services.rate_limit import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
install_secret_filter()
logger = logging.getLogger(__name__)


_PUBLIC_PATHS = {"/health", "/health/ready"}


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "Demasiadas requests, intenta más tarde"},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FoodV AI Service iniciando (env=%s)", "production" if IS_PRODUCTION else "dev")
    logger.info("CORS permitido para: %s", ALLOWED_ORIGINS)
    logger.info("Autenticación API key: %s", "activada" if API_SECRET_KEY else "DESACTIVADA")

    providers = [OllamaProvider(), GroqProvider()]
    app.state.orchestrator = LLMOrchestrator(providers)

    try:
        check_ollama_health()
        logger.info("Ollama UP (modelo=%s)", OLLAMA_MODEL)
    except Exception as exc:
        logger.warning("Ollama no disponible al arranque: %s", exc)

    if GROQ_API_KEY:
        logger.info("Groq fallback configurado")
    else:
        logger.warning("Groq fallback NO configurado — sin redundancia LLM")

    cache = get_cache_service()
    logger.info("Cache Redis: %s", "UP" if cache.is_available else "DOWN")

    yield
    logger.info("FoodV AI Service detenido")


app = FastAPI(
    title="FoodV AI Service",
    description="Microservicio de recomendaciones con IA para FoodV",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None,
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
    openapi_tags=[{"name": "recommendations", "description": "Motor de recomendaciones con IA"}],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    """Valida `X-API-Key` con comparación de tiempo constante (hmac)."""
    path = request.url.path
    if path in _PUBLIC_PATHS:
        return await call_next(request)
    if not IS_PRODUCTION and path in {"/docs", "/openapi.json"}:
        return await call_next(request)

    if not API_SECRET_KEY:
        # En dev sin clave configurada: dejamos pasar (config.py ya logueó el warning).
        return await call_next(request)

    provided = request.headers.get("X-API-Key", "")
    expected = API_SECRET_KEY
    valid = hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))

    if not valid:
        return JSONResponse(
            status_code=401,
            content={"error": "API key inválida o ausente"},
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["X-API-Key", "Content-Type", "Accept"],
    max_age=600,
)

app.include_router(recommendations.router, prefix="/api/ai", tags=["recommendations"])


@app.get("/health")
def health():
    """Liveness — siempre responde si el proceso está vivo."""
    return {"status": "ok", "service": "foodv-ai-service", "version": "2.0.0"}


@app.get("/health/ready", response_model=ReadinessResponse)
def readiness():
    """Readiness — listo para recibir tráfico cuando algún LLM y configuración mínima están OK."""
    ollama_ok = False
    try:
        check_ollama_health()
        ollama_ok = True
    except Exception:
        pass

    cache = get_cache_service()
    ready = ollama_ok or bool(GROQ_API_KEY)

    response = ReadinessResponse(
        ready=ready,
        ollama="up" if ollama_ok else "down",
        groq_configured=bool(GROQ_API_KEY),
        cache="up" if cache.is_available else "down",
    )
    if not ready:
        return JSONResponse(status_code=503, content=response.model_dump())
    return response

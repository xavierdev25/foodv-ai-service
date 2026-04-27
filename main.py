import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from routers import recommendations
from config import ALLOWED_ORIGINS, API_SECRET_KEY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FoodV AI Service iniciado")
    logger.info(f"CORS permitido para: {ALLOWED_ORIGINS}")
    logger.info(f"Autenticación por API key: {'activada' if API_SECRET_KEY else 'desactivada'}")
    yield
    logger.info("FoodV AI Service detenido")


app = FastAPI(
    title="FoodV AI Service",
    description="Microservicio de recomendaciones con IA para FoodV",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
    openapi_tags=[{"name": "recommendations", "description": "Motor de recomendaciones con IA"}],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    if API_SECRET_KEY and request.url.path not in ["/health", "/docs", "/openapi.json"]:
        key = request.headers.get("X-API-Key", "")
        if key != API_SECRET_KEY:
            return JSONResponse(
                status_code=401,
                content={"error": "API key inválida o ausente"}
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(recommendations.router, prefix="/api/ai", tags=["recommendations"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "foodv-ai-service", "version": "2.0.0"}
import json
import hashlib
import logging
import redis
from config import REDIS_URL, AI_CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)

try:
    _redis = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    _redis.ping()
    CACHE_AVAILABLE = True
    logger.info("Redis cache conectado correctamente")
except Exception as e:
    _redis = None
    CACHE_AVAILABLE = False
    logger.warning(f"Redis no disponible — cache deshabilitado: {e}")


def _make_key(user_id: int, products: list) -> str:
    product_ids = sorted([p.get("id", 0) for p in products])
    raw = f"ai:recs:{user_id}:{product_ids}"
    return "foodv:" + hashlib.md5(raw.encode()).hexdigest()


def get_cached(user_id: int, products: list) -> dict | None:
    if not CACHE_AVAILABLE:
        return None
    try:
        key = _make_key(user_id, products)
        value = _redis.get(key)
        if value:
            logger.info(f"Cache HIT para usuario {user_id}")
            return json.loads(value)
    except Exception as e:
        logger.warning(f"Error leyendo cache: {e}")
    return None


def set_cached(user_id: int, products: list, data: dict) -> None:
    if not CACHE_AVAILABLE:
        return
    try:
        key = _make_key(user_id, products)
        _redis.setex(key, AI_CACHE_TTL_SECONDS, json.dumps(data))
        logger.info(f"Cache SET para usuario {user_id} (TTL={AI_CACHE_TTL_SECONDS}s)")
    except Exception as e:
        logger.warning(f"Error escribiendo cache: {e}")
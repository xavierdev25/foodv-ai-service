import logging
import json
import re

import ollama

from models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    ProductRecommendation,
)

logger = logging.getLogger(__name__)

MODEL_NAME = "phi3"


# ---------------------------------------------------------------------------
# Ollama health
# ---------------------------------------------------------------------------

def check_ollama_health() -> dict:
    """Verifica conexión con Ollama y disponibilidad del modelo phi3."""
    try:
        models_response = ollama.list()
        available_models = [m.model for m in models_response.models]
        logger.info(f"Modelos disponibles en Ollama: {available_models}")

        model_found = any(MODEL_NAME in name for name in available_models)
        if not model_found:
            raise RuntimeError(
                f"Modelo '{MODEL_NAME}' no encontrado en Ollama. "
                f"Modelos disponibles: {available_models}"
            )

        return {"status": "ok", "model": MODEL_NAME}
    except ConnectionError as exc:
        logger.error(f"No se pudo conectar a Ollama: {exc}")
        raise RuntimeError(f"No se pudo conectar a Ollama: {exc}") from exc


def list_ollama_models() -> list[dict]:
    """Lista todos los modelos disponibles en Ollama."""
    models_response = ollama.list()
    return [
        {
            "name": m.model,
            "size": f"{m.size / (1024**3):.1f} GB" if m.size else "desconocido",
        }
        for m in models_response.models
    ]


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_score_prompt(product: dict, restrictions: list, preferences: list) -> str:
    restrictions_text = ", ".join(restrictions) if restrictions else "ninguna"
    preferences_text = ", ".join(preferences) if preferences else "ninguna"
    return f"""Eres un evaluador de comida universitaria en Lima, Perú.
Restricciones dietéticas del estudiante: {restrictions_text}
Preferencias: {preferences_text}
Producto: {product['nombre']} (S/.{product['precio']}, {product['categoria']})

Si el producto viola las restricciones dietéticas, responde exactamente: 0.0
Si no viola restricciones, evalúa del 0.1 al 1.0 según las preferencias.
Responde ÚNICAMENTE con un número decimal entre 0.0 y 1.0, sin texto adicional."""


def build_reason_prompt(product: dict, restrictions: list, preferences: list) -> str:
    restrictions_text = ", ".join(restrictions) if restrictions else "ninguna"
    preferences_text = ", ".join(preferences) if preferences else "ninguna"
    return f"""En máximo 4 palabras en español, describe por qué "{product['nombre']}" es bueno para un estudiante con preferencias: {preferences_text}. Solo las 4 palabras, sin puntuación."""

def evaluate_single_product(product: dict, restrictions: list, preferences: list) -> dict | None:
    try:
        # Paso 1: obtener score
        score_response = ollama.chat(
            model="phi3",
            messages=[
                {"role": "system", "content": "Responde SOLO con un número decimal entre 0.0 y 1.0."},
                {"role": "user", "content": build_score_prompt(product, restrictions, preferences)}
            ],
            options={"temperature": 0.1, "num_predict": 10}
        )
        score_text = score_response["message"]["content"].strip()
        # Extraer primer número decimal del texto
        score_match = re.search(r"\d+\.?\d*", score_text)
        if not score_match:
            logger.warning(f"No se pudo extraer score para producto {product['id']}: {score_text}")
            return None
        score = max(0.0, min(1.0, float(score_match.group())))

        if score == 0.0:
            logger.info(f"Producto {product['id']} descartado por restricciones")
            return None

        # Paso 2: obtener reason solo si el score es válido
        reason_response = ollama.chat(
            model="phi3",
            messages=[
                {"role": "system", "content": "Responde SOLO con 4 palabras en español."},
                {"role": "user", "content": build_reason_prompt(product, restrictions, preferences)}
            ],
            options={"temperature": 0.3, "num_predict": 20}
        )
        reason = reason_response["message"]["content"].strip()[:80]

        return {
            "product_id": product["id"],
            "nombre": product["nombre"],
            "precio": float(product["precio"]),
            "categoria": product["categoria"],
            "score": score,
            "reason": reason
        }
    except Exception as e:
        logger.warning(f"Error evaluando producto {product['id']}: {e}")
        return None

# ---------------------------------------------------------------------------
# JSON extraction (robusta)
# ---------------------------------------------------------------------------

def extract_json(text: str) -> dict:
    """Extrae JSON de la respuesta del modelo, tolerando markdown y truncamiento."""
    # Intentar parsear directamente
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Buscar JSON entre bloques markdown
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Buscar desde la primera llave hasta el final del texto
    start = text.find("{")
    if start != -1:
        fragment = text[start:]
        # Intentar reparar JSON truncado añadiendo cierres faltantes
        for closing in ["]}}", "]}", "}"]:
            try:
                return json.loads(fragment + closing)
            except json.JSONDecodeError:
                continue
        # Intentar con el fragmento tal cual
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No se pudo extraer JSON válido de la respuesta del modelo: {text[:200]}")


# ---------------------------------------------------------------------------
# Validación post-LLM
# ---------------------------------------------------------------------------

def _validate_recommendations(
    items: list[dict],
    request: RecommendationRequest,
) -> list[ProductRecommendation]:
    """Valida y filtra las recomendaciones contra los productos reales."""
    valid_products = {p.id: p for p in request.available_products}
    validated: list[ProductRecommendation] = []

    for item in items:
        pid = item.get("product_id")
        if pid not in valid_products:
            logger.warning(f"Descartando recomendación con product_id={pid} (no existe en productos disponibles)")
            continue

        # Corregir datos que el modelo pudo haber alucinado
        real = valid_products[pid]
        validated.append(
            ProductRecommendation(
                product_id=pid,
                nombre=real.nombre,
                precio=real.precio,
                categoria=real.categoria,
                score=max(0.0, min(1.0, float(item.get("score", 0.5)))),
                reason=item.get("reason", "Recomendado por IA")[:80],
            )
        )

    return validated


# ---------------------------------------------------------------------------
# Core recommendation
# ---------------------------------------------------------------------------

def get_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    if not request.available_products:
        return RecommendationResponse(
            user_id=request.user_id,
            recommendations=[]
        )

    logger.info(f"Enviando prompt a Ollama (phi3) para usuario {request.user_id}")

    products = [p.model_dump() if hasattr(p, 'model_dump') else p for p in request.available_products]
    restrictions = list(request.restrictions)
    preferences = list(request.preferences)

    evaluated = []
    for product in products:
        result = evaluate_single_product(product, restrictions, preferences)
        if result is not None:
            evaluated.append(result)

    # Filtrar productos con score 0 (violaron restricciones) y ordenar por score
    filtered = [r for r in evaluated if r.get("score", 0) > 0.0]
    filtered.sort(key=lambda x: x.get("score", 0), reverse=True)

    top = filtered[:request.max_recommendations]

    recommendations = [ProductRecommendation(**item) for item in top]

    logger.info(f"Recomendaciones generadas: {len(recommendations)} de {len(products)} productos")

    return RecommendationResponse(
        user_id=request.user_id,
        recommendations=recommendations
    )
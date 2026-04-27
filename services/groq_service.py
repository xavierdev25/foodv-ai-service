import logging
import json
import re
from groq import Groq
from config import GROQ_API_KEY
from models.schemas import RecommendationRequest, RecommendationResponse, ProductRecommendation

logger = logging.getLogger(__name__)


def get_recommendations_groq(request: RecommendationRequest) -> RecommendationResponse:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY no configurado")

    client = Groq(api_key=GROQ_API_KEY)

    restrictions_text = ", ".join(request.restrictions) if request.restrictions else "ninguna"
    preferences_text = ", ".join(request.preferences) if request.preferences else "ninguna"
    products_text = "\n".join([
        f"- ID:{p.id} {p.nombre} (S/.{p.precio}, {p.categoria})"
        for p in request.available_products
    ])

    prompt = f"""Eres un asistente de recomendaciones de comida universitaria en Lima, Perú.

Usuario ID: {request.user_id}
Restricciones dietéticas: {restrictions_text}
Preferencias: {preferences_text}

Productos disponibles:
{products_text}

Selecciona los {request.max_recommendations} mejores productos para este usuario.
Descarta cualquier producto que viole las restricciones dietéticas.
Responde ÚNICAMENTE con un JSON array con este formato exacto (sin texto adicional):
[
  {{"product_id": 1, "score": 0.95, "reason": "Ideal para almuerzo"}},
  {{"product_id": 2, "score": 0.80, "reason": "Opción económica"}}
]"""

    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500,
    )

    content = response.choices[0].message.content.strip()

    # Extraer JSON array
    match = re.search(r'\[.*\]', content, re.DOTALL)
    if not match:
        raise ValueError(f"Groq no devolvió JSON válido: {content[:200]}")

    items = json.loads(match.group())
    valid_products = {p.id: p for p in request.available_products}

    recommendations = []
    for item in items:
        pid = item.get("product_id")
        if pid not in valid_products:
            continue
        real = valid_products[pid]
        recommendations.append(ProductRecommendation(
            product_id=pid,
            nombre=real.nombre,
            precio=real.precio,
            categoria=real.categoria,
            score=max(0.0, min(1.0, float(item.get("score", 0.5)))),
            reason=item.get("reason", "Recomendado por IA")[:80],
        ))

    logger.info(f"Groq generó {len(recommendations)} recomendaciones")
    return RecommendationResponse(
        user_id=request.user_id,
        recommendations=recommendations,
        generated_by="groq/llama3-8b"
    )
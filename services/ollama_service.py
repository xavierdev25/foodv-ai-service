import ollama
import json
from models.schemas import RecommendationRequest, RecommendationResponse, ProductRecommendation

def build_prompt(request: RecommendationRequest) -> str:
    products_text = "\n".join([
        f"- ID:{p['id']} | {p['nombre']} | S/.{p['precio']} | {p['categoria']}"
        for p in request.available_products
    ])

    restrictions_text = ", ".join(request.restrictions) if request.restrictions else "ninguna"
    preferences_text = ", ".join(request.preferences) if request.preferences else "ninguna"

    return f"""Eres un sistema de recomendaciones de comida para una universidad en Lima, Perú.

El estudiante tiene las siguientes restricciones dietéticas: {restrictions_text}
Sus preferencias son: {preferences_text}

Productos disponibles:
{products_text}

Selecciona los {request.max_recommendations} mejores productos para este estudiante.
Responde SOLO con un JSON válido con esta estructura, sin texto adicional:
{{
  "recommendations": [
    {{
      "product_id": <id>,
      "nombre": "<nombre>",
      "precio": <precio>,
      "categoria": "<categoria>",
      "score": <0.0 a 1.0>,
      "reason": "<razón breve en español>"
    }}
  ]
}}"""

def get_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    prompt = build_prompt(request)

    response = ollama.chat(
        model="phi3",
        messages=[
            {
                "role": "system",
                "content": "Eres un asistente de recomendaciones de comida. Responde SIEMPRE con JSON válido únicamente, sin texto adicional ni markdown."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    content = response["message"]["content"].strip()

    # Limpiar markdown si el modelo lo incluye
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    data = json.loads(content)

    recommendations = [
        ProductRecommendation(**item)
        for item in data.get("recommendations", [])
    ]

    return RecommendationResponse(
        user_id=request.user_id,
        recommendations=recommendations
    )

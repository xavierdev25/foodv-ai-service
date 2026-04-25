from pydantic import BaseModel
from typing import List, Optional

class DietaryRestriction(str):
    VEGETARIANO = "VEGETARIANO"
    VEGANO = "VEGANO"
    SIN_GLUTEN = "SIN_GLUTEN"
    SIN_LACTOSA = "SIN_LACTOSA"
    NINGUNA = "NINGUNA"

class RecommendationRequest(BaseModel):
    user_id: int
    restrictions: List[str] = []
    preferences: List[str] = []
    available_products: List[dict] = []
    max_recommendations: int = 5

class ProductRecommendation(BaseModel):
    product_id: int
    nombre: str
    precio: float
    categoria: str
    score: float
    reason: str

class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: List[ProductRecommendation]
    generated_by: str = "phi3"

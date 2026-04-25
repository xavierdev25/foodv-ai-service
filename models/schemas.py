from pydantic import BaseModel, Field, field_validator
from typing import List
from enum import Enum


class DietaryRestriction(str, Enum):
    VEGETARIANO = "VEGETARIANO"
    VEGANO = "VEGANO"
    SIN_GLUTEN = "SIN_GLUTEN"
    SIN_LACTOSA = "SIN_LACTOSA"
    NINGUNA = "NINGUNA"


class AvailableProduct(BaseModel):
    """Modelo tipado para los productos disponibles en lugar de dict genérico."""
    id: int
    nombre: str
    precio: float = Field(ge=0)
    categoria: str


class RecommendationRequest(BaseModel):
    user_id: int = Field(ge=1, description="ID del usuario")
    restrictions: List[str] = []
    preferences: List[str] = []
    available_products: List[AvailableProduct] = []
    max_recommendations: int = Field(default=5, ge=1, le=20)

    @field_validator("available_products")
    @classmethod
    def validate_products(cls, v):
        if not v:
            raise ValueError("available_products no puede estar vacío")
        return v


class ProductRecommendation(BaseModel):
    product_id: int
    nombre: str
    precio: float
    categoria: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: List[ProductRecommendation]
    generated_by: str = "phi3"


class OllamaHealthResponse(BaseModel):
    ollama: str
    model: str
    available: bool


class OllamaModelInfo(BaseModel):
    name: str
    size: str
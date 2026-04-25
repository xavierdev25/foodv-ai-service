from fastapi import APIRouter, HTTPException
from models.schemas import RecommendationRequest, RecommendationResponse
from services.ollama_service import get_recommendations

router = APIRouter()

@router.post("/recommendations", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest):
    try:
        return get_recommendations(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando recomendaciones: {str(e)}")

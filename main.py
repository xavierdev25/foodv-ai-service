from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import recommendations

app = FastAPI(
    title="FoodV AI Service",
    description="Microservicio de recomendaciones con NLP para FoodV",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommendations.router, prefix="/api/ai", tags=["recommendations"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "foodv-ai-service"}

# FoodV AI Service

Microservicio de recomendaciones gastronómicas para FoodV. Desarrollado con FastAPI, evalúa productos usando el modelo phi3 via Ollama con Groq como fallback, caché en Redis y autenticación por API key.

[![Tests](https://img.shields.io/badge/tests-11%20passing-brightgreen)](tests/)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136.1-teal)

## Stack Tecnológico

| Tecnología | Versión | Uso |
|---|---|---|
| Python | 3.11 | Lenguaje principal |
| FastAPI | 0.136.1 | Framework web |
| Uvicorn | 0.46.0 | Servidor ASGI |
| Ollama SDK | 0.6.1 | Modelo phi3 local |
| Groq SDK | 0.28.0 | Fallback LLM en la nube |
| Redis | 5.0.1 | Caché de recomendaciones |
| SlowAPI | 0.1.9 | Rate limiting |
| Pydantic | 2.13.3 | Validación de datos |

## Arquitectura

```
foodv-ai-service/
├── main.py                  # FastAPI app + CORS + API key middleware + rate limiting
├── config.py                # Variables de entorno
├── models/
│   └── schemas.py           # Modelos Pydantic
├── routers/
│   └── recommendations.py   # Endpoints con caché y rate limiting
├── services/
│   ├── ollama_service.py    # Evaluación con phi3 + extracción JSON robusta
│   ├── groq_service.py      # Fallback con Groq/llama3-8b
│   └── cache_service.py     # Caché Redis con TTL configurable
├── tests/
│   ├── test_prompt_builder.py
│   ├── test_validate_recommendations.py
│   └── test_cache_service.py
├── Dockerfile
├── pytest.ini
└── requirements.txt
```

## Flujo de Recomendaciones

```
Request → API Key validation → Rate limit (10/min)
       → Cache hit? → Return cached
       → Cache miss → Ollama (phi3)?
                   → Success → Cache + Return
                   → Fail    → Groq (llama3-8b)?
                             → Success → Cache + Return
                             → Fail    → 503 error
```

## Estrategia de Evaluación

Cada producto se evalúa individualmente con phi3 en dos pasos:

1. **Score** — phi3 asigna un puntaje de `0.0` a `1.0`. Si el producto viola una restricción dietética el score es `0.0` y se descarta automáticamente.
2. **Reason** — phi3 genera una razón de máximo 4 palabras en español.

Los productos se ordenan por score y se retornan los `max_recommendations` mejores, con validación post-LLM para evitar alucinaciones.

## Seguridad

- **API Key** — header `X-API-Key` requerido en todos los endpoints (excepto `/health`)
- **CORS** — orígenes restringidos vía `ALLOWED_ORIGINS`
- **Rate Limiting** — 10 req/min por IP con SlowAPI
- **Swagger** — activo en `/docs` (deshabilitar en producción via Nginx)

## Requisitos Previos

- Python 3.11+
- [Ollama](https://ollama.com/download) instalado
- Modelo phi3 descargado
- Redis corriendo (opcional — caché se deshabilita si no está disponible)

```bash
ollama pull phi3
```

## Instalación

```bash
git clone https://github.com/TU_USUARIO/foodv-ai-service.git
cd foodv-ai-service

python -m venv venv
.\venv\Scripts\activate   # Windows
source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
cp .env.example .env
# Edita .env con tus valores
```

### Variables de entorno (`.env`)

```env
OLLAMA_HOST=http://localhost:11434
AI_SERVICE_PORT=8001
ALLOWED_ORIGINS=http://localhost:8080
API_SECRET_KEY=change-me-in-production
GROQ_API_KEY=                          # Obtener en console.groq.com
REDIS_URL=redis://localhost:6379
AI_CACHE_TTL_SECONDS=300
```

## Ejecución

```bash
# Terminal 1 — Ollama
ollama serve

# Terminal 2 — AI Service
.\venv\Scripts\activate
uvicorn main:app --reload --port 8001
```

| URL | Descripción |
|---|---|
| `http://localhost:8001/health` | Health check |
| `http://localhost:8001/docs` | Swagger UI |
| `http://localhost:8001/api/ai/recommendations` | Endpoint principal |
| `http://localhost:8001/api/ai/health/ollama` | Estado de Ollama |

## API

### `POST /api/ai/recommendations`

**Headers:** `X-API-Key: tu-api-key`

**Request:**

```json
{
  "user_id": 1,
  "restrictions": ["VEGETARIANO"],
  "preferences": ["económico", "almuerzo"],
  "available_products": [
    {"id": 1, "nombre": "Ensalada César", "precio": 8.50, "categoria": "COMIDA"},
    {"id": 2, "nombre": "Lomo Saltado",   "precio": 14.00, "categoria": "COMIDA"},
    {"id": 3, "nombre": "Jugo de naranja","precio": 4.00,  "categoria": "BEBIDA"}
  ],
  "max_recommendations": 3
}
```

**Response:**

```json
{
  "user_id": 1,
  "recommendations": [
    {
      "product_id": 1,
      "nombre": "Ensalada César",
      "precio": 8.50,
      "categoria": "COMIDA",
      "score": 0.92,
      "reason": "Saludable y económica"
    },
    {
      "product_id": 3,
      "nombre": "Jugo de naranja",
      "precio": 4.00,
      "categoria": "BEBIDA",
      "score": 0.85,
      "reason": "Complemento ideal almuerzo"
    }
  ],
  "generated_by": "phi3"
}
```

### Restricciones dietéticas soportadas

| Valor | Descripción |
|---|---|
| `VEGETARIANO` | Sin carnes |
| `VEGANO` | Sin productos animales |
| `SIN_GLUTEN` | Sin gluten |
| `SIN_LACTOSA` | Sin lácteos |
| `NINGUNA` | Sin restricciones |

## Tests

```bash
.\venv\Scripts\activate
pytest tests/ -v
```

**11 tests — 0 fallos:**

| Suite | Tests | Descripción |
|---|---|---|
| `test_prompt_builder` | 5 | Construcción de prompts y extracción JSON |
| `test_validate_recommendations` | 5 | Validación post-LLM y filtros |
| `test_cache_service` | 4 | Caché Redis con mocks |

## Docker

```bash
# Solo el microservicio
docker build -t foodv-ai-service .
docker run -p 8001:8001 --env-file .env foodv-ai-service

# Stack completo (desde el backend)
cd ../backend
docker-compose up -d
```

## Proyecto Relacionado

[foodv-backend](https://github.com/xavierdev25/foodv-backend-main) — Backend principal con Spring Boot 4.x

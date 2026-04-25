# FoodV AI Service

Microservicio de recomendaciones de comida para FoodV, desarrollado con FastAPI y el modelo de lenguaje phi3 via Ollama.

## Stack Tecnológico

| Tecnología | Versión |
|---|---|
| Python | 3.11 |
| FastAPI | 0.136.1 |
| Uvicorn | 0.46.0 |
| Ollama SDK | 0.6.1 |
| Pydantic | 2.13.3 |
| Modelo LLM | phi3 (2.3 GB) |

## Arquitectura

```
foodv-ai-service/
├── main.py                  # Aplicación FastAPI + CORS + rutas
├── models/
│   └── schemas.py           # Modelos Pydantic con validaciones
├── routers/
│   └── recommendations.py   # Endpoints de recomendaciones
├── services/
│   └── ollama_service.py    # Lógica de evaluación con phi3
├── Dockerfile
└── requirements.txt
```

## Estrategia de Evaluación

El microservicio evalúa cada producto individualmente en dos pasos:

1. **Score** — phi3 asigna un puntaje de 0.0 a 1.0 según las restricciones y preferencias del estudiante. Si el producto viola una restricción dietética, el score es 0.0 y se descarta.
2. **Reason** — phi3 genera una razón breve en español de máximo 4 palabras explicando la recomendación.

Los productos se ordenan por score de mayor a menor y se retornan los `max_recommendations` mejores.

## Requisitos Previos

- Python 3.11+
- [Ollama](https://ollama.com/download) instalado y corriendo
- Modelo phi3 descargado

```bash
ollama pull phi3
```

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/foodv-ai-service.git
cd foodv-ai-service

# 2. Crear entorno virtual
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

## Ejecución

```bash
# 1. Asegurarse que Ollama esté corriendo
ollama serve

# 2. Arrancar el servicio (en otra terminal)
uvicorn main:app --reload --port 8001
```

El servicio estará disponible en `http://localhost:8001`.

## Endpoints

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/health` | Health check del servicio |
| GET | `/api/ai/health/ollama` | Verifica conexión con Ollama y modelo phi3 |
| GET | `/api/ai/models` | Lista modelos disponibles en Ollama |
| POST | `/api/ai/recommendations` | Genera recomendaciones personalizadas |

### POST `/api/ai/recommendations`

**Request:**

```json
{
  "user_id": 1,
  "restrictions": ["VEGETARIANO"],
  "preferences": ["económico", "saludable"],
  "available_products": [
    {"id": 1, "nombre": "Ensalada fresca", "precio": 6.00, "categoria": "COMIDA"},
    {"id": 2, "nombre": "Jugo de naranja", "precio": 4.00, "categoria": "BEBIDA"}
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
      "nombre": "Ensalada fresca",
      "precio": 6.0,
      "categoria": "COMIDA",
      "score": 0.95,
      "reason": "Saludable y económica"
    }
  ],
  "generated_by": "phi3"
}
```

### Restricciones dietéticas soportadas

| Valor | Descripción |
|---|---|
| `VEGETARIANO` | Excluye carnes |
| `VEGANO` | Excluye todos los productos animales |
| `SIN_GLUTEN` | Excluye productos con gluten |
| `SIN_LACTOSA` | Excluye productos lácteos |
| `NINGUNA` | Sin restricciones |

## Docker

```bash
# Construir imagen
docker build -t foodv-ai-service .

# Correr contenedor
docker run -p 8001:8001 foodv-ai-service
```

## Proyecto Relacionado

- [foodv-backend](https://github.com/xavierdev25/foodv-backend) — Backend principal con Spring Boot

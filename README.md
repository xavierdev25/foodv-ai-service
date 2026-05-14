# FoodV AI Service

Microservicio de recomendaciones gastronómicas para FoodV. Está desarrollado con FastAPI y evalúa productos disponibles usando Ollama con el modelo `phi3`; si Ollama no responde o falla, usa Groq como fallback. Incluye caché Redis, rate limiting, validación estricta de entradas y autenticación por API key.

[![Tests](https://img.shields.io/badge/tests-79%20passing-brightgreen)](tests/)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136.1-teal)

## Stack Tecnológico

| Tecnología | Versión | Uso |
|---|---:|---|
| Python | 3.11 | Lenguaje principal |
| FastAPI | 0.136.1 | Framework web |
| Uvicorn | 0.46.0 | Servidor ASGI en desarrollo |
| Gunicorn | 23.0.0 | Servidor de producción |
| Ollama SDK | 0.6.1 | Modelo local `phi3` |
| Groq SDK | 0.28.0 | Fallback LLM en la nube |
| Redis | 5.0.1 | Caché de recomendaciones |
| SlowAPI | 0.1.9 | Rate limiting |
| Pydantic | 2.13.3 | Validación de datos |
| httpx | 0.28.1 | Timeouts HTTP |
| pytest | 8.3.4 | Tests automatizados |

## Arquitectura

```text
foodv-ai-service/
├── main.py                    # FastAPI app, middlewares, CORS, auth, lifespan
├── config.py                  # Configuración desde variables de entorno
├── models/
│   └── schemas.py             # Modelos Pydantic y enums
├── routers/
│   └── recommendations.py     # Endpoints de recomendaciones y health Ollama
├── services/
│   ├── llm_provider.py        # Protocol común para proveedores LLM
│   ├── orchestrator.py        # Fallback Ollama → Groq
│   ├── ollama_service.py      # Prompt batch, llamada JSON a phi3, health
│   ├── groq_service.py        # Fallback cloud con Groq
│   ├── validators.py          # Normalización y validación post-LLM
│   ├── sanitizer.py           # Sanitización contra prompt injection
│   ├── cache_service.py       # Caché Redis con TTL configurable
│   ├── rate_limit.py          # Configuración SlowAPI
│   └── logging_filter.py      # Redacción de secretos y hash de user_id
├── tests/                     # 79 tests unitarios/API/seguridad
├── Dockerfile
├── pytest.ini
└── requirements.txt
```

## Flujo de Recomendaciones

```text
Request
  → API key middleware
  → Rate limit por IP/API key
  → Validación Pydantic estricta
  → Cache hit?
      → sí: retorna respuesta cacheada
      → no: Ollama phi3 en batch con una llamada JSON
            → éxito: valida, ordena, cachea y retorna
            → falla: Groq fallback
                    → éxito: valida, ordena, cachea y retorna
                    → falla: 503
```

## Estrategia de Evaluación

Ollama evalúa todos los productos en batch en una sola llamada JSON. El prompt:

- Incluye restricciones dietéticas, preferencias y productos disponibles.
- Trata los datos del usuario como datos, no como instrucciones.
- Solicita JSON estricto sin markdown ni texto adicional.
- No envía `user_id` al modelo.

Luego el servicio valida la salida:

- Descarta productos inexistentes.
- Normaliza scores fuera de rango.
- Elimina duplicados.
- Ordena por score.
- Limita a `max_recommendations`.
- Trunca razones largas.

Si Ollama no está disponible o devuelve una respuesta inválida, Groq se usa como fallback con el modelo configurado en `GROQ_MODEL`.

## Seguridad

- **API key**: header `X-API-Key`.
- **Comparación timing-safe**: validación con `hmac.compare_digest`.
- **Dev vs prod**:
  - En `ENV=development`, `API_SECRET_KEY` vacío desactiva la autenticación y registra un warning.
  - En `ENV=production`, `API_SECRET_KEY` es obligatorio y debe tener al menos 32 caracteres.
- **Docs**:
  - En desarrollo: `/docs` y `/openapi.json` están disponibles.
  - En producción: `/docs` y `/openapi.json` quedan deshabilitados.
- **CORS**: orígenes explícitos en `ALLOWED_ORIGINS`; no se permite `*`.
- **Rate limiting**: configurado con `RATE_LIMIT_RECOMMENDATIONS`.
- **Sanitización**: bloqueo de patrones de prompt injection en preferencias, nombres y categorías.
- **Logs seguros**: filtros para redacción de tokens/API keys y hash de `user_id`.

## Requisitos Previos

- Python 3.11+
- Ollama instalado
- Modelo `phi3` descargado
- Redis corriendo si se desea caché
- API key Groq opcional para fallback cloud

```bash
ollama pull phi3
```

## Instalación

```bash
git clone https://github.com/xavier25dev/foodv-ai-service.git
cd foodv-ai-service

python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` con tus valores.

## Variables de Entorno

| Variable | Ejemplo | Descripción |
|---|---|---|
| `ENV` | `development` | Entorno: `development`, `staging`, `production` |
| `API_SECRET_KEY` | `secret-token-32chars-min` | API key compartida con el backend |
| `ALLOWED_ORIGINS` | `http://localhost:8080` | Orígenes CORS separados por coma |
| `OLLAMA_HOST` | `http://localhost:11434` | URL de Ollama |
| `OLLAMA_MODEL` | `phi3` | Modelo local |
| `OLLAMA_TIMEOUT_SECONDS` | `30` | Timeout para Ollama |
| `GROQ_API_KEY` | `` | API key Groq opcional |
| `GROQ_MODEL` | `llama3-8b-8192` | Modelo Groq fallback |
| `GROQ_TIMEOUT_SECONDS` | `20` | Timeout para Groq |
| `REDIS_URL` | `redis://localhost:6379` | URL Redis |
| `REDIS_MAX_CONNECTIONS` | `50` | Pool máximo Redis |
| `AI_CACHE_TTL_SECONDS` | `300` | TTL de caché |
| `RATE_LIMIT_RECOMMENDATIONS` | `10/minute` | Límite SlowAPI |
| `AI_SERVICE_PORT` | `8001` | Puerto del servicio |

Ejemplo:

```env
ENV=development
API_SECRET_KEY=
ALLOWED_ORIGINS=http://localhost:8080
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=phi3
OLLAMA_TIMEOUT_SECONDS=30
GROQ_API_KEY=
GROQ_MODEL=llama3-8b-8192
GROQ_TIMEOUT_SECONDS=20
REDIS_URL=redis://localhost:6379
REDIS_MAX_CONNECTIONS=50
AI_CACHE_TTL_SECONDS=300
RATE_LIMIT_RECOMMENDATIONS=10/minute
AI_SERVICE_PORT=8001
```

## Ejecución en Desarrollo

```bash
# Terminal 1: Ollama
ollama serve

# Terminal 2: AI Service
source venv/bin/activate
uvicorn main:app --reload --port 8001
```

En Windows:

```bash
.\venv\Scripts\activate
uvicorn main:app --reload --port 8001
```

## Modo Producción

En producción se recomienda ejecutar con Gunicorn + Uvicorn workers, como define el `Dockerfile`:

```bash
gunicorn main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8001 \
  --timeout 60
```

Variables mínimas en producción:

```env
ENV=production
API_SECRET_KEY=generar-con-secrets-token-urlsafe-48
ALLOWED_ORIGINS=https://tu-backend-o-dominio
OLLAMA_HOST=http://ollama-host:11434
OLLAMA_MODEL=phi3
GROQ_API_KEY=
REDIS_URL=redis://redis:6379
```

En `ENV=production`, si `API_SECRET_KEY` está vacío o es inseguro, el proceso aborta. Además, `/docs` y `/openapi.json` quedan deshabilitados automáticamente.

## Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/health` | No | Liveness |
| `GET` | `/health/ready` | No | Readiness: Ollama/Groq/Redis |
| `GET` | `/docs` | No en dev | Swagger UI, deshabilitado en producción |
| `POST` | `/api/ai/recommendations` | `X-API-Key` si está configurada | Recomendaciones |
| `GET` | `/api/ai/health/ollama` | `X-API-Key` si está configurada | Estado de Ollama y modelo |

## API

### `POST /api/ai/recommendations`

Headers:

```http
X-API-Key: tu-api-key
Content-Type: application/json
```

Request:

```json
{
  "user_id": 1,
  "restrictions": ["VEGETARIANO"],
  "preferences": ["economico", "almuerzo"],
  "available_products": [
    {
      "id": 1,
      "nombre": "Ensalada Cesar",
      "precio": 8.5,
      "categoria": "COMIDA"
    },
    {
      "id": 2,
      "nombre": "Lomo Saltado",
      "precio": 14.0,
      "categoria": "COMIDA"
    },
    {
      "id": 3,
      "nombre": "Jugo de naranja",
      "precio": 4.0,
      "categoria": "BEBIDA"
    }
  ],
  "max_recommendations": 3
}
```

Response:

```json
{
  "user_id": 1,
  "recommendations": [
    {
      "product_id": 1,
      "nombre": "Ensalada Cesar",
      "precio": 8.5,
      "categoria": "COMIDA",
      "score": 0.92,
      "reason": "Saludable y economica"
    },
    {
      "product_id": 3,
      "nombre": "Jugo de naranja",
      "precio": 4.0,
      "categoria": "BEBIDA",
      "score": 0.85,
      "reason": "Complemento ideal"
    }
  ],
  "generated_by": "phi3"
}
```

## Restricciones de Contenido

### Restricciones dietéticas soportadas

| Valor | Descripción |
|---|---|
| `VEGETARIANO` | Sin carnes |
| `VEGANO` | Sin productos animales |
| `SIN_GLUTEN` | Sin gluten |
| `SIN_LACTOSA` | Sin lácteos |
| `NINGUNA` | Sin restricciones |

### Validación anti prompt injection

El servicio valida y sanitiza:

- `restrictions`: solo acepta valores del enum.
- `preferences`: rechaza saltos de línea, backticks, roles `system/assistant` y patrones de instrucciones.
- `available_products.nombre`: rechaza caracteres o patrones peligrosos.
- `available_products.categoria`: rechaza caracteres o patrones peligrosos.
- `available_products`: no puede estar vacío ni tener IDs duplicados.
- `max_recommendations`: rango permitido de 1 a 20.

## Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

Suite actual: **79 tests**.

| Área | Cobertura |
|---|---|
| Prompt builder | Prompt batch, delimitadores y extracción JSON |
| Validadores | Normalización, ordenamiento, deduplicación y trimming |
| Cache | Redis disponible/no disponible, TTL y JSON corrupto |
| Fallback | Orquestador Ollama → Groq |
| Sanitizer | Limpieza de texto, razones seguras y límites |
| Logging filter | Redacción de secretos y hash de user_id |
| API security | API key, 401, 422, health público |
| Prompt injection | Rechazo de payloads maliciosos |

## Docker

```bash
# Solo el microservicio
docker build -t foodv-ai-service .
docker run -p 8001:8001 --env-file .env foodv-ai-service
```

También puede levantarse desde el backend:

```bash
cd ../foodv-backend-main
docker-compose up -d
```

El `Dockerfile` usa Gunicorn con workers Uvicorn y health check contra `/health/ready`.

## Troubleshooting

### Ollama no responde

Verifica que Ollama esté corriendo:

```bash
ollama serve
ollama list
```

Si falta el modelo:

```bash
ollama pull phi3
```

También revisa:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=phi3
```

### Groq devuelve rate limit o falla

Si Groq responde con rate limit, el servicio devolverá 503 si Ollama tampoco está disponible. Revisa cuota, modelo y timeout:

```env
GROQ_API_KEY=...
GROQ_MODEL=llama3-8b-8192
GROQ_TIMEOUT_SECONDS=20
```

### Redis no conecta

Redis es opcional para caché; si no conecta, el servicio sigue funcionando sin caché.

```bash
redis-cli ping
```

Revisa:

```env
REDIS_URL=redis://localhost:6379
REDIS_MAX_CONNECTIONS=50
```

### 401 en `/api/ai/recommendations`

Si `API_SECRET_KEY` está configurada, cada request debe enviar:

```http
X-API-Key: valor-de-API_SECRET_KEY
```

El backend debe usar el mismo valor en:

```env
AI_SERVICE_SECRET_KEY=valor-de-API_SECRET_KEY
```

### 503 en recomendaciones

Significa que ningún proveedor LLM respondió correctamente. Verifica:

- Ollama está activo.
- `phi3` está descargado.
- `GROQ_API_KEY` está configurada si se requiere fallback.
- `/health/ready` devuelve `ready=true`.

## Proyecto Relacionado

`foodv-backend-main` — Backend principal con Spring Boot 4.x + Java 21.

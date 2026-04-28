# SECURITY.md — FoodV AI Service

Documento de referencia de seguridad y privacidad del microservicio.

---

## 1. Modelo de amenazas (resumen)

| Actor | Vector | Mitigación |
|---|---|---|
| Cliente externo no autenticado | Brute-force / scraping de endpoints | API key con `hmac.compare_digest`, rate limit por (IP+API key), `/docs` deshabilitado en producción. |
| Cliente con API key válida (insider) | Prompt injection vía `preferences`/`restrictions` | Schema Pydantic estricto + `DietaryRestriction` enum + sanitizador defensivo en el prompt builder. |
| Administrador del catálogo | Inyección vía `nombre`/`categoría` de productos | Validación regex en `AvailableProduct` + sanitización antes del prompt. |
| LLM (Ollama/Groq) que alucine product IDs | Recomendar productos inexistentes | `normalize_recommendation_items` filtra contra `available_products` reales. |
| LLM que devuelva HTML/scripts en `reason` | XSS si el frontend lo renderiza como HTML | `safe_reason` con `html.escape` + truncado a 80 chars. |
| Atacante con MITM al cloud | Lectura de PII enviada a Groq | NO se envía `user_id` ni datos identificables. Solo restricciones agregadas + catálogo. |
| Atacante interno con acceso a logs | Exfiltración de API keys / tokens | `SecretFilter` redacta `Bearer ...`, `X-API-Key:`, `api_key=...`. |
| LLM colgado | Threadpool exhaustion | Timeout HTTP explícito (Ollama: 30s, Groq: 20s). |

---

## 2. Flujo de datos (qué cruza qué frontera)

```
┌──────────────┐  X-API-Key + JSON   ┌────────────────────┐
│ Spring Boot  │  ─────────────────► │ FoodV AI Service   │
│  (backend)   │                     │  (este servicio)   │
└──────────────┘                     └─────────┬──────────┘
                                               │
              ┌────────────────────────────────┼─────────────────────────┐
              │                                │                         │
              ▼                                ▼                         ▼
     ┌─────────────────┐             ┌────────────────┐         ┌────────────────┐
     │ Ollama (local)  │             │ Redis (cache)  │         │ Groq (cloud)   │
     │ host = OLLAMA_  │             │ host = REDIS_  │         │ AWS us-east    │
     │  HOST           │             │  URL           │         │                │
     └─────────────────┘             └────────────────┘         └────────────────┘
```

### Datos enviados a Ollama (local)

| Dato | Origen | PII | Notas |
|---|---|---|---|
| `restrictions` (enum) | Spring | Sensible (salud) | Permanece on-premise |
| `preferences` (lista corta) | Spring | Sensible | Permanece on-premise |
| `available_products` (id, nombre, categoría, precio) | Catálogo interno | No PII | Datos públicos del menú |
| `user_id` | Spring | NO se incluye en el prompt | El prompt usa delimitadores `<USER_DATA>` sin user_id |

### Datos enviados a Groq (cloud, fallback)

| Dato | Enviado | Notas |
|---|---|---|
| `restrictions` agregadas | Sí | Identidad NO asociada |
| `preferences` agregadas | Sí | Identidad NO asociada |
| `available_products` | Sí | Datos públicos del menú |
| `user_id` | **NO** | Eliminado del prompt explícitamente |
| `email`, `nombre` | **NO** | Nunca llegan a este servicio |

### Datos almacenados en Redis

- Clave: `foodv:ai:recs:<sha256(user_id|product_ids|restrictions|preferences|max_recs)>`
- Valor: respuesta serializada (`product_id`, `nombre`, `precio`, `categoria`, `score`, `reason`)
- TTL: configurable (default 300s)
- **NO se almacena PII directa**.

### Datos en logs

- `user_id` se hashea (`sha256(user_id)[:12]`) antes de loguear.
- `SecretFilter` redacta secretos antes de la escritura.
- Las preferencias y restricciones del usuario NO se loguean.

---

## 3. Configuración de seguridad obligatoria en producción

`config.py` aborta el arranque del proceso si:

- `ENV=production` Y `API_SECRET_KEY` está vacía, contiene un valor de la lista de defaults inseguros, o tiene menos de 32 caracteres.
- `ALLOWED_ORIGINS` contiene `*`.

Generar la API key con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 4. Checklist de deploy a producción

### Bloqueantes

- [ ] `ENV=production` configurado en el contenedor.
- [ ] `API_SECRET_KEY` generada con `secrets.token_urlsafe(48)`, mínimo 32 chars, no en lista de defaults.
- [ ] `ALLOWED_ORIGINS` con dominios HTTPS reales, sin `*`, sin `localhost`.
- [ ] `GROQ_API_KEY` configurada (o aceptar conscientemente la falta de fallback).
- [ ] Reverse proxy (Nginx) con TLS 1.2+ delante del servicio.
- [ ] `--forwarded-allow-ips` restringido al rango del balanceador si se confía en `X-Forwarded-For`.
- [ ] Redis con AUTH habilitado y red privada.
- [ ] Ollama escuchando solo en `localhost` o red privada (NUNCA público).
- [ ] Logs centralizados con retención conforme a política (30-90 días recomendado).
- [ ] Healthcheck del orquestador (k8s/docker-compose) apunta a `/health/ready`.

### Recomendados

- [ ] Métricas Prometheus expuestas en endpoint protegido (no implementado en este repo).
- [ ] Alertas: Ollama DOWN > 5 min, Groq fallback > 10% de requests, error rate > 1%.
- [ ] Backup periódico de Redis (si se usa para algo más que cache transitorio — aquí no).
- [ ] Auditoría trimestral de las dependencias (`pip-audit`).

---

## 5. Cómo reportar una vulnerabilidad

Reportes responsables a: `security@foodv.example` (PGP fingerprint en el sitio público).
NO abrir issues públicos para vulnerabilidades.
Plazo de respuesta: 5 días hábiles.

---

## 6. Rotación de secretos

| Secreto | Frecuencia recomendada |
|---|---|
| `API_SECRET_KEY` | Cada 90 días o ante sospecha de leak. Rotación coordinada con el backend Spring. |
| `GROQ_API_KEY` | Cada 180 días. Revocar en consola Groq y emitir una nueva. |
| Redis password | Cada 180 días. |

---

## 7. Cumplimiento (referencia)

- **GDPR / LGPD**: las restricciones dietéticas pueden constituir datos de salud (Art. 9 GDPR). Se minimizan: no se asocian con identidad antes de salir del host. El consentimiento explícito debe gestionarse en el backend principal.
- **OWASP Top 10 (LLM)**: ver mitigaciones en sección 1 (LLM01 prompt injection, LLM02 insecure output handling, LLM06 sensitive information disclosure).

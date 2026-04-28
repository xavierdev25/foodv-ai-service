FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && apt-get upgrade -y \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd -r foodv \
 && useradd -r -g foodv -m -d /home/foodv -s /usr/sbin/nologin foodv

WORKDIR /app

COPY --chown=foodv:foodv requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=foodv:foodv . .

USER foodv

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8001/health/ready || exit 1

CMD ["gunicorn", "main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--worker-tmp-dir", "/dev/shm", \
     "--bind", "0.0.0.0:8001", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]

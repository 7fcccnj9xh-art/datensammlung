# ============================================================
# Backend Dockerfile – Multi-Stage Build
# Python 3.11 / FastAPI
# ============================================================

# --- Stage 1: Basis mit Dependencies ---
FROM python:3.11-slim AS base

WORKDIR /app

# System-Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libffi-dev \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Produktion ---
FROM base AS production

COPY . .

# Logs und Exports Verzeichnisse anlegen
RUN mkdir -p /app/logs /app/exports /app/obsidian

# Nicht-root User (Sicherheit)
RUN addgroup --gid 1001 appgroup \
    && adduser --uid 1001 --gid 1001 --no-create-home --disabled-password appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8420

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8420", \
     "--workers", "2", "--log-level", "info"]

# --- Stage 3: Entwicklung (mit debugpy) ---
FROM base AS development

RUN pip install debugpy watchfiles

COPY . .

RUN mkdir -p /app/logs /app/exports

EXPOSE 8420 5678

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8420", "--reload"]

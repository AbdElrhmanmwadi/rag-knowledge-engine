FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY src ./src
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN cp ./src/models/db_schemes/minirag/alembic.ini.example ./src/models/db_schemes/minirag/alembic.ini \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /data/rag \
    && chown -R app:app /app /data/rag \
    && chmod +x ./docker-entrypoint.sh

USER app

# The entrypoint runs alembic migrations, then execs uvicorn on port 8000.
ENTRYPOINT ["/app/docker-entrypoint.sh"]

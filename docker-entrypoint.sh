#!/bin/sh
# Backend container entrypoint: apply DB migrations, then launch the API.
set -e

ALEMBIC_DIR=/app/src/models/db_schemes/minirag

# env.py builds the connection URL from POSTGRES_* env vars when the ini is blank.
echo "Applying database migrations (alembic upgrade head)..."
( cd "$ALEMBIC_DIR" && alembic upgrade head )

echo "Starting Uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000

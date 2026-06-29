#!/bin/sh
# Backend container entrypoint: apply DB migrations, then launch the API.
set -e

ALEMBIC_DIR=/app/src/models/db_schemes/minirag

# The real alembic.ini is gitignored; fall back to the committed example.
if [ ! -f "$ALEMBIC_DIR/alembic.ini" ]; then
  echo "alembic.ini not found, creating it from alembic.ini.example"
  cp "$ALEMBIC_DIR/alembic.ini.example" "$ALEMBIC_DIR/alembic.ini"
fi

# env.py builds the connection URL from POSTGRES_* env vars when the ini is blank.
echo "Applying database migrations (alembic upgrade head)..."
if ! ( cd "$ALEMBIC_DIR" && alembic upgrade head ); then
  echo "WARNING: migrations failed; starting the app anyway."
fi

echo "Starting Uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000

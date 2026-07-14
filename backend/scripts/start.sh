#!/usr/bin/env sh
set -eu

alembic upgrade head
exec uvicorn factory_hub.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-8100}"

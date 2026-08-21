#!/usr/bin/env bash
set -euo pipefail

ROLE="${1:-api}"

echo "[aca] role=${ROLE}"

case "${ROLE}" in
  api)
    echo "[aca] running alembic upgrade head..."
    alembic upgrade head
    echo "[aca] starting uvicorn..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    echo "[aca] starting arq worker..."
    exec arq app.workers.settings.WorkerSettings
    ;;
  *)
    echo "Unknown role: ${ROLE} (use api|worker)" >&2
    exit 1
    ;;
esac

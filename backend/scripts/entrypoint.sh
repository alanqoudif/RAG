#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] waiting for platform database..."
python scripts/wait_for_deps.py

echo "[entrypoint] running Alembic migrations..."
alembic upgrade head

if [ "${SEED_ON_STARTUP:-false}" = "true" ]; then
    echo "[entrypoint] seeding development data..."
    python scripts/seed.py
fi

echo "[entrypoint] starting application: $*"
exec "$@"

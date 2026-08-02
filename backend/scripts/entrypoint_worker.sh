#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint-worker] waiting for platform database..."
python scripts/wait_for_deps.py

echo "[entrypoint-worker] starting: $*"
exec "$@"

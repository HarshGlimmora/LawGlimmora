#!/usr/bin/env bash
# Production-style start command. Works on Render, fly.io, Docker, or
# anywhere $PORT is supplied. Locally, $PORT falls back to 8000.
#
# Usage:  ./start.sh
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-2}"

exec uvicorn api.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers "${WORKERS}" \
    --proxy-headers \
    --forwarded-allow-ips='*'

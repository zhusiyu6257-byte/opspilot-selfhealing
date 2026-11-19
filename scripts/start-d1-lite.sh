#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE_FILE="$ROOT_DIR/.run/dev-mode"

echo "[info] Starting local backend stack..."
bash "$ROOT_DIR/scripts/start-dev.sh"

if [ -n "${OPSPILOT_HTTPS:-}" ]; then
  HTTPS_MODE="$OPSPILOT_HTTPS"
elif [ -f "$MODE_FILE" ]; then
  HTTPS_MODE="$(cat "$MODE_FILE")"
else
  HTTPS_MODE="0"
fi

export READONLY_UPSTREAM="${READONLY_UPSTREAM:-$([ "$HTTPS_MODE" = "1" ] && echo https://127.0.0.1:8000 || echo http://127.0.0.1:8000)}"
export READONLY_PROXY_PORT="${READONLY_PROXY_PORT:-8081}"
export READONLY_ALLOWED_ORIGINS="${READONLY_ALLOWED_ORIGINS:-https://opspilot.de5.net,http://127.0.0.1:5177,http://localhost:5177}"

if [ "$HTTPS_MODE" = "1" ]; then
  export NODE_TLS_REJECT_UNAUTHORIZED=0
fi

echo "[info] Starting readonly API proxy on http://127.0.0.1:${READONLY_PROXY_PORT}"
exec node "$ROOT_DIR/scripts/readonly-api-proxy.mjs"

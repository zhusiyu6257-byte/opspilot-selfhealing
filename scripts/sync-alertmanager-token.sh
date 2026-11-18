#!/usr/bin/env bash
# 从 backend/.env 同步 Webhook Token 给 Alertmanager 容器读取。
# 不打印 Token；生成的文件仅本地存在，已被 .gitignore 的 secrets/ 规则排除。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRET_DIR="$ROOT/deploy/secrets"
SECRET_FILE="$SECRET_DIR/opspilot_token"

mkdir -p "$SECRET_DIR"
(
  cd "$ROOT/backend" && .venv/bin/python3 -c \
    "from app.core.config import settings; print(settings.ALERT_WEBHOOK_TOKEN, end='')"
) > "$SECRET_FILE"

chmod 600 "$SECRET_FILE"
echo "[ok] Alertmanager Token 已同步：$SECRET_FILE（mode 600，内容未显示）"

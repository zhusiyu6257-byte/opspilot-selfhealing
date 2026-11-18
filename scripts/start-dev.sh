#!/usr/bin/env bash
# 一键拉起本地开发链路：后端 API + Celery Worker（+ 前端）。
# 幂等：已经在跑的进程会被跳过，不会重复拉起。
# 默认 HTTP；OPSPILOT_HTTPS=1 时前后端都启用本地自签证书。
# 前提：PostgreSQL / Redis 已由 deploy/docker-compose.dev.yml 启动。
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
VENV="$BACKEND_DIR/.venv/bin"
CERT_DIR="$ROOT/deploy/certs"
MODE_FILE="$ROOT/.run/dev-mode"
mkdir -p "$ROOT/.run"

# 优先用显式环境变量；否则沿用上次成功启动的模式，避免切换后误判。
if [ -n "${OPSPILOT_HTTPS:-}" ]; then
  HTTPS_MODE="$OPSPILOT_HTTPS"
elif [ -f "$MODE_FILE" ]; then
  HTTPS_MODE="$(cat "$MODE_FILE")"
else
  HTTPS_MODE="0"
fi
echo "$HTTPS_MODE" > "$MODE_FILE"

# 模式里用 [u]/[c] 括号技巧：能匹配真正的进程，
# 却不会匹配到「命令行里写着这段模式」的调用方 shell 自己。
is_running() { pgrep -f "$1" >/dev/null 2>&1; }

if [ "$HTTPS_MODE" = "1" ]; then
  if [ ! -f "$CERT_DIR/dev.crt" ] || [ ! -f "$CERT_DIR/dev.key" ] || [ ! -f "$CERT_DIR/ca.crt" ]; then
    bash "$ROOT/scripts/generate-dev-ca.sh"
  fi
  # 后端证书现在由本地 CA 签发；curl 用 --cacert 走真正校验，不再用 -k。
  CURL_FLAGS="--cacert $CERT_DIR/ca.crt -fsS"
  API_SCHEME="https"
  FRONT_SCHEME="https"
  SSL_ARGS="--ssl-keyfile $CERT_DIR/dev.key --ssl-certfile $CERT_DIR/dev.crt"
  echo "[info] 模式：HTTPS（本地 CA 签发证书，浏览器需导入 ca.crt 才不告警）"
else
  CURL_FLAGS="-fsS"
  API_SCHEME="http"
  FRONT_SCHEME="http"
  SSL_ARGS=""
  echo "[info] 模式：HTTP（回退模式；切换模式前请先停掉旧进程）"
fi

if is_running "[u]vicorn app.main:app"; then
  echo "[skip] 后端 API 已在运行"
else
  ( cd "$BACKEND_DIR" && setsid nohup "$VENV/uvicorn" app.main:app \
      --host 0.0.0.0 --port 8000 $SSL_ARGS --reload >> uvicorn.log 2>&1 < /dev/null & )
  echo "[ok]   后端 API 已启动（日志 backend/uvicorn.log）"
fi

if is_running "[c]elery.*app.core.celery_app"; then
  echo "[skip] Celery Worker 已在运行"
else
  ( cd "$BACKEND_DIR" && setsid nohup "$VENV/celery" -A app.core.celery_app:celery_app \
      worker --loglevel=info --concurrency=2 >> celery_worker.log 2>&1 < /dev/null & )
  echo "[ok]   Celery Worker 已启动（日志 backend/celery_worker.log）"
fi

OTHER_SCHEME="http"; [ "$FRONT_SCHEME" = "http" ] && OTHER_SCHEME="https"

if curl $CURL_FLAGS "${FRONT_SCHEME}://127.0.0.1:5173/" >/dev/null 2>&1; then
  echo "[skip] 前端 dev server 已在运行（${FRONT_SCHEME}）"
elif curl $CURL_FLAGS "${OTHER_SCHEME}://127.0.0.1:5173/" >/dev/null 2>&1; then
  echo "[warn] 前端正在 ${OTHER_SCHEME} 模式运行，与当前 ${FRONT_SCHEME} 模式不一致；请先停掉旧进程再切换"
else
  ( cd "$ROOT/frontend" && OPSPILOT_HTTPS="$HTTPS_MODE" setsid nohup npm run dev \
      >> vite.log 2>&1 < /dev/null & )
  echo "[ok]   前端 dev server 已启动（日志 frontend/vite.log）"
fi

sleep 3
if curl $CURL_FLAGS "${API_SCHEME}://127.0.0.1:8000/api/v1/healthz" >/dev/null 2>&1; then
  echo "[ok]   健康检查通过：数据库与缓存均可连通"
elif curl $CURL_FLAGS "${OTHER_SCHEME}://127.0.0.1:8000/api/v1/healthz" >/dev/null 2>&1; then
  echo "[warn] 后端正在 ${OTHER_SCHEME} 模式运行，与当前 ${API_SCHEME} 模式不一致；请先停掉旧进程再切换"
else
  echo "[warn] 健康检查未通过，请查看 backend/uvicorn.log 与依赖容器状态"
fi

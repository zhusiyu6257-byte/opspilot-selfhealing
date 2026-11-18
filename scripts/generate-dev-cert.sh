#!/usr/bin/env bash
# 生成仅用于本地开发的自签名证书。
# 自签 = 自己给自己发证，浏览器会提示「不受信任」，这是正常的；
# 生产环境必须使用受信任 CA（Let's Encrypt / 企业内网 CA）签发的证书。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="$ROOT/deploy/certs"
KEY="$CERT_DIR/dev.key"
CRT="$CERT_DIR/dev.crt"

mkdir -p "$CERT_DIR"

if [ -f "$KEY" ] && [ -f "$CRT" ]; then
  echo "[skip] 本地证书已存在：$CERT_DIR"
else
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
    -keyout "$KEY" \
    -out "$CRT" \
    -subj "/C=CN/O=OpsPilot/OU=LocalDev/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
    -addext "basicConstraints=CA:FALSE" \
    -addext "keyUsage=digitalSignature,keyEncipherment" \
    -addext "extendedKeyUsage=serverAuth" >/dev/null 2>&1
  chmod 600 "$KEY"
  chmod 644 "$CRT"
  echo "[ok]   已生成本地开发证书：$CERT_DIR"
fi

echo "证书信息："
openssl x509 -in "$CRT" -noout -subject -ext subjectAltName
echo "注意：私钥已 chmod 600，且 deploy/certs/ 已被 .gitignore 排除。"

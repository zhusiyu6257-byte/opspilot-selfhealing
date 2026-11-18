#!/usr/bin/env bash
# 生成"本地私有 CA + 由它签发的后端证书"，用于替代自签证书。
#
# 大白话：
#   自签证书 = 自己写一张身份证说自己是谁，别人没法核实。
#   私有 CA   = 先建一个"本地公证处"（CA），由它给后端发证。
#   容器里装上公证处的公章（ca.crt），以后看到后端出示的证件，
#   只要公章对得上就放行——这就是真正的校验，不再需要"跳过验证"。
#
# 浏览器那一侧仍会提示不受信任，因为系统不认识这个"本地公证处"。
# 想消除提示，需把 ca.crt 导入操作系统/浏览器的信任根（仅本机）。
#
# 生产环境请用可信 CA（Let's Encrypt / 企业 CA）签发的证书，本脚本仅供本机开发。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="$ROOT/deploy/certs"
CA_KEY="$CERT_DIR/ca.key"
CA_CRT="$CERT_DIR/ca.crt"
SRV_KEY="$CERT_DIR/dev.key"
SRV_CSR="$CERT_DIR/dev.csr"
SRV_CRT="$CERT_DIR/dev.crt"
EXT_FILE="$CERT_DIR/dev.ext"

mkdir -p "$CERT_DIR"

if [ -f "$CA_KEY" ] && [ -f "$CA_CRT" ] && [ -f "$SRV_KEY" ] && [ -f "$SRV_CRT" ]; then
  echo "[skip] 本地 CA 与服务端证书已存在：$CERT_DIR"
else
  # 1) 本地公证处：CA 自签根证书
  if [ ! -f "$CA_KEY" ] || [ ! -f "$CA_CRT" ]; then
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
      -keyout "$CA_KEY" -out "$CA_CRT" \
      -subj "/C=CN/O=OpsPilot/OU=LocalDevCA/CN=OpsPilot Local Dev CA" \
      -addext "basicConstraints=critical,CA:TRUE" \
      -addext "keyUsage=critical,keyCertSign,cRLSign" >/dev/null 2>&1
    chmod 600 "$CA_KEY"
    chmod 644 "$CA_CRT"
    echo "[ok]   本地 CA 已生成：$CA_CRT"
  fi

  # 2) 服务端私钥 + 签证请求
  openssl req -newkey rsa:2048 -nodes \
    -keyout "$SRV_KEY" -out "$SRV_CSR" \
    -subj "/C=CN/O=OpsPilot/OU=LocalDev/CN=localhost" >/dev/null 2>&1

  # 3) 证书要能对上的名字：本机访问 + 容器内访问后端都列进去
  cat > "$EXT_FILE" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,DNS:host.docker.internal,IP:127.0.0.1
EOF

  openssl x509 -req -in "$SRV_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" \
    -CAcreateserial -out "$SRV_CRT" -days 365 -extfile "$EXT_FILE" >/dev/null 2>&1
  chmod 600 "$SRV_KEY"
  chmod 644 "$SRV_CRT"

  # 4) 签完就删中间文件：CSR 与扩展文件留着没用，私钥绝不外传
  rm -f "$SRV_CSR" "$EXT_FILE" "$CERT_DIR/ca.srl"

  echo "[ok]   后端证书已由本地 CA 签发：$SRV_CRT"
fi

echo "后端证书信息："
openssl x509 -in "$SRV_CRT" -noout -subject -ext subjectAltName
echo "签发者："
openssl x509 -in "$SRV_CRT" -noout -issuer
echo "提示：deploy/certs/ 已被 .gitignore 排除；浏览器消除告警需把 ca.crt 导入信任根。"

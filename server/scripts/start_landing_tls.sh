#!/usr/bin/env bash
# 落地页 TLS 实例：演练域名 https 入口（开发用自签证书；生产由 nginx + 真实证书终结 TLS）。
# 前置（一次性）：sudo setcap 'cap_net_bind_service=+ep' server/.venv/bin/python
#   允许普通用户绑定 443；venv 重建（poetry install）后需重新执行。
set -e
cd "$(dirname "$0")/.."

LOG=/tmp/phishlab-landing-tls.log
if ss -ltn 2>/dev/null | grep -q ':443 '; then
  echo "443 已被占用："
  ss -ltnp 2>/dev/null | grep ':443 ' || true
  exit 1
fi
nohup .venv/bin/uvicorn landing.main:app --host 0.0.0.0 --port 443 \
  --ssl-keyfile certs/oa-verify.cn.key --ssl-certfile certs/oa-verify.cn.crt \
  >> "$LOG" 2>&1 &
echo "TLS 实例已启动（pid $!），日志：$LOG"

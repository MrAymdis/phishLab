#!/usr/bin/env bash
# PhishLab 一键启动（裸机，无 Docker）——幂等，已在跑的自动跳过
#   core 8080 / track 8081 / landing 8082 + TLS 443 / celery worker + beat / 前端 vite 5173
# 日志统一 /tmp/phishlab-*.log
# 用法：
#   ./start-all.sh          全部拉起（默认）
#   ./start-all.sh status   查看各服务运行状态
# 注意：机器重启后服务不自动拉起，直接跑本脚本即可；443 绑定依赖
#   /usr/bin/python3.12 上的 cap_net_bind_service（venv 重建后需重跑：
#   sudo setcap 'cap_net_bind_service=+ep' server/.venv/bin/python，注意 setcap 会穿透符号链接）
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER="$ROOT/server"
WEB="$ROOT/web"

log()  { echo "[启动] $1 → 日志 $2"; }
skip() { echo "[跳过] $1 已在运行"; }

start_port() { # 名称 端口 工作目录 启动命令...
  local name=$1 port=$2 dir=$3; shift 3
  if ss -ltn 2>/dev/null | grep -q ":$port "; then
    skip "$name（:${port}）"
    return 0
  fi
  local lf="/tmp/phishlab-$name.log"
  (cd "$dir" && nohup "$@" >> "$lf" 2>&1 &)
  log "$name（:${port}）" "$lf"
}

start_proc() { # 名称 匹配串 工作目录 启动命令...
  local name=$1 pat=$2 dir=$3; shift 3
  if pgrep -f "$pat" >/dev/null 2>&1; then
    skip "$name"
    return 0
  fi
  local lf="/tmp/phishlab-$name.log"
  (cd "$dir" && nohup "$@" >> "$lf" 2>&1 &)
  log "$name" "$lf"
}

status() {
  for p in 8080 8081 8082 443 5173; do
    if ss -ltn 2>/dev/null | grep -q ":$p "; then
      echo "  :$p  运行中"
    else
      echo "  :$p  未监听"
    fi
  done
  for s in "worker:celery -A worker worker" "beat:celery -A worker beat"; do
    local n=${s%%:*} pat=${s#*:}
    if pgrep -f "$pat" >/dev/null 2>&1; then
      echo "  $n   运行中"
    else
      echo "  $n   未运行"
    fi
  done
}

if [ "${1:-}" = "status" ]; then
  echo "PhishLab 服务状态："
  status
  exit 0
fi

start_port core    8080 "$SERVER" "$SERVER/.venv/bin/python" -m uvicorn app.main:app    --host 0.0.0.0 --port 8080
start_port track   8081 "$SERVER" "$SERVER/.venv/bin/python" -m uvicorn track.main:app  --host 0.0.0.0 --port 8081
start_port landing 8082 "$SERVER" "$SERVER/.venv/bin/python" -m uvicorn landing.main:app --host 0.0.0.0 --port 8082
start_port landing-tls 443 "$SERVER" "$SERVER/.venv/bin/uvicorn" landing.main:app --host 0.0.0.0 --port 443 \
  --ssl-keyfile certs/oa-verify.cn.key --ssl-certfile certs/oa-verify.cn.crt
start_proc worker "celery -A worker worker" "$SERVER" "$SERVER/.venv/bin/celery" -A worker worker -l info
start_proc beat   "celery -A worker beat"   "$SERVER" "$SERVER/.venv/bin/celery" -A worker beat   -l info
start_port web    5173 "$WEB" npm run dev

echo ""
echo "等待服务就绪……"
sleep 6
echo ""
echo "== 监听端口 =="
ss -ltn 2>/dev/null | grep -E ":(8080|8081|8082|443|5173) " || true
echo ""
echo "== 冒烟检查 =="
curl -s -o /dev/null -w "core    http://127.0.0.1:8080  → %{http_code}\n" http://127.0.0.1:8080/api/v1/open-apps/stats || true
curl -s -o /dev/null -w "landing https://127.0.0.1       → %{http_code}\n" -k https://127.0.0.1/ || true
curl -s -o /dev/null -w "web     http://127.0.0.1:5173  → %{http_code}\n" http://127.0.0.1:5173/ || true
echo ""
echo "日志：/tmp/phishlab-{core,track,landing,landing-tls,worker,beat,web}.log"

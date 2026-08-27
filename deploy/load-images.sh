#!/usr/bin/env bash
# 在【目标服务器】上执行：导入基础镜像（离线部署用）。
# 用法：bash deploy/load-images.sh [images.tar 路径，默认 ./images.tar]
set -euo pipefail

TAR="${1:-images.tar}"

if [ ! -f "$TAR" ]; then
  echo "镜像包不存在：$TAR（先在联网机器上跑 deploy/export-images.sh 导出）" >&2
  exit 1
fi

docker load -i "$TAR"
echo "✓ 基础镜像已导入；server 镜像构建使用包内离线 wheel（server/vendor/wheels），无需外网。"
echo "  继续：docker compose -f deploy/docker-compose.yml up -d --build"

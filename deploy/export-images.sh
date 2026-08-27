#!/usr/bin/env bash
# 在【联网且有 Docker】的机器上执行：拉取编排所需基础镜像并导出为 images.tar。
# 用法：bash deploy/export-images.sh [输出路径，默认 images.tar]
set -euo pipefail

IMAGES=(mysql:8.0 redis:7-alpine minio/minio nginx:alpine python:3.11-slim)
OUT="${1:-images.tar}"

for img in "${IMAGES[@]}"; do
  docker pull "$img"
done

docker save "${IMAGES[@]}" -o "$OUT"
echo "✓ 已导出 $OUT（$(du -sh "$OUT" | cut -f1)）"
echo "  将 $OUT 拷贝到目标服务器，执行：bash deploy/load-images.sh $OUT"

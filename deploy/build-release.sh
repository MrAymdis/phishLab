#!/usr/bin/env bash
# 构建私有化发布包：phishlab-release-YYYYMMDD.tar.gz（平铺结构，见 docs/部署手册.md §1）。
# 用法：bash deploy/build-release.sh [版本号，默认当天日期]
# 前置：1) web/dist 已构建（npm run build）；2) server/vendor/wheels 已下载离线依赖
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-$(date +%Y%m%d)}"
STAGE="$ROOT/release/stage"
OUT="$ROOT/release/phishlab-release-$VERSION.tar.gz"

[ -d "$ROOT/web/dist" ] || { echo "✗ web/dist 不存在：先 cd web && npm run build" >&2; exit 1; }
command -v rsync >/dev/null || { echo "✗ 需要 rsync" >&2; exit 1; }

rm -rf "$STAGE"
mkdir -p "$STAGE/phishlab/docs" "$ROOT/release"

echo "→ server（源码 + 离线 wheel，排除 venv/缓存/私钥/一次性脚本）"
rsync -a \
  --exclude .venv --exclude __pycache__ --exclude '*.pyc' --exclude .pytest_cache \
  --exclude .env --exclude celerybeat-schedule --exclude tests \
  --exclude scripts/repair_orphan_track_events.py \
  --exclude scripts/wipe_campaign_data.py \
  --exclude deploy/license/vendor_private.pem \
  --exclude certs \
  --exclude scripts/start_landing_tls.sh \
  "$ROOT/server/" "$STAGE/phishlab/server/"

echo "→ web（源码 + dist 产物，排除 node_modules）"
rsync -a --exclude node_modules "$ROOT/web/" "$STAGE/phishlab/web/"

echo "→ deploy / docs"
rsync -a "$ROOT/deploy/" "$STAGE/phishlab/deploy/"
cp "$ROOT/docs/部署手册.md" "$ROOT/docs/离线交付说明.md" "$STAGE/phishlab/docs/"

tar -C "$STAGE" -czf "$OUT" phishlab
rm -rf "$STAGE"
echo "✓ $OUT ($(du -sh "$OUT" | cut -f1))"

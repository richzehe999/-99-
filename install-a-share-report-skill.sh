#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/codex-skills/a-share-report-radar"
DEST="$HOME/.codex/skills/a-share-report-radar"

if [[ ! -f "$SRC/SKILL.md" ]]; then
  echo "Missing skill source: $SRC" >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -R "$SRC" "$DEST"

echo "Installed: $DEST"
echo "You can now ask: 更新A股报告 / 更新盘后验证版 / 更新5月8日盘后版"

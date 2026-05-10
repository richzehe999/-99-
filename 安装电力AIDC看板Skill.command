#!/bin/zsh
set -e

project_dir="/Users/wuzehe/Documents/New project"
source_dir="$project_dir/codex-skills/power-aidc-dashboard"
target_dir="/Users/wuzehe/.codex/skills/power-aidc-dashboard"

echo "正在安装电力 / AIDC 看板 Skill..."
echo "来源: $source_dir"
echo "目标: $target_dir"

if [ ! -f "$source_dir/SKILL.md" ]; then
  echo "安装失败：找不到 SKILL.md"
  exit 1
fi

mkdir -p "/Users/wuzehe/.codex/skills"
rm -rf "$target_dir"
cp -R "$source_dir" "$target_dir"

echo
echo "安装完成。新开 Codex 线程后，触发词如“更新电力/AIDC 看板”“复核看板”“大盘视角调整”会优先使用这个 Skill。"
echo "按任意键关闭窗口。"
if [ -t 0 ]; then
  read -k 1
fi

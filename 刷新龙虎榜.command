#!/bin/zsh
set -u

cd "$(dirname "$0")" || exit 1

echo "A股龙虎榜看板数据刷新"
echo "工作目录：$(pwd)"
echo ""

TODAY_WEEKDAY="$(date +%u)"
case "${TODAY_WEEKDAY}" in
  6)
    DEFAULT_DATE="$(date -v-1d +%F)"
    ;;
  7)
    DEFAULT_DATE="$(date -v-2d +%F)"
    ;;
  *)
    DEFAULT_DATE="$(date +%F)"
    ;;
esac
echo "请输入交易日期，直接回车默认最近工作日 ${DEFAULT_DATE}："
read TRADE_DATE
if [ -z "${TRADE_DATE}" ]; then
  TRADE_DATE="${DEFAULT_DATE}"
fi

NODE_BIN=""
for candidate in \
  "/Applications/Codex.app/Contents/Resources/node" \
  "${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node" \
  "$(command -v node 2>/dev/null)"
do
  if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then
    NODE_BIN="${candidate}"
    break
  fi
done

if [ -z "${NODE_BIN}" ]; then
  echo ""
  echo "没有找到 Node 运行环境。"
  echo "先确认 Codex.app 已安装，或安装 Node.js 后再运行。"
  echo ""
  echo "按回车关闭窗口。"
  read _
  exit 1
fi

echo ""
echo "使用 Node：${NODE_BIN}"
echo "开始刷新 ${TRADE_DATE} 龙虎榜与主力资金数据..."
echo ""

"${NODE_BIN}" scripts/fetch-lhb-data.mjs "${TRADE_DATE}"
STATUS=$?

echo ""
if [ "${STATUS}" -eq 0 ]; then
  echo "刷新完成。"
  echo "看板文件：a-share-lhb-dashboard.html"
  open "a-share-lhb-dashboard.html"
else
  echo "刷新失败。请把上面的最后几行错误截图发给我。"
fi

echo ""
echo "按回车关闭窗口。"
read _

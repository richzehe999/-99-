#!/bin/zsh
script_dir="/Users/wuzehe/Documents/New project"
cd "$script_dir" || exit 1
mkdir -p "$script_dir/logs"
log_file="$script_dir/power-aidc-update-latest.log"
command_log="$script_dir/logs/command.log"
exit_file="$script_dir/logs/last-exit-code.txt"
rm -f "$exit_file"
node_bin="/Users/wuzehe/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
if [ ! -x "$node_bin" ]; then
  node_bin="$(command -v node)"
fi

diagnose_url() {
  label="$1"
  url="$2"
  output_file="$script_dir/logs/diag-$label.txt"
  if [ ! -x "/usr/bin/curl" ]; then
    echo "$label: 系统 curl 不存在，跳过。"
    return
  fi
  /usr/bin/curl -L --silent --show-error --connect-timeout 6 --max-time 10 \
    -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36" \
    -e "https://quote.eastmoney.com/" \
    "$url" > "$output_file" 2>&1
  curl_code=$?
  bytes=$(/usr/bin/wc -c < "$output_file" | tr -d " ")
  echo "$label: curl_exit=$curl_code bytes=$bytes"
  echo "样本: $(head -c 240 "$output_file" | tr '\n' ' ')"
}

diagnose_sources() {
  echo
  echo "行情源连通性诊断："
  diagnose_url "eastmoney" "https://push2.eastmoney.com/api/qt/ulist/get?fltt=2&invt=2&fields=f12,f14,f2,f3,f4,f5,f6,f18,f62,f184&secids=0.002015,0.300274,0.301638,0.300442,1.688981,0.300383"
  diagnose_url "sina" "https://hq.sinajs.cn/list=sz002015,sz300274,sz301638,sz300442,sh688981,sz300383"
  diagnose_url "tencent" "https://qt.gtimg.cn/q=sz002015,sz300274,sz301638,sz300442,sh688981,sz300383"
}

{
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="
echo "入口版本: command-v8-2026-05-14"
echo "工作目录: $(pwd)"
echo "Node 路径: ${node_bin:-未找到 node}"
if [ -z "$node_bin" ] || [ ! -x "$node_bin" ]; then
  echo "Update failed: 没找到可执行的 Node。"
  echo "退出码: 127"
  echo "127" > "$exit_file"
  exit 127
fi
"$node_bin" --version
echo "更新脚本: $script_dir/update-power-aidc-data.js"
echo "更新脚本时间: $(stat -f '%Sm' "$script_dir/update-power-aidc-data.js")"
echo
echo "正在检查更新脚本..."
"$node_bin" --check "$script_dir/update-power-aidc-data.js"
check_code=$?
if [ "$check_code" -ne 0 ]; then
  echo "Update failed: 更新脚本语法检查未通过。"
  echo "退出码: $check_code"
  echo "$check_code" > "$exit_file"
  exit "$check_code"
fi
echo
echo "正在更新电力 / AIDC 看板..."
"$node_bin" "$script_dir/update-power-aidc-data.js"
exit_code=$?
echo
if [ "$exit_code" -eq 0 ]; then
  echo "更新完成，正在打开看板。"
  open "$script_dir/power-aidc-dashboard.html" || echo "看板已更新，但当前环境未能自动打开；请手动打开 power-aidc-dashboard.html。"
else
  echo "更新失败。上面会显示具体失败原因。"
  echo "如果提示 ENOTFOUND 或 timeout，说明当前网络/DNS 访问不到行情源。"
  echo
  echo "最近脚本日志："
  tail -n 12 "$script_dir/logs/update.log" 2>/dev/null || true
  diagnose_sources
fi
echo
echo "退出码: $exit_code"
echo "$exit_code" > "$exit_file"
} 2>&1 | tee "$log_file" | tee -a "$command_log"
echo
echo "日志已保存到: $log_file"
if [ -t 0 ]; then
  echo "按任意键关闭窗口。"
  read -k 1
fi
final_exit=0
if [ -f "$exit_file" ]; then
  final_exit="$(cat "$exit_file")"
fi
exit "$final_exit"

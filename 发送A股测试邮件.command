#!/bin/zsh
set -euo pipefail

cd "/Users/wuzehe/Documents/New project"

echo "发送盘前测试邮件..."
./scripts/send_scheduled_a_share_report.sh premarket

echo "发送盘后测试邮件..."
./scripts/send_scheduled_a_share_report.sh aftermarket

echo
echo "两封测试邮件已提交发送。请检查 240575148@qq.com 收件箱。"
echo
echo "按回车键关闭窗口。"
read -r _

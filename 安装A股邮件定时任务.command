#!/bin/zsh
set -euo pipefail

cd "/Users/wuzehe/Documents/New project"

echo "安装 A股报告邮件定时任务..."
./scripts/install_a_share_email_launch_agents.sh

echo
echo "安装完成。"
echo "盘前邮件：工作日 08:45"
echo "盘后邮件：工作日 16:45"
echo
echo "按回车键关闭窗口。"
read -r _

# A股盘后验证雷达

这是一个静态网页站点，入口文件是 `index.html`。

## 分享方式

1. 直接分享 `a-share-report-site.zip`，对方解压后打开 `index.html`。
2. 上传整个 `a-share-report-site` 文件夹到 Vercel、Netlify、GitHub Pages 或任意静态网站托管服务。
3. 如果使用 GitHub Pages，把 `index.html` 放在仓库根目录或 `docs/` 目录即可。

## 内容口径

当前版本为 2026-05-18 盘后验证版，用真实盘面校验此前科技、能源、量能和板块轮动判断，并保留买方下一步判断维度。

## 本地预览

优先使用本地 HTTP 预览，而不是直接打开 `file://` 路径。Codex/Chrome 自动化对 `file://` 页面有安全限制，使用 `127.0.0.1` 预览更稳定。

双击工作区根目录下的：

```bash
/Users/wuzehe/Documents/New project/open-a-share-report-preview.command
```

它会自动启动本机预览服务，并用 Chrome 打开：

```bash
http://127.0.0.1:端口/a-share-report-site/index.html
```

预览时保持弹出的终端窗口打开，结束后在该窗口按 `Control-C`。

## 邮件推送

邮件发送默认走 Gmail SMTP，收件人是 `240575148@qq.com`。

当前采用两层链路：

- 正式链路：GitHub Actions 在工作日 08:30 / 12:30 / 16:30 生成邮件安全 HTML 并发送。
- 备用链路：macOS launchd 在工作日 08:45 / 12:30 / 16:45 用本机网络环境发送。

邮件正文由 `scripts/cloud_a_share_radar_email.py` 参考 `a-share-report-site/index.html` 生成，不直接发送完整 `index.html`，不把 ZIP 附件作为主要交付。三档任务暂时共用同一个模板，只在发送前更新运行时指数、板块资金和外部变量数据。

本地授权码文件：

```bash
/Users/wuzehe/Documents/New project/local_secrets/gmail_app_password.txt
```

安装本机邮件定时任务：

```bash
cd "/Users/wuzehe/Documents/New project"
./scripts/install_a_share_email_launch_agents.sh
```

手动测试盘前/午间/盘后邮件：

```bash
cd "/Users/wuzehe/Documents/New project"
./scripts/send_scheduled_a_share_report.sh premarket
./scripts/send_scheduled_a_share_report.sh midday
./scripts/send_scheduled_a_share_report.sh aftermarket
```

本机发送日志：

```bash
/Users/wuzehe/Documents/New project/logs/email-dispatch.log
/Users/wuzehe/Documents/New project/logs/premarket-email.err.log
/Users/wuzehe/Documents/New project/logs/midday-email.err.log
/Users/wuzehe/Documents/New project/logs/aftermarket-email.err.log
```

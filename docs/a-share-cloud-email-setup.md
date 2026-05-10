# A股雷达云端邮件部署

目标：

- 电脑关机也能收到邮件。
- 使用 Gmail SMTP 发送真正的邮件安全 `text/html` 正文。
- 收件地址保持 `240575148@qq.com`。
- 每次运行前刷新数据，不复用旧报告。
- 云端 GitHub Actions 是正式发送链路；本机 launchd 只作为备用验证链路。
- 邮件正文由 `scripts/cloud_a_share_radar_email.py` 生成，不直接复用静态站点 `index.html`，也不把 ZIP 作为主要交付。

## 需要的 GitHub Secrets

在 GitHub 仓库中进入：

`Settings -> Secrets and variables -> Actions -> New repository secret`

添加：

| Secret | 值 |
|---|---|
| `SMTP_USER` | `rich.zehe@gmail.com` |
| `SMTP_PASSWORD` | Gmail App Password |
| `A_SHARE_REPORT_TO` | `240575148@qq.com` |

Gmail 不能使用登录密码。需要在 Google 账号中开启两步验证，然后生成 App Password，把这串 App Password 填入 `SMTP_PASSWORD`。

## 上传到 GitHub 前

当前本地目录不是 GitHub 仓库，需要先新建一个私有仓库，再上传项目文件。

必须上传：

- `.github/workflows/a-share-radar-email.yml`
- `scripts/cloud_a_share_radar_email.py`
- `.gitignore`

不要上传：

- `local_secrets/gmail_app_password.txt`
- `logs/`
- `.venv/`、`hotstock_quant_skill/.venv*`
- 任何 `.zip` 打包文件

根目录 `.gitignore` 已经排除了这些本地文件；如果用 GitHub 网页手动上传，也要确认不要把授权码文件拖进去。

## 自动运行时间

GitHub Actions 使用 UTC，已换算为中国时间：

- 工作日 08:30 中国时间：盘前邮件
- 工作日 16:30 中国时间：盘后邮件

工作流文件：

`/.github/workflows/a-share-radar-email.yml`

云端 Gmail SMTP 会自动尝试 `465` 和 `587` 两个端口。

## 邮件格式约束

- 正文必须打开即可读，顶部显示报告日期和数据口径。
- 禁止发送 `<style>`、`<script>`、`<head>`、完整网页结构或 CSS 代码块。
- 附件和站点包只能作为补充，不作为主要阅读入口。

## 手动测试

进入 GitHub 仓库：

`Actions -> A-share radar email -> Run workflow`

选择：

- `premarket`：盘前报告
- `aftermarket`：盘后报告

运行完成后检查 QQ 邮箱。

## 本地校验

生成 HTML 预览：

```bash
python3 scripts/cloud_a_share_radar_email.py \
  --mode premarket \
  --output-html radar-email-preview.html
```

本地环境如果没有 DNS，行情数据会显示为“数据待确认”。GitHub Actions 云端运行时会重新抓取公网数据。

## 故障判断

- `Missing SMTP_PASSWORD secret`：GitHub Secrets 没有配置 Gmail App Password。
- `SMTP authentication failed`：优先检查 `SMTP_USER` 是否为 Gmail 发件账号，`SMTP_PASSWORD` 是否为 App Password。
- Gmail 报登录失败：确认 Google 账号已开启两步验证，并重新生成 App Password。
- 本机没有收到定时邮件：先检查 `~/Library/LaunchAgents/com.codex.ashare.*.email.plist` 是否安装，再看 `logs/email-dispatch.log`。

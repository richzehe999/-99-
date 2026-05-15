# 快速运行说明

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

## 2. 运行示例热点池

```bash
python examples/run_hot_pool.py
```

## 3. 运行示例回测

```bash
python examples/run_backtest.py
```

## 4. 三时段日报与邮件

```bash
make daily-premarket
make daily-midday
make daily-close
```

SMTP 配好后可直接发送邮件：

```bash
make email-premarket
make email-midday
make email-close
```

邮件命令会先确认是否为 A 股交易日；非交易日会跳过生成和发送。2026 年休市判断使用上交所年度休市安排和周末规则。

安装本机 macOS 工作日定时任务：

```bash
python scripts/install_email_launchd.py
```

可在 `config.enhanced.yaml` 填写 SMTP，也可用环境变量：

```text
HOTSTOCK_SMTP_HOST
HOTSTOCK_SMTP_PORT
HOTSTOCK_SMTP_USER
HOTSTOCK_SMTP_PASSWORD
HOTSTOCK_EMAIL_FROM
HOTSTOCK_EMAIL_TO
HOTSTOCK_EMAIL_CC
```

## 5. 数据说明

当前版本默认使用示例数据和本地 CSV 结构。正式接入东方财富、同花顺、AkShare、Tushare 等数据源时，请替换 `providers/` 目录下的 provider 实现。

## 6. 风险声明

本工具仅用于研究和教育，不构成投资建议。所有输出都需要人工复核。

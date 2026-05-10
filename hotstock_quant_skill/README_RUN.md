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

## 4. 数据说明

当前版本默认使用示例数据和本地 CSV 结构。正式接入东方财富、同花顺、AkShare、Tushare 等数据源时，请替换 `providers/` 目录下的 provider 实现。

## 5. 风险声明

本工具仅用于研究和教育，不构成投资建议。所有输出都需要人工复核。

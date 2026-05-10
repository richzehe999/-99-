from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def save_pool_report(df: pd.DataFrame, output_path: str = "reports/daily_hot_pool.md") -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    core = df[df["pool"] == "core"]
    watch = df[df["pool"] == "watch"]

    lines = []
    lines.append("# 热点核心池与观察池")
    lines.append("")
    lines.append("> 本报告仅用于研究和教育，不构成投资建议。")
    lines.append("")
    lines.append("## 核心池")
    lines.append(core[["symbol", "name", "total_score"]].to_markdown(index=False) if not core.empty else "暂无")
    lines.append("")
    lines.append("## 观察池")
    lines.append(watch[["symbol", "name", "total_score"]].to_markdown(index=False) if not watch.empty else "暂无")

    path.write_text("\n".join(lines), encoding="utf-8")


def save_backtest_report(
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    metrics: dict,
    output_excel: str = "reports/backtest_report.xlsx",
    output_chart: str = "reports/backtest_charts/equity_curve.png",
) -> None:
    excel_path = Path(output_excel)
    chart_path = Path(output_chart)
    excel_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_df = pd.DataFrame([metrics])

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        metrics_df.to_excel(writer, sheet_name="metrics", index=False)
        equity_df.to_excel(writer, sheet_name="equity", index=False)
        trades_df.to_excel(writer, sheet_name="trades", index=False)

    plt.figure(figsize=(10, 5))
    plt.plot(pd.to_datetime(equity_df["date"]), equity_df["equity"])
    plt.title("Strategy Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.tight_layout()
    plt.savefig(chart_path, dpi=150)
    plt.close()

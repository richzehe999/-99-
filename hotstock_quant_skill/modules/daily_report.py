"""
Daily report generator for enhanced hotstock quant skill.
"""
from __future__ import annotations
from html import escape
from pathlib import Path
import pandas as pd


COLUMN_LABELS = {
    "theme": "主题",
    "theme_strength": "主题强度",
    "stock_count": "样本数量",
    "avg_pct_change": "平均涨幅",
    "avg_volume_ratio": "平均量比",
    "avg_turnover_million": "平均成交额(百万元)",
    "catalyst_score": "催化分",
    "hit_count": "命中次数",
    "top_keywords": "关键词",
    "top_titles": "相关标题",
    "catalyst_score_norm": "催化强度",
    "symbol": "代码",
    "name": "名称",
    "total_score": "综合评分",
    "pool": "研究池",
    "pct_change": "涨跌幅",
    "turnover_million_cny": "成交额(百万元)",
    "market_cap_billion_cny": "市值(十亿元)",
    "reason": "入池原因",
}

REPORT_SLOTS = {
    "premarket": {
        "label": "08:00 盘前",
        "title": "A股盘前资金观察报告",
        "focus": "隔夜外围市场、前日资金回顾、当日预判",
        "bullets": [
            "隔夜外围市场和重点事件是否影响当日风险偏好。",
            "前一交易日资金流向与强势主题是否具备延续条件。",
            "当日优先观察主题强度、成交额和开盘后量能承接。",
        ],
    },
    "midday": {
        "label": "12:30 午间",
        "title": "A股午间资金观察报告",
        "focus": "上午半日资金流向、盘中异动、下午展望",
        "bullets": [
            "上午主题强度和成交额是否集中在少数主线。",
            "盘中异动是否由消息催化、资金放量或指数共振驱动。",
            "下午重点观察量能延续、冲高回落和主题扩散情况。",
        ],
    },
    "close": {
        "label": "17:00 收盘",
        "title": "A股收盘资金验证报告",
        "focus": "全日资金数据、趋势分析、次日观察条件",
        "bullets": [
            "全日资金和主题强度是否验证早盘或午间判断。",
            "核心池和观察池是否出现成交缩量、冲高回落或消息证伪。",
            "次日按观察条件、风险等级、支撑压力、量能警戒和失效条件复核。",
        ],
    },
}


def _table(df: pd.DataFrame, index: bool = False) -> str:
    try:
        return df.to_markdown(index=index)
    except ImportError:
        return df.to_string(index=index)


def _html_table(df: pd.DataFrame, cols: list[str] | None = None, max_items: int | None = None) -> str:
    if df.empty:
        return '<p class="empty">暂无数据</p>'
    out = df.copy()
    if cols is not None:
        out = out[[c for c in cols if c in out.columns]]
    if max_items is not None:
        out = out.head(max_items)
    out = out.rename(columns={c: COLUMN_LABELS.get(c, c) for c in out.columns})
    return out.to_html(index=False, border=0, classes="data-table", escape=True)


def _fmt(value, digits: int = 2) -> str:
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _pool(df: pd.DataFrame, name: str, max_items: int) -> pd.DataFrame:
    if df.empty or "pool" not in df.columns:
        return pd.DataFrame()
    return df[df["pool"] == name].head(max_items)


def get_report_slot(slot: str | None) -> dict:
    if not slot:
        return REPORT_SLOTS["close"]
    if slot not in REPORT_SLOTS:
        allowed = ", ".join(REPORT_SLOTS)
        raise ValueError(f"Unknown report slot {slot!r}; expected one of: {allowed}")
    return REPORT_SLOTS[slot]


def _daily_summary(theme_strength_df: pd.DataFrame, scored_pool_df: pd.DataFrame) -> list[str]:
    lines = ["## 0. 今日研究结论"]
    if theme_strength_df.empty:
        lines.append("- 主题强度数据不足，今日先以数据补全和人工核验为主。")
    else:
        top_theme = theme_strength_df.iloc[0]
        lines.append(
            "- 今日最强主线："
            f"{top_theme.get('theme', '-')}，主题强度 {_fmt(top_theme.get('theme_strength'))}，"
            f"样本数量 {top_theme.get('stock_count', 0)}。"
        )

    core_count = int((scored_pool_df.get("pool", pd.Series(dtype=str)) == "core").sum()) if not scored_pool_df.empty else 0
    watch_count = int((scored_pool_df.get("pool", pd.Series(dtype=str)) == "watch").sum()) if not scored_pool_df.empty else 0
    lines.append(f"- 量化池状态：核心池 {core_count} 个，观察池 {watch_count} 个。")
    lines.append("- 今日用途：用于盘后复盘、次日观察清单整理和数据核验，不作为交易指令。")
    return lines


def _research_focus(theme_strength_df: pd.DataFrame, catalyst_df: pd.DataFrame) -> list[str]:
    lines = ["## 1. 今日主线与催化"]
    if theme_strength_df.empty:
        lines.append("- 暂无可排序主题。")
        return lines

    top_themes = theme_strength_df.head(3)
    for _, row in top_themes.iterrows():
        theme = row.get("theme", "-")
        catalyst = catalyst_df[catalyst_df["theme"] == theme].head(1) if not catalyst_df.empty and "theme" in catalyst_df.columns else pd.DataFrame()
        keywords = catalyst.iloc[0].get("top_keywords", "-") if not catalyst.empty else "-"
        lines.append(
            f"- {theme}：强度 {_fmt(row.get('theme_strength'))}，"
            f"平均涨幅 {_fmt(row.get('avg_pct_change'))}%，"
            f"平均成交额 {_fmt(row.get('avg_turnover_million'))} 百万元，"
            f"关键词 {keywords}。"
        )
    return lines


def _tracking_questions(scored_pool_df: pd.DataFrame, max_items: int) -> list[str]:
    lines = ["## 4. 明日跟踪问题"]
    core = _pool(scored_pool_df, "core", max_items)
    watch = _pool(scored_pool_df, "watch", max_items)
    names = []
    for frame in [core, watch]:
        if not frame.empty:
            names.extend(frame.get("name", pd.Series(dtype=str)).astype(str).head(5).tolist())

    if names:
        lines.append(f"- 跟踪对象：{', '.join(names[:5])}。")
    else:
        lines.append("- 今日没有形成明确核心/观察清单，明日优先观察主题是否继续扩散。")
    lines.append("- 盘面验证：主题是否继续放量，是否从单点标的扩散到产业链多个环节。")
    lines.append("- 风险核验：是否存在一日脉冲、消息证伪、成交缩量或高位回撤。")
    return lines


def render_daily_html(
    trade_date: str,
    theme_strength_df: pd.DataFrame,
    scored_pool_df: pd.DataFrame,
    catalyst_df: pd.DataFrame,
    max_items: int = 10,
    slot: str | None = "close",
) -> str:
    slot_meta = get_report_slot(slot)
    top_theme = None if theme_strength_df.empty else theme_strength_df.iloc[0]
    core = _pool(scored_pool_df, "core", max_items)
    watch = _pool(scored_pool_df, "watch", max_items)
    core_count = len(core)
    watch_count = len(watch)
    theme_name = "-" if top_theme is None else escape(str(top_theme.get("theme", "-")))
    theme_strength = "-" if top_theme is None else _fmt(top_theme.get("theme_strength"))

    focus_cards = []
    if theme_strength_df.empty:
        focus_cards.append('<div class="focus-card muted">暂无可排序主题，优先补全数据源。</div>')
    else:
        for _, row in theme_strength_df.head(3).iterrows():
            theme = str(row.get("theme", "-"))
            catalyst = catalyst_df[catalyst_df["theme"] == theme].head(1) if not catalyst_df.empty and "theme" in catalyst_df.columns else pd.DataFrame()
            keywords = catalyst.iloc[0].get("top_keywords", "-") if not catalyst.empty else "-"
            focus_cards.append(
                f"""
                <article class="focus-card">
                  <div class="focus-title">{escape(theme)}</div>
                  <div class="focus-meta">强度 {_fmt(row.get('theme_strength'))} · 平均涨幅 {_fmt(row.get('avg_pct_change'))}%</div>
                  <div class="focus-keywords">{escape(str(keywords))}</div>
                </article>
                """
            )

    pool_cols = ["symbol", "name", "total_score", "pool", "pct_change", "turnover_million_cny", "market_cap_billion_cny", "reason"]

    tracking_items = "".join(f"<li>{escape(item)}</li>" for item in slot_meta["bullets"])

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(slot_meta["title"])} - {escape(trade_date)}</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #6b7280;
      --line: #dbe2ee;
      --blue: #2563eb;
      --green: #059669;
      --amber: #b45309;
      --red: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
      line-height: 1.55;
    }}
    header {{
      background: #101827;
      color: #fff;
      padding: 28px 28px 22px;
      border-bottom: 4px solid var(--blue);
    }}
    .wrap {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    .subtitle {{ color: #cbd5e1; font-size: 14px; }}
    .slot {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
      padding: 5px 10px;
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 999px;
      color: #dbeafe;
      background: rgba(37,99,235,0.18);
      font-size: 12px;
      font-weight: 700;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 18px 0 0;
    }}
    .metric {{
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.16);
      padding: 14px;
      border-radius: 8px;
    }}
    .metric-label {{ color: #cbd5e1; font-size: 12px; }}
    .metric-value {{ margin-top: 6px; font-size: 22px; font-weight: 700; }}
    main {{ padding: 22px 28px 42px; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 0 auto 16px;
      padding: 18px;
      max-width: 1180px;
    }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    h3 {{ margin: 16px 0 10px; font-size: 15px; }}
    .notice {{
      border-left: 4px solid var(--amber);
      background: #fff7ed;
      padding: 10px 12px;
      color: #7c2d12;
      border-radius: 6px;
      margin-top: 14px;
    }}
    .focus-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    .focus-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 118px;
    }}
    .focus-title {{ font-size: 17px; font-weight: 700; }}
    .focus-meta {{ color: var(--green); margin: 8px 0; font-size: 13px; }}
    .focus-keywords {{ color: var(--muted); font-size: 13px; }}
    .muted {{ color: var(--muted); }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .data-table th {{
      text-align: left;
      background: #eef3fb;
      color: #334155;
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      white-space: nowrap;
    }}
    .data-table td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      vertical-align: top;
    }}
    .split {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    ul {{ margin: 0; padding-left: 20px; }}
    li {{ margin: 6px 0; }}
    .empty {{ color: var(--muted); margin: 0; }}
    footer {{
      max-width: 1180px;
      margin: 0 auto;
      color: var(--muted);
      font-size: 12px;
      padding: 0 0 28px;
    }}
    @media (max-width: 820px) {{
      header, main {{ padding-left: 14px; padding-right: 14px; }}
      .grid, .focus-grid, .split {{ grid-template-columns: 1fr; }}
      .data-table {{ font-size: 12px; }}
      section {{ padding: 14px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <h1>热点催化与量化观察日报</h1>
      <div class="slot">{escape(slot_meta["label"])} · {escape(slot_meta["focus"])}</div>
      <div class="subtitle">{escape(trade_date)} · 研究分析用途 · 非投资建议</div>
      <div class="grid">
        <div class="metric"><div class="metric-label">今日最强主线</div><div class="metric-value">{theme_name}</div></div>
        <div class="metric"><div class="metric-label">主题强度</div><div class="metric-value">{theme_strength}</div></div>
        <div class="metric"><div class="metric-label">核心池</div><div class="metric-value">{core_count}</div></div>
        <div class="metric"><div class="metric-label">观察池</div><div class="metric-value">{watch_count}</div></div>
      </div>
      <div class="notice">本页面用于每日复盘、次日观察清单整理和数据核验，不构成买入、卖出、持有、目标价或收益承诺。</div>
    </div>
  </header>

  <main>
    <section>
      <h2>今日主线与催化</h2>
      <div class="focus-grid">{''.join(focus_cards)}</div>
    </section>

    <section>
      <h2>主题强度排名</h2>
      {_html_table(theme_strength_df, max_items=max_items)}
    </section>

    <section>
      <h2>研究池</h2>
      <div class="split">
        <div>
          <h3>核心池</h3>
          {_html_table(core, cols=pool_cols, max_items=max_items)}
        </div>
        <div>
          <h3>观察池</h3>
          {_html_table(watch, cols=pool_cols, max_items=max_items)}
        </div>
      </div>
    </section>

    <section>
      <h2>分时段观察重点</h2>
      <ul>
        {tracking_items}
        <li>若数据仍为样例源，优先核验行情、新闻和成交额口径。</li>
      </ul>
    </section>

    <section>
      <h2>主要催化明细</h2>
      {_html_table(catalyst_df, max_items=max_items)}
    </section>

    <section>
      <h2>数据状态与风险提示</h2>
      <ul>
        <li>当前页面由本地日报脚本生成，输出目录为 <code>reports/daily/</code>。</li>
        <li>样例数据不代表真实市场状态，接入真实数据源前需要人工核验。</li>
        <li>历史表现不代表未来结果，热点题材波动和回撤风险较高。</li>
      </ul>
    </section>
  </main>

  <footer>Generated by Hotstock Quant Skill. Research and education only.</footer>
</body>
</html>
"""


def render_daily_markdown(
    trade_date: str,
    theme_strength_df: pd.DataFrame,
    scored_pool_df: pd.DataFrame,
    catalyst_df: pd.DataFrame,
    max_items: int = 10,
    slot: str | None = "close",
) -> str:
    slot_meta = get_report_slot(slot)
    lines = []
    lines.append(f"# {slot_meta['title']} - {trade_date}")
    lines.append("")
    lines.append(f"> {slot_meta['label']}：{slot_meta['focus']}")
    lines.append("")
    lines.append("> 仅用于研究和教育，不构成投资建议或交易建议。")
    lines.append("")
    lines.extend(_daily_summary(theme_strength_df, scored_pool_df))
    lines.append("")
    lines.extend(_research_focus(theme_strength_df, catalyst_df))
    lines.append("")
    lines.append("## 2. 主题强度排名")
    if theme_strength_df.empty:
        lines.append("暂无主题强度数据。")
    else:
        lines.append(_table(theme_strength_df.head(max_items), index=False))
    lines.append("")
    lines.append("## 3. 研究池")
    lines.append("### 3.1 核心池")
    core = _pool(scored_pool_df, "core", max_items)
    if core.empty:
        lines.append("暂无核心池标的。")
    else:
        cols = [c for c in ["symbol", "name", "total_score", "pool", "pct_change", "turnover_million_cny", "market_cap_billion_cny", "reason"] if c in core.columns]
        lines.append(_table(core[cols], index=False))
    lines.append("")
    lines.append("### 3.2 观察池")
    watch = _pool(scored_pool_df, "watch", max_items)
    if watch.empty:
        lines.append("暂无观察池标的。")
    else:
        cols = [c for c in ["symbol", "name", "total_score", "pool", "pct_change", "turnover_million_cny", "market_cap_billion_cny", "reason"] if c in watch.columns]
        lines.append(_table(watch[cols], index=False))
    lines.append("")
    lines.append("## 4. 分时段观察重点")
    for item in slot_meta["bullets"]:
        lines.append(f"- {item}")
    lines.append("- 若数据仍为样例源，优先核验行情、新闻和成交额口径。")
    lines.append("")
    lines.append("## 5. 主要催化明细")
    if catalyst_df.empty:
        lines.append("暂无催化解析结果。")
    else:
        lines.append(_table(catalyst_df.head(max_items), index=False))
    lines.append("")
    lines.append("## 6. 数据状态")
    lines.append("- 当前日报由本地样例数据生成；接入真实数据源前，需要人工核验行情、新闻和成交额口径。")
    lines.append("- 输出目录：`reports/daily/`；运行日志：`logs/app.log`。")
    lines.append("")
    lines.append("## 7. 风险提示")
    lines.append("- 热点题材轮动较快，历史表现不代表未来结果。")
    lines.append("- 小市值标的波动、流动性和回撤风险通常更高。")
    lines.append("- 数据可能存在延迟、缺失或供应商口径差异，实际使用前请独立核验。")
    return "\n".join(lines)


def save_daily_report(markdown: str, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(markdown, encoding="utf-8")


def save_daily_html(html: str, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")


def save_daily_excel(
    path: str,
    theme_strength_df: pd.DataFrame,
    scored_pool_df: pd.DataFrame,
    catalyst_strength_df: pd.DataFrame,
    catalyst_hits_df: pd.DataFrame,
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(p) as writer:
        theme_strength_df.to_excel(writer, sheet_name="theme_strength", index=False)
        scored_pool_df.to_excel(writer, sheet_name="stock_pool", index=False)
        catalyst_strength_df.to_excel(writer, sheet_name="catalyst_strength", index=False)
        catalyst_hits_df.to_excel(writer, sheet_name="catalyst_hits", index=False)

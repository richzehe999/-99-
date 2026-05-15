#!/usr/bin/env python3
import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


CN_TZ = timezone(timedelta(hours=8))
DEFAULT_RECIPIENT = "240575148@qq.com"
DEFAULT_SMTP_HOST = "smtp.qq.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_SMTP_PORTS = (465, 587)
DEFAULT_TEMPLATE_HTML = Path("a-share-report-site/index.html")
BLOCKED_EMAIL_MARKERS = ("<style", "<script", "<head", "</head", "<!doctype", "display:flex", "display:grid")
MODE_NAMES = {
    "premarket": "A股盘前分析雷达",
    "midday": "A股午间联动雷达",
    "aftermarket": "A股盘后验证雷达",
}
MODE_CONTEXT = {
    "premarket": "盘前联动版：承接最新网页模板结论，用于开盘前确认外盘、商品、政策和A股映射条件。",
    "midday": "午间联动版：承接最新网页模板结论，用于午间复核资金方向、强弱扩散和下午验证条件。",
    "aftermarket": "盘后验证版：承接最新网页模板结论，用于收盘后复盘主线、资金和次日观察条件。",
}

TAG_COLORS = {
    "强验证":    ("#91e676", "#103c22"),
    "部分验证":   ("#91e676", "#103c22"),
    "有效但拥挤": ("#ffd663", "#422c00"),
    "补涨观察":   ("#ffd663", "#422c00"),
    "继续观察":   ("#ffd663", "#422c00"),
    "待验证":     ("#8bd4ff", "#082d47"),
    "中强但偏窄": ("#ffd663", "#422c00"),
    "弱到中":     ("#ffd663", "#422c00"),
    "缺口已标注":  ("#8bd4ff", "#082d47"),
    "拥挤度升高":  ("#ff8b91", "#4a1419"),
    "接近警戒":   ("#ff8b91", "#4a1419"),
}


def render_tag(text: str) -> str:
    """如果text匹配已知标签，渲染为彩色badge；否则返回原文本"""
    for keyword, (bg, fg) in TAG_COLORS.items():
        if keyword in text:
            badge = (
                f'<span style="display:inline-block;border-radius:999px;'
                f'padding:3px 8px;background:{bg};color:{fg};'
                f'font-size:12px;font-weight:800;white-space:nowrap;">{keyword}</span>'
            )
            return text.replace(keyword, badge)
    return text


@dataclass
class Quote:
    name: str
    code: str
    price: Optional[float]
    pct: Optional[float]
    amount: Optional[float]


class SiteTemplateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.title = ""
        self.status = ""
        self.paragraphs: List[str] = []
        self.kpis: List[str] = []
        self.summaries: List[str] = []
        self.mini_items: List[str] = []
        self.themes: List[str] = []
        self.dashboard_cards: List[str] = []
        self.sources: List[str] = []
        self.table_rows: List[List[str]] = []
        self._captures: List[Dict[str, Any]] = []
        self._in_tbody = 0
        self._current_row: Optional[List[str]] = None
        self._current_cell: Optional[List[str]] = None
        self._source_depth = 0
        self._section_title_depth = 0
        self._current_section = ""

    @staticmethod
    def _classes(attrs: List[tuple[str, Optional[str]]]) -> set[str]:
        raw = dict(attrs).get("class") or ""
        return set(raw.split())

    @staticmethod
    def _clean(value: str) -> str:
        lines = [" ".join(line.split()) for line in value.splitlines()]
        return "\n".join(line for line in lines if line)

    def _start_capture(self, kind: str, tag: str) -> None:
        self._captures.append({"kind": kind, "tag": tag, "parts": [], "depth": 1})

    def _finish_capture(self, capture: Dict[str, Any]) -> None:
        text = self._clean("".join(capture["parts"]))
        if not text:
            return
        kind = capture["kind"]
        if kind == "title" and not self.title:
            self.title = text
        elif kind == "status" and not self.status:
            self.status = text
        elif kind == "p":
            self.paragraphs.append(text)
        elif kind == "kpi":
            self.kpis.append(text)
        elif kind == "summary":
            self.summaries.append(text)
        elif kind == "mini":
            self.mini_items.append(text)
        elif kind == "theme":
            self.themes.append(text)
        elif kind == "dashboard_card":
            prefix = f"{self._current_section}｜" if self._current_section else ""
            self.dashboard_cards.append(prefix + text)
        elif kind == "source":
            self.sources.append(text)
        elif kind == "section_title":
            self._current_section = text

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag in {"style", "script", "head"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return

        classes = self._classes(attrs)
        for capture in self._captures:
            capture["depth"] += 1
            if tag in {"br", "p", "li", "td", "th", "div", "h2", "h3", "small", "strong", "em"}:
                capture["parts"].append("\n")

        if "source-list" in classes:
            self._source_depth += 1
        if "section-title" in classes:
            self._section_title_depth += 1
        if tag == "tbody":
            self._in_tbody += 1
        if tag == "tr" and self._in_tbody:
            self._current_row = []
        if tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []

        if tag == "h1":
            self._start_capture("title", tag)
        elif tag == "h2" and self._section_title_depth:
            self._start_capture("section_title", tag)
        elif tag == "p":
            self._start_capture("p", tag)
        elif "status-pill" in classes:
            self._start_capture("status", tag)
        elif tag == "article" and "kpi" in classes:
            self._start_capture("kpi", tag)
        elif "summary-row" in classes:
            self._start_capture("summary", tag)
        elif tag == "li" and self._source_depth:
            self._start_capture("source", tag)
        elif tag == "li":
            self._start_capture("mini", tag)
        elif tag == "article" and "theme-card" in classes:
            self._start_capture("theme", tag)
        elif tag == "article" and classes & {"chart-card", "panel", "risk-card"}:
            self._start_capture("dashboard_card", tag)

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            if tag in {"style", "script", "head"}:
                self.skip_depth -= 1
            return

        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            self._current_row.append(self._clean("".join(self._current_cell)))
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            row = [cell for cell in self._current_row if cell]
            if len(row) >= 2:
                self.table_rows.append(row)
            self._current_row = None
        elif tag == "tbody" and self._in_tbody:
            self._in_tbody -= 1

        finished: List[Dict[str, Any]] = []
        for capture in self._captures:
            capture["depth"] -= 1
            if capture["depth"] <= 0:
                finished.append(capture)
        for capture in finished:
            self._captures.remove(capture)
            self._finish_capture(capture)

        if tag == "div" and self._source_depth:
            self._source_depth -= 1
        if tag == "div" and self._section_title_depth:
            self._section_title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        for capture in self._captures:
            capture["parts"].append(data)
        if self._current_cell is not None:
            self._current_cell.append(data)


INDEX_SECIDS = {
    "上证指数": "1.000001",
    "深证成指": "0.399001",
    "创业板指": "0.399006",
    "科创50": "1.000688",
    "沪深300": "1.000300",
    "上证50": "1.000016",
    "中证500": "1.000905",
    "中证1000": "1.000852",
    "北证50": "0.899050",
}

GLOBAL_SYMBOLS = {
    "纳斯达克": "%5EIXIC",
    "标普500": "%5EGSPC",
    "道指": "%5EDJI",
    "WTI原油": "CL=F",
    "黄金": "GC=F",
    "铜": "HG=F",
    "美元/离岸人民币": "CNH=X",
}


def cn_now() -> datetime:
    return datetime.now(CN_TZ)


def fetch_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body)


def safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "-", ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_num(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "数据待确认"
    return f"{value:.{digits}f}"


def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "数据待确认"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def fmt_amount(value: Optional[float]) -> str:
    if value is None:
        return "数据待确认"
    yi = value / 100_000_000
    if yi >= 10_000:
        return f"{yi / 10_000:.2f}万亿"
    return f"{yi:.0f}亿"


def pct_color(value: Optional[float]) -> str:
    if value is None:
        return "#2d3642"
    if value > 0:
        return "#178a5a"
    if value < 0:
        return "#c64a45"
    return "#2d3642"


def fetch_a_share_indices() -> List[Quote]:
    secids = ",".join(INDEX_SECIDS.values())
    fields = "f12,f14,f2,f3,f6"
    url = (
        "https://push2.eastmoney.com/api/qt/ulist.np/get?"
        + urllib.parse.urlencode({"secids": secids, "fields": fields, "fltt": "2"})
    )
    data = fetch_json(url)
    items = data.get("data", {}).get("diff") or []
    quotes: List[Quote] = []
    by_name = {item.get("f14"): item for item in items}
    by_code = {item.get("f12"): item for item in items}

    for name, secid in INDEX_SECIDS.items():
        code = secid.split(".", 1)[1]
        item = by_name.get(name) or by_code.get(code) or {}
        quotes.append(
            Quote(
                name=name,
                code=code,
                price=safe_float(item.get("f2")),
                pct=safe_float(item.get("f3")),
                amount=safe_float(item.get("f6")),
            )
        )
    return quotes


def fetch_board_flow() -> List[Dict[str, Any]]:
    params = {
        "pn": "1",
        "pz": "8",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f62",
        "fs": "m:90+t:2",
        "fields": "f12,f14,f62,f184,f3",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
    try:
        data = fetch_json(url)
    except Exception:
        return []
    return data.get("data", {}).get("diff") or []


def fetch_global_quotes() -> List[Quote]:
    symbols = ",".join(GLOBAL_SYMBOLS.values())
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}"
    try:
        data = fetch_json(url)
    except Exception:
        return []

    results = data.get("quoteResponse", {}).get("result") or []
    by_symbol = {item.get("symbol"): item for item in results}
    quotes: List[Quote] = []
    for name, symbol in GLOBAL_SYMBOLS.items():
        raw_symbol = urllib.parse.unquote(symbol)
        item = by_symbol.get(raw_symbol) or by_symbol.get(symbol) or {}
        quotes.append(
            Quote(
                name=name,
                code=raw_symbol,
                price=safe_float(item.get("regularMarketPrice")),
                pct=safe_float(item.get("regularMarketChangePercent")),
                amount=None,
            )
        )
    return quotes


def html_table(headers: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    head = "".join(
        f'<th style="padding:10px 8px;border-bottom:1px solid #d9e0e7;color:#657180;font-size:12px;text-align:left;">{escape(h)}</th>'
        for h in headers
    )
    body = []
    for row in rows:
        cells = "".join(
            f'<td style="padding:11px 8px;border-bottom:1px solid #edf1f5;vertical-align:top;color:#17202a;">{render_tag(cell)}</td>'
            for cell in row
        )
        body.append(f"<tr>{cells}</tr>")
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


def list_items(items: Iterable[str], limit: int = 8) -> str:
    rows = []
    for item in list(items)[:limit]:
        rows.append(
            '<li style="margin:0 0 8px;padding:0;color:#2d3642;font-size:14px;">'
            f"{escape(item).replace(chr(10), '<br>')}"
            "</li>"
        )
    if not rows:
        rows.append('<li style="margin:0;color:#2d3642;font-size:14px;">数据待确认</li>')
    return '<ul style="margin:0;padding-left:18px;">' + "".join(rows) + "</ul>"


def section(title: str, body: str, subtitle: str = "") -> str:
    title_table = (
        '<table style="width:100%;border-collapse:collapse;margin-bottom:12px;"><tr>'
        '<td style="width:4px;background:#0f7a4f;border-radius:2px;padding:0;margin:0;line-height:0;font-size:1px;">&nbsp;</td>'
        '<td style="padding:0 0 0 12px;vertical-align:bottom;white-space:nowrap;">'
        f'<h2 style="margin:0;color:#17202a;font-size:20px;line-height:1.2;">{escape(title)}</h2></td>'
    )
    if subtitle:
        title_table += (
            '<td style="padding:0 0 0 14px;vertical-align:bottom;text-align:right;width:99%;">'
            f'<span style="color:#657180;font-size:12px;">{escape(subtitle)}</span></td>'
        )
    title_table += "</tr></table>"
    return (
        '<div style="margin-top:18px;padding:18px;border:1px solid #d9e0e7;border-radius:8px;background:#ffffff;">'
        f"{title_table}{body}</div>"
    )


def rows_to_email_table(rows: List[List[str]], limit: int = 8) -> str:
    if not rows:
        return html_table(["项目", "内容"], [["数据待确认", "模板中未提取到表格内容"]])
    headers = [f"列{i + 1}" for i in range(max(len(row) for row in rows[:limit]))]
    normalized = []
    for row in rows[:limit]:
        normalized.append([escape(cell).replace(chr(10), "<br>") for cell in row])
    return html_table(headers, normalized)


def dashboard_cards_to_email(cards: List[str], limit: int = 18) -> str:
    if not cards:
        return list_items([])
    cells = []
    for card_text in cards[:limit]:
        parts = [part for part in card_text.splitlines() if part]
        title = parts[0] if parts else "看板模块"
        body = "<br>".join(escape(part) for part in parts[1:7])
        cells.append(
            '<td style="width:50%;padding:6px;vertical-align:top;">'
            '<div style="min-height:132px;padding:15px;border:1px solid #d9e0e7;border-radius:8px;background:#fbfcfd;">'
            f'<h3 style="margin:0 0 8px;color:#17202a;font-size:16px;line-height:1.25;">{escape(title)}</h3>'
            f'<p style="margin:0;color:#2d3642;font-size:13px;line-height:1.55;">{body}</p>'
            "</div></td>"
        )
    rows = []
    for idx in range(0, len(cells), 2):
        row_cells = cells[idx : idx + 2]
        if len(row_cells) == 1:
            row_cells.append('<td style="width:50%;padding:6px;"></td>')
        rows.append("<tr>" + "".join(row_cells) + "</tr>")
    return '<table style="width:100%;border-collapse:collapse;">' + "".join(rows) + "</table>"


def build_kpi_rows_from_quotes(quotes: List[Quote]) -> List[str]:
    rows = []
    for quote in quotes[:5]:
        price_color = "#178a5a" if (quote.pct is not None and quote.pct > 0) else ("#c64a45" if (quote.pct is not None and quote.pct < 0) else "#17202a")
        rows.append(
            '<td style="width:20%;padding:6px;vertical-align:top;">'
            '<div style="min-height:108px;padding:14px;border:1px solid #d9e0e7;border-radius:8px;background:#ffffff;text-align:center;">'
            f'<div style="font-size:12px;color:#657180;margin-bottom:7px;">{escape(quote.name)}</div>'
            f'<div style="font-size:24px;font-weight:900;color:{price_color};line-height:1.1;">{escape(fmt_num(quote.price))}</div>'
            f'<div style="font-size:12px;color:#2d3642;margin-top:8px;">{escape(fmt_pct(quote.pct))}｜成交 {escape(fmt_amount(quote.amount))}</div>'
            "</div></td>"
        )
    return rows


def build_kpi_rows_from_template(kpis: List[str]) -> List[str]:
    rows = []
    for kpi in kpis[:5]:
        parts = [part for part in kpi.splitlines() if part]
        title = parts[0] if parts else "指标"
        value = parts[1] if len(parts) > 1 else "数据待确认"
        note = " ".join(parts[2:]) if len(parts) > 2 else ""
        if value.startswith("+") or "涨" in value:
            value_color = "#178a5a"
        elif value.startswith("-") or "跌" in value:
            value_color = "#c64a45"
        else:
            value_color = "#17202a"
        rows.append(
            '<td style="width:20%;padding:6px;vertical-align:top;">'
            '<div style="min-height:108px;padding:14px;border:1px solid #d9e0e7;border-radius:8px;background:#ffffff;text-align:center;">'
            f'<div style="font-size:12px;color:#657180;margin-bottom:7px;">{escape(title)}</div>'
            f'<div style="font-size:24px;font-weight:900;color:{value_color};line-height:1.1;">{escape(value)}</div>'
            f'<div style="font-size:12px;color:#2d3642;margin-top:8px;">{escape(note)}</div>'
            "</div></td>"
        )
    return rows


def board_flow_rows(boards: List[Dict[str, Any]]) -> List[List[str]]:
    rows = []
    for item in boards[:8]:
        rows.append(
            [
                str(item.get("f14", "数据待确认")),
                fmt_amount(safe_float(item.get("f62"))),
                fmt_pct(safe_float(item.get("f3"))),
            ]
        )
    return rows


def quote_rows(quotes: List[Quote]) -> List[List[str]]:
    return [[q.name, fmt_num(q.price), fmt_pct(q.pct), fmt_amount(q.amount)] for q in quotes]


def build_runtime_update_section(indices: List[Quote], boards: List[Dict[str, Any]], global_quotes: List[Quote]) -> str:
    runtime_blocks = []
    if indices:
        runtime_blocks.append(section("运行时指数更新", html_table(["指数", "点位", "涨跌幅", "成交额"], quote_rows(indices[:8])), "发送前实时抓取"))
    if boards:
        runtime_blocks.append(section("运行时板块资金", html_table(["板块", "主力净流入", "涨跌幅"], board_flow_rows(boards)), "发送前实时抓取"))
    if global_quotes:
        runtime_blocks.append(section("运行时外部变量", html_table(["变量", "最新值", "涨跌幅"], [[q.name, fmt_num(q.price), fmt_pct(q.pct)] for q in global_quotes]), "发送前实时抓取"))
    return "".join(runtime_blocks)


def build_html_from_site_template(
    mode: str,
    template_path: Path,
    indices: Optional[List[Quote]] = None,
    boards: Optional[List[Dict[str, Any]]] = None,
    global_quotes: Optional[List[Quote]] = None,
) -> str:
    parser = SiteTemplateParser()
    parser.feed(template_path.read_text(encoding="utf-8"))

    indices = indices or []
    boards = boards or []
    global_quotes = global_quotes or []
    report_date = cn_now().strftime("%Y-%m-%d")
    mode_name = MODE_NAMES[mode]
    hero_text = parser.paragraphs[0] if parser.paragraphs else "模板报告内容已读取，数据口径以网页正文为准。"
    status = parser.status or "已接入网页模板"

    has_live_indices = any(quote.price is not None for quote in indices[:5])
    kpi_rows = build_kpi_rows_from_quotes(indices) if has_live_indices else build_kpi_rows_from_template(parser.kpis)
    while len(kpi_rows) < 5:
        kpi_rows.append('<td style="width:20%;padding:6px;"></td>')

    theme_cards = []
    for theme in parser.themes[:6]:
        parts = [part for part in theme.splitlines() if part]
        title = parts[0] if parts else "验证条目"
        body = "<br>".join(escape(part) for part in parts[1:4])
        theme_cards.append(
            '<td style="width:33.33%;padding:6px;vertical-align:top;">'
            '<div style="min-height:126px;padding:15px;border:1px solid #d9e0e7;border-radius:8px;background:#fbfcfd;">'
            f'<h3 style="margin:0 0 8px;color:#17202a;font-size:16px;line-height:1.25;">{render_tag(escape(title))}</h3>'
            f'<p style="margin:0;color:#2d3642;font-size:13px;line-height:1.55;">{body}</p>'
            "</div></td>"
        )
    theme_rows = []
    for idx in range(0, len(theme_cards), 3):
        theme_rows.append("<tr>" + "".join(theme_cards[idx : idx + 3]) + "</tr>")
    theme_table = '<table style="width:100%;border-collapse:collapse;">' + "".join(theme_rows) + "</table>" if theme_rows else list_items([])

    return f"""<div style="margin:0;background:#f7f8f9;color:#17202a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',Arial,sans-serif;line-height:1.5;padding:0;">
  <div style="max-width:1180px;margin:0 auto;background:#f7f8f9;padding:22px;">
    <div style="padding:24px 26px;border:1px solid #d9e0e7;border-radius:8px;background:#ffffff;">
      <table style="width:100%;border-collapse:collapse;"><tr>
        <td style="padding:0;vertical-align:top;">
          <div style="font-size:13px;color:#657180;margin-bottom:8px;">{escape(MODE_CONTEXT[mode])}</div>
          <h1 style="margin:0 0 10px;color:#17202a;font-size:36px;line-height:1.08;">{escape(mode_name)}</h1>
          <p style="margin:0;max-width:920px;color:#2d3642;font-size:14px;">{escape(hero_text)}</p>
        </td>
        <td style="padding:0 0 0 18px;vertical-align:top;text-align:right;white-space:nowrap;width:1%;">
          <div style="border:1px solid #cbd6e1;border-radius:999px;padding:8px 12px;color:#2d3642;background:#ffffff;font-size:12px;display:inline-block;">{escape(status)}</div>
        </td>
      </tr></table>
    </div>

    <table style="width:100%;border-collapse:collapse;margin-top:18px;"><tr>{''.join(kpi_rows)}</tr></table>

    {build_runtime_update_section(indices, boards, global_quotes)}
    {section("完整看板模块", dashboard_cards_to_email(parser.dashboard_cards), "资金、强弱、买方维度、风险观察")}
    {section("结构摘要", list_items(parser.summaries, 8), "从网页模板抽取")}
    {section("验证条目", theme_table, "已验证 / 未确认 / 继续观察")}
    {section("消息传导与风险观察", rows_to_email_table(parser.table_rows, 10), "事件 -> A股映射 -> 盘面验证")}
    {section("后续观察", list_items(parser.mini_items, 9), "盘前、午间、盘后任务共用")}
    {section("来源说明", list_items(parser.sources, 10), "网页模板来源")}

    <p style="margin:22px 0 0;color:#657180;font-size:12px;">报告日期：{escape(report_date)}｜模板：{escape(str(template_path))}｜本报告仅用于市场结构观察，不构成投资建议。</p>
  </div>
</div>"""


def card(title: str, body: str, tag: str = "", tag_color: str = "#eaf1ff", tag_text: str = "#36516e") -> str:
    tag_html = ""
    if tag:
        tag_html = (
            f'<span style="display:inline-block;border-radius:999px;padding:4px 8px;'
            f'background:{tag_color};color:{tag_text};font-size:12px;font-weight:800;margin-bottom:8px;">'
            f"{escape(tag)}</span>"
        )
    return (
        '<td style="width:33.33%;padding:6px;vertical-align:top;">'
        '<div style="min-height:130px;padding:15px;border:1px solid #25445a;border-radius:8px;background:#102333;">'
        f"{tag_html}<h3 style=\"margin:0 0 8px;font-size:17px;color:#eaf4ff;\">{escape(title)}</h3>"
        f'<p style="margin:0;color:#9cb0bf;font-size:14px;">{body}</p>'
        "</div></td>"
    )


def build_html(mode: str, indices: List[Quote], boards: List[Dict[str, Any]], global_quotes: List[Quote]) -> str:
    now = cn_now()
    report_date = now.strftime("%Y-%m-%d")
    mode_name = MODE_NAMES[mode]
    status = {
        "premarket": "盘前最新可得数据",
        "midday": "午间最新可得数据",
        "aftermarket": "盘后收盘数据优先",
    }[mode]

    core_indices = indices[:5]
    kpi_cells = []
    for quote in core_indices:
        kpi_cells.append(
            '<td style="width:20%;padding:6px;vertical-align:top;">'
            '<div style="min-height:112px;padding:14px;border:1px solid #d9e0e7;border-radius:8px;background:#fff;">'
            f'<div style="font-size:12px;color:#657180;margin-bottom:6px;">{escape(quote.name)}</div>'
            f'<div style="font-size:26px;font-weight:800;color:{pct_color(quote.pct)};line-height:1.1;">{fmt_num(quote.price)}</div>'
            f'<div style="font-size:13px;font-weight:700;margin-top:7px;color:#17202a;">{fmt_pct(quote.pct)}'
            f'｜成交 {fmt_amount(quote.amount)}</div>'
            "</div></td>"
        )
    while len(kpi_cells) < 5:
        kpi_cells.append('<td style="width:20%;padding:6px;"></td>')

    index_rows = [
        [
            escape(q.name),
            escape(fmt_num(q.price)),
            f'<span style="color:{pct_color(q.pct)};font-weight:700;">{escape(fmt_pct(q.pct))}</span>',
            escape(fmt_amount(q.amount)),
        ]
        for q in indices
    ]

    global_rows = [
        [
            escape(q.name),
            escape(fmt_num(q.price)),
            f'<span style="color:{pct_color(q.pct)};font-weight:700;">{escape(fmt_pct(q.pct))}</span>',
        ]
        for q in global_quotes
    ] or [["数据待确认", "数据待确认", "数据待确认"]]

    board_rows = []
    for item in boards[:8]:
        flow = safe_float(item.get("f62"))
        pct = safe_float(item.get("f3"))
        board_rows.append(
            [
                escape(str(item.get("f14", "数据待确认"))),
                f'<span style="color:{pct_color(flow)};font-weight:700;">{escape(fmt_amount(flow))}</span>',
                f'<span style="color:{pct_color(pct)};font-weight:700;">{escape(fmt_pct(pct))}</span>',
            ]
        )
    if not board_rows:
        board_rows = [["板块资金接口暂不可用", "数据待确认", "数据待确认"]]

    if mode == "premarket":
        lead = "盘前重点不是下结论，而是把隔夜变量映射到A股板块，并列出开盘确认条件。"
        conclusion_rows = [
            ("外盘", "优先确认纳指、费半、中概与美元/美债是否支持成长风格。"),
            ("商品", "原油、黄金、铜、煤炭只在A股板块成交确认后升级为主线。"),
            ("开盘", "竞价和开盘15分钟验证主线龙头、补涨分支和指数权重。"),
        ]
        cards = [
            card("盘前主线预案", "海外AI、商品波动和国内政策进入观察池，先映射到板块，再等待成交确认。", "预案", "#eaf1ff", "#36516e"),
            card("开盘15分钟", "观察CPO、半导体、油气、红利和指数权重谁主动放量。", "验证", "#eaf7f1", "#0f6842"),
            card("证伪条件", "若热点高开低走、成交不足或外盘反向拖累，盘前预案降级。", "风控", "#fff6e5", "#865a13"),
        ]
    elif mode == "midday":
        lead = "午间重点是复核早盘主线是否被资金确认，并列出下午继续验证或降级条件。"
        conclusion_rows = [
            ("资金", "看早盘主力净流入是否集中在少数主线，还是转为快速轮动。"),
            ("扩散", "确认龙头、补涨、权重和防御方向的相对强弱。"),
            ("下午", "只保留早盘放量确认、承接稳定和仍需证伪的观察点。"),
        ]
        cards = [
            card("早盘资金复核", "用指数、成交额和板块资金判断上午主线是否有效。", "复核", "#eaf7f1", "#0f6842"),
            card("强弱扩散", "关注主线是否从龙头扩散到补涨分支，或转向防御权重。", "扩散", "#eaf1ff", "#36516e"),
            card("下午条件", "若成交不足、冲高回落或热点只剩抱团，午间结论降级。", "条件", "#fff6e5", "#865a13"),
        ]
    else:
        lead = "盘后重点是验证当日主线、资金扩散和外部变量是否被A股盘面确认。"
        conclusion_rows = [
            ("主线", "按指数强弱、板块资金和涨跌家数判断市场风格。"),
            ("传导", "每条消息链必须落到A股映射板块和成交确认。"),
            ("明日", "只保留已验证、部分验证和需要证伪的观察点。"),
        ]
        cards = [
            card("主线验证", "根据当日指数、成交额和板块资金判断主线是否延续。", "验证", "#eaf7f1", "#0f6842"),
            card("外部变量", "美伊、霍尔木兹、原油、黄金、气候等必须经过A股盘面验证。", "传导", "#eaf1ff", "#36516e"),
            card("明日观察", "关注主线放量、补涨承接、防御切换和成交阈值。", "观察", "#fff6e5", "#865a13"),
        ]

    conclusion_html = '<table style="width:100%;border-collapse:collapse;">' + "".join(
        '<tr><td style="width:86px;padding:10px 12px 10px 0;vertical-align:top;border-bottom:1px solid #edf1f5;">'
        f'<b style="font-size:14px;">{escape(label)}</b></td>'
        '<td style="padding:10px 0;vertical-align:top;border-bottom:1px solid #edf1f5;">'
        f'<span style="color:#657180;font-size:14px;">{escape(text)}</span></td></tr>'
        for label, text in conclusion_rows
    ) + '</table>'

    return f"""<div style="margin:0;background:#f7f8f9;color:#17202a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',Arial,sans-serif;line-height:1.5;padding:0;">
  <div style="max-width:1180px;margin:0 auto;background:#ffffff;">
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="width:230px;background:#1d2733;color:#eef4f8;padding:28px 24px;vertical-align:top;">
          <div style="font-size:18px;font-weight:800;">A股消息雷达</div>
          <div style="color:#9eb0c0;font-size:13px;margin-top:4px;">{escape(report_date)}｜{escape(status)}</div>
          <div style="margin-top:34px;font-weight:700;color:#dbe7ee;font-size:15px;">
            <div style="padding:9px 0;">市场基准</div><div style="padding:9px 0;">核心消息</div><div style="padding:9px 0;">传导链</div><div style="padding:9px 0;">外部风险</div><div style="padding:9px 0;">后续验证</div>
          </div>
          <div style="margin-top:36px;border:1px solid rgba(255,255,255,.14);border-radius:8px;padding:14px;color:#b7c6d1;font-size:13px;">
            每次发送前刷新数据；若非交易日，明确使用最近交易日口径。
          </div>
        </td>
        <td style="padding:34px 34px 42px;vertical-align:top;">
          <table style="width:100%;border-collapse:collapse;"><tr>
            <td style="padding:0;vertical-align:top;">
              <h1 style="margin:0 0 10px;font-size:40px;line-height:1.08;color:#17202a;">{escape(mode_name)}</h1>
              <p style="margin:0 0 10px;max-width:780px;font-size:16px;color:#2d3642;">{escape(lead)}</p>
              <p style="margin:0;color:#657180;font-size:13px;">报告日期：{escape(report_date)}｜数据源：东方财富行情接口、Yahoo Finance公开行情等；实际可得性以运行时为准。</p>
            </td>
            <td style="padding:0 0 0 24px;vertical-align:top;text-align:right;white-space:nowrap;width:1%;">
              <div style="border:1px solid #cbd6e1;border-radius:999px;padding:9px 14px;color:#2d3642;background:#fff;font-size:13px;display:inline-block;">{escape(status)}</div>
            </td>
          </tr></table>

          <table style="width:100%;border-collapse:collapse;margin-top:28px;"><tr>{''.join(kpi_cells)}</tr></table>

          <table style="width:100%;border-collapse:collapse;margin-top:22px;">
            <tr>
              <td style="width:50%;padding:8px;vertical-align:top;">
                <div style="padding:18px;border:1px solid #d9e0e7;border-radius:8px;background:#fff;">
                  <h2 style="margin:0 0 12px;font-size:22px;">核心结论</h2>{conclusion_html}
                </div>
              </td>
              <td style="width:50%;padding:8px;vertical-align:top;">
                <div style="padding:18px;border:1px solid #d9e0e7;border-radius:8px;background:#fff;">
                  <h2 style="margin:0 0 12px;font-size:22px;">隔夜/外部变量</h2>
                  {html_table(["变量", "最新值", "涨跌幅"], global_rows)}
                </div>
              </td>
            </tr>
          </table>

          <div style="margin-top:22px;">
            <h2 style="margin:0 0 12px;font-size:22px;">传导链卡片</h2>
            <table style="width:100%;border-collapse:collapse;"><tr>{''.join(cards)}</tr></table>
          </div>

          <div style="margin-top:22px;padding:18px;border:1px solid #d9e0e7;border-radius:8px;background:#fff;">
            <h2 style="margin:0 0 12px;font-size:22px;">核心指数</h2>
            {html_table(["指数", "点位", "涨跌幅", "成交额"], index_rows)}
          </div>

          <div style="margin-top:22px;padding:18px;border:1px solid #d9e0e7;border-radius:8px;background:#fff;">
            <h2 style="margin:0 0 12px;font-size:22px;">板块资金流动</h2>
            {html_table(["板块", "主力净流入", "涨跌幅"], board_rows)}
          </div>

          <div style="margin-top:22px;padding:18px;border:1px solid #d9e0e7;border-radius:8px;background:#fbfcfd;">
            <h2 style="margin:0 0 12px;font-size:22px;">观察清单</h2>
            {html_table(["观察项", "确认条件", "降级条件"], [
              ["主线延续", "核心板块继续放量，补涨分支跟随", "冲高回落且成交不足"],
              ["外部变量", "商品或地缘变化映射到A股板块成交", "只有新闻，没有资金确认"],
              ["风格切换", "红利/能源/消费主动走强", "仍弱于科技成长或指数权重"],
            ])}
          </div>

          <p style="margin:28px 0 0;color:#657180;font-size:12px;">本报告仅用于市场结构观察，不构成投资建议。</p>
        </td>
      </tr>
    </table>
  </div>
</div>"""


def build_plain_fallback(mode: str) -> str:
    now = cn_now().strftime("%Y-%m-%d %H:%M")
    return f"A股雷达报告 {now}\n\nHTML正文生成失败，模式：{mode}。请检查云端任务日志。"


def validate_email_html(html_body: str) -> None:
    lowered = html_body.lower()
    blocked = [marker for marker in BLOCKED_EMAIL_MARKERS if marker in lowered]
    if blocked:
        raise SystemExit(f"Email HTML contains blocked webpage markup: {', '.join(blocked)}")


def parse_smtp_ports() -> List[int]:
    raw = os.environ.get("SMTP_PORTS")
    if raw:
        ports: List[int] = []
        for item in raw.split(","):
            item = item.strip()
            if item:
                ports.append(int(item))
        return ports
    if os.environ.get("SMTP_PORT"):
        return [int(os.environ["SMTP_PORT"])]
    return list(DEFAULT_SMTP_PORTS)


def smtp_login_and_send(
    host: str,
    port: int,
    sender: str,
    password: str,
    message: EmailMessage,
    context: ssl.SSLContext,
) -> None:
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, context=context, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
    try:
        server.ehlo()
        if port != 465:
            server.starttls(context=context)
            server.ehlo()
        server.login(sender, password)
        server.send_message(message)
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass


def send_email(subject: str, html_body: str, plain_body: str) -> None:
    sender = os.environ.get("SMTP_USER") or os.environ.get("GMAIL_SMTP_USER") or os.environ.get("QQ_SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD") or os.environ.get("QQ_SMTP_AUTH_CODE")
    recipient = os.environ.get("A_SHARE_REPORT_TO", DEFAULT_RECIPIENT)
    host = os.environ.get("SMTP_HOST") or DEFAULT_SMTP_HOST
    ports = parse_smtp_ports()

    missing = [name for name, value in [("SMTP_USER", sender), ("SMTP_PASSWORD", password)] if not value]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    errors: List[str] = []
    for port in ports:
        try:
            smtp_login_and_send(host, port, sender, password, message, context)
            return
        except smtplib.SMTPAuthenticationError as exc:
            errors.append(f"{port}: authentication failed {exc.smtp_code} {exc.smtp_error!r}")
        except smtplib.SMTPException as exc:
            errors.append(f"{port}: send failed {exc}")
        except OSError as exc:
            errors.append(f"{port}: network failed {exc}")

    raise SystemExit(
        "SMTP发送失败。已尝试端口 "
        + ", ".join(str(port) for port in ports)
        + "；错误："
        + " | ".join(errors)
        + "。如果使用 Gmail，请确认开启两步验证并使用 App Password，不要使用 Gmail 登录密码。"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and send cloud A-share radar HTML email.")
    parser.add_argument("--mode", choices=["premarket", "midday", "aftermarket"], required=True)
    parser.add_argument(
        "--template-html",
        default=os.environ.get("A_SHARE_EMAIL_TEMPLATE", str(DEFAULT_TEMPLATE_HTML)),
        help="Read the A-share report site template and convert it into email-safe inline HTML.",
    )
    parser.add_argument("--output-html", help="Write generated HTML to this path.")
    parser.add_argument("--send", action="store_true", help="Send the report through SMTP.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mode_name = MODE_NAMES[args.mode]
    report_date = cn_now().strftime("%Y-%m-%d")

    errors: List[str] = []
    try:
        indices = fetch_a_share_indices()
    except Exception as exc:
        errors.append(f"A股指数获取失败: {exc}")
        indices = [Quote(name=name, code=secid.split(".", 1)[1], price=None, pct=None, amount=None) for name, secid in INDEX_SECIDS.items()]

    boards = fetch_board_flow()
    if not boards:
        errors.append("板块资金接口暂不可用")
    global_quotes = fetch_global_quotes()
    if not global_quotes:
        errors.append("外部变量接口暂不可用")

    template_path = Path(args.template_html)
    if template_path.exists():
        html_body = build_html_from_site_template(args.mode, template_path, indices, boards, global_quotes)
    else:
        errors.append(f"模板文件不存在，已回退到运行时行情版: {template_path}")
        html_body = build_html(args.mode, indices, boards, global_quotes)

    if errors:
        html_body += (
            '<div style="max-width:1180px;margin:12px auto;padding:14px;border:1px solid #ff8b91;'
            'background:#1e0d0f;color:#ff8b91;font-family:Arial,sans-serif;">'
            + escape("；".join(errors))
            + "</div>"
        )
    validate_email_html(html_body)

    if args.output_html:
        with open(args.output_html, "w", encoding="utf-8") as handle:
            handle.write(html_body)

    if args.send:
        subject = f"{mode_name} {report_date}"
        send_email(subject, html_body, build_plain_fallback(args.mode))
        print(f"sent {subject}")
    else:
        print(f"generated {mode_name} {report_date}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

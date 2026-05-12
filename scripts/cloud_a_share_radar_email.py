#!/usr/bin/env python3
"""A股雷达邮件：三档任务共用网页模板，发送前刷新运行时数据。"""
import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

CN_TZ = timezone(timedelta(hours=8))
DEFAULT_RECIPIENT = "240575148@qq.com"
DEFAULT_SMTP_HOST = "smtp.qq.com"
DEFAULT_SMTP_PORTS = (465, 587)
DEFAULT_TEMPLATE_HTML = Path("a-share-report-site/index.html")
BLOCKED_EMAIL_MARKERS = ("<style", "<script", "<head", "</head", "<!doctype")
MODE_NAMES = {
    "premarket": "A股盘前分析雷达",
    "midday": "A股午间联动雷达",
    "aftermarket": "A股盘后验证雷达",
}
MODE_CONTEXT = {
    "premarket": "盘前：外部变量 -> A股映射 -> 开盘确认条件。",
    "midday": "午间：早盘资金 -> 强弱扩散 -> 下午验证条件。",
    "aftermarket": "盘后：当日主线 -> 资金结构 -> 次日观察条件。",
}

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
        self.themes: List[str] = []
        self.list_items: List[str] = []
        self.table_rows: List[List[str]] = []
        self._captures: List[Dict[str, Any]] = []
        self._in_tbody = 0
        self._current_row: Optional[List[str]] = None
        self._current_cell: Optional[List[str]] = None

    @staticmethod
    def _classes(attrs: List[tuple[str, Optional[str]]]) -> set[str]:
        return set((dict(attrs).get("class") or "").split())

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
        elif kind == "theme":
            self.themes.append(text)
        elif kind == "li":
            self.list_items.append(text)

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag in {"style", "script", "head"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        classes = self._classes(attrs)
        for capture in self._captures:
            capture["depth"] += 1
            if tag in {"br", "p", "li", "td", "th", "div", "h2", "h3", "small", "strong"}:
                capture["parts"].append("\n")
        if tag == "tbody":
            self._in_tbody += 1
        if tag == "tr" and self._in_tbody:
            self._current_row = []
        if tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []
        if tag == "h1":
            self._start_capture("title", tag)
        elif tag == "p":
            self._start_capture("p", tag)
        elif "status-pill" in classes:
            self._start_capture("status", tag)
        elif tag == "article" and "kpi" in classes:
            self._start_capture("kpi", tag)
        elif "summary-row" in classes:
            self._start_capture("summary", tag)
        elif tag == "article" and "theme-card" in classes:
            self._start_capture("theme", tag)
        elif tag == "li":
            self._start_capture("li", tag)

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

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        for capture in self._captures:
            capture["parts"].append(data)
        if self._current_cell is not None:
            self._current_cell.append(data)


def cn_now() -> datetime:
    return datetime.now(CN_TZ)


def fetch_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 Chrome/124.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "-", ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_num(value: Optional[float], digits: int = 2) -> str:
    return "数据待确认" if value is None else f"{value:.{digits}f}"


def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "数据待确认"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def fmt_amount(value: Optional[float]) -> str:
    if value is None:
        return "数据待确认"
    yi = value / 100_000_000
    return f"{yi / 10_000:.2f}万亿" if abs(yi) >= 10_000 else f"{yi:.0f}亿"


def pct_color(value: Optional[float]) -> str:
    if value is None:
        return "#d7e6ee"
    return "#37b878" if value > 0 else "#ff7b72" if value < 0 else "#d7e6ee"


def fetch_a_share_indices() -> List[Quote]:
    secids = ",".join(INDEX_SECIDS.values())
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get?" + urllib.parse.urlencode(
        {"secids": secids, "fields": "f12,f14,f2,f3,f6", "fltt": "2"}
    )
    data = fetch_json(url)
    items = data.get("data", {}).get("diff") or []
    by_name = {item.get("f14"): item for item in items}
    by_code = {item.get("f12"): item for item in items}
    quotes: List[Quote] = []
    for name, secid in INDEX_SECIDS.items():
        code = secid.split(".", 1)[1]
        item = by_name.get(name) or by_code.get(code) or {}
        quotes.append(Quote(name, code, safe_float(item.get("f2")), safe_float(item.get("f3")), safe_float(item.get("f6"))))
    return quotes


def fetch_board_flow() -> List[Dict[str, Any]]:
    params = {
        "pn": "1",
        "pz": "10",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f62",
        "fs": "m:90+t:2",
        "fields": "f12,f14,f62,f184,f3",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
    data = fetch_json(url)
    return data.get("data", {}).get("diff") or []


def fetch_global_quotes() -> List[Quote]:
    symbols = ",".join(GLOBAL_SYMBOLS.values())
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}"
    data = fetch_json(url)
    results = data.get("quoteResponse", {}).get("result") or []
    by_symbol = {item.get("symbol"): item for item in results}
    quotes: List[Quote] = []
    for name, symbol in GLOBAL_SYMBOLS.items():
        raw_symbol = urllib.parse.unquote(symbol)
        item = by_symbol.get(raw_symbol) or by_symbol.get(symbol) or {}
        quotes.append(Quote(name, raw_symbol, safe_float(item.get("regularMarketPrice")), safe_float(item.get("regularMarketChangePercent")), None))
    return quotes


def html_table(headers: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    head = "".join(
        f'<th style="padding:10px 8px;border-bottom:1px solid #355368;color:#9cb0bf;font-size:12px;text-align:left;">{escape(h)}</th>'
        for h in headers
    )
    body = []
    for row in rows:
        cells = "".join(
            f'<td style="padding:11px 8px;border-bottom:1px solid #1f3a4e;vertical-align:top;color:#d7e6ee;">{cell}</td>'
            for cell in row
        )
        body.append(f"<tr>{cells}</tr>")
    return '<table style="width:100%;border-collapse:collapse;font-size:14px;">' + f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def list_items(items: Iterable[str], limit: int = 8) -> str:
    rows = []
    for item in list(items)[:limit]:
        rows.append(f'<li style="margin:0 0 8px;color:#d7e6ee;font-size:14px;">{escape(item).replace(chr(10), "<br>")}</li>')
    if not rows:
        rows.append('<li style="margin:0;color:#d7e6ee;font-size:14px;">数据待确认</li>')
    return '<ul style="margin:0;padding-left:18px;">' + "".join(rows) + "</ul>"


def section(title: str, body: str, subtitle: str = "") -> str:
    subtitle_html = f'<span style="color:#9cb0bf;font-size:12px;">{escape(subtitle)}</span>' if subtitle else ""
    return (
        '<div style="margin-top:18px;padding:18px;border:1px solid #25445a;border-radius:8px;background:#102333;">'
        '<div style="display:flex;justify-content:space-between;gap:14px;align-items:flex-end;margin-bottom:12px;">'
        f'<h2 style="margin:0;color:#ffd400;font-size:20px;line-height:1.2;">{escape(title)}</h2>{subtitle_html}'
        f"</div>{body}</div>"
    )


def quote_rows(quotes: List[Quote]) -> List[List[str]]:
    return [
        [
            escape(q.name),
            escape(fmt_num(q.price)),
            f'<span style="color:{pct_color(q.pct)};font-weight:700;">{escape(fmt_pct(q.pct))}</span>',
            escape(fmt_amount(q.amount)),
        ]
        for q in quotes
    ]


def board_rows(boards: List[Dict[str, Any]]) -> List[List[str]]:
    rows = []
    for item in boards[:10]:
        flow = safe_float(item.get("f62"))
        pct = safe_float(item.get("f3"))
        rows.append(
            [
                escape(str(item.get("f14", "数据待确认"))),
                f'<span style="color:{pct_color(flow)};font-weight:700;">{escape(fmt_amount(flow))}</span>',
                f'<span style="color:{pct_color(pct)};font-weight:700;">{escape(fmt_pct(pct))}</span>',
            ]
        )
    return rows or [["板块资金接口暂不可用", "数据待确认", "数据待确认"]]


def build_runtime_update_section(indices: List[Quote], boards: List[Dict[str, Any]], global_quotes: List[Quote]) -> str:
    return "".join(
        [
            section("运行时指数更新", html_table(["指数", "点位", "涨跌幅", "成交额"], quote_rows(indices[:9])), "发送前实时抓取"),
            section("运行时板块资金", html_table(["板块", "主力净流入", "涨跌幅"], board_rows(boards)), "发送前实时抓取"),
            section("运行时外部变量", html_table(["变量", "最新值", "涨跌幅", "成交额"], quote_rows(global_quotes)), "发送前实时抓取"),
        ]
    )


def build_kpi_rows(indices: List[Quote], template_kpis: List[str]) -> List[str]:
    rows = []
    live = any(q.price is not None for q in indices[:5])
    if live:
        for q in indices[:5]:
            rows.append(
                '<td style="width:20%;padding:6px;vertical-align:top;">'
                '<div style="min-height:108px;padding:14px;border:1px solid #25445a;border-radius:8px;background:#0f2231;text-align:center;">'
                f'<div style="font-size:12px;color:#9cb0bf;margin-bottom:7px;">{escape(q.name)}</div>'
                f'<div style="font-size:24px;font-weight:900;color:{pct_color(q.pct)};line-height:1.1;">{escape(fmt_num(q.price))}</div>'
                f'<div style="font-size:12px;color:#c7d5de;margin-top:8px;">{escape(fmt_pct(q.pct))} | 成交 {escape(fmt_amount(q.amount))}</div>'
                '</div></td>'
            )
    else:
        for kpi in template_kpis[:5]:
            parts = [part for part in kpi.splitlines() if part]
            rows.append(
                '<td style="width:20%;padding:6px;vertical-align:top;">'
                '<div style="min-height:108px;padding:14px;border:1px solid #25445a;border-radius:8px;background:#0f2231;text-align:center;">'
                f'<div style="font-size:12px;color:#9cb0bf;margin-bottom:7px;">{escape(parts[0] if parts else "指标")}</div>'
                f'<div style="font-size:24px;font-weight:900;color:#ffd400;line-height:1.1;">{escape(parts[1] if len(parts) > 1 else "数据待确认")}</div>'
                f'<div style="font-size:12px;color:#c7d5de;margin-top:8px;">{escape(" ".join(parts[2:]))}</div>'
                '</div></td>'
            )
    while len(rows) < 5:
        rows.append('<td style="width:20%;padding:6px;"></td>')
    return rows


def rows_to_email_table(rows: List[List[str]], limit: int = 10) -> str:
    if not rows:
        return html_table(["项目", "内容"], [["数据待确认", "模板中未提取到表格内容"]])
    width = max(len(row) for row in rows[:limit])
    normalized = [[escape(cell).replace(chr(10), "<br>") for cell in row] + [""] * (width - len(row)) for row in rows[:limit]]
    return html_table([f"列{i + 1}" for i in range(width)], normalized)


def build_html_from_site_template(mode: str, template_path: Path, indices: List[Quote], boards: List[Dict[str, Any]], global_quotes: List[Quote]) -> str:
    parser = SiteTemplateParser()
    parser.feed(template_path.read_text(encoding="utf-8"))
    report_date = cn_now().strftime("%Y-%m-%d")
    mode_name = MODE_NAMES[mode]
    hero_text = parser.paragraphs[0] if parser.paragraphs else "模板报告内容已读取，数据口径以网页正文为准。"
    status = parser.status or "已接入网页模板"
    theme_rows = []
    for theme in parser.themes[:6]:
        parts = [part for part in theme.splitlines() if part]
        title = parts[0] if parts else "验证条目"
        body = "<br>".join(escape(part) for part in parts[1:4])
        theme_rows.append(
            '<tr><td style="padding:12px 8px;border-bottom:1px solid #1f3a4e;">'
            f'<b style="color:#ffd400;">{escape(title)}</b><div style="color:#d7e6ee;margin-top:5px;">{body}</div>'
            '</td></tr>'
        )
    theme_table = '<table style="width:100%;border-collapse:collapse;font-size:14px;">' + "".join(theme_rows) + "</table>" if theme_rows else list_items([])
    return f"""<div style="margin:0;background:#08121a;color:#eaf4ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',Arial,sans-serif;line-height:1.5;padding:0;">
  <div style="max-width:1180px;margin:0 auto;background:#08121a;padding:22px;">
    <div style="padding:24px 26px;border:1px solid #25445a;border-radius:8px;background:#102333;">
      <div style="font-size:13px;color:#9cb0bf;margin-bottom:8px;">{escape(MODE_CONTEXT[mode])}</div>
      <h1 style="margin:0 0 10px;color:#ffd400;font-size:36px;line-height:1.08;">{escape(mode_name)}</h1>
      <p style="margin:0;max-width:920px;color:#c7d5de;font-size:14px;">{escape(hero_text)}</p>
      <div style="display:inline-block;margin-top:12px;border:1px solid #355368;border-radius:999px;padding:8px 12px;color:#d9e8f0;background:#0b1a25;font-size:12px;">{escape(status)}</div>
    </div>
    <table style="width:100%;border-collapse:collapse;margin-top:18px;"><tr>{''.join(build_kpi_rows(indices, parser.kpis))}</tr></table>
    {build_runtime_update_section(indices, boards, global_quotes)}
    {section("模板结构摘要", list_items(parser.summaries, 8), "从网页模板抽取")}
    {section("验证条目", theme_table, "已验证 / 未确认 / 继续观察")}
    {section("消息传导与风险观察", rows_to_email_table(parser.table_rows, 10), "事件 -> A股映射 -> 盘面验证")}
    {section("后续观察", list_items(parser.list_items, 9), "三档任务共用同一模板")}
    <p style="margin:22px 0 0;color:#9cb0bf;font-size:12px;">报告日期：{escape(report_date)} | 模板：{escape(str(template_path))} | 本报告仅用于市场结构观察，不构成投资建议。</p>
  </div>
</div>"""


def build_plain_runtime_html(mode: str, indices: List[Quote], boards: List[Dict[str, Any]], global_quotes: List[Quote]) -> str:
    report_date = cn_now().strftime("%Y-%m-%d")
    mode_name = MODE_NAMES[mode]
    return f"""<div style="margin:0;background:#08121a;color:#eaf4ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',Arial,sans-serif;line-height:1.5;padding:22px;">
  <div style="max-width:1180px;margin:0 auto;">
    <h1 style="margin:0 0 10px;color:#ffd400;font-size:34px;">{escape(mode_name)}</h1>
    <p style="margin:0 0 18px;color:#c7d5de;">模板文件未找到，已使用运行时数据兜底版。报告日期：{escape(report_date)}</p>
    {build_runtime_update_section(indices, boards, global_quotes)}
    <p style="margin:22px 0 0;color:#9cb0bf;font-size:12px;">本报告仅用于市场结构观察，不构成投资建议。</p>
  </div>
</div>"""


def validate_email_html(html_body: str) -> None:
    lowered = html_body.lower()
    blocked = [marker for marker in BLOCKED_EMAIL_MARKERS if marker in lowered]
    if blocked:
        raise SystemExit(f"Email HTML contains blocked webpage markup: {', '.join(blocked)}")


def parse_smtp_ports() -> List[int]:
    raw = os.environ.get("SMTP_PORTS")
    if raw:
        return [int(item.strip()) for item in raw.split(",") if item.strip()]
    if os.environ.get("SMTP_PORT"):
        return [int(os.environ["SMTP_PORT"])]
    return list(DEFAULT_SMTP_PORTS)


def smtp_login_and_send(host: str, port: int, sender: str, password: str, message: EmailMessage, context: ssl.SSLContext) -> None:
    server = smtplib.SMTP_SSL(host, port, context=context, timeout=30) if port == 465 else smtplib.SMTP(host, port, timeout=30)
    try:
        server.ehlo()
        if port != 465:
            server.starttls(context=context)
            server.ehlo()
        server.login(sender, password, initial_response_ok=False)
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
    if not sender or not password:
        raise SystemExit("Missing SMTP credentials: set QQ_SMTP_USER and QQ_SMTP_AUTH_CODE")
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
        except (smtplib.SMTPException, OSError) as exc:
            errors.append(f"{port}: {exc}")
    raise SystemExit("SMTP发送失败。已尝试端口 " + ", ".join(str(p) for p in ports) + "；错误：" + " | ".join(errors))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and send cloud A-share radar HTML email.")
    parser.add_argument("--mode", choices=["premarket", "midday", "aftermarket"], required=True)
    parser.add_argument("--template-html", default=os.environ.get("A_SHARE_EMAIL_TEMPLATE", str(DEFAULT_TEMPLATE_HTML)))
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
        indices = [Quote(name, secid.split(".", 1)[1], None, None, None) for name, secid in INDEX_SECIDS.items()]
    try:
        boards = fetch_board_flow()
    except Exception as exc:
        errors.append(f"板块资金获取失败: {exc}")
        boards = []
    try:
        global_quotes = fetch_global_quotes()
    except Exception as exc:
        errors.append(f"外部变量获取失败: {exc}")
        global_quotes = []

    template_path = Path(args.template_html)
    if template_path.exists():
        html_body = build_html_from_site_template(args.mode, template_path, indices, boards, global_quotes)
    else:
        errors.append(f"模板文件不存在，已回退到运行时行情版: {template_path}")
        html_body = build_plain_runtime_html(args.mode, indices, boards, global_quotes)
    if errors:
        html_body += '<div style="max-width:1180px;margin:12px auto;padding:14px;border:1px solid #806428;background:#201807;color:#ffd400;font-family:Arial,sans-serif;">' + escape("；".join(errors)) + "</div>"
    validate_email_html(html_body)
    if args.output_html:
        Path(args.output_html).write_text(html_body, encoding="utf-8")
    if args.send:
        subject = f"{mode_name} {report_date}"
        send_email(subject, html_body, f"{subject}\n\n本报告已在发送前刷新运行时数据。")
        print(f"sent {subject}")
    else:
        print(f"generated {mode_name} {report_date}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

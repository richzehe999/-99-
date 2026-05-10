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
from typing import Any, Dict, Iterable, List, Optional


CN_TZ = timezone(timedelta(hours=8))
DEFAULT_RECIPIENT = "240575148@qq.com"
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_SMTP_PORTS = (465, 587)
BLOCKED_EMAIL_MARKERS = ("<style", "<script", "<head", "</head", "<!doctype")


@dataclass
class Quote:
    name: str
    code: str
    price: Optional[float]
    pct: Optional[float]
    amount: Optional[float]


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
            f'<td style="padding:11px 8px;border-bottom:1px solid #edf1f5;vertical-align:top;">{cell}</td>'
            for cell in row
        )
        body.append(f"<tr>{cells}</tr>")
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


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
        '<div style="min-height:130px;padding:15px;border:1px solid #d9e0e7;border-radius:8px;background:#fbfcfd;">'
        f"{tag_html}<h3 style=\"margin:0 0 8px;font-size:17px;color:#17202a;\">{escape(title)}</h3>"
        f'<p style="margin:0;color:#657180;font-size:14px;">{body}</p>'
        "</div></td>"
    )


def build_html(mode: str, indices: List[Quote], boards: List[Dict[str, Any]], global_quotes: List[Quote]) -> str:
    now = cn_now()
    report_date = now.strftime("%Y-%m-%d")
    mode_name = "A股盘前分析雷达" if mode == "premarket" else "A股盘后验证雷达"
    status = "盘前最新可得数据" if mode == "premarket" else "盘后收盘数据优先"

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

    conclusion_html = "".join(
        '<div style="display:grid;grid-template-columns:86px 1fr;gap:12px;padding:10px 0;border-bottom:1px solid #edf1f5;">'
        f'<b style="font-size:14px;">{escape(label)}</b><span style="color:#657180;font-size:14px;">{escape(text)}</span></div>'
        for label, text in conclusion_rows
    )

    return f"""<div style="margin:0;background:#f7f8f9;color:#17202a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',Arial,sans-serif;line-height:1.5;padding:0;">
  <div style="max-width:1180px;margin:0 auto;background:#ffffff;">
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="width:230px;background:#1d2733;color:#eef4f8;padding:28px 24px;vertical-align:top;">
          <div style="font-size:18px;font-weight:800;">A股消息雷达</div>
          <div style="color:#9eb0c0;font-size:13px;margin-top:4px;">{escape(report_date)}｜{escape(status)}</div>
          <div style="display:grid;gap:18px;margin-top:34px;font-weight:700;color:#dbe7ee;font-size:15px;">
            <div>市场基准</div><div>核心消息</div><div>传导链</div><div>外部风险</div><div>后续验证</div>
          </div>
          <div style="margin-top:36px;border:1px solid rgba(255,255,255,.14);border-radius:8px;padding:14px;color:#b7c6d1;font-size:13px;">
            每次发送前刷新数据；若非交易日，明确使用最近交易日口径。
          </div>
        </td>
        <td style="padding:34px 34px 42px;vertical-align:top;">
          <div style="display:flex;justify-content:space-between;gap:24px;align-items:flex-start;">
            <div>
              <h1 style="margin:0 0 10px;font-size:40px;line-height:1.08;color:#17202a;">{escape(mode_name)}</h1>
              <p style="margin:0 0 10px;max-width:780px;font-size:16px;color:#2d3642;">{escape(lead)}</p>
              <p style="margin:0;color:#657180;font-size:13px;">报告日期：{escape(report_date)}｜数据源：东方财富行情接口、Yahoo Finance公开行情等；实际可得性以运行时为准。</p>
            </div>
            <div style="white-space:nowrap;border:1px solid #cbd6e1;border-radius:999px;padding:9px 14px;color:#2d3642;background:#fff;font-size:13px;">{escape(status)}</div>
          </div>

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
    parser.add_argument("--mode", choices=["premarket", "aftermarket"], required=True)
    parser.add_argument("--output-html", help="Write generated HTML to this path.")
    parser.add_argument("--send", action="store_true", help="Send the report through QQ SMTP.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mode_name = "A股盘前分析雷达" if args.mode == "premarket" else "A股盘后验证雷达"
    report_date = cn_now().strftime("%Y-%m-%d")

    errors: List[str] = []
    try:
        indices = fetch_a_share_indices()
    except Exception as exc:
        errors.append(f"A股指数获取失败: {exc}")
        indices = [Quote(name=name, code=secid.split(".", 1)[1], price=None, pct=None, amount=None) for name, secid in INDEX_SECIDS.items()]

    boards = fetch_board_flow()
    global_quotes = fetch_global_quotes()
    html_body = build_html(args.mode, indices, boards, global_quotes)

    if errors:
        html_body += (
            '<div style="max-width:1180px;margin:12px auto;padding:14px;border:1px solid #fff6e5;'
            'background:#fffaf0;color:#865a13;font-family:Arial,sans-serif;">'
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

#!/usr/bin/env python3
"""Feishu A-share radar notification - 盘前/午间/盘后推送"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


CN_TZ = timezone(timedelta(hours=8))

INDEX_SECIDS = {
    "上证指数": "1.000001",
    "深证成指": "0.399001",
    "创业板指": "0.399006",
    "科创50": "1.000688",
    "沪深300": "1.000300",
}

GLOBAL_SYMBOLS = {
    "纳斯达克": "%5EIXIC",
    "标普500": "%5EGSPC",
    "WTI原油": "CL=F",
    "黄金": "GC=F",
    "美元/离岸人民币": "CNH=X",
}

MODE_INFO = {
    "premarket": {
        "title": "A股盘前雷达",
        "color": "blue",
        "desc": "盘前8:00推送 — 隔夜外盘、商品、政策与开盘条件",
    },
    "midday": {
        "title": "A股午间雷达",
        "color": "indigo",
        "desc": "午间12:10推送 — 早盘资金方向、主线强度与下午条件",
    },
    "aftermarket": {
        "title": "A股盘后雷达",
        "color": "purple",
        "desc": "收盘16:20推送 — 当日复盘、主线验证与明日观察",
    },
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
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "-", ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "--"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def fmt_amount(value: Optional[float]) -> str:
    if value is None:
        return "--"
    yi = value / 100_000_000
    if yi >= 10_000:
        return f"{yi / 10_000:.2f}万亿"
    return f"{yi:.0f}亿"


def fetch_a_share_indices() -> List[Dict[str, Any]]:
    secids = ",".join(INDEX_SECIDS.values())
    url = (
        "https://push2.eastmoney.com/api/qt/ulist.np/get?"
        + urllib.parse.urlencode({"secids": secids, "fields": "f12,f14,f2,f3,f6", "fltt": "2"})
    )
    data = fetch_json(url)
    items = data.get("data", {}).get("diff") or []
    by_name = {item.get("f14"): item for item in items}
    by_code = {item.get("f12"): item for item in items}

    results = []
    for name, secid in INDEX_SECIDS.items():
        code = secid.split(".", 1)[1]
        item = by_name.get(name) or by_code.get(code) or {}
        results.append({
            "name": name,
            "price": safe_float(item.get("f2")),
            "pct": safe_float(item.get("f3")),
            "amount": safe_float(item.get("f6")),
        })
    return results


def fetch_board_flow(top_n: int = 5) -> List[Dict[str, Any]]:
    params = {
        "pn": "1",
        "pz": str(top_n + 3),
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
    return (data.get("data", {}).get("diff") or [])[:top_n]


def fetch_board_outflow(top_n: int = 5) -> List[Dict[str, Any]]:
    params = {
        "pn": "1",
        "pz": str(top_n + 3),
        "po": "0",
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
    return (data.get("data", {}).get("diff") or [])[:top_n]


def fetch_global_quotes() -> List[Dict[str, Any]]:
    symbols = ",".join(GLOBAL_SYMBOLS.values())
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}"
    try:
        data = fetch_json(url)
    except Exception:
        return []

    results = data.get("quoteResponse", {}).get("result") or []
    by_symbol = {item.get("symbol"): item for item in results}
    quotes = []
    for name, symbol in GLOBAL_SYMBOLS.items():
        raw = urllib.parse.unquote(symbol)
        item = by_symbol.get(raw) or by_symbol.get(symbol) or {}
        quotes.append({
            "name": name,
            "price": safe_float(item.get("regularMarketPrice")),
            "pct": safe_float(item.get("regularMarketChangePercent")),
        })
    return quotes


# ── Feishu card builders ──────────────────────────────────────────


def pct_color(value: Optional[float]) -> str:
    if value is None:
        return "grey"
    return "green" if value > 0 else "red"


def pct_emoji(value: Optional[float]) -> str:
    if value is None:
        return "➖"
    return "🟢" if value > 0 else ("🔴" if value < 0 else "➖")


def index_field(idx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "is_short": True,
        "text": {
            "tag": "lark_md",
            "content": (
                f"**{idx['name']}**\n"
                f"{fmt_pct(idx['pct'])}"
            ),
        },
    }


def build_kpi_section(indices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not indices:
        return [{"tag": "div", "text": {"tag": "lark_md", "content": "数据获取失败"}}]

    index_md = "  ".join(
        f"{idx['name']} {idx['price'] if idx['price'] else '--'} ({fmt_pct(idx['pct'])})"
        for idx in indices[:5]
    )
    return [
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**市场核心**\n{index_md}"}},
    ]


def build_board_section(boards_in: List[Dict[str, Any]], boards_out: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lines = []
    if boards_in:
        inflows = " ".join(
            f"{b.get('f14','?')}{fmt_amount(safe_float(b.get('f62')))}"
            for b in boards_in[:5]
        )
        lines.append(f"**净流入** {inflows}")
    if boards_out:
        outflows = " ".join(
            f"{b.get('f14','?')}{fmt_amount(safe_float(b.get('f62')))}"
            for b in boards_out[:5]
        )
        lines.append(f"**净流出** {outflows}")
    if not lines:
        lines.append("板块资金接口暂不可用")
    return [{"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}}]


def build_global_section(quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not quotes:
        return [{"tag": "div", "text": {"tag": "lark_md", "content": "外部变量接口暂不可用"}}]
    md = "  ".join(
        f"{q['name']} {q['price'] if q['price'] else '--'} ({fmt_pct(q['pct'])})"
        for q in quotes
    )
    return [{"tag": "div", "text": {"tag": "lark_md", "content": f"**外部变量**\n{md}"}}]


def build_followup(mode: str) -> List[Dict[str, Any]]:
    followups = {
        "premarket": [
            "🟢 竞价 & 开盘15分钟验证主线方向",
            "🔴 若高开低走 / 量能不足，盘前预案降级",
            "👀 关注外盘期指和商品期货开盘联动",
        ],
        "midday": [
            "🟢 下午看主线是否继续扩散（龙头→补涨）",
            "🔴 若冲高回落+成交缩量，减仓观察",
            "👀 关注午后外部变量变化（港股、韩日、商品）",
        ],
        "aftermarket": [
            "🟢 明日看成交是否守住3万亿、主线是否延续",
            "🔴 若电子/通信继续抛售+新主线一日游，降低仓位",
            "👀 关注隔夜外盘和宏观数据",
        ],
    }
    items = followups.get(mode, [])
    return [
        {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(items)}},
    ]


def build_card(mode: str, indices: List[Dict[str, Any]], boards_in: List[Dict[str, Any]], boards_out: List[Dict[str, Any]], globals_: List[Dict[str, Any]]) -> str:
    info = MODE_INFO[mode]
    now_str = cn_now().strftime("%Y-%m-%d %H:%M")

    elements = []

    # Description
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"{info['desc']}\n更新时间：{now_str}"},
    })

    # Divider
    elements.append({"tag": "hr"})

    # KPI
    elements.extend(build_kpi_section(indices))

    elements.append({"tag": "hr"})

    # Board flows
    elements.extend(build_board_section(boards_in, boards_out))

    elements.append({"tag": "hr"})

    # Global
    elements.extend(build_global_section(globals_))

    elements.append({"tag": "hr"})

    # Follow-up
    elements.extend(build_followup(mode))

    # Note
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "数据源：东方财富行情接口 / Yahoo Finance | 仅供市场结构观察，不构成投资建议"}],
    })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{info['title']} {cn_now().strftime('%m/%d')}"},
            "template": info["color"],
        },
        "elements": elements,
    }

    return json.dumps({"msg_type": "interactive", "card": card}, ensure_ascii=False)


def send_feishu(webhook_url: str, payload: str) -> None:
    data = payload.encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    result = json.loads(body)
    if result.get("code") != 0:
        raise SystemExit(f"Feishu API error: {result}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Feishu A-share radar notification")
    parser.add_argument("--mode", choices=["premarket", "midday", "aftermarket"], required=True)
    parser.add_argument("--webhook-url", default=os.environ.get("FEISHU_WEBHOOK_URL"), help="Feishu webhook URL (or set FEISHU_WEBHOOK_URL)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.webhook_url:
        raise SystemExit("Missing --webhook-url or FEISHU_WEBHOOK_URL env var")

    errors = []

    indices = fetch_a_share_indices()
    if not indices:
        errors.append("指数获取失败")

    boards_in = fetch_board_flow(5)
    boards_out = fetch_board_outflow(5)
    if not boards_in and not boards_out:
        errors.append("板块资金接口不可用")

    globals_ = fetch_global_quotes()
    if not globals_:
        errors.append("外部变量接口不可用")

    payload = build_card(args.mode, indices, boards_in, boards_out, globals_)
    send_feishu(args.webhook_url, payload)

    now = cn_now().strftime("%H:%M")
    mode_name = {"premarket": "盘前", "midday": "午间", "aftermarket": "盘后"}[args.mode]
    print(f"[{now}] 飞书{mode_name}雷达推送成功")
    if errors:
        print(f"  警告: {'; '.join(errors)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

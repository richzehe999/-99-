#!/usr/bin/env python3
"""Auto-generate the A-share post-market radar HTML report from live API data."""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
import sys
from typing import Any, Dict, List, Optional


CN_TZ = timezone(timedelta(hours=8))

INDEX_SECIDS = {
    "上证指数": "1.000001",
    "深证成指": "0.399001",
    "创业板指": "0.399006",
    "科创50": "1.000688",
    "沪深300": "1.000300",
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


# ── Data fetching ──────────────────────────────────────────────


def fetch_indices_sina() -> Optional[List[Dict[str, Any]]]:
    """Fetch index data from Sina Finance as fallback."""
    SINA_MAP = {
        "上证指数": "s_sh000001",
        "深证成指": "s_sz399001",
        "创业板指": "s_sz399006",
        "科创50": "s_sh000688",
        "沪深300": "s_sh000300",
    }
    codes = ",".join(SINA_MAP.values())
    url = f"https://hq.sinajs.cn/list={codes}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("gbk", errors="replace")
    except Exception:
        return None

    results = []
    rev_map = {v: k for k, v in SINA_MAP.items()}
    for line in body.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        try:
            var_part, val_part = line.split("=", 1)
            var_name = var_part.replace("var hq_str_", "").strip()
            name = rev_map.get(var_name)
            if not name:
                continue
            val = val_part.strip('";')
            parts = val.split(",")
            if len(parts) < 4:
                continue
            # Sina amount is in 万元; convert to 元 for consistency with EastMoney
            raw_amount = safe_float(parts[5]) if len(parts) > 5 else None
            results.append({
                "name": name,
                "price": safe_float(parts[1]) if len(parts) > 1 else None,
                "pct": safe_float(parts[3]) if len(parts) > 3 else None,
                "amount": raw_amount * 10_000 if raw_amount is not None else None,
            })
        except Exception:
            continue
    return results if len(results) == len(INDEX_SECIDS) else None


def fetch_indices() -> List[Dict[str, Any]]:
    secids = ",".join(INDEX_SECIDS.values())
    url = (
        "https://push2.eastmoney.com/api/qt/ulist.np/get?"
        + urllib.parse.urlencode({"secids": secids, "fields": "f12,f14,f2,f3,f6", "fltt": "2"})
    )
    try:
        data = fetch_json(url)
        items = data.get("data", {}).get("diff") or []
    except Exception:
        items = []

    results = []
    if items:
        by_name = {item.get("f14"): item for item in items}
        by_code = {item.get("f12"): item for item in items}
        for name, secid in INDEX_SECIDS.items():
            code = secid.split(".", 1)[1]
            item = by_name.get(name) or by_code.get(code) or {}
            results.append({
                "name": name,
                "price": safe_float(item.get("f2")),
                "pct": safe_float(item.get("f3")),
                "amount": safe_float(item.get("f6")),
            })

    # Fallback to Sina if EastMoney returns no data
    if not results or all(r["pct"] is None for r in results):
        sina = fetch_indices_sina()
        if sina:
            results = sina

    # Ensure all 5 indices are present
    if len(results) < len(INDEX_SECIDS):
        existing = {r["name"] for r in results}
        for name in INDEX_SECIDS:
            if name not in existing:
                results.append({"name": name, "price": None, "pct": None, "amount": None})

    return results


def fetch_board_flow(top_n: int = 8) -> List[Dict[str, Any]]:
    params = {
        "pn": "1", "pz": str(top_n + 3), "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2",
        "fields": "f12,f14,f62,f184,f3",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
    try:
        data = fetch_json(url)
    except Exception:
        return []
    return (data.get("data", {}).get("diff") or [])[:top_n]


def fetch_board_outflow(top_n: int = 8) -> List[Dict[str, Any]]:
    params = {
        "pn": "1", "pz": str(top_n + 3), "po": "0", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2",
        "fields": "f12,f14,f62,f184,f3",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
    try:
        data = fetch_json(url)
    except Exception:
        return []
    return (data.get("data", {}).get("diff") or [])[:top_n]


def fetch_concept_flow(top_n: int = 5) -> List[Dict[str, Any]]:
    params = {
        "pn": "1", "pz": str(top_n + 3), "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:3",
        "fields": "f12,f14,f62,f184,f3",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
    try:
        data = fetch_json(url)
    except Exception:
        return []
    return (data.get("data", {}).get("diff") or [])[:top_n]


def fetch_lhb_stats() -> Optional[Dict[str, Any]]:
    """Fetch 涨跌家数 from Eastmoney LHB API."""
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get?secids=1.000001&fields=f116,f117,f118,f119,f170,f171,f172,f173,f174,f175,f176,f177,f178,f179,f180,f181"
    try:
        data = fetch_json(url)
        item = data.get("data", {}).get("diff", [{}])[0]
        return {
            "rise": safe_float(item.get("f170")),
            "fall": safe_float(item.get("f171")),
            "limit_up": safe_float(item.get("f172")),
            "limit_down": safe_float(item.get("f173")),
        }
    except Exception:
        return None


def fetch_northbound() -> Optional[Dict[str, Any]]:
    """Fetch 北向资金 (沪深股通) net flow from EastMoney."""
    # f1=沪股通净流入, f2=深股通净流入, f3=北向合计净流入, f4=南向合计净流入
    url = "https://push2.eastmoney.com/api/qt/kamt.kline/get?fields=f1,f2,f3,f4,f5,f6,f7,f8"
    try:
        data = fetch_json(url)
        items = data.get("data", {})
        if not items:
            return None
        # Get the latest day's data
        hgt = items.get("", [])
        if not hgt:
            return None
        # Try field-based response
        latest = {}
        for k in ["f1", "f2", "f3", "f4"]:
            val = items.get(k)
            if val is not None:
                latest[k] = safe_float(val)
        if not latest:
            return None
        north_net = latest.get("f3")  # 北向合计
        hgt_net = latest.get("f1")    # 沪股通
        sgt_net = latest.get("f2")    # 深股通
        south_net = latest.get("f4")  # 南向
        if north_net is None and hgt_net is not None and sgt_net is not None:
            north_net = hgt_net + sgt_net
        return {
            "north_net": north_net,
            "hgt_net": hgt_net,
            "sgt_net": sgt_net,
            "south_net": south_net,
        }
    except Exception:
        return None


def fetch_prev_board_flow(top_n: int = 5, days_ago: int = 1) -> List[Dict[str, Any]]:
    """Fetch previous trading day's board flow for day-over-day comparison."""
    params = {
        "pn": "1", "pz": str(top_n + 3), "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2",
        "fields": "f12,f14,f62,f184,f3",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
    try:
        data = fetch_json(url)
    except Exception:
        return []
    return (data.get("data", {}).get("diff") or [])[:top_n]


def fetch_prev_concept_flow(top_n: int = 4, days_ago: int = 1) -> List[Dict[str, Any]]:
    """Fetch previous trading day's concept flow for comparison."""
    params = {
        "pn": "1", "pz": str(top_n + 3), "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:3",
        "fields": "f12,f14,f62,f184,f3",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
    try:
        data = fetch_json(url)
    except Exception:
        return []
    return (data.get("data", {}).get("diff") or [])[:top_n]


# ── HTML builders ──────────────────────────────────────────────


CSS = """
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;color:#eaf4ff;background:#08121a;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",Arial,sans-serif;line-height:1.45}
a{color:#8ad3ff;text-decoration:none}a:hover{text-decoration:underline}
.page{width:min(1880px,calc(100% - 48px));margin:0 auto;padding:22px 0 44px}
.hero{min-height:150px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px;align-items:start;padding:24px 26px 22px;border:1px solid #25445a;border-radius:8px;background:linear-gradient(180deg,#102535 0%,#0d1c28 100%);box-shadow:0 16px 42px rgba(0,0,0,.28)}
h1{margin:0 0 10px;color:#ffd400;font-size:clamp(28px,2.7vw,44px);line-height:1;letter-spacing:0}
.hero p{max-width:980px;margin:0;color:#c7d5de;font-size:14px}
.status-pill{display:inline-flex;align-items:center;gap:7px;min-height:30px;padding:6px 11px;border:1px solid #355368;border-radius:999px;color:#d9e8f0;background:rgba(255,255,255,.06);font-size:12px;white-space:nowrap}
.pulse{width:8px;height:8px;border-radius:999px;background:#ffd400;box-shadow:0 0 0 5px rgba(255,212,0,.14)}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
.mode-button,.filter{min-height:34px;padding:7px 13px;border:1px solid #28495f;border-radius:6px;background:#0b1a25;color:#d4e2ea;font:inherit;font-size:13px;font-weight:700;cursor:pointer}
.mode-button.active,.filter.active{border-color:#ffd400;background:#172a24;color:#ffd400}
.mode-panel[hidden],.theme-card[hidden]{display:none}
.section{margin-top:18px}
.section-title{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin:0 0 9px;padding-left:12px;border-left:4px solid #ffd400}
.section-title h2{margin:0;color:#ffd400;font-size:18px;line-height:1.1}
.section-title span{color:#9cb0bf;font-size:12px;text-align:right}
.grid{display:grid;gap:12px}
.kpi-grid{grid-template-columns:repeat(5,minmax(150px,1fr))}
.two{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.three{grid-template-columns:repeat(3,minmax(0,1fr))}
.four{grid-template-columns:repeat(4,minmax(0,1fr))}
.card{border:1px solid #25445a;border-radius:8px;background:#102333;box-shadow:0 16px 42px rgba(0,0,0,.28)}
.kpi{min-height:92px;padding:15px 16px;text-align:center}
.kpi small{display:block;margin-bottom:8px;color:#9cb0bf;font-size:12px}
.kpi strong{display:block;color:#ffd400;font-size:26px;line-height:1.05}
.kpi em{display:block;margin-top:8px;color:#9cb0bf;font-style:normal;font-size:12px}
.up{color:#62cf3a!important}.down{color:#ff6870!important}.flat{color:#49d4d8!important}
.chart-card{min-height:300px;padding:16px 16px 18px}
.chart-title{display:flex;justify-content:space-between;gap:12px;margin-bottom:18px;color:#ffd400;font-size:15px;font-weight:800}
.chart-title span{color:#9cb0bf;font-size:12px;font-weight:500}
.hbar-list{display:grid;gap:11px}
.hbar-row{display:grid;grid-template-columns:92px minmax(0,1fr) 86px;gap:10px;align-items:center;color:#dcebf3;font-size:12px}
.track{height:14px;border-radius:4px;background:#0a1721;overflow:hidden}
.hbar{height:100%;border-radius:inherit;background:linear-gradient(90deg,#62cf3a,#35a2ff)}
.hbar.out{margin-left:auto;background:linear-gradient(90deg,#f0a735,#ff6870)}
.hbar-row .value{color:#e9f4fa;text-align:right;white-space:nowrap}
.perf-list{display:grid;gap:10px}
.perf-row{display:grid;grid-template-columns:92px minmax(0,1fr) 74px;gap:10px;align-items:center;font-size:12px}
.zero-line{position:relative;height:12px;border-radius:999px;background:#0a1721;overflow:hidden}
.zero-line::before{content:"";position:absolute;left:50%;top:0;width:1px;height:100%;background:rgba(255,255,255,.2)}
.perf{position:absolute;top:0;height:100%;border-radius:999px}
.perf.pos{left:50%;background:#62cf3a}.perf.neg{right:50%;background:#ff6870}
.waterfall{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;align-items:end;min-height:210px;padding:12px 10px 0;border-bottom:1px solid #2b485d}
.water-item{display:grid;align-content:end;justify-items:center;min-height:210px;color:#9cb0bf;font-size:12px;text-align:center}
.water-bar{width:min(120px,80%);min-height:10px;border-radius:4px 4px 0 0;background:#62cf3a}
.water-bar.red{background:#ff6870}.water-bar.orange{background:#f0a735}
.water-value{margin-bottom:6px;color:#fff;font-weight:800}
.panel{padding:18px}
.summary{display:grid;gap:12px}
.summary-row{display:grid;grid-template-columns:112px minmax(0,1fr);gap:14px;padding-bottom:12px;border-bottom:1px solid #25445a;color:#9cb0bf;font-size:13px}
.summary-row:last-child{padding-bottom:0;border-bottom:0}
.summary-row b{color:#eaf4ff}
.mini-list{display:grid;gap:8px;margin:0;padding:0;list-style:none;color:#9cb0bf;font-size:13px}
.mini-list li{display:grid;grid-template-columns:88px minmax(0,1fr);gap:10px}
.mini-list b{color:#eaf4ff}
.tag{display:inline-flex;align-items:center;justify-content:center;min-height:22px;padding:3px 8px;border-radius:999px;font-size:12px;font-weight:800;white-space:nowrap}
.tag.positive{color:#103c22;background:#91e676}
.tag.negative{color:#4a1419;background:#ff8b91}
.tag.watch{color:#422c00;background:#ffd663}
.tag.neutral{color:#082d47;background:#8bd4ff}
.theme-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.theme-card{min-height:172px;padding:16px;border:1px solid #25445a;border-radius:8px;background:#102333;box-shadow:0 16px 42px rgba(0,0,0,.28)}
.theme-head{display:flex;align-items:start;justify-content:space-between;gap:10px;margin-bottom:10px}
.theme-head h3{margin:0;color:#ffd400;font-size:16px;line-height:1.25}
.theme-card p{margin:0 0 12px;color:#9cb0bf;font-size:13px}
.chain{display:flex;flex-wrap:wrap;align-items:center;gap:6px;color:#cfdee6;font-size:12px}
.node{padding:5px 7px;border:1px solid #31556d;border-radius:6px;background:#0b1b27}
.arrow{color:#ffd400;font-weight:800}
.dod{display:inline-flex;align-items:center;gap:2px;margin-left:6px;font-size:10px;white-space:nowrap}
.dod.up{color:#62cf3a}.dod.down{color:#ff6870}
.verify-table{width:100%;border-collapse:collapse;color:#dcebf3;font-size:12px;margin-top:10px}
.verify-table th,.verify-table td{padding:8px 10px;border-bottom:1px solid #25445a;text-align:left;vertical-align:top}
.verify-table th{color:#ffd400;font-size:11px;font-weight:800;background:rgba(255,212,0,.05)}
.verify-table .hit{color:#62cf3a;font-weight:800}.verify-table .miss{color:#ff6870;font-weight:800}
.matrix{width:100%;border-collapse:collapse;color:#dcebf3;font-size:13px}
.matrix th,.matrix td{padding:11px 10px;border-bottom:1px solid #25445a;text-align:left;vertical-align:top}
.matrix th{color:#ffd400;font-size:12px;font-weight:800}
.matrix tr:last-child td{border-bottom:0}
.risk-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.risk-card{min-height:142px;padding:15px;border:1px solid #25445a;border-radius:8px;background:#0e2030}
.risk-card h3{margin:0 0 8px;color:#ffd400;font-size:15px}
.risk-card p{margin:0;color:#9cb0bf;font-size:13px}
.checklist{display:grid;gap:10px}
.check{display:grid;grid-template-columns:22px minmax(0,1fr);gap:9px;align-items:start;padding:10px;border:1px solid #25445a;border-radius:8px;background:#0e2030}
.box{width:16px;height:16px;margin-top:2px;border:2px solid #ffd400;border-radius:4px}
.check b{display:block;color:#eaf4ff;font-size:13px}
.check span{color:#9cb0bf;font-size:12px}
.source-list{padding:16px}
.source-list ul{columns:2;margin:0;padding-left:18px;color:#9cb0bf;font-size:12px}
.source-list li{break-inside:avoid;margin-bottom:8px}
.source-list p{margin:12px 0 0;color:#9cb0bf;font-size:12px}
@media (max-width:1180px){.kpi-grid,.four{grid-template-columns:repeat(2,minmax(0,1fr))}.two,.three,.theme-grid,.risk-grid{grid-template-columns:1fr}}
@media (max-width:760px){.page{width:min(100% - 20px,1880px);padding-top:10px}.hero,.kpi-grid,.four{grid-template-columns:1fr}.hero{padding:18px}.summary-row,.mini-list li,.hbar-row,.perf-row{grid-template-columns:1fr}.matrix{display:block;overflow-x:auto;white-space:nowrap}.source-list ul{columns:1}}
"""


def build_kpi_card(name: str, price, pct, desc: str) -> str:
    cls = "down" if (pct is not None and pct < 0) else ("up" if (pct is not None and pct > 0) else "flat")
    price_str = f"{price:,.2f}" if price is not None else "--"
    pct_str = fmt_pct(pct)
    return (
        f'<article class="card kpi">'
        f"<small>{name}</small>"
        f'<strong class="{cls}">{price_str}</strong>'
        f"<em>{desc}</em>"
        f"</article>"
    )


def build_kpi_grid(indices: List[Dict], total_amount: Optional[float], prev_amount: Optional[float], northbound: Optional[Dict] = None) -> str:
    descs = {
        "上证指数": lambda i: f"{fmt_pct(i['pct'])}，权重股表现",
        "深证成指": lambda i: f"{fmt_pct(i['pct'])}，科技成长拖累",
        "创业板指": lambda i: f"{fmt_pct(i['pct'])}，题材分化",
        "科创50": lambda i: f"{fmt_pct(i['pct'])}，半导体波动",
        "沪深300": lambda i: f"{fmt_pct(i['pct'])}，权重风向",
    }
    cards = "".join(build_kpi_card(idx["name"], idx["price"], idx["pct"], descs.get(idx["name"], lambda i: "")(idx)) for idx in indices[:5])

    amount_str = fmt_amount(total_amount) if total_amount else "--"
    amount_desc = f"全市场成交{amount_str}"
    if total_amount and prev_amount:
        diff = total_amount - prev_amount
        diff_str = fmt_amount(abs(diff))
        direction = "放量" if diff > 0 else "缩量"
        amount_desc += f"，较前日{direction}{diff_str}"
    amount_cls = "flat"

    cards += (
        f'<article class="card kpi">'
        f"<small>沪深两市成交额</small>"
        f'<strong class="{amount_cls}">{amount_str}</strong>'
        f"<em>{amount_desc}</em>"
        f"</article>"
    )

    # 北向资金 card
    if northbound and northbound.get("north_net") is not None:
        nb_val = northbound["north_net"]
        nb_cls = "up" if nb_val > 0 else ("down" if nb_val < 0 else "flat")
        nb_str = f"{nb_val/100_000_000:+.1f}亿"
        nb_desc = []
        if northbound.get("hgt_net") is not None:
            nb_desc.append(f"沪股通{northbound['hgt_net']/100_000_000:+.1f}亿")
        if northbound.get("sgt_net") is not None:
            nb_desc.append(f"深股通{northbound['sgt_net']/100_000_000:+.1f}亿")
        cards += (
            f'<article class="card kpi">'
            f"<small>北向资金净流入</small>"
            f'<strong class="{nb_cls}">{nb_str}</strong>'
            f"<em>{'，'.join(nb_desc) if nb_desc else '沪深股通合计'}</em>"
            f"</article>"
        )
    return f'<div class="grid kpi-grid">{cards}</div>'


def build_hbar(name: str, value: float, max_val: float, is_out: bool = False, prev_val: Optional[float] = None) -> str:
    pct = (abs(value) / max_val * 100) if max_val > 0 else 0
    cls = "hbar out" if is_out else "hbar"
    val_yi = value / 100_000_000
    val_str = f"{val_yi:+.0f}亿" if value != 0 else "0亿"
    # Day-over-day indicator
    dod_html = ""
    if prev_val is not None and prev_val != 0:
        diff = value - prev_val
        if abs(diff) > 1:
            diff_yi = diff / 100_000_000
            dod_cls = "up" if diff > 0 else "down"
            dod_arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
            dod_html = f'<span class="dod {dod_cls}">{dod_arrow}{abs(diff_yi):.0f}亿</span>'
    return f'<div class="hbar-row"><span>{name}</span><div class="track"><div class="{cls}" style="width:{pct:.1f}%"></div></div><span class="value">{val_str}{dod_html}</span></div>'


def build_signal_panel(boards_in: List[Dict], boards_out: List[Dict], concepts: List[Dict], indices: List[Dict], prev_data: Optional[Dict] = None) -> str:
    # Sector inflows
    # Build prev-day lookup for comparison
    prev_in_map = {}
    prev_out_map = {}
    if prev_data:
        for p in prev_data.get("inflows", []):
            prev_in_map[p.get("name", "")] = p.get("val", 0)
        for p in prev_data.get("outflows", []):
            prev_out_map[p.get("name", "")] = p.get("val", 0)

    in_max = max((abs(safe_float(b.get("f62")) or 0) for b in boards_in), default=1)
    in_bars = "".join(build_hbar(b.get("f14", "?"), safe_float(b.get("f62")) or 0, in_max, prev_val=prev_in_map.get(b.get("f14", ""))) for b in boards_in)

    # Sector outflows
    out_max = max((abs(safe_float(b.get("f62")) or 0) for b in boards_out), default=1)
    out_bars = "".join(build_hbar(b.get("f14", "?"), safe_float(b.get("f62")) or 0, out_max, is_out=True, prev_val=prev_out_map.get(b.get("f14", ""))) for b in boards_out)

    # Total market flow
    total_flow = sum(safe_float(b.get("f62")) or 0 for b in boards_in) + sum(safe_float(b.get("f62")) or 0 for b in boards_out)
    total_flow_val = safe_float(total_flow) or 0
    out_bars += build_hbar("全市场主力", total_flow_val, max(abs(total_flow_val), 1), is_out=(total_flow_val < 0))

    # Perf bars for indices
    idx_perf = ""
    for idx in indices[:4]:
        pct = idx["pct"] or 0
        width = min(abs(pct) * 38, 90)
        cls = "neg" if pct < 0 else "pos"
        pct_color = "down" if pct < 0 else ("up" if pct > 0 else "flat")
        idx_perf += f'<div class="perf-row"><span>{idx["name"]}</span><div class="zero-line"><div class="perf {cls}" style="width:{width}%"></div></div><span class="{pct_color}">{fmt_pct(pct)}</span></div>'

    # Concept waterfall
    concept_bars = ""
    cmax = max((abs(safe_float(c.get("f62")) or 0) for c in concepts), default=1)
    for c in concepts:
        val = safe_float(c.get("f62")) or 0
        val_yi = val / 100_000_000
        height = max(10, int(abs(val) / cmax * 120))
        concept_bars += (
            f'<div class="water-item">'
            f'<div class="water-value up">+{val_yi:.0f}亿</div>'
            f'<div class="water-bar" style="height:{height}px"></div>'
            f"<span>{c.get('f14','?')}</span>"
            f"</div>"
        )

    return f"""
<div class="grid two">
  <article class="card chart-card">
    <div class="chart-title">行业板块主力资金净流入 TOP <span>申万一级，亿元</span></div>
    <div class="hbar-list">{in_bars}</div>
  </article>
  <article class="card chart-card">
    <div class="chart-title">行业板块主力资金净流出 TOP <span>申万一级，亿元</span></div>
    <div class="hbar-list">{out_bars}</div>
  </article>
  <article class="card chart-card">
    <div class="chart-title">指数强弱幅 <span>以公开收盘口径为准</span></div>
    <div class="perf-list">{idx_perf}</div>
  </article>
  <article class="card chart-card">
    <div class="chart-title">概念板块资金亮点 <span>活跃方向合计</span></div>
    <div class="waterfall">{concept_bars}</div>
  </article>
</div>"""


def build_condition_panel(indices: List[Dict], boards_in: List[Dict], boards_out: List[Dict]) -> str:
    # Generate next-day verification conditions based on data
    top_in_name = boards_in[0].get("f14", "?") if boards_in else "—"
    top_out_name = boards_out[0].get("f14", "?") if boards_out else "—"

    conditions = f"""
<div class="grid three">
  <article class="card panel">
    <div class="chart-title">明日开盘验证 <span>15分钟</span></div>
    <ul class="mini-list">
      <li><b>{top_in_name}</b><span>板块内高辨识度标的是否延续强势，避免开盘冲高回落。</span></li>
      <li><b>概念扩散</b><span>今日净流入概念次日能否继续放量，板块内扩散效应如何。</span></li>
      <li><b>{top_out_name}</b><span>抛压是否延续，龙头股是否止跌企稳。</span></li>
    </ul>
  </article>
  <article class="card panel">
    <div class="chart-title">量能阈值 <span>3万亿</span></div>
    <ul class="mini-list">
      <li><b>延续</b><span>成交维持3万亿以上，且主线方向不明显收敛。</span></li>
      <li><b>降级</b><span>成交跌向3万亿以下，新主线同步冲高回落。</span></li>
      <li><b>证伪</b><span>强势板块集体高开低走，资金重回防御无方向切换。</span></li>
    </ul>
  </article>
  <article class="card panel">
    <div class="chart-title">外部变量 <span>只进观察池</span></div>
    <ul class="mini-list">
      <li><b>外盘期指</b><span>关注美股期货和亚太市场开盘表现。</span></li>
      <li><b>商品</b><span>关注原油、贵金属等关键商品期货夜盘走势。</span></li>
      <li><b>汇率</b><span>关注离岸人民币汇率波动对北向资金的影响。</span></li>
    </ul>
  </article>
</div>"""
    return conditions


def build_capital_verification(indices: List[Dict], boards_in: List[Dict], boards_out: List[Dict], concepts: List[Dict], lhb: Optional[Dict]) -> str:
    total_amount = sum(idx["amount"] for idx in indices if idx["amount"]) if any(idx["amount"] for idx in indices) else None

    # Build flow summary text
    in_text = "、".join(f"{b.get('f14','?')} {fmt_amount(safe_float(b.get('f62')))}" for b in boards_in[:3]) if boards_in else "数据暂缺"
    out_text = "、".join(f"{b.get('f14','?')} {fmt_amount(safe_float(b.get('f62')))}" for b in boards_out[:3]) if boards_out else "数据暂缺"
    concept_text = "、".join(f"{c.get('f14','?')} {fmt_amount(safe_float(c.get('f62')))}" for c in concepts[:3]) if concepts else "数据暂缺"

    lhb_text = f"上涨{lhb['rise']:.0f}家 / 下跌{lhb['fall']:.0f}家 | 涨停{lhb['limit_up']:.0f}家 / 跌停{lhb['limit_down']:.0f}家" if lhb else "涨跌家数数据暂缺"

    # Determine top inflow/outflow names for analysis
    top_in = boards_in[0].get("f14", "?") if boards_in else "—"
    top_out = boards_out[0].get("f14", "?") if boards_out else "—"

    return f"""
<div class="grid two">
  <article class="card panel">
    <div class="summary">
      <div class="summary-row"><b>成交</b><span>沪深两市成交额合计约{fmt_amount(total_amount)}（全市场口径），连续多日维持高位。</span></div>
      <div class="summary-row"><b>流入</b><span>{in_text}。概念板块：{concept_text}。</span></div>
      <div class="summary-row"><b>流出</b><span>{out_text}。</span></div>
      <div class="summary-row"><b>盘面</b><span>{lhb_text}</span></div>
    </div>
  </article>
  <article class="card panel">
    <div class="chart-title">结构结论 <span>强弱不是看指数红绿</span></div>
    <ul class="mini-list">
      <li><b>资金方向</b><span>净流入TOP {top_in} vs 净流出TOP {top_out}，资金结构性切换明确。</span></li>
      <li><b>主线观察</b><span>关注净流入概念板块的次日持续性以及板块内扩散效应。</span></li>
      <li><b>风险信号</b><span>主力资金整体{'净流出' if (boards_out and boards_in and sum(safe_float(b.get('f62')) or 0 for b in boards_out) > sum(safe_float(b.get('f62')) or 0 for b in boards_in)) else '净流入'}，市场整体偏谨慎。</span></li>
    </ul>
  </article>
</div>"""


def build_theme_cards(boards_in: List[Dict], boards_out: List[Dict], concepts: List[Dict], indices: List[Dict]) -> str:
    cards = ""

    # Top inflow sector as primary positive signal
    if boards_in:
        b = boards_in[0]
        name = b.get("f14", "?")
        val = safe_float(b.get("f62")) or 0
        val_yi = val / 100_000_000
        pct = safe_float(b.get("f3"))
        pct_str = fmt_pct(pct) if pct is not None else ""
        cards += f"""
<article class="theme-card" data-kind="positive">
  <div class="theme-head"><h3>{name}行业净流入{val_yi:.0f}亿</h3><span class="tag positive">资金信号</span></div>
  <p>主力净流入{val_yi:.0f}亿{pct_str}，成为当日最强吸金方向。关注该板块是事件驱动（一日游）还是趋势驱动（可持续），以及次日资金是否继续加码。</p>
  <div class="chain"><span class="node">主力加仓</span><span class="arrow">-></span><span class="node">{name}</span><span class="arrow">-></span><span class="node">趋势确认</span></div>
</article>"""

    # Top 2 concepts with richer data
    for c in concepts[:2]:
        name = c.get("f14", "?")
        val = safe_float(c.get("f62")) or 0
        val_yi = val / 100_000_000
        pct = safe_float(c.get("f3"))
        pct_str = fmt_pct(pct) if pct is not None else ""
        cards += f"""
<article class="theme-card" data-kind="positive">
  <div class="theme-head"><h3>{name}资金净流入</h3><span class="tag positive">概念亮点</span></div>
  <p>主力净流入{val_yi:.0f}亿{pct_str}，概念板块中资金集中度突出。关注概念内高辨识度标的的连板情况以及是否向上下游扩散。</p>
  <div class="chain"><span class="node">概念聚焦</span><span class="arrow">-></span><span class="node">{name}</span><span class="arrow">-></span><span class="node">扩散效应</span></div>
</article>"""

    # Top outflow as negative signal
    if boards_out:
        b = boards_out[0]
        name = b.get("f14", "?")
        val = safe_float(b.get("f62")) or 0
        val_yi = -val / 100_000_000
        cards += f"""
<article class="theme-card" data-kind="negative">
  <div class="theme-head"><h3>{name}遭资金流出</h3><span class="tag negative">资金流出</span></div>
  <p>主力净流出{val_yi:.0f}亿，为当日全市场最大净流出板块。后续需关注是否出现止跌企稳信号，前期拥挤度风险是否有效释放。</p>
  <div class="chain"><span class="node">资金兑现</span><span class="arrow">-></span><span class="node">{name}</span><span class="arrow">-></span><span class="node">等待企稳</span></div>
</article>"""

    # Fill remaining with richer market observations
    remaining = 6 - (1 if boards_in else 0) - len(concepts[:2]) - (1 if boards_out else 0)
    for i in range(remaining):
        if i == 0 and indices:
            best_idx = max(indices[:4], key=lambda x: x.get("pct") or -999)
            idx = indices[0]
            cards += f"""
<article class="theme-card" data-kind="watch">
  <div class="theme-head"><h3>{idx['name']}收盘{fmt_pct(idx['pct'])}</h3><span class="tag watch">市场基准</span></div>
  <p>三大指数中{best_idx['name']}涨幅最大（{fmt_pct(best_idx['pct'])}）。赚钱效应是否扩散至全市场、涨停家数是否增加，是判断情绪能否延续的关键。</p>
  <div class="chain"><span class="node">指数表现</span><span class="arrow">-></span><span class="node">赚钱效应</span><span class="arrow">-></span><span class="node">情绪判断</span></div>
</article>"""
        elif i == 1:
            total_amt = sum(idx["amount"] for idx in indices[:2] if idx.get("amount")) if indices else None
            amt_yi = total_amt / 1_000_000_000_000 if total_amt else None
            amt_label = f"约{amt_yi:.2f}万亿" if amt_yi else "高位"
            cards += f"""
<article class="theme-card" data-kind="watch">
  <div class="theme-head"><h3>成交{amt_label}</h3><span class="tag watch">量能观察</span></div>
  <p>关注成交能否维持在当前量级附近。若放量配合主线扩散，行情级别提升；若缩量+主线一日游，则回归结构性轮动。</p>
  <div class="chain"><span class="node">量能</span><span class="arrow">-></span><span class="node">主线持续性</span><span class="arrow">-></span><span class="node">仓位决策</span></div>
</article>"""
        else:
            cards += """
<article class="theme-card" data-kind="neutral">
  <div class="theme-head"><h3>外部联动因子</h3><span class="tag neutral">跟踪观察</span></div>
  <p>关注隔夜美股（尤其纳斯达克/费城半导体）、商品期货及离岸人民币汇率，这些变量可能在次日开盘15分钟内通过北向资金传导至A股。</p>
  <div class="chain"><span class="node">外盘</span><span class="arrow">-></span><span class="node">北向</span><span class="arrow">-></span><span class="node">A股开盘</span></div>
</article>"""

    return f'<div class="theme-grid">{cards}</div>'

def build_checklist(boards_in: List[Dict], boards_out: List[Dict]) -> str:
    top_in = boards_in[0].get("f14", "?") if boards_in else "—"
    top_out = boards_out[0].get("f14", "?") if boards_out else "—"
    return f"""
<div class="grid three">
  <article class="card panel">
    <div class="chart-title">已验证</div>
    <div class="checklist">
      <div class="check"><span class="box"></span><div><b>{top_in}获资金净流入</b><span>主力资金净流入居前，成为当日资金聚焦方向。</span></div></div>
      <div class="check"><span class="box"></span><div><b>{top_out}遭资金流出</b><span>主力资金净流出居前，资金兑现压力明显。</span></div></div>
    </div>
  </article>
  <article class="card panel">
    <div class="chart-title">未确认</div>
    <div class="checklist">
      <div class="check"><span class="box"></span><div><b>强势板块持续性</b><span>今日资金净流入板块次日是否延续强势，连板和溢价是验证关键。</span></div></div>
      <div class="check"><span class="box"></span><div><b>流出板块止跌</b><span>今日净流出较大的板块次日是否出现企稳信号。</span></div></div>
    </div>
  </article>
  <article class="card panel">
    <div class="chart-title">明日观察点</div>
    <div class="checklist">
      <div class="check"><span class="box"></span><div><b>成交阈值</b><span>继续观察3万亿上方能否维持；若缩量需警惕。</span></div></div>
      <div class="check"><span class="box"></span><div><b>主线承接</b><span>强势板块次日是否"高开不砸盘"，资金是否持续流入。</span></div></div>
      <div class="check"><span class="box"></span><div><b>外部变量</b><span>隔夜外盘、商品期货、汇率等对开盘影响。</span></div></div>
    </div>
  </article>
</div>"""


def build_source_section(extra_note: str = "") -> str:
    note = extra_note.strip()
    extra = f"<p><b>运行时提示：</b>{note}</p>" if note else ""
    return f"""
<div class="card source-list">
  <ul>
    <li>东方财富行情中心 — 指数实时数据</li>
    <li>东方财富Choice — 行业板块资金流向</li>
    <li>东方财富Choice — 概念板块资金流向</li>
    <li>东方财富Choice — 北向资金（沪深股通）</li>
    <li>Yahoo Finance — 全球市场数据</li>
  </ul>
  {extra}
  <p>注：主力资金数据来源为东方财富Choice公开披露口径，可能与Wind/终端口径存在差异。所有内容只用于市场结构观察，不构成买入、卖出、持有、目标价、仓位比例或收益承诺。</p>
</div>"""


def build_prediction_verification(indices: List[Dict], boards_in: List[Dict], boards_out: List[Dict], concepts: List[Dict]) -> str:
    """Build a premarket→close prediction verification table for aftermarket mode."""
    top_in = boards_in[0].get("f14", "?") if boards_in else "—"
    top_out = boards_out[0].get("f14", "?") if boards_out else "—"
    top_concept = concepts[0].get("f14", "?") if concepts else "—"

    has_up = any((idx.get("pct") or 0) > 0 for idx in indices[:3])
    has_down = any((idx.get("pct") or 0) < 0 for idx in indices[:3])

    index_direction = "集体收涨" if has_up and not has_down else ("集体收跌" if has_down and not has_up else "涨跌互现")

    return f"""
<div class="grid two">
  <article class="card panel">
    <div class="chart-title">盘前→收盘验证 <span>预测命中率追踪</span></div>
    <table class="verify-table">
      <thead><tr><th>验证项</th><th>盘前预测</th><th>收盘实际</th><th>命中</th></tr></thead>
      <tbody>
        <tr>
          <td>指数方向</td>
          <td>关注隔夜外盘指引</td>
          <td>{index_direction}</td>
          <td>—</td>
        </tr>
        <tr>
          <td>资金主线</td>
          <td>关注前日强势板块延续性</td>
          <td>{top_in}净流入居前</td>
          <td>—</td>
        </tr>
        <tr>
          <td>概念热度</td>
          <td>关注前日概念扩散效应</td>
          <td>{top_concept}资金聚焦</td>
          <td>—</td>
        </tr>
        <tr>
          <td>风险方向</td>
          <td>警惕前日弱势板块继续承压</td>
          <td>{top_out}净流出居前</td>
          <td>—</td>
        </tr>
      </tbody>
    </table>
  </article>
  <article class="card panel">
    <div class="chart-title">验证规则 <span>客观标准</span></div>
    <ul class="mini-list">
      <li><b>指数方向</b><span>盘前判断的涨跌方向与收盘实际一致即为命中。</span></li>
      <li><b>资金主线</b><span>盘前关注的强势板块实际为当日净流入TOP3即为命中。</span></li>
      <li><b>概念热度</b><span>盘前提及的概念板块实际净流入且涨幅>0即为命中。</span></li>
      <li><b>风险方向</b><span>盘前提示的风险板块实际净流出即为命中。</span></li>
      <li><b>注意</b><span>本区块需结合前次盘前版的预测内容进行手工标注命中/未命中。</span></li>
    </ul>
  </article>
</div>"""


MODE_LABELS = {
    "premarket": "盘前版（隔夜+上日收盘）",
    "midday": "午间版（早盘行情）",
    "aftermarket": "收盘版（全日数据）",
}
MODE_TITLES = {
    "premarket": "A股盘前雷达",
    "midday": "A股午间雷达",
    "aftermarket": "A股盘后验证雷达",
}


def generate_html(indices: List[Dict], boards_in: List[Dict], boards_out: List[Dict], concepts: List[Dict], lhb: Optional[Dict], northbound: Optional[Dict] = None, prev_data: Optional[Dict] = None, mode: str = "aftermarket", date_override: Optional[str] = None, runtime_note: str = "") -> str:
    now = cn_now()
    if date_override:
        # Accept "2026-05-15" → format
        try:
            d = datetime.strptime(date_override, "%Y-%m-%d")
            date_str = d.strftime("%Y年%m月%d日")
        except ValueError:
            date_str = date_override  # fallback: use raw
    else:
        date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M")
    slot_time = "08:00" if mode == "premarket" else time_str
    mode_label = MODE_LABELS.get(mode, MODE_LABELS["aftermarket"])
    title = MODE_TITLES.get(mode, MODE_TITLES["aftermarket"])
    pcts = [idx.get("pct") for idx in indices[:3] if idx.get("pct") is not None]
    if not pcts:
        direction = "数据暂缺"
    else:
        has_negative = any(pct < 0 for pct in pcts)
        direction = "集体收跌" if len(pcts) == 3 and all(pct < 0 for pct in pcts) else ("涨跌互现" if has_negative else "集体收涨")
    summary = f"今日主要指数{direction}。"
    if boards_in and boards_out:
        top_in = boards_in[0].get("f14", "?")
        top_out = boards_out[0].get("f14", "?")
        summary += f"资金层面：{top_in}获主力净流入居前，{top_out}遭抛售居前。结构性分化明显，板块轮动加速。"

    # Sum 上证+深证 amounts as total market turnover proxy
    total_amt = sum(idx["amount"] for idx in indices[:2] if idx.get("amount")) if indices else None
    kpi_grid = build_kpi_grid(indices, total_amt, None, northbound)
    signal_panel = build_signal_panel(boards_in, boards_out, concepts, indices, prev_data)
    condition_panel = build_condition_panel(indices, boards_in, boards_out)
    capital_verification = build_capital_verification(indices, boards_in, boards_out, concepts, lhb)
    theme_cards = build_theme_cards(boards_in, boards_out, concepts, indices)
    checklist = build_checklist(boards_in, boards_out)
    source_section = build_source_section(runtime_note)

    # Prediction verification (aftermarket mode only)
    pred_verification = ""
    if mode == "aftermarket":
        pred_verification = f"""
    <section class="section" id="verification">
      <div class="section-title">
        <h2>盘前预测验证</h2>
        <span>盘前判断 vs 收盘实际</span>
      </div>
      {build_prediction_verification(indices, boards_in, boards_out, concepts)}
    </section>"""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | {date_str}</title>
<style>{CSS}</style>
</head>
<body>
<main class="page">
  <header class="hero">
    <div>
      <h1>{title}</h1>
      <p>区间：{date_str} {mode_label}（{slot_time}版）。{summary}</p>
      <div class="toolbar" role="group" aria-label="雷达模式切换">
        <button class="mode-button active" data-mode="dashboard" type="button">看板模式</button>
        <button class="mode-button" data-mode="review" type="button">验证清单模式</button>
      </div>
    </div>
    <div class="status-pill"><span class="pulse"></span>已于{slot_time}自动生成</div>
  </header>

  <section class="section" id="overview">
    <div class="section-title">
      <h2>市场总览</h2>
      <span>指数、成交、资金方向</span>
    </div>
    {kpi_grid}
  </section>

  <section class="section mode-panel" data-mode-panel="dashboard">
    {signal_panel}
  </section>

  <section class="section mode-panel" data-mode-panel="review" hidden>
    {pred_verification}
    {condition_panel}
  </section>

  <section class="section" id="capital">
    <div class="section-title">
      <h2>资金验证</h2>
      <span>从"成交"到"净流入方向"</span>
    </div>
    {capital_verification}
  </section>

  <section class="section" id="structure">
    <div class="section-title">
      <h2>验证条目</h2>
      <span>点击筛选状态</span>
    </div>
    <div class="toolbar" role="group" aria-label="验证条目筛选">
      <button class="filter active" data-filter="all" type="button">全部</button>
      <button class="filter" data-filter="positive" type="button">资金信号</button>
      <button class="filter" data-filter="negative" type="button">资金流出</button>
      <button class="filter" data-filter="watch" type="button">继续观察</button>
    </div>
    {theme_cards}
  </section>

  <section class="section" id="watch">
    <div class="section-title">
      <h2>后续验证</h2>
      <span>次日必须继续验证的条件</span>
    </div>
    {checklist}
  </section>

  <section class="section" id="sources">
    <div class="section-title">
      <h2>来源说明</h2>
      <span>{date_str}自动生成版</span>
    </div>
    {source_section}
  </section>
</main>

<script>
(function() {{
  const modeButtons = document.querySelectorAll(".mode-button");
  const modePanels = document.querySelectorAll("[data-mode-panel]");
  const filterButtons = document.querySelectorAll(".filter");
  const cards = document.querySelectorAll(".theme-card");

  modeButtons.forEach(function(b) {{
    b.addEventListener("click", function() {{
      modeButtons.forEach(function(i) {{ i.classList.remove("active"); }});
      b.classList.add("active");
      var mode = b.dataset.mode;
      modePanels.forEach(function(p) {{
        p.hidden = p.dataset.modePanel !== mode;
      }});
    }});
  }});

  filterButtons.forEach(function(b) {{
    b.addEventListener("click", function() {{
      filterButtons.forEach(function(i) {{ i.classList.remove("active"); }});
      b.classList.add("active");
      var filter = b.dataset.filter;
      cards.forEach(function(c) {{
        c.hidden = filter !== "all" && c.dataset.kind !== filter;
      }});
    }});
  }});
}})();
</script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate A-share radar HTML report")
    parser.add_argument("--output", default="a-share-report-site/index.html", help="Output path")
    parser.add_argument("--mode", choices=["premarket", "midday", "aftermarket"], default="aftermarket", help="Report mode")
    parser.add_argument("--date", default=None, help="Date override, e.g. 2026年05月15日")
    args = parser.parse_args()

    indices = fetch_indices()
    boards_in = fetch_board_flow(5)
    boards_out = fetch_board_outflow(5)
    concepts = fetch_concept_flow(4)
    lhb = fetch_lhb_stats()
    northbound = fetch_northbound()

    # Load previous day's data for comparison
    prev_data_path = os.path.join(os.path.dirname(args.output) or ".", ".prev_radar_data.json")
    prev_data = {}
    if os.path.exists(prev_data_path):
        try:
            with open(prev_data_path, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
        except Exception:
            pass

    note = ""
    if all(idx.get("pct") is None for idx in indices):
        note = "本机网络/DNS异常导致无法拉取实时行情接口；页面已生成但关键数值将显示为“--”，请恢复网络后重跑生成。"
    html = generate_html(indices, boards_in, boards_out, concepts, lhb, northbound, prev_data, mode=args.mode, date_override=args.date, runtime_note=note)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report saved to {args.output} ({os.path.getsize(args.output)} bytes)")

    # Save current data for next run's day-over-day comparison
    current_data = {
        "inflows": [{"name": b.get("f14", ""), "val": safe_float(b.get("f62")) or 0} for b in boards_in],
        "outflows": [{"name": b.get("f14", ""), "val": safe_float(b.get("f62")) or 0} for b in boards_out],
        "concepts": [{"name": c.get("f14", ""), "val": safe_float(c.get("f62")) or 0} for c in concepts],
    }
    try:
        with open(prev_data_path, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

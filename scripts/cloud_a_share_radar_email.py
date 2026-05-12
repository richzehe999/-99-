#!/usr/bin/env python3
"""A股雷达邮件 — 板块资金流向报告"""
import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from html import escape
from typing import Any, Dict, Iterable, List, Optional, Tuple

CN_TZ = timezone(timedelta(hours=8))
DEFAULT_RECIPIENT = "240575148@qq.com"
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_SMTP_PORTS = (465, 587)
BLOCKED_EMAIL_MARKERS = ("<script", "<!doctype")

# ── 数据结构 ──────────────────────────────────────────────

@dataclass
class Quote:
    name: str
    code: str
    price: Optional[float]
    pct: Optional[float]
    amount: Optional[float]

@dataclass
class SectorFlow:
    name: str
    net_inflow: Optional[float]   # 主力净流入（元）
    pct: Optional[float]          # 板块涨跌幅

@dataclass
class ConceptHot:
    name: str
    pct: Optional[float]
    inflow: Optional[float]       # 主力净流入
    driver: str                   # 核心驱动力

# ── 常量 ──────────────────────────────────────────────────

INDEX_SECIDS = {
    "上证指数": "1.000001", "深证成指": "0.399001",
    "创业板指": "0.399006", "科创50": "1.000688",
    "沪深300": "1.000300", "上证50": "1.000016",
    "中证500": "1.000905", "中证1000": "1.000852",
    "北证50": "0.899050",
}

GLOBAL_SYMBOLS = {
    "纳斯达克": "%5EIXIC", "标普500": "%5EGSPC", "道指": "%5EDJI",
    "WTI原油": "CL=F", "黄金": "GC=F", "铜": "HG=F",
    "美元/离岸人民币": "CNH=X",
}

# 概念板块 secid 映射（东方财富 BK 代码）
CONCEPT_IDS: Dict[str, str] = {}  # 动态获取

# ── 工具函数 ──────────────────────────────────────────────

def cn_now() -> datetime:
    return datetime.now(CN_TZ)

def fetch_json(url: str, timeout: int = 25) -> Dict[str, Any]:
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

def safe_float(v: Any) -> Optional[float]:
    try:
        if v in (None, "-", ""):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None

def fmt_num(v: Optional[float], digits: int = 2) -> str:
    if v is None:
        return "-"
    return f"{v:.{digits}f}"

def fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "-"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"

def fmt_amount(v: Optional[float]) -> str:
    """将元的数值转为亿/万亿显示"""
    if v is None:
        return "-"
    yi = v / 100_000_000
    if abs(yi) >= 10_000:
        return f"{yi / 10_000:.2f}万亿"
    return f"{yi:.0f}亿"

def pct_color(v: Optional[float]) -> str:
    if v is None:
        return "#657180"
    return "#178a5a" if v > 0 else "#c64a45" if v < 0 else "#657180"

def direction_icon(v: Optional[float]) -> str:
    if v is None:
        return "―"
    return "▲" if v > 0 else "▼" if v < 0 else "―"

def css_color(v: Optional[float]) -> str:
    """返回 'up' | 'down' | 'flat'"""
    if v is None:
        return "flat"
    return "up" if v > 0 else "down" if v < 0 else "flat"

# ── 数据获取 ──────────────────────────────────────────────

def fetch_a_share_indices() -> List[Quote]:
    secids = ",".join(INDEX_SECIDS.values())
    fields = "f12,f14,f2,f3,f6"
    url = (
        "https://push2.eastmoney.com/api/qt/ulist.np/get?"
        + urllib.parse.urlencode({"secids": secids, "fields": fields, "fltt": "2"})
    )
    data = fetch_json(url)
    items = data.get("data", {}).get("diff") or []
    by_name = {i.get("f14"): i for i in items}
    by_code = {i.get("f12"): i for i in items}
    out: List[Quote] = []
    for name, secid in INDEX_SECIDS.items():
        code = secid.split(".", 1)[1]
        item = by_name.get(name) or by_code.get(code) or {}
        out.append(Quote(
            name=name, code=code,
            price=safe_float(item.get("f2")),
            pct=safe_float(item.get("f3")),
            amount=safe_float(item.get("f6")),
        ))
    return out

def fetch_board_flow() -> Tuple[List[SectorFlow], List[SectorFlow]]:
    """获取行业板块资金流入/流出各 TOP 8"""
    params = {
        "pn": "1", "pz": "15", "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2",
        "fields": "f12,f14,f62,f184,f3",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
    try:
        data = fetch_json(url)
    except Exception:
        return [], []
    items = data.get("data", {}).get("diff") or []
    all_flows: List[SectorFlow] = []
    for item in items:
        inflow = safe_float(item.get("f62"))
        all_flows.append(SectorFlow(
            name=str(item.get("f14", "")),
            net_inflow=inflow,
            pct=safe_float(item.get("f3")),
        ))
    # 按净流入排序
    all_flows.sort(key=lambda x: x.net_inflow or 0, reverse=True)
    inflows = [f for f in all_flows if (f.net_inflow or 0) > 0][:8]
    outflows = [f for f in all_flows if (f.net_inflow or 0) < 0][-8:]
    outflows.reverse()
    return inflows, outflows

def fetch_concept_hot() -> List[ConceptHot]:
    """获取概念板块热点 TOP 5（按主力净流入排序）"""
    params = {
        "pn": "1", "pz": "6", "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:3",
        "fields": "f12,f14,f62,f184,f3",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
    try:
        data = fetch_json(url)
    except Exception:
        return []
    items = data.get("data", {}).get("diff") or []
    out: List[ConceptHot] = []
    # 驱动力映射（静态关键词匹配）
    driver_map = {
        "半导体": "国产替代 + 存储超级周期 + 大基金",
        "芯片": "国产替代 + 存储超级周期 + 大基金",
        "光通信": "AI算力基建 + 800G光模块订单",
        "人工智能": "AI应用落地 + 算力需求爆发",
        "算力": "AI算力基建 + 科创再贷款1.2万亿",
        "低空经济": "政策密集催化 + 产业落地加速",
        "商业航天": "朱雀三号发射预期 + 国家航天局政策",
        "新能源": "锂电供需反转 + 储能需求爆发",
        "储能": "电池排产创新高 + 政策支持",
        "创新药": "集采边际缓和 + 创新药出海",
        "军工": "国防预算增长 + 订单恢复",
        "消费电子": "AI手机/PC换机周期",
        "传媒": "AI应用 + 短剧出海",
        "金融科技": "数字人民币 + 券商IT投入",
        "机器人": "人形机器人产业化加速",
        "高股息": "利率下行 + 防御资金配置",
        "有色金属": "全球库存回补 + 涨价周期",
        "中特估": "央国企改革 + 市值管理纳入考核",
        "数据要素": "数据资产入表政策落地",
        "无人驾驶": "L3商业化加速 + 特斯拉FSD入华",
    }
    for item in items[:5]:
        name = str(item.get("f14", ""))
        inflow = safe_float(item.get("f62"))
        pct_v = safe_float(item.get("f3"))
        # 匹配驱动力
        driver = "热点资金驱动"
        for kw, desc in driver_map.items():
            if kw in name:
                driver = desc
                break
        out.append(ConceptHot(name=name, pct=pct_v, inflow=inflow, driver=driver))
    return out

def fetch_global_quotes() -> List[Quote]:
    symbols = ",".join(GLOBAL_SYMBOLS.values())
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}"
    try:
        data = fetch_json(url)
    except Exception:
        return []
    results = data.get("quoteResponse", {}).get("result") or []
    by_sym = {i.get("symbol"): i for i in results}
    out: List[Quote] = []
    for name, symbol in GLOBAL_SYMBOLS.items():
        raw = urllib.parse.unquote(symbol)
        item = by_sym.get(raw) or by_sym.get(symbol) or {}
        out.append(Quote(
            name=name, code=raw,
            price=safe_float(item.get("regularMarketPrice")),
            pct=safe_float(item.get("regularMarketChangePercent")),
            amount=None,
        ))
    return out

# ── HTML 构建 ──────────────────────────────────────────────

def style_tag() -> str:
    return """
<style>
  .rpt a{color:#2b6cb5}
  .rpt table{border-collapse:collapse;width:100%}
  .rpt td,.rpt th{padding:10px 8px;text-align:left;border-bottom:1px solid #edf1f5;font-size:14px}
  .rpt th{color:#657180;font-size:12px;font-weight:700;border-bottom:1px solid #d9e0e7}
  .up{color:#178a5a}
  .down{color:#c64a45}
  .flat{color:#657180}
  .kpi-box{min-height:112px;padding:14px;border:1px solid #d9e0e7;border-radius:8px;background:#fff}
  .card{min-height:130px;padding:15px;border:1px solid #d9e0e7;border-radius:8px;background:#fbfcfd}
  .section-box{padding:18px;border:1px solid #d9e0e7;border-radius:8px;background:#fff}
  .tag{display:inline-block;border-radius:999px;padding:4px 8px;font-size:12px;font-weight:800;margin-bottom:8px}
  .tag-blue{background:#eaf1ff;color:#36516e}
  .tag-green{background:#eaf7f1;color:#0f6842}
  .tag-orange{background:#fff6e5;color:#865a13}
  .driver{color:#657180;font-size:13px;margin-top:4px;line-height:1.4}
  .bar-wrap{display:flex;align-items:center;gap:6px}
  .bar-bg{flex:1;height:14px;background:#edf1f5;border-radius:7px;overflow:hidden}
  .bar-fill{height:100%;border-radius:7px}
</style>
"""

def html_table(headers: Iterable[str], rows: Iterable[Iterable[str]],
               header_attrs: str = "") -> str:
    hdr = "".join(
        f"<th{header_attrs}>{escape(h)}</th>" for h in headers
    )
    body = "".join(
        f"<tr>{''.join(f'<td>{c}</td>' for c in row)}</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table>"

def build_flow_section(inflows: List[SectorFlow], outflows: List[SectorFlow]) -> str:
    rows: List[str] = []
    # 流入
    for f in inflows[:6]:
        pct_s = f'<span class="{css_color(f.pct)}">{fmt_pct(f.pct)}</span>'
        rows.append(f"""
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #edf1f5">
          <span style="flex:1"><b>{escape(f.name)}</b> {pct_s}</span>
          <span style="flex:0 0 120px;text-align:right">
            <span class="up">{direction_icon(f.net_inflow)}</span> {escape(fmt_amount(f.net_inflow))}
          </span>
        </div>""")
    sep = '<div style="margin:12px 0;border-top:2px dashed #d9e0e7;position:relative;text-align:center">'
    sep += '<span style="background:#fff;padding:0 8px;color:#657180;font-size:12px;position:relative;top:-10px">净流出</span></div>'
    rows.append(sep)
    for f in outflows[:6]:
        pct_s = f'<span class="{css_color(f.pct)}">{fmt_pct(f.pct)}</span>'
        rows.append(f"""
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #edf1f5">
          <span style="flex:1"><b>{escape(f.name)}</b> {pct_s}</span>
          <span style="flex:0 0 120px;text-align:right">
            <span class="down">{direction_icon(f.net_inflow)}</span> {escape(fmt_amount(abs(f.net_inflow or 0)))}
          </span>
        </div>""")
    return "".join(rows)

def build_concept_section(concepts: List[ConceptHot]) -> str:
    if not concepts:
        return '<p style="color:#657180">概念板块数据暂不可用</p>'
    rows: List[str] = []
    for i, c in enumerate(concepts):
        rank = ["🥇", "🥈", "🥉", "4", "5"][i]
        pct_cls = css_color(c.pct)
        inflow_cls = css_color(c.inflow)
        bar_pct = min(abs(c.inflow or 0) / (abs(concepts[0].inflow or 1) or 1) * 100, 100)
        bar_color = "#178a5a" if (c.inflow or 0) > 0 else "#c64a45"
        rows.append(f"""
        <div style="padding:12px 0;border-bottom:1px solid #edf1f5">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
            <span style="font-size:16px">{rank}</span>
            <b style="flex:1;font-size:15px">{escape(c.name)}</b>
            <span style="font-size:14px;font-weight:700" class="{pct_cls}">{fmt_pct(c.pct)}</span>
            <span style="font-size:13px;font-weight:600" class="{inflow_cls}">{fmt_amount(c.inflow)}</span>
          </div>
          <div class="bar-wrap" style="padding-left:30px">
            <div class="bar-bg"><div class="bar-fill" style="width:{bar_pct:.0f}%;background:{bar_color}"></div></div>
          </div>
          <div class="driver">💡 {escape(c.driver)}</div>
        </div>""")
    return "".join(rows)

def build_html(mode: str, indices: List[Quote],
               inflows: List[SectorFlow], outflows: List[SectorFlow],
               concepts: List[ConceptHot],
               global_quotes: List[Quote],
               errors: List[str]) -> str:
    now = cn_now()
    report_date = now.strftime("%Y-%m-%d")
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    mode_name = "盘前分析" if mode == "premarket" else "盘后验证"
    status_txt = "盘前最新数据 — 隔夜外盘已更新" if mode == "premarket" else "盘后收盘数据 — 当日行情已确认"

    # ── KPI ──
    core = indices[:5]
    kpi_cells = "".join(
        f'<td style="width:20%;padding:6px;vertical-align:top;">'
        f'<div class="kpi-box">'
        f'<div style="font-size:12px;color:#657180;margin-bottom:6px">{escape(q.name)}</div>'
        f'<div class="{css_color(q.pct)}" style="font-size:26px;font-weight:800;line-height:1.1">{fmt_num(q.price)}</div>'
        f'<div style="font-size:13px;font-weight:700;margin-top:7px"><span class="{css_color(q.pct)}">{fmt_pct(q.pct)}</span>'
        f'{" ｜ 成交 " + fmt_amount(q.amount) if q.amount is not None else ""}</div>'
        f'</div></td>' for q in core
    )
    while len(core) < 5:
        kpi_cells += '<td style="width:20%;padding:6px"></td>'

    # ── 核心指数表格 ──
    index_rows = [[
        escape(q.name), fmt_num(q.price),
        f'<span class="{css_color(q.pct)}" style="font-weight:700">{fmt_pct(q.pct)}</span>',
        fmt_amount(q.amount),
    ] for q in indices]

    # ── 全球 ──
    global_rows = [[
        escape(q.name), fmt_num(q.price),
        f'<span class="{css_color(q.pct)}" style="font-weight:700">{fmt_pct(q.pct)}</span>',
    ] for q in global_quotes] or [["数据待确认"] * 3]

    # ── 板块资金 ──
    flow_html = build_flow_section(inflows, outflows)

    # ── 概念热点 ──
    concept_html = build_concept_section(concepts)

    # ── 观察清单 ──
    if mode == "premarket":
        checklist = [
            ["外盘传导", "隔夜美股/商品走势映射到A股板块", "外盘反转向下则降级"],
            ["开盘15分钟", "观察CPO、半导体、红利谁主动放量", "高开低走且成交不足"],
            ["主线确认", "核心板块继续放量、补涨跟随后", "冲高回落且量能萎缩"],
            ["风格切换", "红利/能源/消费主动走强", "仍弱于科技成长"],
        ]
    else:
        checklist = [
            ["主线验证", "当日指数、板块资金确认主线延续", "冲高回落且放量滞涨"],
            ["资金扩散", "资金从核心板块向外扩散", "仅核心板块独涨、无跟随后"],
            ["外部变量", "商品/地缘变化映射到A股板块成交", "只有新闻无资金确认"],
            ["明日承接", "核心板块尾盘承接强劲", "尾盘跳水且北向流出"],
        ]

    # ── 市场情绪 ──
    # 简单情绪判断：看涨跌数量和沪深300流入
    up_count = sum(1 for q in indices if (q.pct or 0) > 0)
    total = len(indices) or 1
    sentiment_pct = up_count / total * 100
    if sentiment_pct >= 70:
        sentiment_text = "偏乐观 😊"
        sentiment_color = "#178a5a"
    elif sentiment_pct >= 40:
        sentiment_text = "中性 😐"
        sentiment_color = "#e6a23c"
    else:
        sentiment_text = "偏谨慎 😟"
        sentiment_color = "#c64a45"

    # ── 组装 ──
    error_html = ""
    if errors:
        error_html = (
            '<div style="margin-top:12px;padding:14px;border:1px solid #fff6e5;'
            'background:#fffaf0;color:#865a13;border-radius:8px;font-size:13px">'
            + escape("；".join(errors)) + "</div>"
        )

    return f"""<html><head><meta charset="utf-8">{style_tag()}</head><body>
<div class="rpt" style="margin:0;background:#f7f8f9;color:#17202a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',Arial,sans-serif;line-height:1.5">
  <div style="max-width:1180px;margin:0 auto;background:#fff">

    <!-- 顶部横幅 -->
    <table><tr>
      <td style="width:220px;background:#1d2733;color:#eef4f8;padding:28px 20px;vertical-align:top">
        <div style="font-size:18px;font-weight:800">A股板块雷达</div>
        <div style="color:#9eb0c0;font-size:13px;margin-top:4px">{escape(report_date)} {escape(weekday_cn)}</div>
        <div style="margin-top:34px;display:grid;gap:14px;font-weight:700;color:#dbe7ee;font-size:15px">
          <div>{escape(mode_name)}</div>
          <div>核心指数</div><div>板块资金</div><div>热点概念</div><div>外部变量</div><div>后续验证</div>
        </div>
        <div style="margin-top:28px;padding:12px;border:1px solid rgba(255,255,255,.14);border-radius:8px;font-size:13px;color:#b7c6d1">
          {escape(report_date)} — {escape(weekday_cn)}<br>
          {escape(status_txt)}
        </div>
        <div style="margin-top:16px;padding:12px;border:1px solid rgba(255,255,255,.14);border-radius:8px;font-size:13px;color:#b7c6d1;background:rgba(255,255,255,.04)">
          <div>市场情绪: <span style="color:{sentiment_color};font-weight:700">{sentiment_text}</span></div>
          <div style="font-size:11px;margin-top:4px;color:#9eb0c0">基于核心指数涨跌分布</div>
        </div>
      </td>
      <td style="padding:34px 34px 42px;vertical-align:top">
        <div style="display:flex;justify-content:space-between;gap:24px;align-items:flex-start">
          <div>
            <h1 style="margin:0 0 10px;font-size:38px;line-height:1.08">{escape(mode_name)}报告</h1>
            <p style="margin:0 0 10px;font-size:15px;color:#2d3642;max-width:720px">
              {"隔夜外盘和商品数据已更新，A股盘前关注主线映射和集合竞价验证" if mode == "premarket"
               else "当日行情已收盘，验证主线延续性、资金扩散和板块轮动结构"}
            </p>
            <p style="margin:0;color:#657180;font-size:13px">
              报告日期：{escape(report_date)}｜数据源：东方财富行情接口、Yahoo Finance
            </p>
          </div>
          <div style="white-space:nowrap;border:1px solid #cbd6e1;border-radius:999px;padding:9px 14px;background:#fff;font-size:13px;color:#2d3642">{escape(status_txt)}</div>
        </div>

        {error_html}

        <!-- KPI 卡片 -->
        <table style="width:100%;margin-top:28px"><tr>{kpi_cells}</tr></table>

        <!-- 核心内容：双栏 -->
        <table style="width:100%;margin-top:22px">
          <tr>
            <!-- 左栏：核心结论 + 热点概念 -->
            <td style="width:50%;padding:8px;vertical-align:top">
              <div class="section-box">
                <div style="font-size:20px;font-weight:700;margin-bottom:12px">📋 核心结论</div>
                <div style="font-size:13px;color:#657180;margin-bottom:12px">
                  {"盘前：隔夜变量 → 板块映射 → 开盘验证" if mode == "premarket"
                   else "盘后：当日主线 → 资金结构 → 明日预案"}
                </div>
                <div style="padding:10px 0;border-bottom:1px solid #edf1f5">
                  <b>指数强弱</b>
                  <div style="color:#657180;font-size:13px;margin-top:4px">
                    {escape("市场涨跌分化、结构行情为主" if sentiment_pct < 70 else "指数普涨、强势格局")}
                  </div>
                </div>
                <div style="padding:10px 0;border-bottom:1px solid #edf1f5">
                  <b>资金结构</b>
                  <div style="color:#657180;font-size:13px;margin-top:4px">
                    {"净流入" + str(len(inflows)) + "个板块 / 净流出" + str(len(outflows)) + "个板块"}
                  </div>
                </div>
                <div style="padding:10px 0">
                  <b>风格倾向</b>
                  <div style="color:#657180;font-size:13px;margin-top:4px">
                    {escape("关注外部变量传导和开盘确认" if mode == "premarket" else "科技成长 vs 防御风格切换观察")}
                  </div>
                </div>
              </div>

              <!-- 热点概念板块 -->
              <div class="section-box" style="margin-top:16px">
                <div style="font-size:20px;font-weight:700;margin-bottom:12px">🔥 热点概念板块</div>
                {concept_html}
              </div>
            </td>

            <!-- 右栏：外部变量 -->
            <td style="width:50%;padding:8px;vertical-align:top">
              <div class="section-box">
                <div style="font-size:20px;font-weight:700;margin-bottom:12px">🌍 隔夜 / 外部变量</div>
                {html_table(["变量", "最新值", "涨跌幅"], global_rows)}
              </div>
            </td>
          </tr>
        </table>

        <!-- 传导链卡片 -->
        <div style="margin-top:22px;padding:18px;border:1px solid #d9e0e7;border-radius:8px">
          <div style="font-size:20px;font-weight:700;margin-bottom:12px">🔗 传导链 & 操作指引</div>
          <table style="width:100%"><tr>
            <td style="width:33.33%;padding:6px;vertical-align:top">
              <div class="card">
                <span class="tag tag-blue">{'开盘确认' if mode == 'premarket' else '主线验证'}</span>
                <div style="font-size:15px;font-weight:600;margin-bottom:6px">{'集合竞价 + 开盘15分钟' if mode == 'premarket' else '核心板块 vs 补涨分支'}</div>
                <div style="font-size:13px;color:#657180;line-height:1.4">
                  {'关注成交量环比和龙头股方向' if mode == 'premarket' else '验证当日主线延续性和资金扩散'}
                </div>
              </div>
            </td>
            <td style="width:33.33%;padding:6px;vertical-align:top">
              <div class="card">
                <span class="tag tag-green">{'板块映射' if mode == 'premarket' else '资金结构'}</span>
                <div style="font-size:15px;font-weight:600;margin-bottom:6px">{'外部变量→A股映射' if mode == 'premarket' else '行业 vs 概念资金对比'}</div>
                <div style="font-size:13px;color:#657180;line-height:1.4">
                  {'每个外部变量必须落到A股板块和成交确认' if mode == 'premarket' else '判断资金是扩散还是收敛'}
                </div>
              </div>
            </td>
            <td style="width:33.33%;padding:6px;vertical-align:top">
              <div class="card">
                <span class="tag tag-orange">{'风险控制' if mode == 'premarket' else '明日观察'}</span>
                <div style="font-size:15px;font-weight:600;margin-bottom:6px">{'高开低走 / 无量上涨' if mode == 'premarket' else '主线承接 / 风格切换'}</div>
                <div style="font-size:13px;color:#657180;line-height:1.4">
                  {'盘前预案若未被开盘验证，及时降级' if mode == 'premarket' else '保留已验证方向，放弃未确认题材'}
                </div>
              </div>
            </td>
          </tr></table>
        </div>

        <!-- 板块资金流动 -->
        <table style="width:100%;margin-top:22px">
          <tr>
            <td style="width:50%;padding:8px;vertical-align:top">
              <div class="section-box">
                <div style="font-size:20px;font-weight:700;margin-bottom:12px">💰 板块资金流向</div>
                <div style="font-size:13px;color:#657180;margin-bottom:8px">主力净流入流出 TOP 6（行业板块）</div>
                {flow_html}
              </div>
            </td>
            <td style="width:50%;padding:8px;vertical-align:top">
              <div class="section-box">
                <div style="font-size:20px;font-weight:700;margin-bottom:12px">📊 核心指数表现</div>
                {html_table(["指数", "点位", "涨跌幅", "成交额"], index_rows)}
              </div>

              <!-- 观察清单 -->
              <div class="section-box" style="margin-top:16px">
                <div style="font-size:20px;font-weight:700;margin-bottom:12px">📌 观察清单</div>
                {html_table(["观察项", "确认条件", "降级条件"], checklist)}
              </div>
            </td>
          </tr>
        </table>

        <p style="margin:28px 0 0;color:#657180;font-size:12px;text-align:center">
          本报告基于公开行情数据生成，仅供参考，不构成投资建议。<br>
          数据源：东方财富行情接口、Yahoo Finance 公开行情
        </p>
      </td>
    </tr></table>
  </div>
</div></body></html>"""

# ── 纯文本降级 ──────────────────────────────────────────────

def build_plain_fallback(mode: str) -> str:
    return f"A股雷达报告 {cn_now().strftime('%Y-%m-%d %H:%M')}\n\n（HTML 正文生成失败，模式：{mode}。请检查云端日志。）"

# ── 邮箱发送 ──────────────────────────────────────────────

def validate_email_html(html_body: str) -> None:
    lowered = html_body.lower()
    blocked = [m for m in BLOCKED_EMAIL_MARKERS if m in lowered]
    if blocked:
        raise SystemExit(f"Email HTML contains blocked webpage markup: {', '.join(blocked)}")

def parse_smtp_ports() -> List[int]:
    raw = os.environ.get("SMTP_PORTS")
    if raw:
        return [int(i.strip()) for i in raw.split(",") if i.strip()]
    if os.environ.get("SMTP_PORT"):
        return [int(os.environ["SMTP_PORT"])]
    return list(DEFAULT_SMTP_PORTS)

def smtp_login_and_send(host: str, port: int, sender: str, password: str,
                        message: EmailMessage, context: ssl.SSLContext) -> None:
    server = smtplib.SMTP_SSL(host, port, context=context, timeout=30) if port == 465 \
        else smtplib.SMTP(host, port, timeout=30)
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
    sender = (os.environ.get("SMTP_USER") or os.environ.get("GMAIL_SMTP_USER")
              or os.environ.get("QQ_SMTP_USER"))
    password = (os.environ.get("SMTP_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD")
                or os.environ.get("QQ_SMTP_AUTH_CODE"))
    recipient = os.environ.get("A_SHARE_REPORT_TO", DEFAULT_RECIPIENT)
    host = os.environ.get("SMTP_HOST") or DEFAULT_SMTP_HOST
    ports = parse_smtp_ports()

    missing = [n for n, v in [("SMTP_USER", sender), ("SMTP_PASSWORD", password)] if not v]
    if missing:
        raise SystemExit(f"Missing required env: {', '.join(missing)}")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype="html")

    ctx = ssl.create_default_context()
    errors: List[str] = []
    for port in ports:
        try:
            smtp_login_and_send(host, port, sender, password, msg, ctx)
            return
        except smtplib.SMTPAuthenticationError as exc:
            errors.append(f"{port}: auth failed {exc.smtp_code}")
        except (smtplib.SMTPException, OSError) as exc:
            errors.append(f"{port}: {exc}")
    raise SystemExit(f"SMTP fail — tried {ports}: {' | '.join(errors)}")

# ── 主入口 ──────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A股雷达邮件生成与发送")
    p.add_argument("--mode", choices=["premarket", "aftermarket"], required=True)
    p.add_argument("--output-html", help="保存HTML到本地路径")
    p.add_argument("--send", action="store_true", help="发送邮件")
    return p.parse_args()

def main() -> None:
    args = parse_args()
    mode_name = "盘前分析" if args.mode == "premarket" else "盘后验证"
    report_date = cn_now().strftime("%Y-%m-%d")

    errors: List[str] = []

    # 获取数据
    try:
        indices = fetch_a_share_indices()
    except Exception as exc:
        errors.append(f"A股指数: {exc}")
        indices = [Quote(name=n, code=s.split(".", 1)[1], price=None, pct=None, amount=None)
                   for n, s in INDEX_SECIDS.items()]

    try:
        inflows, outflows = fetch_board_flow()
    except Exception as exc:
        errors.append(f"板块资金: {exc}")
        inflows, outflows = [], []

    try:
        concepts = fetch_concept_hot()
    except Exception as exc:
        errors.append(f"概念热点: {exc}")
        concepts = []

    global_quotes = fetch_global_quotes()

    # 生成 HTML
    html_body = build_html(args.mode, indices, inflows, outflows, concepts, global_quotes, errors)
    validate_email_html(html_body)

    if args.output_html:
        with open(args.output_html, "w", encoding="utf-8") as f:
            f.write(html_body)

    if args.send:
        subject = f"A股{mode_name}报告 {report_date}"
        send_email(subject, html_body, build_plain_fallback(args.mode))
        print(f"✅ sent: {subject}")
    else:
        print(f"✅ generated: {mode_name} {report_date}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

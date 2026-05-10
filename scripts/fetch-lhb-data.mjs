#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const dataDir = path.join(rootDir, "data");
const htmlPath = path.join(rootDir, "a-share-lhb-dashboard.html");

const args = process.argv.slice(2);
const applyJsonPath = args[0] === "--apply-json" ? args[1] : "";
const tradeDate = applyJsonPath ? "" : args[0] || localDate();
const apiHost = "datacenter-web.eastmoney.com";
const apiPath = "/api/data/v1/get";
const pushHost = "push2.eastmoney.com";
const pushHisHost = "push2his.eastmoney.com";
const pushUt = "b2884a393a59ad64002292a3e90d46a5";
const marketFs = "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2";

const summaryColumns = [
  "SECURITY_CODE",
  "SECUCODE",
  "SECURITY_NAME_ABBR",
  "TRADE_DATE",
  "EXPLAIN",
  "CLOSE_PRICE",
  "CHANGE_RATE",
  "BILLBOARD_NET_AMT",
  "BILLBOARD_BUY_AMT",
  "BILLBOARD_SELL_AMT",
  "BILLBOARD_DEAL_AMT",
  "ACCUM_AMOUNT",
  "DEAL_NET_RATIO",
  "DEAL_AMOUNT_RATIO",
  "TURNOVERRATE",
  "FREE_MARKET_CAP",
  "EXPLANATION",
  "SECURITY_TYPE_CODE"
].join(",");

async function main() {
  await fs.mkdir(dataDir, { recursive: true });

  if (applyJsonPath) {
    const jsonPath = path.resolve(rootDir, applyJsonPath);
    const data = JSON.parse(await fs.readFile(jsonPath, "utf8"));
    if (!Array.isArray(data.marketFlowEntries) || data.marketFlowEntries.length === 0) {
      data.marketFlowEntries = buildMarketFlowFallback(data.fullRankEntries || []);
      data.marketFlowCount = data.marketFlowEntries.length;
      await fs.writeFile(jsonPath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
    }
    await patchHtml(data);
    process.stdout.write(`已从 ${jsonPath} 回写看板。\n`);
    return;
  }

  const summaryRows = await fetchPaged({
    reportName: "RPT_DAILYBILLBOARD_DETAILSNEW",
    columns: summaryColumns,
    sortColumns: "SECURITY_CODE,TRADE_DATE",
    sortTypes: "1,-1",
    filter: `(TRADE_DATE<='${tradeDate}')(TRADE_DATE>='${tradeDate}')`,
    pageSize: "500"
  });

  if (!summaryRows.length) {
    const hint = isWeekendDate(tradeDate)
      ? "该日期是周末，A股没有龙虎榜数据；请改用最近一个交易日。"
      : "可能是非交易日、数据尚未发布，或接口临时返回空。";
    throw new Error(`未获取到 ${tradeDate} 龙虎榜汇总数据。${hint}`);
  }

  const uniqueStocks = dedupeStocks(summaryRows);
  const details = [];
  for (const [index, stock] of uniqueStocks.entries()) {
    process.stdout.write(`抓取逐席位 ${index + 1}/${uniqueStocks.length} ${stock.SECURITY_CODE} ${stock.SECURITY_NAME_ABBR}\n`);
    const buyRows = await fetchSeatRows(stock.SECURITY_CODE, "BUY");
    const sellRows = await fetchSeatRows(stock.SECURITY_CODE, "SELL");
    details.push(...normalizeDetailRows(stock, buyRows, "买入"));
    details.push(...normalizeDetailRows(stock, sellRows, "卖出"));
    await sleep(120);
  }

  const fullRankEntries = uniqueStocks
    .map((row, index) => normalizeRankRow(row, index + 1))
    .sort((a, b) => b.net - a.net)
    .map((row, index) => ({ ...row, rank: index + 1 }));

  await enrichRankFundTrends(fullRankEntries);

  let marketFlowEntries = [];
  try {
    process.stdout.write("抓取市场主力资金前20/后20...\n");
    marketFlowEntries = await fetchMarketFlowEntries();
  } catch (error) {
    process.stdout.write(`主力资金抓取跳过：${error.message}\n`);
  }
  if (!marketFlowEntries.length) {
    process.stdout.write("全市场主力资金接口返回空，使用龙虎榜上榜股近5日主力资金回补。\n");
    marketFlowEntries = buildMarketFlowFallback(fullRankEntries);
  }

  const output = {
    source: "Eastmoney datacenter-web",
    generatedAt: new Date().toISOString(),
    tradeDate,
    summaryCount: summaryRows.length,
    stockCount: uniqueStocks.length,
    detailCount: details.length,
    marketFlowCount: marketFlowEntries.length,
    fullRankEntries,
    entries: details,
    marketFlowEntries
  };

  const jsonPath = path.join(dataDir, `lhb-${tradeDate}.json`);
  await fs.writeFile(jsonPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  await patchHtml(output);

  process.stdout.write(`完成：${jsonPath}\n`);
  process.stdout.write(`汇总行 ${summaryRows.length}，去重个股 ${uniqueStocks.length}，逐席位明细 ${details.length}。\n`);
}

async function fetchSeatRows(stockCode, side) {
  const reportName = side === "BUY" ? "RPT_BILLBOARD_DAILYDETAILSBUY" : "RPT_BILLBOARD_DAILYDETAILSSELL";
  return fetchPaged({
    reportName,
    columns: "ALL",
    sortColumns: side,
    sortTypes: "-1",
    filter: `(TRADE_DATE='${tradeDate}')(SECURITY_CODE="${stockCode}")`,
    pageSize: "50"
  });
}

async function fetchMarketFlowEntries() {
  const [inRows, outRows] = await Promise.all([
    fetchMarketFlowRank("in"),
    fetchMarketFlowRank("out")
  ]);
  const rows = [
    ...inRows.map((row, index) => normalizeMarketFlowRow(row, "净流入", index + 1)),
    ...outRows.map((row, index) => normalizeMarketFlowRow(row, "净流出", index + 1))
  ];

  const enriched = [];
  for (const [index, row] of rows.entries()) {
    process.stdout.write(`抓取近5日资金 ${index + 1}/${rows.length} ${row.code} ${row.name}\n`);
    const trend = await fetchFundTrend(row.code);
    enriched.push({ ...row, ...trend });
    await sleep(80);
  }
  return enriched;
}

async function enrichRankFundTrends(rows) {
  for (const [index, row] of rows.entries()) {
    try {
      process.stdout.write(`抓取龙虎榜个股近5日主力资金 ${index + 1}/${rows.length} ${row.code} ${row.name}\n`);
      const trend = await fetchFundTrend(row.code);
      Object.assign(row, trend);
      await sleep(70);
    } catch (error) {
      row.trend5 = [];
      row.trendTotal5 = null;
      row.trendNote = `近5日主力资金抓取失败：${error.message}`;
    }
  }
}

async function fetchMarketFlowRank(direction) {
  const payload = await fetchJson({
    pn: "1",
    pz: "20",
    po: direction === "in" ? "1" : "0",
    np: "1",
    ut: pushUt,
    fltt: "2",
    invt: "2",
    fid: "f62",
    fs: marketFs,
    fields: "f12,f13,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f100,f124"
  }, 1, pushHost, "/api/qt/clist/get");
  return payload?.data?.diff || [];
}

function buildMarketFlowFallback(rankRows) {
  const rows = (rankRows || [])
    .map((row) => {
      const trend5 = Array.isArray(row.trend5) ? row.trend5 : [];
      const latestNet = toWanSafe(trend5[trend5.length - 1], 1);
      const trendTotal5 = Number.isFinite(Number(row.trendTotal5)) ? Number(row.trendTotal5) : null;
      return {
        code: row.code || "",
        name: row.name || "",
        close: row.close ?? null,
        change: row.change ?? null,
        net: latestNet,
        direction: latestNet < 0 ? "净流出" : "净流入",
        theme: row.industry || row.note || "龙虎榜上榜股",
        source: "龙虎榜上榜股近5日主力资金回补",
        trend5,
        trendTotal5,
        trendNote: row.trendNote || "由龙虎榜上榜股近5日主力资金回补"
      };
    })
    .filter((row) => row.code && row.net !== 0);

  const inflow = rows
    .filter((row) => row.net > 0)
    .sort((a, b) => b.net - a.net)
    .slice(0, 20)
    .map((row, index) => ({ ...row, rank: index + 1, direction: "净流入" }));
  const outflow = rows
    .filter((row) => row.net < 0)
    .sort((a, b) => a.net - b.net)
    .slice(0, 20)
    .map((row, index) => ({ ...row, rank: index + 1, direction: "净流出" }));
  return [...inflow, ...outflow];
}

async function fetchFundTrend(code) {
  const payload = await fetchJson({
    lmt: "5",
    klt: "101",
    secid: secidFromCode(code),
    fields1: "f1,f2,f3,f7",
    fields2: "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63"
  }, 1, pushHisHost, "/api/qt/stock/fflow/daykline/get");
  const klines = payload?.data?.klines || [];
  const values = klines
    .map((line) => {
      const parts = String(line).split(",");
      return {
        date: parts[0] || "",
        net: yuanToWan(parts[1]),
        change: toNullableNumber(parts[12])
      };
    })
    .filter((item) => item.date);
  const trend5 = values.map((item) => item.net);
  const trendTotal5 = values.reduce((sum, item) => sum + item.net, 0);
  const first = values[0]?.date || "";
  const last = values[values.length - 1]?.date || "";
  return {
    trend5,
    trendTotal5: values.length ? Number(trendTotal5.toFixed(2)) : null,
    trendNote: values.length ? `${first} 至 ${last} 合计 ${formatWanText(trendTotal5)}` : "近5日明细待接口补齐"
  };
}

async function fetchPaged(baseParams) {
  const pageSize = Number(baseParams.pageSize || 500);
  const rows = [];
  for (let pageNumber = 1; pageNumber <= 20; pageNumber += 1) {
    const payload = await fetchJson({
      ...baseParams,
      source: "WEB",
      client: "WEB",
      pageNumber: String(pageNumber),
      pageSize: String(pageSize)
    });
    const result = payload.result;
    const pageRows = result?.data || [];
    rows.push(...pageRows);
    const pages = Number(result?.pages || 1);
    if (pageNumber >= pages || pageRows.length < pageSize) break;
  }
  return rows;
}

async function fetchJson(params, attempt = 1, host = apiHost, requestPath = apiPath) {
  const query = new URLSearchParams(params).toString();
  const url = `https://${host}${requestPath}?${query}`;
  try {
    const response = await fetch(url, {
      headers: {
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Referer": "https://data.eastmoney.com/stock/lhb.html",
      "Accept": "application/json,text/plain,*/*"
      },
      redirect: "follow",
      signal: AbortSignal.timeout(15000)
    });
    const body = await response.text();
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${body.slice(0, 200)}`);
    }
    return parseJsonBody(body);
  } catch (error) {
    if (attempt < 3) {
      await sleep(500 * attempt);
      return fetchJson(params, attempt + 1, host, requestPath);
    }
    throw new Error(formatFetchError(error, host));
  }
}

function formatFetchError(error, host) {
  const cause = error?.cause;
  const code = cause?.code ? `${cause.code}: ` : "";
  if (cause?.code === "ENOTFOUND") {
    return `${code}无法访问 ${host}，通常是当前运行环境没有网络/DNS权限`;
  }
  if (error?.name === "TimeoutError" || error?.code === "ABORT_ERR") {
    return `访问 ${host} 超时，请稍后重试`;
  }
  return `${code}${error?.message || String(error)}`;
}

function parseJsonBody(text) {
  const trimmed = text.trim();
  if (trimmed.startsWith("{")) return JSON.parse(trimmed);
  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start >= 0 && end > start) return JSON.parse(trimmed.slice(start, end + 1));
  throw new Error(`无法解析接口返回：${trimmed.slice(0, 200)}`);
}

function dedupeStocks(rows) {
  const map = new Map();
  for (const row of rows) {
    const key = `${row.SECURITY_CODE}|${row.EXPLANATION || row.EXPLAIN || ""}`;
    if (!map.has(key)) map.set(key, row);
  }
  return [...map.values()];
}

function normalizeRankRow(row, rank) {
  return {
    rank,
    code: row.SECURITY_CODE || "",
    name: row.SECURITY_NAME_ABBR || "",
    close: toWanSafe(row.CLOSE_PRICE, 1),
    change: toWanSafe(row.CHANGE_RATE, 1),
    turnover: toWanSafe(row.TURNOVERRATE, 1),
    net: yuanToWan(row.BILLBOARD_NET_AMT),
    buy: yuanToWan(row.BILLBOARD_BUY_AMT),
    sell: yuanToWan(row.BILLBOARD_SELL_AMT),
    deal: yuanToWan(row.BILLBOARD_DEAL_AMT),
    reason: row.EXPLANATION || row.EXPLAIN || "",
    industry: row.SECURITY_TYPE_CODE || "",
    note: row.EXPLANATION || row.EXPLAIN || "",
    trend5: [],
    trendTotal5: null,
    trendNote: "近5日主力资金待刷新"
  };
}

function normalizeDetailRows(stock, rows, side) {
  return rows.map((row) => ({
    code: row.SECURITY_CODE || stock.SECURITY_CODE || "",
    name: stock.SECURITY_NAME_ABBR || row.SECURITY_NAME_ABBR || "",
    side,
    seat: row.OPERATEDEPT_NAME || "",
    amount: yuanToWan(side === "卖出" ? row.SELL : row.BUY),
    buyAmount: yuanToWan(row.BUY),
    sellAmount: yuanToWan(row.SELL),
    netAmount: yuanToWan(row.NET),
    reason: `${tradeDate} ${side}席位；${row.EXPLANATION || stock.EXPLANATION || stock.EXPLAIN || ""}`.trim()
  })).filter((row) => row.seat && row.amount !== 0);
}

function normalizeMarketFlowRow(row, direction, rank) {
  return {
    rank,
    code: row.f12 || "",
    name: row.f14 || "",
    close: toNullableNumber(row.f2),
    change: toNullableNumber(row.f3),
    net: yuanToWan(row.f62),
    netRatio: toNullableNumber(row.f184),
    direction,
    theme: row.f100 || "",
    source: "东方财富资金流向",
    trend5: [],
    trendTotal5: null,
    trendNote: "近5日明细待接口补齐"
  };
}

async function patchHtml(data) {
  let html = await fs.readFile(htmlPath, "utf8");
  const version = `${data.tradeDate}.eastmoney-full.${data.stockCount}.${data.detailCount}`;
  html = replaceConst(html, "TODAY_SEED_VERSION", JSON.stringify(version));
  html = replaceArrayConst(html, "todayEntries", JSON.stringify(data.entries, null, 6));
  html = replaceArrayConst(html, "fullRankEntries", JSON.stringify(data.fullRankEntries, null, 6));
  html = replaceArrayConst(html, "marketFlowEntries", JSON.stringify(data.marketFlowEntries || [], null, 6));
  html = html.replace(
    /复核口径：[^<]+/,
    `复核口径：${data.tradeDate} 已接东方财富全量接口，汇总 ${data.summaryCount} 行，去重上榜项 ${data.stockCount} 个，逐席位明细 ${data.detailCount} 条。`
  );
  html = html.replace(
    /\{ label: "当前逐席位明细", value: "[^"]+", note: "[^"]+" \}/,
    `{ label: "当前逐席位明细", value: "${data.stockCount}项 / ${data.detailCount}条", note: "由东方财富全量接口生成，本地时间 ${new Date().toLocaleString("zh-CN", { hour12: false })}" }`
  );
  await fs.writeFile(htmlPath, html, "utf8");
}

function replaceConst(source, name, value) {
  const pattern = new RegExp(`const ${name} = .*?;`);
  if (!pattern.test(source)) throw new Error(`未找到常量 ${name}`);
  return source.replace(pattern, `const ${name} = ${value};`);
}

function replaceArrayConst(source, name, value) {
  const marker = `const ${name} = [`;
  const start = source.indexOf(marker);
  if (start < 0) throw new Error(`未找到数组 ${name}`);

  const bracketStart = start + marker.length - 1;
  let depth = 0;
  let inString = false;
  let quote = "";
  let escaped = false;

  for (let index = bracketStart; index < source.length; index += 1) {
    const char = source[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === quote) {
        inString = false;
      }
      continue;
    }

    if (char === "\"" || char === "'" || char === "`") {
      inString = true;
      quote = char;
      continue;
    }
    if (char === "[") depth += 1;
    if (char === "]") {
      depth -= 1;
      if (depth === 0) {
        let end = index + 1;
        while (/\s/.test(source[end] || "")) end += 1;
        if (source[end] !== ";") throw new Error(`数组 ${name} 结束位置异常`);
        return `${source.slice(0, start)}const ${name} = ${value};${source.slice(end + 1)}`;
      }
    }
  }

  throw new Error(`未找到数组 ${name} 的结束位置`);
}

function yuanToWan(value) {
  return toWanSafe(value, 10000);
}

function toNullableNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Number(number.toFixed(2)) : null;
}

function toWanSafe(value, divisor) {
  const number = Number(value);
  return Number.isFinite(number) ? Number((number / divisor).toFixed(2)) : 0;
}

function formatWanText(value) {
  const number = Number(value || 0);
  if (Math.abs(number) >= 10000) return `${(number / 10000).toFixed(2)}亿`;
  return `${Math.round(number)}万`;
}

function secidFromCode(code) {
  if (/^(6|688|689)/.test(String(code))) return `1.${code}`;
  return `0.${code}`;
}

function localDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function isWeekendDate(value) {
  const date = new Date(`${value}T12:00:00+08:00`);
  const day = date.getDay();
  return day === 0 || day === 6;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((error) => {
  console.error(`全量数据抓取失败：${error.message}`);
  console.error("看板没有写入不完整数据；请在网络可访问的终端里重新运行刷新脚本。");
  process.exitCode = 1;
});

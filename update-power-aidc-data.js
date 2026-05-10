#!/usr/bin/env node

const fs = require("fs");
const http = require("http");
const https = require("https");
const path = require("path");
const { execFile } = require("child_process");
const { URL } = require("url");

const dashboardPath = path.join(__dirname, "power-aidc-dashboard.html");
const dataDir = path.join(__dirname, "data");
const logsDir = path.join(__dirname, "logs");
const snapshotPath = path.join(dataDir, "quotes.json");
const updateLogPath = path.join(logsDir, "update.log");
const VERSION = "quotes-eastmoney-v6-2026-05-09";
const EASTMONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b";

const stocks = [
  { code: "002015", name: "协鑫能科", market: "SZ", cost: 19.53 },
  { code: "300274", name: "阳光电源", market: "SZ", cost: 140.53 },
  { code: "301638", name: "南网数字", market: "SZ", cost: 30.22 },
  { code: "300442", name: "润泽科技", market: "SZ", cost: 96.06 },
  { code: "688981", name: "中芯国际", market: "SH", cost: 123.10 },
  { code: "300383", name: "光环新网", market: "SZ", cost: 17.29 }
];

const marketIndices = [
  { code: "000001", name: "上证指数", market: "SH", cost: 1 },
  { code: "399001", name: "深成指", market: "SZ", cost: 1 },
  { code: "399006", name: "创业板指", market: "SZ", cost: 1 },
  { code: "000688", name: "科创50", market: "SH", cost: 1 },
  { code: "000300", name: "沪深300", market: "SH", cost: 1 }
];

function ensureDirs() {
  fs.mkdirSync(dataDir, { recursive: true });
  fs.mkdirSync(logsDir, { recursive: true });
}

function appendLog(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  fs.appendFileSync(updateLogPath, line);
}

function secid(stock) {
  return `${stock.market === "SH" ? "1" : "0"}.${stock.code}`;
}

function requestTextNode(url) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const transport = parsed.protocol === "http:" ? http : https;
    const req = transport.get(parsed, {
      headers: {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "close",
        "Referer": "https://quote.eastmoney.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
      },
      timeout: 9000
    }, res => {
      let text = "";
      res.setEncoding("utf8");
      res.on("data", chunk => {
        text += chunk;
      });
      res.on("end", () => {
        if (res.statusCode >= 400) {
          reject(new Error(`HTTP ${res.statusCode}`));
          return;
        }
        resolve(text);
      });
    });
    req.on("timeout", () => {
      req.destroy(new Error("node timeout"));
    });
    req.on("error", reject);
  });
}

function requestTextCurl(url) {
  return new Promise((resolve, reject) => {
    const curlPath = "/usr/bin/curl";
    if (!fs.existsSync(curlPath)) {
      reject(new Error("curl not found"));
      return;
    }
    const args = [
      "-L",
      "--silent",
      "--show-error",
      "--connect-timeout", "8",
      "--max-time", "15",
      "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "-H", "Accept: */*",
      "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
      "-H", "Cache-Control: no-cache",
      "-e", "https://quote.eastmoney.com/",
      url
    ];
    execFile(curlPath, args, { encoding: "utf8", maxBuffer: 8 * 1024 * 1024 }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error((stderr || error.message || "curl failed").trim()));
        return;
      }
      resolve(stdout);
    });
  });
}

async function requestText(url) {
  const errors = [];
  for (const [name, requester] of [
    ["node", requestTextNode],
    ["curl", requestTextCurl]
  ]) {
    try {
      const text = await requester(url);
      if (text && text.trim()) {
        if (name === "curl") appendLog(`request fallback succeeded host=${new URL(url).hostname}`);
        return text;
      }
      errors.push(`${name}: empty response`);
    } catch (error) {
      errors.push(`${name}: ${error.message}`);
    }
  }
  throw new Error(errors.join("; "));
}

async function requestEastmoney() {
  const fields = "f12,f14,f2,f3,f4,f5,f6,f18,f43,f47,f48,f57,f58,f60,f169,f170,f62,f184";
  const callback = `jQuery${Date.now()}`;
  const secids = stocks.map(secid).join(",");
  const urls = [
    `https://push2.eastmoney.com/api/qt/ulist/get?fltt=2&invt=2&ut=${EASTMONEY_UT}&fields=${fields}&secids=${secids}&_=${Date.now()}`,
    `https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&ut=${EASTMONEY_UT}&fields=${fields}&secids=${secids}&cb=${callback}&_=${Date.now()}`
  ];
  let lastError = null;
  for (let index = 0; index < urls.length; index += 1) {
    const text = await requestText(urls[index]);
    fs.writeFileSync(path.join(__dirname, `power-aidc-raw-response-eastmoney-${index + 1}.txt`), text);
    fs.writeFileSync(path.join(__dirname, "power-aidc-raw-response-eastmoney.txt"), text);
    try {
      return parseEastmoney(text);
    } catch (error) {
      lastError = error;
    }
  }
  try {
    return await requestEastmoneySingles(fields);
  } catch (error) {
    throw new Error(`批量接口失败：${lastError ? lastError.message : "未知错误"}；个股接口失败：${error.message}`);
  }
}

async function requestEastmoneySingles(fields) {
  const byCode = {};
  const raw = [];
  const errors = [];
  for (const stock of stocks) {
    const url = `https://push2.eastmoney.com/api/qt/stock/get?fltt=2&invt=2&ut=${EASTMONEY_UT}&fields=${fields}&secid=${secid(stock)}&_=${Date.now()}`;
    try {
      const text = await requestText(url);
      raw.push(`--- ${stock.code} ${stock.name} ---\n${text}`);
      const row = parseEastmoneyStock(text, stock);
      byCode[stock.code] = row;
    } catch (error) {
      errors.push(`${stock.code}: ${error.message}`);
    }
  }
  fs.writeFileSync(path.join(__dirname, "power-aidc-raw-response-eastmoney-singles.txt"), raw.join("\n"));
  if (Object.keys(byCode).length === stocks.length) return byCode;
  throw new Error(errors.length ? errors.join(" | ") : `only ${Object.keys(byCode).length}/${stocks.length} rows`);
}

function sinaSymbol(stock) {
  return `${stock.market === "SH" ? "sh" : "sz"}${stock.code}`;
}

async function requestSina() {
  const urls = [
    `https://hq.sinajs.cn/list=${stocks.map(sinaSymbol).join(",")}`,
    `http://hq.sinajs.cn/list=${stocks.map(sinaSymbol).join(",")}`
  ];
  let text = "";
  let lastError = null;
  for (const url of urls) {
    try {
      text = await requestText(url);
      fs.writeFileSync(path.join(__dirname, "power-aidc-raw-response-sina.txt"), text);
      if (text.trim()) break;
    } catch (error) {
      lastError = error;
    }
  }
  if (!text.trim() && lastError) throw lastError;
  const byCode = {};
  for (const stock of stocks) {
    const pattern = new RegExp(`var hq_str_${sinaSymbol(stock)}="([^"]*)"`);
    const match = text.match(pattern);
    if (!match || !match[1]) continue;
    const parts = match[1].split(",");
    const last = Number(parts[3]);
    const prevClose = Number(parts[2]);
    const change = Number.isFinite(last) && Number.isFinite(prevClose) ? last - prevClose : NaN;
    byCode[stock.code] = {
      code: stock.code,
      name: parts[0] || stock.name,
      last,
      pct: prevClose ? change / prevClose * 100 : NaN,
      change,
      volume: Number(parts[8]),
      amount: Number(parts[9]),
      prevClose,
      mainNet: NaN,
      mainRatio: NaN
    };
  }
  if (!Object.keys(byCode).length) throw new Error(`新浪行情为空：${text.slice(0, 300).replace(/\s+/g, " ")}`);
  return byCode;
}

async function requestTencent() {
  const urls = [
    `https://qt.gtimg.cn/q=${stocks.map(sinaSymbol).join(",")}`,
    `http://qt.gtimg.cn/q=${stocks.map(sinaSymbol).join(",")}`
  ];
  let text = "";
  let lastError = null;
  for (const url of urls) {
    try {
      text = await requestText(url);
      fs.writeFileSync(path.join(__dirname, "power-aidc-raw-response-tencent.txt"), text);
      if (text.trim()) break;
    } catch (error) {
      lastError = error;
    }
  }
  if (!text.trim() && lastError) throw lastError;
  const byCode = {};
  for (const stock of stocks) {
    const pattern = new RegExp(`v_${sinaSymbol(stock)}="([^"]*)"`);
    const match = text.match(pattern);
    if (!match || !match[1]) continue;
    const parts = match[1].split("~");
    const last = Number(parts[3]);
    const prevClose = Number(parts[4]);
    const pct = Number(parts[32]);
    byCode[stock.code] = {
      code: stock.code,
      name: parts[1] || stock.name,
      last,
      pct,
      change: Number(parts[31]),
      volume: Number(parts[6]),
      amount: Number(parts[37]) * 10000,
      prevClose,
      mainNet: NaN,
      mainRatio: NaN
    };
  }
  if (!Object.keys(byCode).length) throw new Error(`腾讯行情为空：${text.slice(0, 300).replace(/\s+/g, " ")}`);
  return byCode;
}

async function getQuoteData() {
  try {
    const data = await requestEastmoney();
    const market = await getMarketSnapshot();
    return { source: "东方财富", data, market };
  } catch (error) {
    const cachedPath = path.join(__dirname, "power-aidc-raw-response-eastmoney.txt");
    if (fs.existsSync(cachedPath)) {
      appendLog(`quote fallback used cached eastmoney raw reason=${error.message}`);
      return { source: "东方财富", data: parseEastmoney(fs.readFileSync(cachedPath, "utf8")), market: { source: null, error: error.message, indices: [] } };
    }
    throw error;
  }
}

async function getMarketSnapshot() {
  const fields = "f12,f14,f2,f3,f4,f5,f6,f18,f43,f47,f48,f57,f58,f60,f169,f170";
  const secids = marketIndices.map(secid).join(",");
  const url = `https://push2.eastmoney.com/api/qt/ulist/get?fltt=2&invt=2&ut=${EASTMONEY_UT}&fields=${fields}&secids=${secids}&_=${Date.now()}`;
  try {
    const text = await requestText(url);
    fs.writeFileSync(path.join(__dirname, "power-aidc-raw-response-eastmoney-market.txt"), text);
    return { source: "东方财富", error: null, indices: parseEastmoneyMarket(text) };
  } catch (error) {
    appendLog(`market snapshot failed ${error.message}`);
    return { source: null, error: error.message, indices: [] };
  }
}

async function getLatestTradingDate() {
  const stock = stocks[0];
  const url = `https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=${secid(stock)}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20260101&end=20500101&ut=${EASTMONEY_UT}&_=${Date.now()}`;
  const text = await requestText(url);
  const payload = JSON.parse(extractJson(text));
  const rows = payload && payload.data && Array.isArray(payload.data.klines) ? payload.data.klines : [];
  if (!rows.length) throw new Error("无法从日K接口确认最近交易日");
  const latest = rows[rows.length - 1].split(",")[0];
  if (!/^\d{4}-\d{2}-\d{2}$/.test(latest)) throw new Error(`最近交易日格式异常：${latest}`);
  return latest;
}

function parseEastmoney(text) {
  const cleaned = extractJson(text);
  const payload = JSON.parse(cleaned);
  if (payload && payload.rc && payload.rc !== 0 && (!payload.data || !payload.data.diff)) {
    throw new Error(`eastmoney rc=${payload.rc} data=${payload.data === null ? "null" : typeof payload.data}`);
  }
  const rows = payload && payload.data && Array.isArray(payload.data.diff) ? payload.data.diff : [];
  if (!rows.length) throw new Error("empty eastmoney diff");
  const byCode = {};
  for (const item of rows) {
    byCode[item.f12 || item.f57] = normalizeEastmoneyRow(item);
  }
  return byCode;
}

function parseEastmoneyMarket(text) {
  const cleaned = extractJson(text);
  const payload = JSON.parse(cleaned);
  if (payload && payload.rc && payload.rc !== 0 && (!payload.data || !payload.data.diff)) {
    throw new Error(`eastmoney market rc=${payload.rc} data=${payload.data === null ? "null" : typeof payload.data}`);
  }
  const rows = payload && payload.data && Array.isArray(payload.data.diff) ? payload.data.diff : [];
  if (!rows.length) throw new Error("empty eastmoney market diff");
  return rows.map(item => {
    const fallback = marketIndices.find(index => index.code === (item.f12 || item.f57)) || { cost: 1 };
    const row = normalizeEastmoneyRow(item, fallback);
    return {
      code: row.code,
      name: row.name,
      last: finiteOrNull(row.last),
      pct: finiteOrNull(row.pct),
      change: finiteOrNull(row.change),
      amount: finiteOrNull(row.amount)
    };
  });
}

function parseEastmoneyStock(text, stock) {
  const cleaned = extractJson(text);
  const payload = JSON.parse(cleaned);
  if (payload && payload.rc && payload.rc !== 0 && !payload.data) {
    throw new Error(`eastmoney stock rc=${payload.rc} data=null`);
  }
  if (!payload || !payload.data) throw new Error("empty eastmoney stock data");
  const row = normalizeEastmoneyRow(payload.data, stock);
  if (!Number.isFinite(row.last) || row.last <= 0) {
    throw new Error(`invalid eastmoney price ${row.last}`);
  }
  return row;
}

function firstFinite(...values) {
  for (const value of values) {
    const number = Number(value);
    if (Number.isFinite(number)) return number;
  }
  return NaN;
}

function normalizeEastmoneyPrice(value, stock) {
  let number = Number(value);
  if (!Number.isFinite(number)) return NaN;
  if (number > stock.cost * 20) number = number / 100;
  return number;
}

function normalizeEastmoneyPct(value) {
  let number = Number(value);
  if (!Number.isFinite(number)) return NaN;
  if (Math.abs(number) > 100) number = number / 100;
  return number;
}

function normalizeEastmoneyRow(item, fallbackStock = {}) {
  const stock = stocks.find(row => row.code === (item.f12 || item.f57 || fallbackStock.code)) || fallbackStock;
  return {
    code: item.f12 || item.f57 || stock.code,
    name: item.f14 || item.f58 || stock.name,
    last: normalizeEastmoneyPrice(firstFinite(item.f2, item.f43), stock),
    pct: normalizeEastmoneyPct(firstFinite(item.f3, item.f170)),
    change: firstFinite(item.f4, item.f169),
    volume: firstFinite(item.f5, item.f47),
    amount: firstFinite(item.f6, item.f48),
    prevClose: normalizeEastmoneyPrice(firstFinite(item.f18, item.f60), stock),
    mainNet: firstFinite(item.f62),
    mainRatio: normalizeEastmoneyPct(firstFinite(item.f184))
  };
}

function extractJson(text) {
  const trimmed = text.trim();
  if (!trimmed) throw new Error("行情接口返回空内容");
  if (trimmed.startsWith("{")) return trimmed;
  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start >= 0 && end > start) return trimmed.slice(start, end + 1);
  throw new Error(`行情接口返回非 JSON：${trimmed.slice(0, 500).replace(/\s+/g, " ")}`);
}

function formatCapital(value) {
  if (!Number.isFinite(value)) return "待核验";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (abs >= 100000000) return `${sign}${(abs / 100000000).toFixed(2)} 亿元`;
  if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(2)} 万元`;
  return `${sign}${abs.toFixed(0)} 元`;
}

function formatAmount(value) {
  if (!Number.isFinite(value)) return "待核验";
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)} 亿元`;
  if (value >= 10000) return `${(value / 10000).toFixed(2)} 万元`;
  return `${value.toFixed(0)} 元`;
}

function formatPct(value) {
  if (!Number.isFinite(value)) return "待核验";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function finiteOrNull(value) {
  return Number.isFinite(value) ? value : null;
}

function latestWeekdayLabel(date = new Date()) {
  const day = date.getDay();
  const copy = new Date(date);
  if (day === 0) copy.setDate(copy.getDate() - 2);
  if (day === 6) copy.setDate(copy.getDate() - 1);
  return `${copy.getFullYear()}-${String(copy.getMonth() + 1).padStart(2, "0")}-${String(copy.getDate()).padStart(2, "0")}`;
}

function buildSnapshot(result, dateLabel) {
  const items = stocks.map(stock => {
    const row = result.data[stock.code] || {};
    const pnlPct = Number.isFinite(row.last) ? (row.last - stock.cost) / stock.cost * 100 : NaN;
    return {
      code: stock.code,
      name: stock.name,
      market: stock.market,
      cost: stock.cost,
      last: finiteOrNull(row.last),
      pct: finiteOrNull(row.pct),
      change: finiteOrNull(row.change),
      volume: finiteOrNull(row.volume),
      amount: finiteOrNull(row.amount),
      prevClose: finiteOrNull(row.prevClose),
      mainNet: finiteOrNull(row.mainNet),
      mainRatio: finiteOrNull(row.mainRatio),
      pnlPct: finiteOrNull(pnlPct),
      opinion: opinionFor(stock, row)
    };
  });
  return {
    date: dateLabel,
    updatedAt: new Date().toISOString(),
    source: result.source,
    hasMainFund: result.source === "东方财富",
    market: result.market || { source: null, error: "未请求大盘指数", indices: [] },
    items
  };
}

function writeSnapshot(snapshot) {
  fs.writeFileSync(snapshotPath, JSON.stringify(snapshot, null, 2));
}

function embedSnapshot(html, snapshot) {
  const json = JSON.stringify(snapshot).replace(/</g, "\\u003c");
  const block = `<script id="localQuoteSnapshot" type="application/json">${json}</script>`;
  if (html.includes('<script id="localQuoteSnapshot" type="application/json">')) {
    return html.replace(/<script id="localQuoteSnapshot" type="application\/json">[\s\S]*?<\/script>/, block);
  }
  return html.replace("</body>", `  ${block}\n</body>`);
}

function opinionFor(stock, row) {
  if (!row || !Number.isFinite(row.last) || !Number.isFinite(row.mainNet)) {
    return `${stock.name} 数据不足，不生成个股结论。`;
  }
  const pnl = (row.last - stock.cost) / stock.cost * 100;
  if (row.mainNet > 0 && pnl >= 0) return `${stock.name} 现价/资金同向偏强，保留或继续观察核心仓。`;
  if (row.mainNet < 0 && pnl < 0) return `${stock.name} 现价弱于成本且主力流出，短线承接不足。`;
  if (row.mainNet > 0) return `${stock.name} 主力资金转正，但价格仍需确认承接。`;
  return `${stock.name} 主力资金转负，先降为观察，不加仓。`;
}

function replaceStockLast(html, code, last) {
  if (!Number.isFinite(last)) return html;
  const stockBlock = new RegExp(`(code:\\s*"${code}"[\\s\\S]*?last:\\s*)[-0-9.]+`, "m");
  return html.replace(stockBlock, `$1${last.toFixed(2)}`);
}

function replaceDefaultFunds(html, code, row, dateLabel) {
  if (!row) return html;
  const hasFund = Number.isFinite(row.mainNet);
  const net = hasFund ? formatCapital(row.mainNet) : "资金源未返回";
  const ratio = Number.isFinite(row.mainRatio) ? `，占比 ${row.mainRatio.toFixed(2)}%` : "";
  const currentMatch = html.match(new RegExp(`"${code}": \\[([^\\n]+)\\]`));
  let preserved = ["北向/港股通待盘后核验", "龙虎榜需盘后核验", "融资余额待盘后刷新"];
  if (currentMatch) {
    const cells = Array.from(currentMatch[1].matchAll(/"([^"]*)"/g)).map(match => match[1]);
    if (cells.length >= 5) preserved = cells.slice(1, 4);
  }
  const next = `"${code}": ["${dateLabel} 主力净流入 ${net}${ratio}", "${preserved[0]}", "${preserved[1]}", "${preserved[2]}", "${opinionFor(stocks.find(item => item.code === code), row)}"]`;
  const pattern = new RegExp(`"${code}": \\[[^\\n]+\\]`);
  return html.replace(pattern, next);
}

function replaceDailyRow(html, stock, row, dateLabel) {
  if (!row || !Number.isFinite(row.last)) return html;
  const perf = `${stock.name} 最新价 ${row.last.toFixed(2)}，涨跌幅 ${formatPct(row.pct)}，成交额 ${formatAmount(row.amount)}。`;
  const fund = Number.isFinite(row.mainNet)
    ? `${dateLabel} 主力净流入 ${formatCapital(row.mainNet)}${Number.isFinite(row.mainRatio) ? `，占比 ${row.mainRatio.toFixed(2)}%` : ""}。`
    : `${dateLabel} 主力资金待核验。`;
  const opinion = opinionFor(stock, row);
  const pattern = new RegExp(`(<tr data-daily-code="${stock.code}">[\\s\\S]*?<td data-daily-field="performance">)[\\s\\S]*?(</td>\\s*<td data-daily-field="fund">)[\\s\\S]*?(</td>\\s*<td data-daily-field="opinion">)[\\s\\S]*?(</td>)`, "m");
  return html.replace(pattern, `$1${perf}$2${fund}$3${opinion}$4`);
}

function replaceSnapshot(html, dateLabel) {
  return html
    .replace(/Snapshot · [^<]+/g, `Snapshot · ${dateLabel} 本地快照`)
    .replace(/\d{4}-\d{2}-\d{2}：本地更新器已刷新个股现价和主力资金；[^<]+/g, `${dateLabel}：本地更新器已刷新个股现价和主力资金；北向、龙虎榜、融资余额按公开披露口径补充。`)
    .replace(/<span>5 月 8 日成交额<\/span>\s*<strong>待核验<\/strong>\s*<p>[^<]+<\/p>/, `<span>${dateLabel.replace("2026-", "").replace("-", " 月 ")} 日个股快照</span>\n              <strong>已刷新</strong>\n              <p>总成交额仍需市场复盘源核验；个股现价和主力资金已写入。</p>`);
}

async function main() {
  ensureDirs();
  appendLog(`start update version=${VERSION}`);
  console.log(`脚本版本: ${VERSION}`);
  const result = await getQuoteData();
  const data = result.data;
  const missing = stocks.filter(stock => !data[stock.code]).map(stock => `${stock.name}(${stock.code})`);
  if (missing.length) throw new Error(`missing quote rows: ${missing.join(", ")}`);

  let dateLabel = latestWeekdayLabel();
  try {
    dateLabel = await getLatestTradingDate();
  } catch (error) {
    appendLog(`latest trading date fallback=${dateLabel} reason=${error.message}`);
  }
  const snapshot = buildSnapshot(result, dateLabel);
  writeSnapshot(snapshot);
  let html = fs.readFileSync(dashboardPath, "utf8");
  html = replaceSnapshot(html, dateLabel);
  for (const stock of stocks) {
    const row = data[stock.code];
    html = replaceStockLast(html, stock.code, row.last);
    html = replaceDefaultFunds(html, stock.code, row, dateLabel);
    html = replaceDailyRow(html, stock, row, dateLabel);
  }
  html = embedSnapshot(html, snapshot);
  fs.writeFileSync(dashboardPath, html);
  appendLog(`success source=${result.source} hasMainFund=${snapshot.hasMainFund}`);

  console.log(`Updated ${dashboardPath}`);
  console.log(`Snapshot ${snapshotPath}`);
  console.log(`Log ${updateLogPath}`);
  console.log(`行情源: ${result.source}`);
  if (snapshot.market && snapshot.market.indices && snapshot.market.indices.length) {
    console.log(`大盘指数: ${snapshot.market.source} ${snapshot.market.indices.length} 项`);
    for (const index of snapshot.market.indices) {
      console.log(`${index.name} ${index.code}: index=${index.last} pct=${formatPct(index.pct)} amount=${formatAmount(index.amount)}`);
    }
  } else {
    console.log(`大盘指数: 未更新${snapshot.market && snapshot.market.error ? `；${snapshot.market.error}` : ""}`);
  }
  if (result.source !== "东方财富") {
    console.log("注意：备用行情源不提供主力资金，资金字段已标为资金源未返回。");
  }
  for (const stock of stocks) {
    const row = data[stock.code];
    console.log(`${stock.name} ${stock.code}: price=${row.last} pct=${formatPct(row.pct)} amount=${formatAmount(row.amount)} main=${formatCapital(row.mainNet)}`);
  }
}

main().catch(error => {
  ensureDirs();
  appendLog(`failed ${error.message}`);
  console.error(`Update failed: ${error.message}`);
  for (const name of ["eastmoney", "sina", "tencent"]) {
    const rawPath = path.join(__dirname, `power-aidc-raw-response-${name}.txt`);
    if (fs.existsSync(rawPath)) {
      const raw = fs.readFileSync(rawPath, "utf8");
      console.error(`${name} raw sample: ${raw.slice(0, 500).replace(/\s+/g, " ")}`);
    }
  }
  process.exit(1);
});

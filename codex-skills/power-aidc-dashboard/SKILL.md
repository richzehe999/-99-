---
name: power-aidc-dashboard
description: Use when the user asks to update, verify, repair, or extend the local 电力/AIDC/算电协同 A股 dashboard in /Users/wuzehe/Documents/New project, especially triggers like “更新电力/AIDC 看板”, “复核看板”, “现价/主力资金获取不到”, “东方财富”, “100W模拟盘”, or “大盘视角”.
---

# Power/AIDC Dashboard

## Scope

Work in `/Users/wuzehe/Documents/New project`.

Primary artifacts:
- `power-aidc-dashboard.html`
- `update-power-aidc-data.js`
- `更新电力AIDC看板.command`
- `data/quotes.json`
- `power-aidc-update-latest.log`
- `logs/update.log`

User preference: ship usable local artifacts quickly, be direct, and distinguish confirmed data from fields that still need manual/post-close verification.

## Non-Negotiables

- Do not silently change data source. If the user says not to换数据源, keep 东方财富 as the required successful source.
- For update claims, verify with concrete evidence: latest log, `data/quotes.json`, and dashboard snapshot.
- Do not say “OK/完成” unless the latest run has `退出码: 0` and the expected source/fields are present.
- If fallback sources appear, report that clearly. Fallback quotes are not equivalent to 东方财富主力资金.
- Preserve the current local-dashboard style and the user’s terms: 电力/AIDC、算电协同、主力资金、北向、龙虎榜、融资、100W模拟盘.

## Current Working Contract

The working updater version should show:
- command entry: `command-v5-2026-05-09`
- script: `quotes-eastmoney-v5-2026-05-09`
- success source: `东方财富`

Expected successful log lines include:
- `行情源: 东方财富`
- six stock lines with `price=... pct=... amount=... main=...`
- `退出码: 0`

Tracked stocks:
- 协鑫能科 `002015`
- 阳光电源 `300274`
- 南网数字 `301638`
- 润泽科技 `300442`
- 中芯国际 `688981`
- 光环新网 `300383`

## Refresh Verification

When the user says “更新了”, “复核一下”, or asks whether it is OK:

1. Read `power-aidc-update-latest.log`.
2. Check `data/quotes.json` exists and parse it.
3. Check:
   - latest date/update time
   - source
   - `hasMainFund`
   - all six stocks have `last`
   - main fund fields exist when source is 东方财富
4. Answer with the actual state, not assumptions.

Suggested command:

```bash
sed -n '1,160p' power-aidc-update-latest.log
ls -l data/quotes.json power-aidc-dashboard.html logs/update.log
/Users/wuzehe/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node -e "const fs=require('fs'); const q=JSON.parse(fs.readFileSync('data/quotes.json','utf8')); console.log(JSON.stringify({date:q.date,updatedAt:q.updatedAt,source:q.source,hasMainFund:q.hasMainFund,count:q.items?.length,items:q.items?.map(x=>[x.name,x.code,x.last,x.pct,x.mainNet])},null,2));"
```

## Failure Repair

When update fails:

1. Read the exact error and raw files:
   - `power-aidc-raw-response-eastmoney.txt`
   - `power-aidc-raw-response-eastmoney-1.txt`
   - `power-aidc-raw-response-eastmoney-2.txt`
   - `power-aidc-raw-response-eastmoney-singles.txt`
2. If 东方财富 returns `rc:102` and `data:null`, prefer fixing the 东方财富 request shape before considering any new source.
3. Keep the updater using:
   - Eastmoney batch `qt/ulist/get`
   - Eastmoney per-stock `qt/stock/get`
   - `ut=fa5fd1943c7b386f172d6893dbfba10b`
   - Node request first, system `/usr/bin/curl` fallback second
4. Update version strings in both JS and `.command` when behavior changes.
5. Validate with:
   - Node syntax check
   - command entry dry run
   - HTML script syntax check if the dashboard changed

Do not present sandbox DNS failure as user-machine failure. The Codex sandbox may show `ENOTFOUND`; user Terminal may still succeed.

## Dashboard Changes

For “大盘视角” or structural improvement requests, evolve the dashboard from stock table to three-layer decision panel:

1. 大盘温度:
   - 上证、深成指、创业板、科创50、沪深300
   - 两市成交额 and change vs prior day
   - 上涨/下跌家数, 涨停/跌停 if available
2. 板块强弱:
   - 电力、AIDC/数据中心、算力、光模块/CPO、半导体、电网设备
   - relative strength versus broad index
3. 个股执行:
   - current price, main fund, simulated P/L, action status
   - allow/avoid add-position logic based on market + sector + stock confirmation

Use conservative labels for unavailable data: `待盘后核验`, `数据源未覆盖`, or `需手动确认`.

## Verification Before Final

Before claiming completion:

```bash
/Users/wuzehe/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check update-power-aidc-data.js
node - <<'NODE'
const fs = require('fs');
const html = fs.readFileSync('power-aidc-dashboard.html', 'utf8');
const scripts = [...html.matchAll(/<script(?![^>]*type="application\/json")[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
for (const script of scripts) new Function(script);
console.log(`HTML script syntax ok: ${scripts.length}`);
NODE
```


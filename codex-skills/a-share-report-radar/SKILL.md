---
name: a-share-report-radar
description: Use when the user says “更新A股报告”, “更新盘后验证版”, “A股盘后雷达”, “做今天A股报告”, or asks Codex to update/create the A股盘后验证雷达 static website. Handles current A-share data lookup, prior thesis validation, HTML report updates, dated archive generation, shareable zip packaging, and browser verification in the New project workspace.
---

# A股盘后验证雷达

## Workflow

1. Confirm the target trading date and report type.
   - Default to the latest A股 trading day if the user asks for “更新一下”, “盘后验证版”, or a date-specific report.
   - Treat market data as time-sensitive; browse for fresh sources before writing conclusions.
   - Never reuse an older report date, index values, turnover, sector conclusion, or prior HTML body as the current report. Old reports are references only.

2. Gather source data.
   - Prioritize current-day 收评/收盘 sources from 每日经济新闻, 新浪/格隆汇, 中国经济网, 新华财经, 证券时报, 东方财富, and official/company announcements for event catalysts.
   - Capture at minimum: 上证指数, 深证成指, 创业板指, 科创50 or 科创综指, total成交额,涨跌家数/涨停家数 if available, strongest themes, weakest themes, and major catalyst news.
   - Use primary or close-to-primary sources for external catalysts, for example company announcements for 英伟达/康宁 style events.

3. Compare against the previous thesis.
   - Read `references/report-context.md` when you need established report structure, current workspace paths, or prior thesis chain.
   - Explicitly classify each chain as `已验证`, `强验证`, `部分验证`, `未确认`, `连续未确认`, or `继续观察`.
   - Do not keep stale guesses as conclusions. If the market rejects a thesis, downgrade it clearly.

4. Update the static site.
   - Edit `a-share-report-site/index.html`.
   - Keep the existing layout and CSS unless the user asks for design changes.
   - Update the browser-open legacy path too if it exists, especially `a-share-report-2026-05-04.html`, so the currently open file reflects the newest report.
   - Create a dated archive file named `a-share-report-YYYY-MM-DD.html`.
   - Include the buyer-perspective section when updating daily reports. Place it immediately after the verification conclusion/strength section and before core signal cards.

5. Rebuild the shareable package.
   - Run `python3 codex-skills/a-share-report-radar/scripts/package_site.py --date YYYY-MM-DD`.
   - This syncs archive files and rebuilds `a-share-report-site.zip`.

6. Validate before final response.
   - File checks: confirm the date, key index values, share zip, no empty `href=""`/`src=""`, no unfinished placeholder text, no local absolute paths inside the shareable `index.html`.
   - Browser checks: open `a-share-report-site/index.html`, verify title/data/core themes/sources, test one filter button, and check console errors.
   - If browser tooling cannot attach to the user’s open tab, open the same local file in a controllable tab and verify there.

## Gmail Email Output

- When sending the report by Gmail, use `templates/email-inline-html-rules.md`.
- The Gmail body must be email-safe inline HTML, not a full webpage copied from `index.html`.
- Do not include `<style>`, `<head>`, `<script>`, or CSS blocks in the Gmail body. Gmail may expose those as visible text.
- The email body must include the updated report date and refreshed data gathered during the current run.
- Sending a stale 2026-05-07 report on later runs is a hard failure unless the report explicitly states that 2026-05-07 is the latest available trading date.

## HTML Update Rules

- The five KPI cards should remain: 上证指数, 深证成指, 创业板指, 科创50/科创综指, 全市场成交额.
- Theme cards should use these `data-kind` values:
  - `positive`: validated or strong thesis
  - `negative`: unconfirmed or contradicted thesis
  - `watch`: unresolved watch item
- Keep the matrix columns conceptually as:
  `此前推演 | 当日盘面证据 | A股映射 | 验证状态 | 后续处理`
- Keep the buyer-perspective module visible as cards plus a compact table. It should not be buried after the transmission matrix.
- Buyer cards should summarize:
  `维度 | 当前状态标签 | 看什么 | 次日判断信号`
- Buyer detail table should summarize:
  `维度 | 当日客观读数 | 下一步判断用途`
- Buyer-perspective dimensions should usually include: 资金连续性, 拥挤度与位置, 扩散质量, 催化兑现, 风格切换, 证伪条件.
- Keep conclusions factual and short. Prefer “盘面确认/未确认” language over broad market calls.
- The report is not investment advice; avoid direct buy/sell recommendations.

## Final Response

Include:
- Updated files and zip path.
- The core thesis changes in 3-5 bullets.
- Verification result, including browser render, filter interaction, and console error count.
- Source links used for the new report.

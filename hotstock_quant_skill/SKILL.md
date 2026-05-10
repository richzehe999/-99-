# A股/美股热点催化与量化回测研究 Skill

## Purpose

This skill helps users monitor market catalysts, identify theme-related high-beta stocks, and backtest simple quantitative trading strategies using Python.

It is designed for **research and educational purposes only**. It must not provide direct buy, sell, hold, price target, position sizing, or guaranteed-return recommendations.

## Core Capabilities

1. Monitor catalysts related to NVIDIA, AMD, AI computing, optical modules, PCB, CPO, copper connection, liquid cooling, semiconductors, and other market themes.
2. Screen stocks based on theme relevance, market capitalization, liquidity, turnover, momentum, capital activity, and volatility.
3. Generate a structured "Core Pool" and "Watch Pool" for short-term trend tracking.
4. Backtest moving average, RSI, and theme momentum strategies.
5. Output performance metrics including win rate, total return, annualized return, maximum drawdown, Sharpe ratio, trade count, profit factor, and average holding period.
6. Export research reports in Markdown, CSV, Excel, or chart image format.

## Typical User Requests

- "帮我监控 NVIDIA 产业链，筛选 A 股中小市值弹性标的。"
- "用 5/20 均线策略回测联特科技过去两年的表现。"
- "生成今日 AI 算力核心池和观察池。"
- "比较 RSI 策略和均线策略在光模块板块的回测结果。"
- "对 AMD/NVIDIA 催化事件相关标的做短线趋势跟踪。"

## Inputs

The user may provide:

- Market: A-shares, Hong Kong stocks, US stocks
- Themes: NVIDIA, AMD, AI computing, optical modules, PCB, CPO, copper connection, liquid cooling
- Stock universe
- Market cap range
- Liquidity filters
- Turnover filters
- Backtest period
- Strategy type
- Strategy parameters
- Risk controls

## Outputs

The skill can generate:

- Daily catalyst summary
- Theme strength ranking
- Core stock pool
- Watch stock pool
- Exclusion list
- Backtest result table
- Strategy performance report
- Net value curve
- Drawdown chart
- Parameter optimization results

## Workflow

1. Parse user request.
2. Identify relevant market themes and catalyst keywords.
3. Pull market, news, announcement, and price data from configured providers.
4. Clean and normalize data.
5. Score stocks by theme relevance, liquidity, trend strength, capital activity, market cap elasticity, and volatility.
6. Generate Core Pool and Watch Pool.
7. Run selected backtest strategy.
8. Calculate performance metrics.
9. Export report.

## Safety and Compliance Boundaries

The skill must not:

- Provide direct buy, sell, or hold instructions.
- Claim that a stock will definitely rise or fall.
- Claim guaranteed returns.
- Recommend leverage, margin, full-position, or heavy-position actions.
- Present historical backtest performance as future expected performance.
- Treat incomplete or unverified data as confirmed fact.

The skill may:

- Say that a stock enters a research pool based on configured rules.
- Explain why a stock has high theme relevance.
- Report historical backtest metrics.
- Discuss risk factors and data limitations.
- Encourage independent verification and professional consultation.

## Disclaimer

This skill is for educational and research purposes only. It does not provide financial, investment, tax, or legal advice. Users should not rely on the output as a basis for trading decisions without independent verification and professional consultation.



## Enhanced Edition Capabilities

The enhanced edition adds the following research workflows:

1. News and catalyst parsing
   - Reads local news CSV or normalized RSS/news-provider data.
   - Extracts theme-level catalyst hits by keyword.
   - Produces a catalyst strength table.

2. Theme strength index
   - Combines catalyst intensity, average stock price change, turnover, and volume ratio.
   - Outputs theme ranking such as NVIDIA chain, AMD chain, optical communication, PCB, liquid cooling.

3. Enhanced stock pool builder
   - Joins universe data, quote data, and catalyst data.
   - Scores stocks by theme relevance, money strength, trend strength, market-cap elasticity, and catalyst strength.
   - Generates Core Pool, Watch Pool, and Exclusion Pool.

4. Batch backtesting
   - Runs a strategy across multiple symbols.
   - Exports summary metrics to Excel or CSV.

5. Parameter optimization
   - Searches MA and RSI parameter combinations.
   - Exports ranked optimization results.

6. Daily report generation
   - Creates Markdown and Excel reports.
   - Includes theme strength, core/watch pools, catalysts, and risk warnings.

7. Push notification template
   - Provides webhook-based push messaging.
   - Can be adapted to Enterprise WeChat, Feishu, DingTalk, Telegram, or custom webhook services.

## Enhanced Edition Commands

```bash
python examples/run_enhanced_daily.py
python examples/run_parameter_optimization.py
python examples/run_batch_backtest.py
```

## Data Provider Notes

The provider layer is intentionally abstract. In production, plug in authorized data sources only:

- AkShare / Tushare for research-oriented market data.
- Licensed Eastmoney, Tonghuashun/iFinD, Wind, Choice, Bloomberg, Refinitiv, or broker APIs where available.
- Local CSV fallback for reproducible testing.

Always check data licensing, API terms, rate limits, and compliance requirements before live usage.

## Financial Safety Boundary

This skill must not output direct buy/sell/hold instructions, guaranteed return claims, or position-sizing orders. It may output research classifications such as "core pool", "watch pool", "excluded by filter", "historical backtest result", and "risk flags".

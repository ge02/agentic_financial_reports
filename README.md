# 📈 DAX AI Financial Reporter

An agentic AI-powered financial reporter that automatically fetches trading data for all DAX 40 stocks, analyzes market activity over the last 5 working days, and generates a structured, human-readable financial report.

---

## 🧠 What It Does

The agent autonomously:

1. **Fetches** the current list of all DAX 40 constituent stocks via `pytickersymbols`
2. **Pulls** the last 5 trading days of OHLCV data (Open, High, Low, Close, Volume) for each stock via `yfinance`
3. **Analyzes** performance metrics: price change, % gain/loss, volume trends, top movers, sector performance
4. **Generates** a structured Markdown or HTML financial report summarizing DAX activity
5. **Optionally emails or saves** the report as a file or web dashboard

---

## 📡 Data Sources

No paid subscription or API key required to get started.

| Source | Library | API Key Required | Notes |
|---|---|---|---|
| Yahoo Finance | `yfinance` | ❌ No | Primary data source — free, ~2,000 req/hour |
| DAX ticker list | `pytickersymbols` | ❌ No | Provides up-to-date DAX 40 Yahoo tickers |
| Alpha Vantage | `alpha_vantage` | ✅ Yes (free tier) | Optional fallback; 5 req/min on free plan |
| Finnhub | `finnhub-python` | ✅ Yes (free tier) | Optional — good for news & sentiment data |

> **Recommended setup:** Use `yfinance` + `pytickersymbols` for zero-friction local development. Switch to Alpha Vantage or Finnhub for production deployments needing higher reliability.

---

## 🗂️ Project Structure

```
dax-ai-reporter/
│
├── agent/
│   ├── __init__.py
│   ├── data_fetcher.py        # Fetches DAX stock data via yfinance
│   ├── analyzer.py            # Computes metrics: movers, trends, summary stats
│   ├── report_generator.py    # Calls Claude API to write the narrative report
│   └── scheduler.py           # Optional: runs the agent on a schedule (cron / APScheduler)
│
├── templates/
│   └── report_template.md     # Markdown template for the generated report
│
├── output/
│   └── reports/               # Generated reports saved here (date-stamped)
│
├── tests/
│   ├── test_fetcher.py
│   └── test_analyzer.py
│
├── .env.example               # Environment variable template
├── requirements.txt
├── main.py                    # Entry point — run this to generate a report
└── README.md
```

---

## ⚙️ How It Works — Agent Flow

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │  1. Fetch DAX 40 tickers      │
         │     (pytickersymbols)         │
         └──────────────┬────────────────┘
                        │
                        ▼
         ┌───────────────────────────────┐
         │  2. Download last 5 trading   │
         │     days of OHLCV data        │
         │     (yfinance, .DE tickers)   │
         └──────────────┬────────────────┘
                        │
                        ▼
         ┌───────────────────────────────┐
         │  3. Analyze market data       │
         │     - Top gainers / losers    │
         │     - Index-level summary     │
         │     - Volume anomalies        │
         │     - Sector breakdown        │
         └──────────────┬────────────────┘
                        │
                        ▼
         ┌───────────────────────────────┐
         │  4. Generate report via       │
         │     Claude AI (narrative +    │
         │     structured data)          │
         └──────────────┬────────────────┘
                        │
                        ▼
         ┌───────────────────────────────┐
         │  5. Save / export report      │
         │     (Markdown, HTML, email)   │
         └───────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- An Anthropic API key (for the AI report generation step)

### Installation

```bash
git clone https://github.com/your-username/dax-ai-reporter.git
cd dax-ai-reporter

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
# Required
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional — only needed if using Alpha Vantage as fallback
ALPHA_VANTAGE_API_KEY=your_key_here

# Optional — report output settings
REPORT_OUTPUT_DIR=output/reports
REPORT_FORMAT=markdown   # Options: markdown, html
```

### Run the Reporter

```bash
python main.py
```

This will generate a report in `output/reports/` named with the current date, e.g. `dax_report_2026-04-24.md`.

---

## 📊 Sample Report Output

```
# DAX 40 Market Report — 24 April 2026

## 5-Day Summary (18 Apr – 24 Apr 2026)

The DAX 40 ended the week up **+1.8%**, driven largely by gains in the
technology and automotive sectors. Volatility remained moderate, with the
index trading in a range of 17,820 – 18,350 points.

## 🏆 Top Gainers

| Stock       | Ticker  | 5D Change | Close  |
|-------------|---------|-----------|--------|
| Siemens     | SIE.DE  | +5.2%     | €178.40|
| SAP SE      | SAP.DE  | +4.1%     | €192.10|
| Infineon    | IFX.DE  | +3.8%     | €34.62 |

## 📉 Top Losers

| Stock       | Ticker  | 5D Change | Close  |
|-------------|---------|-----------|--------|
| Bayer AG    | BAYN.DE | -3.1%     | €28.44 |
| Vonovia     | VNA.DE  | -2.4%     | €25.90 |

## 📈 Volume Analysis

Unusual volume spikes were detected in Deutsche Telekom (+87% above 30-day
avg) and Rheinmetall (+62%), suggesting heightened institutional interest.

## 🤖 AI Commentary

*Generated by Claude:*
"The DAX showed resilience this week amid ongoing uncertainty around
European interest rate policy. Cyclical sectors led the recovery while
real estate continued to face headwinds from elevated borrowing costs..."
```

---

## 🧩 Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Data fetching | `yfinance`, `pytickersymbols` |
| Data processing | `pandas`, `numpy` |
| AI report writing | Anthropic Claude API (`anthropic` SDK) |
| Scheduling (optional) | `APScheduler` or system cron |
| Report rendering | Markdown / Jinja2 HTML templates |
| Testing | `pytest` |

---

## 🔮 Planned Features

- [ ] Interactive HTML report with charts (using `plotly`)
- [ ] Email delivery via SendGrid or SMTP
- [ ] Slack / Teams notification integration
- [ ] Watchlist alerts for abnormal price movements
- [ ] Sentiment analysis from financial news headlines (Finnhub)
- [ ] Weekly/monthly trend comparisons
- [ ] Docker container for easy deployment
- [ ] News scraper searching Twitter/Reddit/Instagram etc. for news related to DAX movement, 

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙋 Contributing

Pull requests are welcome! Please open an issue first to discuss what you'd like to change.
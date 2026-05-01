#!/usr/bin/env python3
"""DAX AI Financial Reporter — entry point."""

import os
import time
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf
from pytickersymbols import PyTickerSymbols
import anthropic
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path(os.getenv("REPORT_OUTPUT_DIR", "output/reports"))
REPORT_FORMAT = os.getenv("REPORT_FORMAT", "markdown")


# ---------------------------------------------------------------------------
# Step 1 — Fetch DAX 40 tickers
# ---------------------------------------------------------------------------

def _valid_yahoo_ticker(t: str) -> bool:
    """Reject malformed tickers like AIR.PA.DE (multiple exchange suffixes)."""
    parts = t.split(".")
    return len(parts) == 2 and len(parts[-1]) in (1, 2, 3)


def get_dax_tickers() -> list[dict]:
    pts = PyTickerSymbols()
    stocks = []
    for stock in pts.get_stocks_by_index("DAX"):
        # pytickersymbols stores the primary ticker in "symbol" (e.g. "ADS.DE")
        symbol = stock.get("symbol", "")
        yahoo_ticker = symbol if _valid_yahoo_ticker(symbol) else None

        if not yahoo_ticker:
            # Fallback: scan symbols list — prefer .DE, then .F (Frankfurt, EUR)
            candidates = [s.get("yahoo", "") for s in stock.get("symbols", [])]
            for suffix in (".DE", ".F"):
                for c in candidates:
                    if c.endswith(suffix) and _valid_yahoo_ticker(c):
                        yahoo_ticker = c
                        break
                if yahoo_ticker:
                    break

        if yahoo_ticker:
            stocks.append({
                "name": stock.get("name", yahoo_ticker),
                "ticker": yahoo_ticker,
                "industries": stock.get("industries", []),
            })
    return stocks


# ---------------------------------------------------------------------------
# Step 2 — Download OHLCV data
# ---------------------------------------------------------------------------

_REQUEST_PAUSE = 1.0      # seconds between tickers
_RETRY_WAITS = [30, 60]  # backoff schedule on rate-limit errors


def _fetch_ticker(ticker: str) -> tuple[pd.Series | None, pd.Series | None]:
    for attempt, wait in enumerate([0] + _RETRY_WAITS):
        if wait:
            print(f"     Rate limited — waiting {wait}s before retry {attempt}/{len(_RETRY_WAITS)}...")
            time.sleep(wait)
        try:
            hist = yf.Ticker(ticker).history(period="15d", auto_adjust=True)
            if not hist.empty:
                return hist["Close"], hist["Volume"]
            return None, None
        except Exception as e:
            if "rate" not in str(e).lower() and "429" not in str(e):
                print(f"     Warning: {ticker} skipped ({e})")
                return None, None
            if attempt == len(_RETRY_WAITS):
                print(f"     Warning: {ticker} skipped after {attempt + 1} attempts (still rate limited)")
                return None, None
    return None, None


def fetch_ohlcv(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    closes: dict[str, pd.Series] = {}
    volumes: dict[str, pd.Series] = {}
    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(_REQUEST_PAUSE)
        close_s, volume_s = _fetch_ticker(ticker)
        if close_s is not None:
            closes[ticker] = close_s
            volumes[ticker] = volume_s

    if not closes:
        return pd.DataFrame(), pd.DataFrame()

    close = pd.DataFrame(closes).dropna(how="all").tail(5)
    volume = pd.DataFrame(volumes).dropna(how="all").tail(5)
    return close, volume


# ---------------------------------------------------------------------------
# Step 3 — Analyze
# ---------------------------------------------------------------------------

def analyze(stocks: list[dict], close: pd.DataFrame, volume: pd.DataFrame) -> dict:
    if close.empty or len(close) < 2:
        raise ValueError(f"Not enough data: {len(close)} trading day(s) fetched. Check your internet connection or try again later.")

    ticker_map = {s["ticker"]: s for s in stocks}

    returns = (close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100

    vol_avg = volume.mean()
    vol_last = volume.iloc[-1]
    vol_spike = ((vol_last - vol_avg) / vol_avg * 100).dropna()

    def stock_info(ticker, value):
        info = ticker_map.get(ticker, {})
        return {"ticker": ticker, "name": info.get("name", ticker), "value": round(float(value), 2)}

    top_gainers = [stock_info(t, v) for t, v in returns.nlargest(5).items()]
    top_losers = [stock_info(t, v) for t, v in returns.nsmallest(5).items()]
    vol_spikes = [stock_info(t, v) for t, v in vol_spike.nlargest(5).items()]

    sector_buckets: dict[str, list[float]] = {}
    for ticker, ret in returns.items():
        industries = ticker_map.get(ticker, {}).get("industries", [])
        sector = industries[0] if industries else "Other"
        sector_buckets.setdefault(sector, []).append(float(ret))
    sector_avg = {s: round(sum(v) / len(v), 2) for s, v in sector_buckets.items()}

    return {
        "date": date.today().strftime("%d %B %Y"),
        "period": f"{close.index[0].strftime('%d %b')} – {close.index[-1].strftime('%d %b %Y')}",
        "dax_avg_return": round(float(returns.mean()), 2),
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "vol_spikes": vol_spikes,
        "sector_performance": sector_avg,
    }


# ---------------------------------------------------------------------------
# Step 4 — Generate AI commentary via Claude
# ---------------------------------------------------------------------------

def _build_data_summary(analysis: dict) -> str:
    lines = [
        f"Report date: {analysis['date']}",
        f"Period: {analysis['period']}",
        f"DAX 40 average 5-day return: {analysis['dax_avg_return']:+.2f}%",
        "",
        "Top 5 Gainers:",
        *[f"  {s['name']} ({s['ticker']}): {s['value']:+.2f}%" for s in analysis["top_gainers"]],
        "",
        "Top 5 Losers:",
        *[f"  {s['name']} ({s['ticker']}): {s['value']:+.2f}%" for s in analysis["top_losers"]],
        "",
        "Unusual Volume (vs 5-day avg):",
        *[f"  {s['name']} ({s['ticker']}): +{s['value']:.0f}% above average" for s in analysis["vol_spikes"]],
        "",
        "Sector Performance:",
        *[
            f"  {sector}: {ret:+.2f}%"
            for sector, ret in sorted(analysis["sector_performance"].items(), key=lambda x: -x[1])
        ],
    ]
    return "\n".join(lines)


def generate_ai_commentary(analysis: dict) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "_AI commentary unavailable — set ANTHROPIC_API_KEY in your .env file._"

    client = anthropic.Anthropic(api_key=api_key)
    data_summary = _build_data_summary(analysis)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": (
                    "You are a professional financial analyst specialising in European equity markets. "
                    "Write concise, insightful commentary for a DAX 40 weekly report. "
                    "Be factual and direct. Avoid excessive hedging. Keep under 250 words."
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write market commentary for the following DAX 40 data:\n\n{data_summary}\n\n"
                    "Use 2–3 short paragraphs: (1) overall market direction, "
                    "(2) notable movers and sector trends, (3) volume signals."
                ),
            }
        ],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Step 5 — Render & save report
# ---------------------------------------------------------------------------

def _md_table(rows: list[dict], headers: list[str], cols: list[str]) -> str:
    sep = "|" + "|".join("---" for _ in headers) + "|"
    header = "|" + "|".join(headers) + "|"
    body = "\n".join("|" + "|".join(str(row[c]) for c in cols) + "|" for row in rows)
    return f"{header}\n{sep}\n{body}"


def render_report(analysis: dict, commentary: str) -> str:
    sign = "+" if analysis["dax_avg_return"] >= 0 else ""

    gainers_rows = [
        {"Stock": s["name"], "Ticker": s["ticker"], "5D Change": f"{s['value']:+.2f}%"}
        for s in analysis["top_gainers"]
    ]
    losers_rows = [
        {"Stock": s["name"], "Ticker": s["ticker"], "5D Change": f"{s['value']:+.2f}%"}
        for s in analysis["top_losers"]
    ]
    vol_rows = [
        {"Stock": s["name"], "Ticker": s["ticker"], "% Above 5D Avg": f"+{s['value']:.0f}%"}
        for s in analysis["vol_spikes"]
    ]
    sector_rows = [
        {"Sector": sector, "5D Avg Return": f"{ret:+.2f}%"}
        for sector, ret in sorted(analysis["sector_performance"].items(), key=lambda x: -x[1])
    ]

    return f"""# DAX 40 Market Report — {analysis['date']}

## 5-Day Summary ({analysis['period']})

DAX 40 average return: **{sign}{analysis['dax_avg_return']:.2f}%**

## Top Gainers

{_md_table(gainers_rows, ["Stock", "Ticker", "5D Change"], ["Stock", "Ticker", "5D Change"])}

## Top Losers

{_md_table(losers_rows, ["Stock", "Ticker", "5D Change"], ["Stock", "Ticker", "5D Change"])}

## Volume Spikes

{_md_table(vol_rows, ["Stock", "Ticker", "% Above 5D Avg"], ["Stock", "Ticker", "% Above 5D Avg"])}

## Sector Performance

{_md_table(sector_rows, ["Sector", "5D Avg Return"], ["Sector", "5D Avg Return"])}

## AI Commentary

*Generated by Claude:*

{commentary}

---
*Report generated {analysis['date']} · DAX AI Financial Reporter*
"""


def save_report(content: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")

    if REPORT_FORMAT == "html":
        import markdown as md
        html_body = md.markdown(content, extensions=["tables"])
        content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>DAX Report {today}</title>
  <style>
    body {{ font-family: sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 1rem; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f5f5f5; }}
  </style>
</head>
<body>{html_body}</body>
</html>"""
        path = OUTPUT_DIR / f"dax_report_{today}.html"
    else:
        path = OUTPUT_DIR / f"dax_report_{today}.md"

    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("DAX AI Financial Reporter")
    print("=" * 40)

    print("1/5  Fetching DAX 40 tickers...")
    stocks = get_dax_tickers()
    print(f"     {len(stocks)} stocks found")

    print("2/5  Downloading OHLCV data (last 5 trading days)...")
    close, volume = fetch_ohlcv([s["ticker"] for s in stocks])
    if close.empty:
        print("     No data returned — rate limited or no connection. Try again in a minute.")
        return
    print(f"     {len(close.columns)} tickers × {len(close)} days")

    print("3/5  Analyzing market data...")
    analysis = analyze(stocks, close, volume)

    print("4/5  Generating AI commentary via Claude...")
    commentary = generate_ai_commentary(analysis)

    print("5/5  Rendering and saving report...")
    report = render_report(analysis, commentary)
    path = save_report(report)

    print(f"\nDone. Report saved to: {path}")


if __name__ == "__main__":
    main()

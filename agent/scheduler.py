#!/usr/bin/env python3
"""
Weekday scheduler for the DAX AI Financial Reporter.

Runs the full pipeline every weekday at 06:00 local time and delivers
a compact summary to WhatsApp via Twilio.

Usage:
    python agent/scheduler.py          # run scheduler (blocks)
    python agent/scheduler.py --now    # run once immediately, then exit
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import (
    analyze,
    fetch_ohlcv,
    generate_ai_commentary,
    get_dax_tickers,
    render_report,
    save_report,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WhatsApp formatting
# ---------------------------------------------------------------------------

def format_whatsapp_message(analysis: dict, commentary: str) -> str:
    """Build a concise WhatsApp-friendly summary (uses *bold* and plain text)."""
    avg = analysis["dax_avg_return"]
    sign = "+" if avg >= 0 else ""
    arrow = "📈" if avg >= 0 else "📉"

    gainers = "\n".join(
        f"  {s['name']} ({s['ticker']}): {s['value']:+.2f}%"
        for s in analysis["top_gainers"][:3]
    )
    losers = "\n".join(
        f"  {s['name']} ({s['ticker']}): {s['value']:+.2f}%"
        for s in analysis["top_losers"][:3]
    )

    # Keep commentary under ~300 chars for readability on mobile
    short_commentary = commentary.strip()
    if len(short_commentary) > 300:
        short_commentary = short_commentary[:297] + "..."

    return (
        f"{arrow} *DAX 40 Report — {analysis['date']}*\n"
        f"Period: {analysis['period']}\n"
        f"Avg 5-day return: *{sign}{avg:.2f}%*\n"
        f"\n"
        f"*Top Gainers*\n{gainers}\n"
        f"\n"
        f"*Top Losers*\n{losers}\n"
        f"\n"
        f"*AI Commentary*\n{short_commentary}"
    )


# ---------------------------------------------------------------------------
# WhatsApp delivery
# ---------------------------------------------------------------------------

def send_whatsapp(message: str) -> bool:
    """
    Send a WhatsApp message via Twilio.
    Returns True on success, False on failure.

    Required environment variables:
        TWILIO_ACCOUNT_SID   — from console.twilio.com
        TWILIO_AUTH_TOKEN    — from console.twilio.com
        TWILIO_WHATSAPP_FROM — e.g. whatsapp:+14155238886 (sandbox number)
        WHATSAPP_TO          — your number, e.g. whatsapp:+491701234567
    """
    sid   = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_ = os.getenv("TWILIO_WHATSAPP_FROM")
    to    = os.getenv("WHATSAPP_TO")

    if not all([sid, token, from_, to]):
        log.warning("WhatsApp not configured — skipping delivery. "
                    "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                    "TWILIO_WHATSAPP_FROM, and WHATSAPP_TO in .env")
        return False

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        msg = client.messages.create(body=message, from_=from_, to=to)
        log.info("WhatsApp message sent — SID: %s", msg.sid)
        return True
    except Exception as e:
        log.error("WhatsApp delivery failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Pipeline job
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    log.info("Starting DAX pipeline...")

    stocks = get_dax_tickers()
    log.info("Tickers: %d stocks", len(stocks))

    close, volume = fetch_ohlcv([s["ticker"] for s in stocks])
    if close.empty:
        log.error("No OHLCV data returned — aborting.")
        return
    log.info("Data: %d tickers × %d days", len(close.columns), len(close))

    analysis = analyze(stocks, close, volume)
    log.info("Analysis complete. DAX avg return: %+.2f%%", analysis["dax_avg_return"])

    commentary = generate_ai_commentary(analysis)
    log.info("AI commentary generated.")

    report = render_report(analysis, commentary)
    path = save_report(report)
    log.info("Report saved to %s", path)

    whatsapp_msg = format_whatsapp_message(analysis, commentary)
    send_whatsapp(whatsapp_msg)

    log.info("Pipeline complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="DAX AI Financial Reporter scheduler")
    parser.add_argument(
        "--now", action="store_true",
        help="Run the pipeline once immediately and exit (skip scheduling)"
    )
    args = parser.parse_args()

    if args.now:
        run_pipeline()
        return

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=6,
            minute=0,
        ),
        name="dax_reporter",
        misfire_grace_time=3600,  # run even if delayed up to 1h (e.g. machine wake)
    )

    log.info("Scheduler started — DAX report will run every weekday at 06:00.")
    log.info("Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()

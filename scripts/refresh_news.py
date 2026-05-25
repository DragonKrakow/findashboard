#!/usr/bin/env python3
"""
refresh_news.py
───────────────
Fetches RSS feeds, deduplicates articles, asks Groq to classify and
summarise each one, then writes the results to data/news.json.
Also generates a structured AI analysis block (headline, themes, risks,
opportunities) in data/market.json and updates signals data with live
prices fetched via yfinance.

Run locally:
    GROQ_API_KEY=gsk_... python scripts/refresh_news.py

In GitHub Actions:
    Set GROQ_API_KEY as a repository secret — never hard-code it here.
"""

import json
import os
import sys
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import feedparser
from dateutil import parser as dateparser
from groq import Groq

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

RSS_FEEDS = [
    # Finance / macro
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.ft.com/?format=rss",
    # Crypto
    "https://cointelegraph.com/rss",
    "https://coindesk.com/arc/outboundfeeds/rss/",
    # Tech / markets
    "https://www.wsj.com/xml/rss/3_7085.xml",
    "https://seekingalpha.com/feed.xml",
]

GROQ_MODEL   = "llama3-70b-8192"   # fast, cheap, high-quality
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "10"))
DATA_DIR     = Path(__file__).parent.parent / "data"

CATEGORIES = ["macro", "earnings", "crypto", "commodities", "tech", "fx", "other"]

SYSTEM_PROMPT = """You are a professional financial analyst assistant.
Given a news article title and body (may be truncated), respond with a JSON object:
{
  "category": "<one of: macro | earnings | crypto | commodities | tech | fx | other>",
  "sentiment": "<bullish | bearish | neutral>",
  "signal":    "<buy | sell | hold | watch>",
  "summary":   "<2-3 sentence plain-English summary, 60-120 words, no markdown>",
  "tags":      ["<tag1>", "<tag2>", ...]
}
Rules:
- summary must be factual and concise
- tags should be lowercase ticker symbols or keywords (max 5)
- respond with ONLY the JSON, no preamble
"""

# ── Helpers ──────────────────────────────────────────────────────────────────

def article_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def fetch_feeds() -> list[dict]:
    """Fetch all configured RSS feeds and return a flat list of raw entries."""
    entries: list[dict] = []
    for feed_url in RSS_FEEDS:
        try:
            log.info(f"Fetching {feed_url}")
            feed = feedparser.parse(feed_url, agent="FinDashboard/1.0")
            for entry in feed.entries[:MAX_ARTICLES]:
                entries.append({
                    "title":  entry.get("title", ""),
                    "url":    entry.get("link", ""),
                    "source": feed.feed.get("title", feed_url),
                    "body":   entry.get("summary", entry.get("description", ""))[:500],
                    "published_at": _parse_date(entry),
                })
        except Exception as exc:
            log.warning(f"Failed to fetch {feed_url}: {exc}")
    return entries


def _parse_date(entry) -> str:
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                return dateparser.parse(raw).astimezone(timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def deduplicate(entries: list[dict]) -> list[dict]:
    """Remove duplicates by URL."""
    seen: set[str] = set()
    unique: list[dict] = []
    for e in entries:
        key = e["url"]
        if key and key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def classify_with_groq(client: Groq, entry: dict) -> dict | None:
    """Ask Groq to classify/summarise a single article. Returns parsed JSON or None."""
    user_msg = f"Title: {entry['title']}\n\nBody: {entry['body']}"
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content
        return json.loads(text)
    except Exception as exc:
        log.warning(f"Groq classification failed for '{entry['title'][:40]}': {exc}")
        return None

AI_ANALYSIS_PROMPT = """You are a senior financial market strategist.
Given a list of recent news headlines and their categories/sentiments, write a brief market analysis.
Respond with a JSON object:
{
  "headline": "<10-15 word bold thesis statement>",
  "body": "<3-4 sentence balanced market overview, 80-120 words>",
  "key_themes": ["<theme1>", "<theme2>", "<theme3>", "<theme4>", "<theme5>"],
  "risks": ["<risk1 – short>", "<risk2 – short>", "<risk3 – short>"],
  "opportunities": ["<opportunity1 – short>", "<opportunity2 – short>", "<opportunity3 – short>"]
}
Rules:
- Be factual and balanced (not overly bullish or bearish)
- key_themes should identify dominant market narratives
- risks should be concrete, near-term downside scenarios
- opportunities should be actionable asset/sector ideas
- Respond with ONLY the JSON, no preamble
"""


def generate_ai_analysis(client: Groq, articles: list[dict]) -> dict | None:
    """Ask Groq to produce a structured market analysis from the classified articles."""
    if not articles:
        return None

    # Build a brief summary of what was in the news
    news_snapshot = "\n".join(
        f"- [{a['category']}|{a['sentiment']}] {a['title']}"
        for a in articles[:30]
    )
    user_msg = f"Recent financial news headlines:\n{news_snapshot}"

    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": AI_ANALYSIS_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as exc:
        log.warning(f"AI analysis generation failed: {exc}")
        return None


def update_market_json(ai_analysis: dict | None) -> None:
    """Merge the fresh AI analysis block into data/market.json (preserves other fields)."""
    market_path = DATA_DIR / "market.json"
    try:
        market = json.loads(market_path.read_text())
    except Exception:
        log.warning("Could not read market.json — skipping AI analysis merge")
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    # Update the top-level refresh timestamp for the whole file
    market["generated_at"] = now_iso

    if ai_analysis:
        # Embed the same timestamp inside the analysis block so the frontend
        # can display when this specific analysis was generated independently
        # of when other market fields (indices, macro) were last updated.
        ai_analysis["generated_at"] = now_iso
        market["ai_analysis"] = ai_analysis
        log.info("Updated ai_analysis block in market.json")

    market_path.write_text(json.dumps(market, indent=2, ensure_ascii=False))
    log.info(f"Updated market.json ({market_path})")



# ── Live price refresh ────────────────────────────────────────────────────────

# Mapping from dashboard ticker labels to yfinance symbols
_TICKER_MAP = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
}


def update_signals_prices() -> None:
    """
    Update prices and sparklines (last 14 trading days) in data/signals.json
    using yfinance.  15 days of data are fetched to guarantee 14 usable points
    after dropping any NaN values at the start of the period.  Runs after
    classify_with_groq so price data is always refreshed even if Groq
    classification is partially skipped.  Safe to no-op if yfinance is
    unavailable.
    """
    if not HAS_YFINANCE:
        log.warning("yfinance not installed — skipping live price refresh.")
        return

    signals_path = DATA_DIR / "signals.json"
    try:
        signals = json.loads(signals_path.read_text())
    except Exception as exc:
        log.warning(f"Could not read signals.json: {exc}")
        return

    watchlist = signals.get("watchlist", [])
    if not watchlist:
        return

    # Build list of symbols for a single batch download
    symbols = [_TICKER_MAP.get(item["ticker"], item["ticker"]) for item in watchlist]
    log.info(f"Fetching live prices for: {symbols}")

    try:
        hist = yf.download(
            symbols,
            period="15d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        close = hist["Close"] if "Close" in hist.columns else hist
    except Exception as exc:
        log.warning(f"yfinance download failed: {exc}")
        return

    for item in watchlist:
        yf_sym = _TICKER_MAP.get(item["ticker"], item["ticker"])
        try:
            if len(symbols) == 1:
                series = close
            else:
                series = close[yf_sym]
            series = series.dropna()
            if len(series) < 2:
                log.warning(f"  Insufficient data for {item['ticker']} ({yf_sym}): only {len(series)} point(s)")
                continue
            prev_close = float(series.iloc[-2])
            last_close = float(series.iloc[-1])
            change_pct = (last_close - prev_close) / prev_close * 100 if prev_close else 0.0
            # Use up to 14 trailing data points; may be fewer if less history is available
            sparkline   = [round(float(v), 4) for v in series.iloc[-14:].tolist()]
            item["price"]      = round(last_close, 4)
            item["change_pct"] = round(change_pct, 4)
            item["sparkline"]  = sparkline
            log.info(f"  {item['ticker']}: {last_close:.2f} ({change_pct:+.2f}%)")
        except Exception as exc:
            log.warning(f"  Could not update {item['ticker']} ({yf_sym}): {exc}")

    signals["generated_at"] = datetime.now(timezone.utc).isoformat()
    signals_path.write_text(json.dumps(signals, indent=2, ensure_ascii=False))
    log.info(f"Updated signals.json with live prices → {signals_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        log.error("GROQ_API_KEY environment variable is not set.")
        sys.exit(1)

    client = Groq(api_key=api_key)

    log.info("Fetching RSS feeds…")
    raw = fetch_feeds()
    entries = deduplicate(raw)
    log.info(f"  → {len(raw)} raw entries, {len(entries)} after deduplication")

    articles: list[dict] = []
    for idx, entry in enumerate(entries):
        log.info(f"  [{idx+1}/{len(entries)}] Classifying: {entry['title'][:60]}")
        info = classify_with_groq(client, entry)
        if info is None:
            # Fallback with minimal metadata
            info = {
                "category":  "other",
                "sentiment": "neutral",
                "signal":    "watch",
                "summary":   entry["body"][:200] or entry["title"],
                "tags":      [],
            }
        articles.append({
            "id":           article_id(entry["url"]),
            "title":        entry["title"],
            "source":       entry["source"],
            "url":          entry["url"],
            "published_at": entry["published_at"],
            "category":     info.get("category", "other"),
            "sentiment":    info.get("sentiment", "neutral"),
            "signal":       info.get("signal", "watch"),
            "summary":      info.get("summary", ""),
            "tags":         info.get("tags", [])[:5],
        })

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "articles":     articles,
    }

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "news.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    log.info(f"Wrote {len(articles)} articles → {out_path}")

    # Generate structured AI market analysis and merge into market.json
    log.info("Generating AI market analysis…")
    ai_analysis = generate_ai_analysis(client, articles)
    update_market_json(ai_analysis)

    # Refresh live prices in signals.json via yfinance
    log.info("Refreshing live prices in signals.json…")
    update_signals_prices()


if __name__ == "__main__":
    main()

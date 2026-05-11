#!/usr/bin/env python3
"""
refresh_news.py
───────────────
Fetches RSS feeds, deduplicates articles, asks Groq to classify and
summarise each one, then writes the results to data/news.json.

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


if __name__ == "__main__":
    main()

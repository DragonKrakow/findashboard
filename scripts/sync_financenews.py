#!/usr/bin/env python3
"""
sync_financenews.py
-------------------
Reads public data files from DragonKrakow/financenews (read-only source repo)
and produces normalized catalog artifacts inside findashboard/data/catalog/.

Run locally or via GitHub Actions on a schedule.

Outputs
-------
data/catalog/instruments.json  – enriched instrument catalog (financenews watchlist merged with signals)
data/catalog/signals.json      – normalized signals from financenews
data/catalog/news.json         – normalized news articles from financenews
data/catalog/overview.json     – summary counts and freshness metadata
"""

import json
import pathlib
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FINANCENEWS_BASE = "https://raw.githubusercontent.com/DragonKrakow/financenews/main"

SOURCES = {
    "watchlist": f"{FINANCENEWS_BASE}/watchlist.json",
    "signals":   f"{FINANCENEWS_BASE}/signals.json",
    "news":      f"{FINANCENEWS_BASE}/data.json",
}

OUT_DIR = pathlib.Path(__file__).parent.parent / "data" / "catalog"

SNAPSHOT_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")
GENERATED_AT  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_json(url: str) -> object:
    """Fetch JSON from a URL; return None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "findashboard-sync/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, Exception) as exc:
        print(f"  WARNING: could not fetch {url}: {exc}", file=sys.stderr)
        return None


def write_json(path: pathlib.Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  wrote {path}  ({path.stat().st_size:,} bytes)")


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------

def normalize_watchlist(raw) -> list[dict]:
    """Convert financenews watchlist.json → catalog instrument list."""
    if not raw or not isinstance(raw, list):
        return []
    instruments = []
    for item in raw:
        sym = (item.get("symbol") or "").strip().upper()
        if not sym:
            continue
        inst_type = (item.get("type") or "").lower()
        if inst_type not in ("stock", "etf", "crypto", "bond", "index"):
            inst_type = "unknown"
        instruments.append({
            "id":              sym.lower().replace(".", "-"),
            "ticker":          sym,
            "name":            item.get("name") or sym,
            "instrument_type": inst_type,
            "sector":          None,
            "currency":        None,
            "market":          None,
            "exchange":        None,
            "country":         None,
            "isin":            None,
            "tags":            item.get("tags") or [],
            "source":          "financenews",
            "snapshot_date":   SNAPSHOT_DATE,
        })
    return instruments


def normalize_signals(raw) -> list[dict]:
    """Convert financenews signals.json → catalog signal list."""
    if not raw or not isinstance(raw, list):
        return []
    signals = []
    for item in raw:
        ticker = (item.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        headline = item.get("top_related_headline") or {}
        signals.append({
            "ticker":          ticker,
            "signal":          (item.get("signal") or "neutral").lower(),
            "confidence":      (item.get("confidence") or "low").lower(),
            "reasoning":       item.get("reasoning") or "",
            "action":          item.get("suggested_research_action") or "",
            "headline_title":  headline.get("title") or "",
            "headline_url":    headline.get("link") or "",
            "last_updated":    item.get("last_updated") or GENERATED_AT,
            "source":          "financenews",
        })
    return signals


def normalize_news(raw) -> list[dict]:
    """Convert financenews data.json → catalog news list."""
    if not raw or not isinstance(raw, list):
        return []
    articles = []
    for item in raw:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        sentiment_label = (item.get("sentiment_label") or "neutral").lower()
        # map to standard labels
        if "bull" in sentiment_label:
            sentiment = "bullish"
        elif "bear" in sentiment_label:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
        articles.append({
            "title":       title,
            "url":         item.get("link") or "",
            "source":      item.get("source") or "unknown",
            "published_at": item.get("published") or GENERATED_AT,
            "summary":     item.get("summary") or "",
            "sentiment":   sentiment,
            "sentiment_score": item.get("sentiment_score") or 0.0,
            "tags":        item.get("matched_keywords") or [],
            "signal":      "watch",
            "category":    _categorize(item),
            "source_repo": "financenews",
        })
    return articles


def _categorize(item: dict) -> str:
    kw = [k.lower() for k in (item.get("matched_keywords") or [])]
    title = (item.get("title") or "").lower()
    if any(k in kw or k in title for k in ["ai", "tech", "semiconductor", "software"]):
        return "technology"
    if any(k in kw or k in title for k in ["oil", "energy", "gas", "coal"]):
        return "energy"
    if any(k in kw or k in title for k in ["fed", "rate", "inflation", "ecb", "central bank"]):
        return "macro"
    if any(k in kw or k in title for k in ["defense", "military", "war", "geopolit"]):
        return "geopolitical"
    if any(k in kw or k in title for k in ["crypto", "bitcoin", "ethereum"]):
        return "crypto"
    return "markets"


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------

def merge_signals_into_instruments(instruments: list[dict], signals: list[dict]) -> list[dict]:
    """Enrich instruments with signal data where available."""
    sig_map = {s["ticker"]: s for s in signals}
    for inst in instruments:
        sig = sig_map.get(inst["ticker"])
        if sig:
            inst["signal"]     = sig["signal"]
            inst["confidence"] = sig["confidence"]
            inst["reasoning"]  = sig["reasoning"]
    return instruments


def build_overview(instruments: list[dict], signals: list[dict], news: list[dict],
                   source_status: dict) -> dict:
    by_type: dict[str, int] = {}
    for inst in instruments:
        t = inst.get("instrument_type") or "unknown"
        by_type[t] = by_type.get(t, 0) + 1

    signal_counts: dict[str, int] = {}
    for sig in signals:
        s = sig.get("signal") or "neutral"
        signal_counts[s] = signal_counts.get(s, 0) + 1

    return {
        "generated_at":    GENERATED_AT,
        "snapshot_date":   SNAPSHOT_DATE,
        "totals": {
            "catalog_instruments": len(instruments),
            "signals":             len(signals),
            "news_articles":       len(news),
        },
        "by_type":         by_type,
        "signal_summary":  signal_counts,
        "source_status":   source_status,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("sync_financenews.py – syncing from DragonKrakow/financenews …")

    source_status: dict[str, bool] = {}

    # Fetch
    print("  fetching watchlist …")
    raw_watchlist = fetch_json(SOURCES["watchlist"])
    source_status["watchlist"] = raw_watchlist is not None

    print("  fetching signals …")
    raw_signals = fetch_json(SOURCES["signals"])
    source_status["signals"] = raw_signals is not None

    print("  fetching news …")
    raw_news = fetch_json(SOURCES["news"])
    source_status["news"] = raw_news is not None

    # Normalize
    instruments = normalize_watchlist(raw_watchlist)
    signals     = normalize_signals(raw_signals)
    news        = normalize_news(raw_news)

    # Enrich instruments with signals
    instruments = merge_signals_into_instruments(instruments, signals)

    # Build overview
    overview = build_overview(instruments, signals, news, source_status)

    # Write outputs
    print(f"  writing to {OUT_DIR} …")
    write_json(OUT_DIR / "instruments.json", {
        "generated_at":  GENERATED_AT,
        "snapshot_date": SNAPSHOT_DATE,
        "source":        "financenews",
        "count":         len(instruments),
        "instruments":   instruments,
    })
    write_json(OUT_DIR / "signals.json", {
        "generated_at":  GENERATED_AT,
        "snapshot_date": SNAPSHOT_DATE,
        "source":        "financenews",
        "count":         len(signals),
        "signals":       signals,
    })
    write_json(OUT_DIR / "news.json", {
        "generated_at":  GENERATED_AT,
        "snapshot_date": SNAPSHOT_DATE,
        "source":        "financenews",
        "count":         len(news),
        "articles":      news,
    })
    write_json(OUT_DIR / "overview.json", overview)

    print("Done.")
    failed = [k for k, v in source_status.items() if not v]
    if failed:
        print(f"  WARNING: {len(failed)} source(s) failed: {', '.join(failed)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

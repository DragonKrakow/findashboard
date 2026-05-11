# FinDashboard Pro

A **GitHub Pages-ready financial dashboard** that shows market indices, macro indicators, watchlist signals, and an AI-curated news digest.  Data is refreshed automatically by **GitHub Actions** using the **Groq API** — no backend server required, no API keys exposed in the browser.

![Dashboard preview](https://raw.githubusercontent.com/DragonKrakow/findashboard/main/assets/preview.png)

---

## Features

| Feature | Details |
|---------|---------|
| 📈 Market indices | S&P 500, NASDAQ, Dow, FTSE 100, DAX, Nikkei |
| 🌍 Macro indicators | 10Y yield, DXY, Brent, Gold, VIX, EUR/USD |
| 😨 Fear & Greed gauge | Visual sentiment meter from 0 (Extreme Fear) to 100 (Extreme Greed) |
| 📋 Watchlist signals | Stocks, ETFs, and crypto with AI-generated Buy / Sell / Hold / Watch signals |
| 📰 AI News Digest | RSS feeds summarised by Groq LLaMA-3, filterable by category |
| 🤖 Auto-refresh | GitHub Actions cron job every 4 hours |
| 🔐 Secure | Groq API key stored as a GitHub secret — never in client-side code |

---

## Project Structure

```
findashboard/
├── index.html                    # Dashboard (reads from data/*.json)
├── data/
│   ├── news.json                 # AI-summarised articles (auto-generated)
│   ├── signals.json              # Watchlist & signals (auto-generated)
│   └── market.json               # Indices & macro data (auto-generated)
├── scripts/
│   └── refresh_news.py           # GitHub Actions refresh script
├── .github/
│   └── workflows/
│       └── refresh-news.yml      # Scheduled workflow (every 4 hours)
└── README.md
```

---

## Quick Start — Local Preview

No build step required; the dashboard is plain HTML + vanilla JavaScript.

```bash
# Clone the repo
git clone https://github.com/DragonKrakow/findashboard.git
cd findashboard

# Serve locally (Python built-in server works great)
python -m http.server 8080
# Then open http://localhost:8080 in your browser
```

> **Why a server?**  Browsers block `fetch()` calls to local `file://` paths.  Any static server works — Python, Node `serve`, VS Code Live Server, etc.

---

## GitHub Pages Deployment

1. Go to your repository on GitHub → **Settings → Pages**.
2. Under *Source*, choose **Deploy from a branch**.
3. Select branch `main` and directory `/ (root)`.
4. Click **Save**.
5. Your dashboard will be live at:
   ```
   https://dragonkrakow.github.io/findashboard/
   ```

The `index.html` at the root is automatically served by GitHub Pages.

---

## Setting Up the Groq API Key (Required for AI Refresh)

The refresh script calls the **Groq API** to classify and summarise each news article using the `llama3-70b-8192` model (free tier available).

### Step 1 — Get your Groq API key

1. Sign up / log in at [console.groq.com](https://console.groq.com).
2. Navigate to **API Keys → Create API Key**.
3. Copy the key (starts with `gsk_…`).

### Step 2 — Add the secret to GitHub

1. In your repository go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Name: `GROQ_API_KEY`
4. Value: paste your key.
5. Click **Add secret**.

> ⚠️ **Never** paste your API key into `index.html`, `refresh_news.py`, or any file that gets committed.  The workflow reads it from GitHub Secrets at runtime only.

---

## How the AI Refresh Works

```
┌─────────────────────────────────────────────────────────┐
│  GitHub Actions (every 4 hours or manual trigger)       │
│                                                         │
│  1. Fetch RSS feeds (Reuters, Bloomberg, CoinDesk …)    │
│  2. Deduplicate articles by URL                         │
│  3. For each article → ask Groq LLaMA-3:               │
│       • category  (macro / earnings / crypto / …)      │
│       • sentiment (bullish / bearish / neutral)         │
│       • signal    (buy / sell / hold / watch)           │
│       • summary   (2-3 sentence plain-English digest)   │
│       • tags      (ticker symbols / keywords)           │
│  4. Write results → data/news.json                      │
│  5. git commit + git push  →  GitHub Pages re-serves   │
└─────────────────────────────────────────────────────────┘
```

The **frontend** (`index.html`) only reads the pre-generated `data/*.json` files — no API calls from the browser, no exposed credentials.

### Manual Refresh

You can trigger a refresh at any time:

1. Go to **Actions → Refresh AI News Digest**.
2. Click **Run workflow**.
3. Optionally set *Maximum articles per feed* (default 10).
4. Click **Run workflow** to start.

### Customising RSS Feeds

Edit the `RSS_FEEDS` list in `scripts/refresh_news.py` to add or remove sources.  Any public RSS/Atom feed works.

---

## Running the Refresh Script Locally

```bash
# Install dependencies
pip install feedparser groq python-dateutil

# Set your key
export GROQ_API_KEY="gsk_your_key_here"

# Run
python scripts/refresh_news.py
```

The script writes to `data/news.json` and logs progress to stdout.

---

## Customisation

### Adding Tickers / Signals

Edit `data/signals.json` to add or remove watchlist entries.  Each entry has:

```json
{
  "ticker":     "AAPL",
  "name":       "Apple Inc.",
  "type":       "stock",
  "price":      213.45,
  "change_pct": 0.62,
  "signal":     "hold",
  "note":       "Brief analyst note here"
}
```

`type` can be `stock`, `etf`, or `crypto`.  `signal` can be `buy`, `sell`, `hold`, or `watch`.

### Updating Market / Macro Data

`data/market.json` contains indices and macro indicators.  You can update these manually or extend the GitHub Actions workflow with a free data API (e.g., Yahoo Finance via `yfinance`).

### Changing the Groq Model

Edit `GROQ_MODEL` in `scripts/refresh_news.py`.  The default is `llama3-70b-8192`.  Other options:

| Model | Notes |
|-------|-------|
| `llama3-70b-8192` | Best quality, default |
| `llama3-8b-8192`  | Faster, cheaper |
| `mixtral-8x7b-32768` | Longer context window |

See [Groq's model list](https://console.groq.com/docs/models) for the latest options.

---

## Architecture Notes (from Build Guide)

The architecture follows a **static-first** pattern to work within GitHub Pages constraints:

- **No backend server** — everything is pre-generated JSON committed to the repository.
- **GitHub Actions as the data pipeline** — runs on a schedule, fetches RSS, calls Groq, commits results.
- **Groq for AI** — fast inference via the free/paid Groq API (replaces direct Anthropic browser calls which are insecure).
- **Deduplication** — articles are deduplicated by URL before Groq classification to save API credits.
- **Telegram alerts** (optional) — add a `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secret and extend the workflow to `curl` the Bot API with high-signal articles.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Dashboard shows "Failed to load" | Run from a local web server, not `file://` |
| Actions workflow fails | Check `GROQ_API_KEY` secret is set correctly |
| No articles after refresh | Check RSS feed URLs are accessible from GitHub Actions runners |
| Groq API error 429 | You've hit the free-tier rate limit; reduce `MAX_ARTICLES` or upgrade |

---

## Licence

MIT — use freely, contribute back if you improve it.

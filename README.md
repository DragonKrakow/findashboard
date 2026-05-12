# FinDashboard Pro

A **GitHub Pages-ready financial dashboard** with tabbed navigation showing market indices, macro indicators, watchlist signals, geopolitical risk events, an AI analysis panel, and an AI-curated news digest. Data is refreshed automatically by **GitHub Actions** using the **Groq API** — no backend server required, no API keys exposed in the browser.

---

## Features

| Feature | Details |
|---------|---------|
| 📊 Overview dashboard | KPI tiles, sentiment gauge, AI analysis headline, top stories |
| 📈 Markets tab | All global indices with sparkline mini-charts, full macro snapshot |
| 💼 Portfolio tab | Enhanced watchlist with sector info, sparklines, buy/sell/hold/watch signals |
| 🤖 AI Insights tab | AI-generated market analysis, key themes, risks, and opportunities |
| 🌍 Geopolitical tab | Risk monitor cards with impact-sector tags and risk-level badges |
| 📰 News tab | RSS news classified by Groq AI — filterable by category, timeline view |
| 🔄 AI Refresh button | One-click button opens the GitHub Actions workflow page to trigger a data refresh |
| 🔐 Secure | Groq API key stored as a GitHub secret — never in client-side code |
| 📁 Reference copy | `FinDashboard_Pro.html` preserved with full documentation of the browser-side AI pattern (disabled/archive) |

---

## AI Refresh Button

The **🔄 Refresh AI** button in the top-right corner of the dashboard opens a modal that explains how the refresh works and provides a direct link to the GitHub Actions workflow page.

**How to trigger a refresh:**
1. Click **🔄 Refresh AI** in the dashboard header.
2. Click **↗ Open GitHub Actions** in the modal.
3. On the workflow page, click **Run workflow** → **Run workflow**.
4. The workflow fetches new RSS data, runs Groq AI classification, and commits updated JSON files.
5. GitHub Pages re-serves the fresh data within seconds.

> **Requirement:** You must be signed in to GitHub and have write access to the repository.

**Why not directly from the browser?** Calling AI APIs client-side exposes your secret API key to every visitor. This dashboard uses a *static-first* architecture where the workflow runs server-side in GitHub Actions with secrets stored safely. See `FinDashboard_Pro.html` for a documented demonstration of the browser-side pattern and its limitations.

---

## Project Structure

```
findashboard/
├── index.html                    # Live dashboard (tabbed, reads from data/*.json)
├── FinDashboard_Pro.html         # Reference/archive copy with browser-AI pattern notes
├── data/
│   ├── news.json                 # AI-summarised articles (auto-generated)
│   ├── signals.json              # Watchlist & signals with sparklines (auto-generated)
│   └── market.json               # Indices, macro, geopolitical & AI analysis (auto-generated)
├── scripts/
│   └── refresh_news.py           # GitHub Actions refresh script
├── .github/
│   └── workflows/
│       └── refresh-news.yml      # Scheduled workflow (every 4 hours)
└── README.md
```

---

## Dashboard Sections

### Overview tab
- Ticker strip with sparkline mini-charts for all tracked indices
- KPI tiles: Fear & Greed index, buy signal count, active geo-risk events, news count
- Market sentiment gauge
- AI market analysis headline
- Top 3 news stories

### Markets tab
- Full global indices table (US, EU, APAC) with sparklines
- Macro indicators: yields, DXY, commodities, VIX, FX pairs
- Sentiment gauge

### Portfolio tab
- Portfolio summary pills (total, buy/hold/sell/watch counts)
- Full watchlist table: ticker, name, type, sector, price, change%, trend sparkline, signal badge, note

### AI Insights tab
- AI-generated market analysis (updated each refresh)
- Three-column layout: Key Themes · Key Risks · Opportunities
- Note on how the secure refresh mechanism works

### Geopolitical tab
- Risk event cards with event name, region, risk-level badge (high/medium/low), impact sectors, and analyst note
- Macro & FX snapshot

### News tab
- Category filter buttons (macro, earnings, crypto, commodities, tech, fx, other)
- News cards: title, source, signal badge, relative timestamp, AI summary, sentiment label, tags

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

> **Why a server?** Browsers block `fetch()` calls to local `file://` paths. Any static server works — Python, Node `serve`, VS Code Live Server, etc.

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

The refresh script calls the **Groq API** to classify and summarise each news article and to generate the market analysis using the `llama3-70b-8192` model (free tier available).

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

> ⚠️ **Never** paste your API key into `index.html`, `refresh_news.py`, or any file that gets committed. The workflow reads it from GitHub Secrets at runtime only.

---

## How the AI Refresh Works

```
┌─────────────────────────────────────────────────────────────────┐
│  GitHub Actions (every 4 hours or manual trigger)               │
│                                                                 │
│  1. Fetch RSS feeds (Reuters, Bloomberg, CoinDesk …)            │
│  2. Deduplicate articles by URL                                 │
│  3. For each article → ask Groq LLaMA-3:                       │
│       • category  (macro / earnings / crypto / …)              │
│       • sentiment (bullish / bearish / neutral)                 │
│       • signal    (buy / sell / hold / watch)                   │
│       • summary   (2-3 sentence plain-English digest)           │
│       • tags      (ticker symbols / keywords)                   │
│  4. Write results → data/news.json                              │
│  5. From all classified articles → ask Groq for a              │
│       market analysis (headline, themes, risks, opportunities)  │
│  6. Merge analysis block → data/market.json                     │
│  7. git commit + git push → GitHub Pages re-serves             │
└─────────────────────────────────────────────────────────────────┘
```

The **frontend** (`index.html`) only reads the pre-generated `data/*.json` files — no API calls from the browser, no exposed credentials.

### Manual Refresh

You can trigger a refresh at any time:

1. Click **🔄 Refresh AI** in the dashboard header.
2. Click **↗ Open GitHub Actions** in the modal.
3. Click **Run workflow** to start.
4. Optionally set *Maximum articles per feed* (default 10).

Or go directly to **Actions → Refresh AI News Digest → Run workflow**.

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

The script writes to `data/news.json` and updates `data/market.json` with a fresh AI analysis block.

---

## Customisation

### Adding Tickers / Signals

Edit `data/signals.json` to add or remove watchlist entries. Each entry supports:

```json
{
  "ticker":     "AAPL",
  "name":       "Apple Inc.",
  "sector":     "Technology",
  "type":       "stock",
  "price":      213.45,
  "change_pct": 0.62,
  "signal":     "hold",
  "note":       "Brief analyst note here",
  "sparkline":  [209, 210, 208, 211, 212, 213]
}
```

`type` can be `stock`, `etf`, or `crypto`. `signal` can be `buy`, `sell`, `hold`, or `watch`.

### Updating Market / Macro Data

`data/market.json` contains indices, macro indicators, geopolitical events, and the AI analysis block. You can update these manually or extend the GitHub Actions workflow with a free data API (e.g., Yahoo Finance via `yfinance`).

### Adding Geopolitical Events

Edit the `geopolitical` array in `data/market.json`:

```json
{
  "event": "Event Name",
  "region": "Region",
  "risk_level": "high",
  "impact_sectors": ["energy", "fx"],
  "note": "Brief analyst note"
}
```

`risk_level` can be `high`, `medium`, or `low`.

### Changing the Groq Model

Edit `GROQ_MODEL` in `scripts/refresh_news.py`. The default is `llama3-70b-8192`.

| Model | Notes |
|-------|-------|
| `llama3-70b-8192` | Best quality, default |
| `llama3-8b-8192`  | Faster, cheaper |
| `mixtral-8x7b-32768` | Longer context window |

---

## Architecture Notes

The architecture follows a **static-first** pattern to work within GitHub Pages constraints:

- **No backend server** — everything is pre-generated JSON committed to the repository.
- **GitHub Actions as the data pipeline** — runs on a schedule, fetches RSS, calls Groq, commits results.
- **Groq for AI** — fast inference via the free/paid Groq API (replaces direct Anthropic browser calls which are insecure).
- **Deduplication** — articles are deduplicated by URL before Groq classification to save API credits.
- **AI analysis** — after classifying all articles, the script asks Groq for a structured market analysis (headline, themes, risks, opportunities) and stores it in `data/market.json`.
- **Reference copy** — `FinDashboard_Pro.html` is preserved as an archive showing the browser-side AI pattern with full security documentation and the AI assistant inputs disabled.

### AI Refresh — Fully Secured Flow

For a real-time AI assistant that works from a static site securely:
1. Deploy a lightweight serverless function (Cloudflare Workers, Vercel Edge, AWS Lambda).
2. The function receives the user question and appends the AI API key server-side before forwarding.
3. The static page calls your function endpoint — the key never reaches the browser.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Dashboard shows "Failed to load" | Run from a local web server, not `file://` |
| Actions workflow fails | Check `GROQ_API_KEY` secret is set correctly |
| No articles after refresh | Check RSS feed URLs are accessible from GitHub Actions runners |
| Groq API error 429 | You've hit the free-tier rate limit; reduce `MAX_ARTICLES` or upgrade |
| AI analysis not updating | Ensure the workflow has `contents: write` permission and the commit step runs |

---

## Licence

MIT — use freely, contribute back if you improve it.

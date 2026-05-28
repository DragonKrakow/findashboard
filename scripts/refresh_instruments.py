#!/usr/bin/env python3
"""Build a best-effort instrument universe from free/public sources."""

from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
LATEST_DIR = ROOT_DIR / "data" / "instruments" / "latest"
INSTRUMENTS_PATH = LATEST_DIR / "instruments.json"
OVERVIEW_PATH = LATEST_DIR / "market_overview.json"

REQUEST_TIMEOUT = 25
USER_AGENT = "findashboard-instruments/1.0 (https://github.com/DragonKrakow/findashboard)"

TARGET_MARKETS = [
    "New York",
    "Milan",
    "Shanghai",
    "Tokyo",
    "London",
    "Paris",
    "Berlin",
    "Madrid",
    "Seoul",
    "Beijing",
]

SEED_INSTRUMENTS = [
    {"name": "Apple Inc.", "isin": "US0378331005", "market": "New York", "exchange": "NASDAQ", "ticker": "AAPL", "instrument_type": "stock", "currency": "USD", "country": "US", "source_url": "https://www.sec.gov"},
    {"name": "SPDR S&P 500 ETF Trust", "isin": "US78462F1030", "market": "New York", "exchange": "NYSEARCA", "ticker": "SPY", "instrument_type": "etf", "currency": "USD", "country": "US", "source_url": "https://www.sec.gov"},
    {"name": "Eni S.p.A.", "isin": "IT0003132476", "market": "Milan", "exchange": "Borsa Italiana", "ticker": "ENI", "instrument_type": "stock", "currency": "EUR", "country": "IT", "source_url": "https://www.borsaitaliana.it"},
    {"name": "Xtrackers FTSE MIB UCITS ETF", "isin": "LU0274212538", "market": "Milan", "exchange": "Borsa Italiana", "ticker": "XMIB", "instrument_type": "etf", "currency": "EUR", "country": "IT", "source_url": "https://www.borsaitaliana.it"},
    {"name": "Kweichow Moutai Co., Ltd.", "isin": "CNE0000018R8", "market": "Shanghai", "exchange": "SSE", "ticker": "600519", "instrument_type": "stock", "currency": "CNY", "country": "CN", "source_url": "http://www.sse.com.cn"},
    {"name": "China 50 ETF", "isin": "CNE1000003W8", "market": "Shanghai", "exchange": "SSE", "ticker": "510050", "instrument_type": "etf", "currency": "CNY", "country": "CN", "source_url": "http://www.sse.com.cn"},
    {"name": "Toyota Motor Corp.", "isin": "JP3633400001", "market": "Tokyo", "exchange": "TSE", "ticker": "7203", "instrument_type": "stock", "currency": "JPY", "country": "JP", "source_url": "https://www.jpx.co.jp"},
    {"name": "NEXT FUNDS Nikkei 225 ETF", "isin": "JP3027650005", "market": "Tokyo", "exchange": "TSE", "ticker": "1321", "instrument_type": "etf", "currency": "JPY", "country": "JP", "source_url": "https://www.jpx.co.jp"},
    {"name": "AstraZeneca PLC", "isin": "GB0009895292", "market": "London", "exchange": "LSE", "ticker": "AZN", "instrument_type": "stock", "currency": "GBP", "country": "GB", "source_url": "https://www.londonstockexchange.com"},
    {"name": "iShares Core FTSE 100 UCITS ETF", "isin": "IE0005042456", "market": "London", "exchange": "LSE", "ticker": "ISF", "instrument_type": "etf", "currency": "GBP", "country": "GB", "source_url": "https://www.londonstockexchange.com"},
    {"name": "LVMH Moet Hennessy Louis Vuitton SE", "isin": "FR0000121014", "market": "Paris", "exchange": "Euronext Paris", "ticker": "MC", "instrument_type": "stock", "currency": "EUR", "country": "FR", "source_url": "https://www.euronext.com"},
    {"name": "Amundi CAC 40 UCITS ETF", "isin": "LU1681046931", "market": "Paris", "exchange": "Euronext Paris", "ticker": "C40", "instrument_type": "etf", "currency": "EUR", "country": "FR", "source_url": "https://www.euronext.com"},
    {"name": "Siemens AG", "isin": "DE0007236101", "market": "Berlin", "exchange": "Xetra", "ticker": "SIE", "instrument_type": "stock", "currency": "EUR", "country": "DE", "source_url": "https://www.deutsche-boerse.com"},
    {"name": "iShares Core DAX UCITS ETF", "isin": "DE0005933931", "market": "Berlin", "exchange": "Xetra", "ticker": "EXS1", "instrument_type": "etf", "currency": "EUR", "country": "DE", "source_url": "https://www.deutsche-boerse.com"},
    {"name": "Banco Santander SA", "isin": "ES0113900J37", "market": "Madrid", "exchange": "BME", "ticker": "SAN", "instrument_type": "stock", "currency": "EUR", "country": "ES", "source_url": "https://www.bolsamadrid.es"},
    {"name": "iShares IBEX 35 UCITS ETF", "isin": "IE00B0M62S72", "market": "Madrid", "exchange": "BME", "ticker": "IBE", "instrument_type": "etf", "currency": "EUR", "country": "ES", "source_url": "https://www.bolsamadrid.es"},
    {"name": "Samsung Electronics Co., Ltd.", "isin": "KR7005930003", "market": "Seoul", "exchange": "KRX", "ticker": "005930", "instrument_type": "stock", "currency": "KRW", "country": "KR", "source_url": "https://global.krx.co.kr"},
    {"name": "KODEX 200 ETF", "isin": "KR7069520009", "market": "Seoul", "exchange": "KRX", "ticker": "069500", "instrument_type": "etf", "currency": "KRW", "country": "KR", "source_url": "https://global.krx.co.kr"},
    {"name": "Industrial and Commercial Bank of China", "isin": "CNE1000003G1", "market": "Beijing", "exchange": "SZSE", "ticker": "601398", "instrument_type": "stock", "currency": "CNY", "country": "CN", "source_url": "http://www.szse.cn"},
    {"name": "CSI 300 ETF", "isin": "CNE1000008H5", "market": "Beijing", "exchange": "SZSE", "ticker": "159919", "instrument_type": "etf", "currency": "CNY", "country": "CN", "source_url": "http://www.szse.cn"},
]

EXCHANGE_TO_MARKET = {
    "NASDAQ": ("New York", "US", "USD"),
    "NYSE": ("New York", "US", "USD"),
    "NYSEMKT": ("New York", "US", "USD"),
    "NYSEARCA": ("New York", "US", "USD"),
    "BATS": ("New York", "US", "USD"),
    "IEX": ("New York", "US", "USD"),
}


def _fetch_text(url: str) -> str:
    response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def _fetch_json(url: str) -> Any:
    response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.json()


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _normalize(instrument: dict[str, Any], snapshot_date: str) -> dict[str, Any] | None:
    ticker = _clean(instrument.get("ticker")).upper()
    exchange = _clean(instrument.get("exchange"))
    name = _clean(instrument.get("name"))
    instrument_type = _clean(instrument.get("instrument_type")).lower() or "stock"
    if not ticker or not exchange or not name:
        return None

    normalized = {
        "name": name,
        "isin": _clean(instrument.get("isin")) or None,
        "market": _clean(instrument.get("market")) or "Unknown",
        "exchange": exchange,
        "ticker": ticker,
        "instrument_type": "etf" if instrument_type == "etf" else "stock",
        "currency": _clean(instrument.get("currency")) or None,
        "country": _clean(instrument.get("country")).upper() or None,
        "issuer": _clean(instrument.get("issuer")) or None,
        "sector": _clean(instrument.get("sector")) or None,
        "industry": _clean(instrument.get("industry")) or None,
        "listing_status": _clean(instrument.get("listing_status")) or "active",
        "source_url": _clean(instrument.get("source_url")) or None,
        "snapshot_date": snapshot_date,
    }
    return normalized


def fetch_nasdaq_trader(snapshot_date: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    status: dict[str, Any] = {"source": "nasdaqtrader", "url": "https://www.nasdaqtrader.com/dynamic/SymDir/", "ok": True, "records": 0}

    try:
        nasdaq_text = _fetch_text("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt")
        other_text = _fetch_text("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt")
    except Exception:  # pragma: no cover - network dependent
        status["ok"] = False
        status["error"] = "source unavailable"
        return records, status

    for row in csv.DictReader(nasdaq_text.splitlines(), delimiter="|"):
        symbol = _clean(row.get("Symbol"))
        if not symbol or symbol == "File Creation Time" or _clean(row.get("Test Issue")) == "Y":
            continue
        records.append(
            {
                "name": _clean(row.get("Security Name")) or symbol,
                "isin": None,
                "market": "New York",
                "exchange": "NASDAQ",
                "ticker": symbol,
                "instrument_type": "etf" if _clean(row.get("ETF")) == "Y" else "stock",
                "currency": "USD",
                "country": "US",
                "source_url": status["url"],
                "snapshot_date": snapshot_date,
            }
        )

    exchange_map = {
        "N": "NYSE",
        "A": "NYSEMKT",
        "P": "NYSEARCA",
        "Z": "BATS",
        "V": "IEX",
    }
    for row in csv.DictReader(other_text.splitlines(), delimiter="|"):
        symbol = _clean(row.get("ACT Symbol"))
        exchange = exchange_map.get(_clean(row.get("Exchange")), "NYSE")
        if not symbol or symbol == "File Creation Time" or _clean(row.get("Test Issue")) == "Y":
            continue
        records.append(
            {
                "name": _clean(row.get("Security Name")) or symbol,
                "isin": None,
                "market": "New York",
                "exchange": exchange,
                "ticker": symbol,
                "instrument_type": "etf" if _clean(row.get("ETF")) == "Y" else "stock",
                "currency": "USD",
                "country": "US",
                "source_url": status["url"],
                "snapshot_date": snapshot_date,
            }
        )

    status["records"] = len(records)
    return records, status


def fetch_sec_company_exchange(snapshot_date: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    status: dict[str, Any] = {
        "source": "sec-company-tickers-exchange",
        "url": "https://www.sec.gov/files/company_tickers_exchange.json",
        "ok": True,
        "records": 0,
    }
    try:
        payload = _fetch_json(status["url"])
        data_rows = payload.get("data", []) if isinstance(payload, dict) else []
        for row in data_rows:
            if not isinstance(row, list) or len(row) < 4:
                continue
            _, company_name, ticker, exchange = row[:4]
            exchange_clean = _clean(exchange).upper() or "NASDAQ"
            market, country, currency = EXCHANGE_TO_MARKET.get(exchange_clean, ("New York", "US", "USD"))
            records.append(
                {
                    "name": _clean(company_name) or _clean(ticker),
                    "isin": None,
                    "market": market,
                    "exchange": exchange_clean,
                    "ticker": _clean(ticker),
                    "instrument_type": "stock",
                    "currency": currency,
                    "country": country,
                    "source_url": status["url"],
                    "snapshot_date": snapshot_date,
                }
            )
    except Exception:  # pragma: no cover - network dependent
        status["ok"] = False
        status["error"] = "source unavailable"
        return records, status

    status["records"] = len(records)
    return records, status


def fetch_sec_funds(snapshot_date: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    status: dict[str, Any] = {
        "source": "sec-company-tickers-mf",
        "url": "https://www.sec.gov/files/company_tickers_mf.json",
        "ok": True,
        "records": 0,
    }
    try:
        payload = _fetch_json(status["url"])
        data_rows = payload.get("data", []) if isinstance(payload, dict) else []
        for row in data_rows:
            if not isinstance(row, list) or len(row) < 5:
                continue
            _, _, _, issuer_name, ticker = row[:5]
            ticker_clean = _clean(ticker)
            if not ticker_clean:
                continue
            name_clean = _clean(issuer_name)
            fund_type = "etf" if "ETF" in name_clean.upper() or "EXCHANGE TRADED" in name_clean.upper() else "stock"
            records.append(
                {
                    "name": name_clean or ticker_clean,
                    "isin": None,
                    "market": "New York",
                    "exchange": "NYSEARCA" if fund_type == "etf" else "NASDAQ",
                    "ticker": ticker_clean,
                    "instrument_type": fund_type,
                    "currency": "USD",
                    "country": "US",
                    "issuer": name_clean,
                    "source_url": status["url"],
                    "snapshot_date": snapshot_date,
                }
            )
    except Exception:  # pragma: no cover - network dependent
        status["ok"] = False
        status["error"] = "source unavailable"
        return records, status

    status["records"] = len(records)
    return records, status


def deduplicate(instruments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    by_isin: dict[str, int] = {}
    by_exchange_ticker: dict[str, int] = {}

    for instrument in instruments:
        isin = _clean(instrument.get("isin")).upper()
        exchange_ticker = f"{_clean(instrument.get('exchange')).upper()}::{_clean(instrument.get('ticker')).upper()}"

        if isin and isin in by_isin:
            continue
        if not isin and exchange_ticker in by_exchange_ticker:
            continue

        if isin and exchange_ticker in by_exchange_ticker:
            idx = by_exchange_ticker[exchange_ticker]
            existing = deduped[idx]
            existing.update({k: v for k, v in instrument.items() if v not in (None, "")})
            by_isin[isin] = idx
            continue

        deduped.append(instrument)
        idx = len(deduped) - 1
        by_exchange_ticker[exchange_ticker] = idx
        if isin:
            by_isin[isin] = idx

    deduped.sort(key=lambda x: (x.get("market", ""), x.get("exchange", ""), x.get("ticker", "")))
    return deduped


def build_market_overview(generated_at: str, instruments: list[dict[str, Any]]) -> dict[str, Any]:
    market_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"stocks": 0, "etfs": 0, "total": 0})
    exchange_counts: dict[str, dict[str, Any]] = defaultdict(lambda: {"market": "Unknown", "stocks": 0, "etfs": 0, "total": 0})

    totals = {"instruments": 0, "stocks": 0, "etfs": 0}
    with_isin = 0

    for instrument in instruments:
        market = instrument.get("market") or "Unknown"
        exchange = instrument.get("exchange") or "Unknown"
        kind = instrument.get("instrument_type") or "stock"

        totals["instruments"] += 1
        if kind == "etf":
            totals["etfs"] += 1
            market_counts[market]["etfs"] += 1
            exchange_counts[exchange]["etfs"] += 1
        else:
            totals["stocks"] += 1
            market_counts[market]["stocks"] += 1
            exchange_counts[exchange]["stocks"] += 1

        market_counts[market]["total"] += 1
        exchange_counts[exchange]["total"] += 1
        exchange_counts[exchange]["market"] = market

        if instrument.get("isin"):
            with_isin += 1

    markets = [{"market": market, **market_counts[market]} for market in sorted(market_counts)]
    exchanges = [
        {"exchange": exchange, "market": values["market"], "stocks": values["stocks"], "etfs": values["etfs"], "total": values["total"]}
        for exchange, values in sorted(exchange_counts.items())
    ]

    return {
        "generated_at": generated_at,
        "totals": totals,
        "completeness": {
            "with_isin": with_isin,
            "missing_isin": totals["instruments"] - with_isin,
        },
        "markets": markets,
        "exchanges": exchanges,
    }


def main() -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    snapshot_date = generated_at[:10]

    source_statuses: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []

    for source in (fetch_nasdaq_trader, fetch_sec_company_exchange, fetch_sec_funds):
        records, status = source(snapshot_date)
        source_statuses.append(status)
        log.info("Source %s -> ok=%s, records=%s", status["source"], status["ok"], status["records"])
        collected.extend(records)

    collected.extend(SEED_INSTRUMENTS)

    normalized: list[dict[str, Any]] = []
    for instrument in collected:
        norm = _normalize(instrument, snapshot_date)
        if norm:
            normalized.append(norm)

    deduped = deduplicate(normalized)

    LATEST_DIR.mkdir(parents=True, exist_ok=True)

    instruments_payload = {
        "generated_at": generated_at,
        "snapshot_date": snapshot_date,
        "target_markets": TARGET_MARKETS,
        "source_count": len(source_statuses),
        "source_status": source_statuses,
        "record_count": len(deduped),
        "instruments": deduped,
    }

    overview_payload = build_market_overview(generated_at, deduped)

    INSTRUMENTS_PATH.write_text(json.dumps(instruments_payload, indent=2, ensure_ascii=False) + "\n")
    OVERVIEW_PATH.write_text(json.dumps(overview_payload, indent=2, ensure_ascii=False) + "\n")

    log.info("Wrote %s (%d instruments)", INSTRUMENTS_PATH, len(deduped))
    log.info("Wrote %s", OVERVIEW_PATH)


if __name__ == "__main__":
    main()

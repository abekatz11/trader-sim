#!/usr/bin/env python3
"""
Headless market data fetcher for GitHub Actions.
Outputs JSON to stdout for piping to gist.
"""

import json
import requests
import time
from datetime import datetime
import pytz
import sys

# Stock universe - must match config.py
STOCK_UNIVERSE = [
    "PLTR", "SOFI", "HOOD", "AFRM", "UPST", "PATH", "DKNG", "RBLX",
    "U", "SNAP", "PINS", "ROKU", "SQ", "COIN", "MARA", "RIOT",
    "MRNA", "BNTX", "CRSP", "NVAX", "SGEN", "EXAS", "VRTX", "REGN",
    "RIVN", "LCID", "NIO", "XPEV", "PLUG", "FCEL", "CHPT", "QS",
    "GME", "AMC", "BBBY", "TLRY", "SNDL", "SPCE",
    "CRWD", "DDOG", "NET", "ZS", "MDB", "SNOW", "TTD", "ENPH",
    "TSLA", "AMD", "NVDA", "META",
]

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}


def is_market_open() -> bool:
    """Check if US stock market is currently open."""
    try:
        et = pytz.timezone('US/Eastern')
        now = datetime.now(et)

        # Weekend check
        if now.weekday() >= 5:
            return False

        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

        return market_open <= now <= market_close
    except Exception:
        return True  # Assume open if can't determine


def fetch_stock_data(symbol: str) -> dict:
    """Fetch data for a single stock from Yahoo Finance."""
    url = YAHOO_CHART_URL.format(symbol=symbol)
    params = {"interval": "1d", "range": "3mo"}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()
        result = data.get("chart", {}).get("result")
        if not result:
            return None

        chart = result[0]
        meta = chart.get("meta", {})
        timestamps = chart.get("timestamp", [])
        quotes = chart.get("indicators", {}).get("quote", [{}])[0]

        if not timestamps or not quotes:
            return None

        closes = [c for c in quotes.get("close", []) if c is not None]
        highs = [h for h in quotes.get("high", []) if h is not None]
        lows = [l for l in quotes.get("low", []) if l is not None]
        volumes = [v for v in quotes.get("volume", []) if v is not None]

        if len(closes) < 50:
            return None

        current_price = meta.get("regularMarketPrice", closes[-1])

        # Calculate indicators
        sma_10 = sum(closes[-10:]) / 10
        sma_20 = sum(closes[-20:]) / 20
        sma_50 = sum(closes[-50:]) / 50

        # RSI calculation
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-14:]]
        losses = [-d if d < 0 else 0 for d in deltas[-14:]]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        # ATR calculation
        trs = []
        for i in range(-14, 0):
            if i == -14:
                tr = highs[i] - lows[i]
            else:
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1])
                )
            trs.append(tr)
        atr = sum(trs) / 14

        # Returns
        daily_change = ((current_price - closes[-2]) / closes[-2]) * 100 if len(closes) >= 2 else 0
        weekly_change = ((current_price - closes[-5]) / closes[-5]) * 100 if len(closes) >= 5 else 0
        monthly_change = ((current_price - closes[-20]) / closes[-20]) * 100 if len(closes) >= 20 else 0

        avg_volume = sum(volumes[-20:]) / min(20, len(volumes))

        return {
            "price": round(current_price, 2),
            "daily_change": round(daily_change, 2),
            "weekly_change": round(weekly_change, 2),
            "monthly_change": round(monthly_change, 2),
            "rsi": round(rsi, 2),
            "atr": round(atr, 2),
            "sma_10": round(sma_10, 2),
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2),
            "volume": int(avg_volume),
            "above_sma_10": current_price > sma_10,
            "above_sma_20": current_price > sma_20,
            "above_sma_50": current_price > sma_50,
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}", file=sys.stderr)
        return None


def main():
    """Fetch all stocks and output JSON."""
    start_time = time.time()

    stocks = {}
    errors = []

    for i, symbol in enumerate(STOCK_UNIVERSE):
        print(f"Fetching {symbol} ({i+1}/{len(STOCK_UNIVERSE)})...", file=sys.stderr)

        data = fetch_stock_data(symbol)
        if data:
            stocks[symbol] = data
        else:
            errors.append(symbol)

        # Rate limiting
        time.sleep(0.3)

    elapsed = time.time() - start_time

    output = {
        "timestamp": int(time.time()),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "market_open": is_market_open(),
        "fetch_time_seconds": round(elapsed, 1),
        "stocks_fetched": len(stocks),
        "stocks_failed": errors,
        "stocks": stocks,
    }

    # Output JSON to stdout
    print(json.dumps(output, indent=2))

    print(f"\nDone: {len(stocks)}/{len(STOCK_UNIVERSE)} stocks in {elapsed:.1f}s", file=sys.stderr)
    if errors:
        print(f"Failed: {errors}", file=sys.stderr)


if __name__ == "__main__":
    main()

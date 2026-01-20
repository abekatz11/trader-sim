"""Market data fetching using Yahoo Finance API with fallback to sample data."""

import requests
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import random
import warnings
import os
import time

from config import STOCK_UNIVERSE, INDICATORS, SCREENING

# Environment variable to force sample data mode
USE_SAMPLE_DATA = os.environ.get('TRADER_SIM_SAMPLE_DATA', '').lower() in ('1', 'true', 'yes')

# GitHub Gist configuration for cached data
# Set these environment variables or replace with your gist URL
GIST_USER = os.environ.get('TRADER_SIM_GIST_USER', '')
GIST_ID = os.environ.get('TRADER_SIM_GIST_ID', '')
GIST_CACHE_MAX_AGE = 600  # 10 minutes - use gist data if fresher than this

# Cached gist data
_gist_cache = None
_gist_cache_time = 0

# Yahoo Finance API endpoints (try multiple)
YAHOO_ENDPOINTS = [
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
    "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
]

# Request headers to mimic browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}

# Rate limiting
_last_request_time = 0
REQUEST_DELAY = 0.5  # 500ms between requests
_rate_limited = False  # Track if we've been rate limited
_rate_limit_until = 0  # Timestamp when rate limit should expire

# Sample prices (fallback values - approximately current as of Jan 2026)
SAMPLE_PRICES = {
    "AAPL": 250.00, "MSFT": 420.00, "GOOGL": 195.00, "AMZN": 225.00, "NVDA": 140.00,
    "META": 600.00, "JPM": 245.00, "BAC": 46.00, "V": 315.00, "WMT": 92.00,
    "KO": 63.00, "PEP": 152.00, "MCD": 295.00, "JNJ": 145.00, "UNH": 525.00,
    "PFE": 26.00, "XOM": 108.00, "CVX": 150.00, "SPY": 600.00, "QQQ": 525.00
}

# Cache for live data availability check
_live_data_available = None


def _fetch_from_gist() -> Optional[Dict]:
    """Fetch cached market data from GitHub Gist."""
    global _gist_cache, _gist_cache_time

    if not GIST_USER or not GIST_ID:
        return None

    # Return memory-cached data if recent
    if _gist_cache and (time.time() - _gist_cache_time) < 60:
        return _gist_cache

    try:
        url = f"https://gist.githubusercontent.com/{GIST_USER}/{GIST_ID}/raw/market_data.json"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None

        data = resp.json()
        timestamp = data.get('timestamp', 0)
        age = time.time() - timestamp

        if age > GIST_CACHE_MAX_AGE:
            return None  # Data too stale

        _gist_cache = data
        _gist_cache_time = time.time()
        return data
    except Exception:
        return None


def _get_gist_stock_data(symbol: str) -> Optional[Dict]:
    """Get stock data from gist cache if available."""
    gist_data = _fetch_from_gist()
    if not gist_data:
        return None

    stocks = gist_data.get('stocks', {})
    return stocks.get(symbol)


def _fetch_yahoo_chart(symbol: str, range_str: str = "3mo", interval: str = "1d") -> Optional[Dict]:
    """Fetch data directly from Yahoo Finance chart API."""
    global _last_request_time, _rate_limited, _rate_limit_until

    # If we're rate limited, check if we should try again
    if _rate_limited:
        if time.time() < _rate_limit_until:
            return None  # Still rate limited, don't try
        else:
            _rate_limited = False  # Rate limit expired, try again

    # Rate limiting between our requests
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)

    params = {
        "interval": interval,
        "range": range_str,
    }

    # Try each endpoint
    for endpoint in YAHOO_ENDPOINTS:
        url = endpoint.format(symbol=symbol)
        try:
            _last_request_time = time.time()
            resp = requests.get(url, headers=HEADERS, params=params, timeout=10)

            if resp.status_code == 429:
                # Rate limited - set backoff and try next endpoint
                _rate_limited = True
                _rate_limit_until = time.time() + 300  # 5 minute backoff
                continue

            if resp.status_code != 200:
                continue

            data = resp.json()
            result = data.get("chart", {}).get("result")
            if result:
                _rate_limited = False  # Success - clear rate limit flag
                return result[0]
        except requests.exceptions.RequestException:
            continue

    return None


def _parse_chart_to_dataframe(chart_data: Dict) -> Optional[pd.DataFrame]:
    """Parse Yahoo chart API response into a DataFrame."""
    try:
        timestamps = chart_data.get("timestamp", [])
        quotes = chart_data.get("indicators", {}).get("quote", [{}])[0]

        if not timestamps or not quotes:
            return None

        df = pd.DataFrame({
            "Open": quotes.get("open", []),
            "High": quotes.get("high", []),
            "Low": quotes.get("low", []),
            "Close": quotes.get("close", []),
            "Volume": quotes.get("volume", []),
        }, index=pd.to_datetime(timestamps, unit='s'))

        # Remove rows with NaN close prices
        df = df.dropna(subset=['Close'])

        return df if not df.empty else None
    except Exception:
        return None


def _check_live_data() -> bool:
    """Check if live data is available."""
    global _live_data_available
    if _live_data_available is not None:
        return _live_data_available

    chart = _fetch_yahoo_chart("SPY", "5d")
    _live_data_available = chart is not None and "timestamp" in chart
    return _live_data_available


def _use_sample_data() -> bool:
    """Determine whether to use sample data."""
    if USE_SAMPLE_DATA:
        return True
    return not _check_live_data()


def _get_sample_price(symbol: str) -> float:
    """Get sample price with small random variation."""
    base = SAMPLE_PRICES.get(symbol, 100.0)
    variation = random.uniform(-0.02, 0.02)
    return round(base * (1 + variation), 2)


def _generate_sample_history(symbol: str, days: int = 90) -> pd.DataFrame:
    """Generate sample historical data for a symbol."""
    base_price = SAMPLE_PRICES.get(symbol, 100.0)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='B')

    prices = [base_price]
    for _ in range(days - 1):
        change = random.gauss(0.0005, 0.015)
        prices.append(prices[-1] * (1 + change))

    df = pd.DataFrame({
        'Open': [p * random.uniform(0.995, 1.005) for p in prices],
        'High': [p * random.uniform(1.0, 1.02) for p in prices],
        'Low': [p * random.uniform(0.98, 1.0) for p in prices],
        'Close': prices,
        'Volume': [int(random.uniform(5e6, 50e6)) for _ in prices]
    }, index=dates)

    return df


def get_historical_data(symbol: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """Get historical OHLCV data for a symbol."""
    if _use_sample_data():
        return _generate_sample_history(symbol, 90)

    chart = _fetch_yahoo_chart(symbol, period)
    if chart:
        df = _parse_chart_to_dataframe(chart)
        if df is not None and len(df) >= 50:
            return df

    return _generate_sample_history(symbol, 90)


def get_current_price(symbol: str) -> Optional[float]:
    """Get the current/latest price for a symbol."""
    if _use_sample_data():
        return _get_sample_price(symbol)

    # Try gist cache first
    gist_data = _get_gist_stock_data(symbol)
    if gist_data and 'price' in gist_data:
        return gist_data['price']

    # Fall back to live API
    chart = _fetch_yahoo_chart(symbol, "5d")
    if chart:
        meta = chart.get("meta", {})
        price = meta.get("regularMarketPrice")
        if price:
            return round(float(price), 2)

        # Fallback to last close
        df = _parse_chart_to_dataframe(chart)
        if df is not None and not df.empty:
            return round(float(df['Close'].iloc[-1]), 2)

    return _get_sample_price(symbol)


def get_current_prices(symbols: List[str] = None) -> Dict[str, float]:
    """Get current prices for multiple symbols."""
    if symbols is None:
        symbols = STOCK_UNIVERSE

    if _use_sample_data():
        return {s: _get_sample_price(s) for s in symbols}

    prices = {}
    for symbol in symbols:
        price = get_current_price(symbol)
        if price:
            prices[symbol] = price

    return prices


def calculate_sma(data: pd.DataFrame, period: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return data['Close'].rolling(window=period).mean()


def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high = data['High']
    low = data['Low']
    close = data['Close']

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def get_stock_analysis(symbol: str) -> Optional[Dict]:
    """Get comprehensive analysis for a single stock."""
    # Try gist cache first (has pre-calculated indicators)
    gist_data = _get_gist_stock_data(symbol)
    if gist_data:
        return {
            "symbol": symbol,
            "price": gist_data.get('price', 0),
            "daily_change": gist_data.get('daily_change', 0),
            "weekly_change": gist_data.get('weekly_change', 0),
            "monthly_change": gist_data.get('monthly_change', 0),
            "sma_10": gist_data.get('sma_10', 0),
            "sma_20": gist_data.get('sma_20', 0),
            "sma_50": gist_data.get('sma_50', 0),
            "rsi": gist_data.get('rsi', 50),
            "atr": gist_data.get('atr', 0),
            "avg_volume": gist_data.get('volume', 0),
            "above_sma_10": gist_data.get('above_sma_10', False),
            "above_sma_20": gist_data.get('above_sma_20', False),
            "above_sma_50": gist_data.get('above_sma_50', False),
        }

    # Fall back to live calculation
    hist = get_historical_data(symbol)
    if hist is None or len(hist) < 50:
        return None

    current_price = float(hist['Close'].iloc[-1])
    prev_close = float(hist['Close'].iloc[-2])

    sma_10 = float(calculate_sma(hist, 10).iloc[-1])
    sma_20 = float(calculate_sma(hist, 20).iloc[-1])
    sma_50 = float(calculate_sma(hist, 50).iloc[-1])
    rsi = float(calculate_rsi(hist, INDICATORS['rsi_period']).iloc[-1])
    atr = float(calculate_atr(hist, INDICATORS['atr_period']).iloc[-1])

    daily_return = ((current_price - prev_close) / prev_close) * 100
    weekly_return = ((current_price - float(hist['Close'].iloc[-5])) / float(hist['Close'].iloc[-5])) * 100 if len(hist) >= 5 else 0
    monthly_return = ((current_price - float(hist['Close'].iloc[-20])) / float(hist['Close'].iloc[-20])) * 100 if len(hist) >= 20 else 0

    avg_volume = float(hist['Volume'].tail(20).mean())

    return {
        "symbol": symbol,
        "price": round(current_price, 2),
        "daily_change": round(daily_return, 2),
        "weekly_change": round(weekly_return, 2),
        "monthly_change": round(monthly_return, 2),
        "sma_10": round(sma_10, 2),
        "sma_20": round(sma_20, 2),
        "sma_50": round(sma_50, 2),
        "rsi": round(rsi, 2),
        "atr": round(atr, 2),
        "avg_volume": int(avg_volume),
        "above_sma_10": current_price > sma_10,
        "above_sma_20": current_price > sma_20,
        "above_sma_50": current_price > sma_50,
    }


def screen_stocks(symbols: List[str] = None) -> List[Dict]:
    """Screen stocks based on criteria in config."""
    if symbols is None:
        symbols = STOCK_UNIVERSE

    screened = []
    for symbol in symbols:
        analysis = get_stock_analysis(symbol)
        if analysis is None:
            continue

        if analysis['atr'] < SCREENING['min_atr']:
            continue
        if analysis['avg_volume'] < SCREENING['min_avg_volume']:
            continue
        if analysis['price'] > SCREENING['max_price']:
            continue
        if analysis['price'] < SCREENING['min_price']:
            continue

        screened.append(analysis)

    return screened


def get_market_summary(symbols: List[str] = None) -> Dict:
    """Get a summary of market conditions."""
    if symbols is None:
        symbols = STOCK_UNIVERSE

    analyses = []
    for symbol in symbols:
        analysis = get_stock_analysis(symbol)
        if analysis:
            analyses.append(analysis)

    if not analyses:
        return {"error": "No data available"}

    avg_daily_change = sum(a['daily_change'] for a in analyses) / len(analyses)
    avg_rsi = sum(a['rsi'] for a in analyses) / len(analyses)

    gainers = sorted(analyses, key=lambda x: x['daily_change'], reverse=True)[:5]
    losers = sorted(analyses, key=lambda x: x['daily_change'])[:5]

    return {
        "stocks_analyzed": len(analyses),
        "avg_daily_change": round(avg_daily_change, 2),
        "avg_rsi": round(avg_rsi, 2),
        "top_gainers": gainers,
        "top_losers": losers,
        "all_stocks": analyses,
    }


def is_using_sample_data() -> bool:
    """Check if currently using sample data."""
    return _use_sample_data()


def get_data_source_status() -> str:
    """Get a description of the current data source status."""
    if USE_SAMPLE_DATA:
        return "Sample data (forced via TRADER_SIM_SAMPLE_DATA env var)"

    # Check if gist cache is available and fresh
    gist_data = _fetch_from_gist()
    if gist_data:
        age = int(time.time() - gist_data.get('timestamp', 0))
        return f"Gist cache ({age}s old, {gist_data.get('stocks_fetched', 0)} stocks)"

    if _rate_limited:
        remaining = int(_rate_limit_until - time.time())
        if remaining > 0:
            return f"Sample data (Yahoo API rate limited, retry in {remaining}s)"
        return "Sample data (rate limit expired, will retry)"
    if _live_data_available is False:
        return "Sample data (Yahoo API unavailable)"
    if _live_data_available is True:
        return "Live data (Yahoo Finance API)"
    return "Live data (Yahoo Finance API)"


def reset_rate_limit():
    """Reset rate limit flag (for testing/debugging)."""
    global _rate_limited, _rate_limit_until, _live_data_available
    _rate_limited = False
    _rate_limit_until = 0
    _live_data_available = None

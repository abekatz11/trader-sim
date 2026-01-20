"""Market data fetching using yfinance with fallback to sample data."""

import yfinance as yf
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import random
import warnings
import os

# Suppress yfinance warnings
warnings.filterwarnings('ignore', module='yfinance')

from config import STOCK_UNIVERSE, INDICATORS, SCREENING

# Environment variable to force sample data mode
USE_SAMPLE_DATA = os.environ.get('TRADER_SIM_SAMPLE_DATA', '').lower() in ('1', 'true', 'yes')

# Sample prices (realistic values as of late 2024)
SAMPLE_PRICES = {
    "AAPL": 178.50, "MSFT": 378.25, "GOOGL": 141.80, "AMZN": 178.90, "NVDA": 495.20,
    "META": 505.75, "JPM": 198.40, "BAC": 35.80, "V": 279.60, "WMT": 162.30,
    "KO": 59.85, "PEP": 168.40, "MCD": 295.20, "JNJ": 155.60, "UNH": 528.90,
    "PFE": 28.45, "XOM": 104.75, "CVX": 147.20, "SPY": 478.50, "QQQ": 405.80
}

# Flag to track if live data is available
_live_data_available = None


def _check_live_data() -> bool:
    """Check if live data is available."""
    global _live_data_available
    if _live_data_available is not None:
        return _live_data_available

    try:
        test = yf.download("SPY", period="1d", progress=False, auto_adjust=True)
        _live_data_available = not test.empty
    except Exception:
        _live_data_available = False

    return _live_data_available


def _use_sample_data() -> bool:
    """Determine whether to use sample data."""
    if USE_SAMPLE_DATA:
        return True
    return not _check_live_data()


def _get_sample_price(symbol: str) -> float:
    """Get sample price with small random variation."""
    base = SAMPLE_PRICES.get(symbol, 100.0)
    variation = random.uniform(-0.02, 0.02)  # +/- 2%
    return round(base * (1 + variation), 2)


def _generate_sample_history(symbol: str, days: int = 90) -> pd.DataFrame:
    """Generate sample historical data for a symbol."""
    base_price = SAMPLE_PRICES.get(symbol, 100.0)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='B')

    # Generate random walk prices
    prices = [base_price]
    for _ in range(days - 1):
        change = random.gauss(0.0005, 0.015)  # Small positive drift, realistic volatility
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

    try:
        hist = yf.download(symbol, period=period, progress=False, auto_adjust=True)
        if hist.empty:
            return _generate_sample_history(symbol, 90)
        return hist
    except Exception as e:
        print(f"Error fetching history for {symbol}, using sample data: {e}")
        return _generate_sample_history(symbol, 90)


def get_current_price(symbol: str) -> Optional[float]:
    """Get the current/latest price for a symbol."""
    if _use_sample_data():
        return _get_sample_price(symbol)

    try:
        hist = yf.download(symbol, period="5d", progress=False, auto_adjust=True)
        if hist.empty:
            return _get_sample_price(symbol)
        return round(float(hist['Close'].iloc[-1]), 2)
    except Exception as e:
        return _get_sample_price(symbol)


def get_current_prices(symbols: List[str] = None) -> Dict[str, float]:
    """Get current prices for multiple symbols."""
    if symbols is None:
        symbols = STOCK_UNIVERSE

    if _use_sample_data():
        return {s: _get_sample_price(s) for s in symbols}

    try:
        data = yf.download(symbols, period="5d", progress=False, auto_adjust=True, group_by='ticker')

        prices = {}
        if len(symbols) == 1:
            if not data.empty:
                prices[symbols[0]] = round(float(data['Close'].iloc[-1]), 2)
        else:
            for symbol in symbols:
                try:
                    if symbol in data.columns.get_level_values(0):
                        close_price = data[symbol]['Close'].dropna()
                        if len(close_price) > 0:
                            prices[symbol] = round(float(close_price.iloc[-1]), 2)
                except Exception:
                    continue

        # Fill missing with sample data
        for symbol in symbols:
            if symbol not in prices:
                prices[symbol] = _get_sample_price(symbol)

        return prices
    except Exception as e:
        return {s: _get_sample_price(s) for s in symbols}


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
    hist = get_historical_data(symbol)
    if hist is None or len(hist) < 50:
        return None

    current_price = float(hist['Close'].iloc[-1])
    prev_close = float(hist['Close'].iloc[-2])

    # Calculate indicators
    sma_10 = float(calculate_sma(hist, 10).iloc[-1])
    sma_20 = float(calculate_sma(hist, 20).iloc[-1])
    sma_50 = float(calculate_sma(hist, 50).iloc[-1])
    rsi = float(calculate_rsi(hist, INDICATORS['rsi_period']).iloc[-1])
    atr = float(calculate_atr(hist, INDICATORS['atr_period']).iloc[-1])

    # Calculate returns
    daily_return = ((current_price - prev_close) / prev_close) * 100
    weekly_return = ((current_price - float(hist['Close'].iloc[-5])) / float(hist['Close'].iloc[-5])) * 100 if len(hist) >= 5 else 0
    monthly_return = ((current_price - float(hist['Close'].iloc[-20])) / float(hist['Close'].iloc[-20])) * 100 if len(hist) >= 20 else 0

    # Average volume
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

        # Apply screening filters
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

    # Calculate market-wide metrics
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

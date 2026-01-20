"""Configuration settings for Trader-Sim."""

# Account settings
STARTING_CASH = 1000
SIMULATION_DAYS = 30

# Stock universe - liquid, well-known stocks
STOCK_UNIVERSE = [
    # Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
    # Finance
    "JPM", "BAC", "V",
    # Consumer
    "WMT", "KO", "PEP", "MCD",
    # Healthcare
    "JNJ", "UNH", "PFE",
    # Energy
    "XOM", "CVX",
    # ETFs
    "SPY", "QQQ"
]

# Screening parameters
SCREENING = {
    "min_atr": 1.5,             # Minimum ATR (volatility filter)
    "min_avg_volume": 1000000,  # Minimum average daily volume
    "max_price": 500,           # Max price per share (affordability)
    "min_price": 5,             # Min price (avoid penny stocks)
}

# Technical indicators to calculate
INDICATORS = {
    "sma_periods": [10, 20, 50],  # Simple moving averages
    "rsi_period": 14,             # RSI lookback
    "atr_period": 14,             # ATR lookback
}

# Risk management
RISK = {
    "max_position_pct": 0.25,    # Max 25% of portfolio in one stock
    "max_positions": 5,          # Max number of holdings
}

# Data paths
DATA_DIR = "data"
PORTFOLIO_FILE = "data/portfolio.json"

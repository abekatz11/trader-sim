"""Configuration settings for Trader-Sim."""

# Account settings
STARTING_CASH = 1000
SIMULATION_DAYS = 30

# Stock universe - 50 volatile small/mid-cap and growth stocks
STOCK_UNIVERSE = [
    # Small-cap tech / growth
    "PLTR", "SOFI", "HOOD", "AFRM", "UPST", "PATH", "DKNG", "RBLX",
    "U", "SNAP", "PINS", "ROKU", "SQ", "COIN", "MARA", "RIOT",

    # Biotech (volatile)
    "MRNA", "BNTX", "CRSP", "NVAX", "SGEN", "EXAS", "VRTX", "REGN",

    # EV / Clean energy
    "RIVN", "LCID", "NIO", "XPEV", "PLUG", "FCEL", "CHPT", "QS",

    # Meme / High-volatility
    "GME", "AMC", "BBBY", "TLRY", "SNDL", "SPCE",

    # Mid-cap growth
    "CRWD", "DDOG", "NET", "ZS", "MDB", "SNOW", "TTD", "ENPH",

    # Volatile large-cap (for balance)
    "TSLA", "AMD", "NVDA", "META",
]

# Screening parameters
SCREENING = {
    "min_atr": 1.0,             # Lower ATR threshold for smaller stocks
    "min_avg_volume": 500000,   # Lower volume threshold for small caps
    "max_price": 500,           # Max price per share (affordability)
    "min_price": 1,             # Allow lower-priced stocks
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
    "max_positions": 10,         # Increased for larger universe
}

# Data paths
DATA_DIR = "data"
PORTFOLIO_FILE = "data/portfolio.json"

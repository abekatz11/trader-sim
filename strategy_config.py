"""
Trading Strategy Configuration

Edit this file to control how Claude makes trading decisions.
The GUIDANCE section is natural language - write it however makes sense to you.
The GUARDRAILS section contains hard limits that the system enforces.
"""

# =============================================================================
# YOUR TRADING GUIDANCE (Natural Language)
# =============================================================================
# Write your trading philosophy here. Be as specific or general as you want.
# Claude will read this and make decisions accordingly.

GUIDANCE = """
I want a momentum + mean-reversion hybrid strategy for volatile small-cap stocks.

BUYING CRITERIA:
- Look for oversold bounces: RSI below 30 often signals panic selling and a potential bounce
- Buy momentum plays when a stock is above its 20-day SMA with positive daily change
- Favor high-conviction trades over many small positions
- More aggressive entries in the morning when volatility is highest
- Consider adding to winning positions if the trend continues

SELLING CRITERIA:
- Take profits at +15-20% gains - don't get greedy
- Cut losses at -8 to -10% - protect capital, don't hope for recovery
- Trim or sell when RSI goes above 70-75 (overbought)
- Sell if a stock breaks below its 20-day SMA after we bought for momentum

RISK MANAGEMENT:
- Keep some cash reserve for new opportunities
- Reduce position sizes when the overall market is very volatile
- Don't chase stocks that have already moved 10%+ in a day
- Prefer stocks with higher trading volume for liquidity

GENERAL PREFERENCES:
- I'm comfortable with higher risk for higher potential reward
- Favor biotech, EV, and small-cap tech sectors
- Crypto-related stocks (MARA, RIOT, COIN) are fine but volatile
- Fewer, larger positions are better than many tiny ones
"""

# =============================================================================
# HARD GUARDRAILS (System-Enforced Limits)
# =============================================================================
# These limits are enforced by the system regardless of what Claude suggests.
# Claude's trades will be rejected if they violate these rules.

GUARDRAILS = {
    # Position limits
    "max_position_pct": 0.25,       # Max 25% of portfolio in any single stock
    "max_positions": 8,             # Maximum number of holdings at once
    "min_position_value": 20,       # Don't buy less than $20 worth

    # Trade limits
    "max_daily_trades": 8,          # Max trades per day (buys + sells)
    "max_daily_buys": 5,            # Max buy orders per day

    # Risk limits
    "max_single_loss_pct": 12,      # Force sell if position down more than 12%
    "min_cash_reserve": 25,         # Always keep at least $25 cash

    # Blocked symbols (stocks Claude should never trade)
    "blocked_symbols": [],          # e.g., ["GME", "AMC"] to block specific stocks

    # Require reasoning for transparency
    "require_reasoning": True,      # Claude must explain each trade decision
}

# =============================================================================
# TRADING SCHEDULE
# =============================================================================

SCHEDULE = {
    "market_open": "09:30",         # ET
    "market_close": "16:00",        # ET
    "check_interval_minutes": 5,    # How often to check for trades
    "skip_first_minutes": 5,        # Skip first 5 min (market open chaos)
    "skip_last_minutes": 10,        # Skip last 10 min (end of day volatility)
    "trade_days": [0, 1, 2, 3, 4],  # Monday=0 through Friday=4
}

# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    "log_file": "data/trade_log.json",
    "daily_summary_file": "data/daily_summary.txt",
    "verbose": True,                # Print decisions to console
}

#!/usr/bin/env python3
"""Backfill SPY prices for existing trading sessions."""
import json
import yfinance as yf
from datetime import datetime, timedelta

# Load trade log
with open('data/trade_log.json', 'r') as f:
    trade_log = json.load(f)

sessions = trade_log['sessions']
print(f"Loaded {len(sessions)} sessions")

# Get date range
dates = [datetime.fromisoformat(s['timestamp']) for s in sessions]
start_date = min(dates) - timedelta(days=1)
end_date = max(dates) + timedelta(days=1)

print(f"Fetching SPY data from {start_date.date()} to {end_date.date()}...")

# Fetch SPY historical data
spy = yf.Ticker("SPY")
hist = spy.history(start=start_date, end=end_date)

# Build date -> price map
spy_prices = {}
for date, row in hist.iterrows():
    date_str = date.strftime('%Y-%m-%d')
    spy_prices[date_str] = row['Close']

print(f"Fetched {len(spy_prices)} SPY prices")

# Backfill sessions
updated = 0
for session in sessions:
    if 'spy_price' not in session or session['spy_price'] is None:
        session_date = session['timestamp'][:10]  # YYYY-MM-DD

        # Find closest SPY price
        if session_date in spy_prices:
            session['spy_price'] = round(spy_prices[session_date], 2)
            updated += 1
        else:
            # Find nearest date
            available_dates = sorted(spy_prices.keys())
            closest = min(available_dates, key=lambda d: abs(datetime.fromisoformat(d) - datetime.fromisoformat(session_date)))
            session['spy_price'] = round(spy_prices[closest], 2)
            updated += 1

print(f"Updated {updated} sessions with SPY prices")

# Save updated log
with open('data/trade_log.json', 'w') as f:
    json.dump(trade_log, f, indent=2)

print("Trade log updated successfully!")

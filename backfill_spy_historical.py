#!/usr/bin/env python3
"""Backfill SPY prices with actual historical data for each trading session."""
import json
import requests
from datetime import datetime, timedelta

# Load trade log
with open('data/trade_log.json', 'r') as f:
    trade_log = json.load(f)

sessions = trade_log['sessions']
print(f"Loaded {len(sessions)} sessions")

# Get date range
dates = [datetime.fromisoformat(s['timestamp']) for s in sessions]
start_date = min(dates)
end_date = max(dates)

print(f"Date range: {start_date.date()} to {end_date.date()}")
print(f"Fetching historical SPY data from Yahoo Finance...")

# Fetch SPY historical data using Yahoo Finance API
period1 = int(start_date.timestamp()) - 86400  # 1 day before
period2 = int(end_date.timestamp()) + 86400     # 1 day after

url = f"https://query1.finance.yahoo.com/v8/finance/chart/SPY?period1={period1}&period2={period2}&interval=1d"
headers = {'User-Agent': 'Mozilla/5.0'}

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    quotes = data['chart']['result'][0]
    timestamps = quotes['timestamp']
    closes = quotes['indicators']['quote'][0]['close']

    # Build date -> price map
    spy_prices = {}
    for ts, close in zip(timestamps, closes):
        date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        spy_prices[date] = close

    print(f"Fetched {len(spy_prices)} historical SPY prices")
    print(f"Sample prices: {list(spy_prices.items())[:3]}")

    # Backfill sessions
    updated = 0
    for session in sessions:
        session_date = session['timestamp'][:10]  # YYYY-MM-DD

        # Find closest SPY price
        if session_date in spy_prices:
            session['spy_price'] = round(spy_prices[session_date], 2)
            updated += 1
        else:
            # Find nearest available date
            available_dates = sorted(spy_prices.keys())
            closest = min(available_dates,
                         key=lambda d: abs(datetime.fromisoformat(d) - datetime.fromisoformat(session_date)))
            session['spy_price'] = round(spy_prices[closest], 2)
            updated += 1
            print(f"  Used {closest} price for {session_date}")

    print(f"\nUpdated {updated} sessions with historical SPY prices")

    # Show sample
    print(f"\nFirst session: {sessions[0]['timestamp'][:10]} -> SPY ${sessions[0]['spy_price']}")
    print(f"Last session:  {sessions[-1]['timestamp'][:10]} -> SPY ${sessions[-1]['spy_price']}")

    # Save updated log
    with open('data/trade_log.json', 'w') as f:
        json.dump(trade_log, f, indent=2)

    print("\n✓ Trade log updated with historical SPY prices!")
    print("Refresh your browser to see the realistic S&P 500 benchmark.")

except requests.RequestException as e:
    print(f"ERROR fetching SPY data: {e}")
    print("\nTrying alternative approach with yfinance...")

    try:
        import yfinance as yf
        print("Fetching via yfinance...")
        spy = yf.Ticker("SPY")
        hist = spy.history(start=start_date - timedelta(days=1),
                          end=end_date + timedelta(days=1))

        spy_prices = {}
        for date, row in hist.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            spy_prices[date_str] = row['Close']

        print(f"Fetched {len(spy_prices)} prices via yfinance")

        if len(spy_prices) == 0:
            print("ERROR: No data returned from yfinance")
            exit(1)

        # Backfill
        updated = 0
        for session in sessions:
            session_date = session['timestamp'][:10]

            if session_date in spy_prices:
                session['spy_price'] = round(spy_prices[session_date], 2)
                updated += 1
            else:
                available_dates = sorted(spy_prices.keys())
                if available_dates:
                    closest = min(available_dates,
                                 key=lambda d: abs(datetime.fromisoformat(d) - datetime.fromisoformat(session_date)))
                    session['spy_price'] = round(spy_prices[closest], 2)
                    updated += 1

        print(f"Updated {updated} sessions")

        with open('data/trade_log.json', 'w') as f:
            json.dump(trade_log, f, indent=2)

        print("✓ Done via yfinance!")

    except ImportError:
        print("ERROR: yfinance not installed. Install with: pip install yfinance")
        exit(1)
    except Exception as e2:
        print(f"ERROR with yfinance: {e2}")
        exit(1)

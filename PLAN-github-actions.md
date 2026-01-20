# Plan: GitHub Actions Auto-Refresh

## Overview
Automatically fetch market data every 5 minutes during market hours using GitHub Actions, storing results in a GitHub Gist that the local app can read.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Actions                          │
│  (runs every 5 min, Mon-Fri 9:30am-4pm ET)                 │
│                                                             │
│  1. Fetch prices for all 50 stocks                         │
│  2. Calculate indicators (RSI, SMA, ATR)                   │
│  3. Save JSON to GitHub Gist                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Gist                             │
│  market_data.json (public or secret gist)                  │
│  - timestamp                                                │
│  - prices: {AAPL: 250.00, ...}                             │
│  - analysis: {AAPL: {rsi: 45, sma_10: 248, ...}, ...}     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Local App                               │
│  python3 main.py status                                     │
│                                                             │
│  - Check gist timestamp                                     │
│  - If fresh (<10 min old): use cached data                 │
│  - If stale: fetch live (fallback)                         │
└─────────────────────────────────────────────────────────────┘
```

## Files to Create

### 1. `refresh_data.py` - Data fetcher for GitHub Actions
```python
# Fetches all stock data and outputs JSON
# - Runs headless (no rich output)
# - Handles errors gracefully
# - Outputs to stdout or file
```

### 2. `.github/workflows/market-refresh.yml` - Scheduled workflow
```yaml
name: Refresh Market Data
on:
  schedule:
    # Every 5 minutes, 9:30am-4pm ET (14:30-21:00 UTC), Mon-Fri
    - cron: '*/5 14-20 * * 1-5'
  workflow_dispatch:  # Manual trigger for testing

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install requests pandas
      - name: Fetch market data
        run: python refresh_data.py > market_data.json
      - name: Update Gist
        uses: exuanbo/actions-deploy-gist@v1
        with:
          token: ${{ secrets.GIST_TOKEN }}
          gist_id: <YOUR_GIST_ID>
          file_path: market_data.json
```

### 3. Update `market_data.py` - Add gist reading
```python
GIST_URL = "https://gist.githubusercontent.com/<user>/<gist_id>/raw/market_data.json"
CACHE_MAX_AGE = 600  # 10 minutes

def _fetch_from_gist():
    """Fetch cached data from GitHub Gist."""
    resp = requests.get(GIST_URL, timeout=5)
    data = resp.json()
    age = time.time() - data['timestamp']
    if age < CACHE_MAX_AGE:
        return data
    return None  # Too stale, fetch live
```

## Setup Steps

### One-time setup:
1. **Create GitHub Gist**
   - Go to https://gist.github.com
   - Create new gist with filename `market_data.json`
   - Content: `{}`
   - Note the gist ID from URL

2. **Create Personal Access Token**
   - GitHub Settings → Developer Settings → Personal Access Tokens
   - Create token with `gist` scope
   - Copy token

3. **Add secret to repo**
   - Repo Settings → Secrets → Actions
   - Add `GIST_TOKEN` with your token

4. **Push workflow file**
   - Commit `.github/workflows/market-refresh.yml`
   - GitHub Actions will start running on schedule

## Data Schema

```json
{
  "timestamp": 1705784400,
  "generated_at": "2025-01-20T14:30:00Z",
  "market_open": true,
  "stocks": {
    "AAPL": {
      "price": 250.47,
      "daily_change": -1.98,
      "weekly_change": -4.05,
      "monthly_change": -8.48,
      "rsi": 7.4,
      "atr": 4.44,
      "sma_10": 255.20,
      "sma_20": 260.15,
      "sma_50": 265.00,
      "volume": 43152369
    },
    ...
  }
}
```

## Cost & Limits

- **GitHub Actions**: 2,000 free minutes/month for private repos (unlimited for public)
- **Gist storage**: Free, unlimited
- **API calls**: ~78/day (every 5 min × 6.5 hours) = ~390/week

## Implementation Order

1. [ ] Create `refresh_data.py` script
2. [ ] Test locally: `python refresh_data.py`
3. [ ] Create GitHub Gist, note the ID
4. [ ] Create Personal Access Token
5. [ ] Add `GIST_TOKEN` secret to repo
6. [ ] Create `.github/workflows/market-refresh.yml`
7. [ ] Push and test with manual workflow trigger
8. [ ] Update `market_data.py` to read from gist
9. [ ] Test local app reads cached data

## Future Enhancements

- [ ] Add Slack/Discord notification on big movers
- [ ] Store historical data (append to gist or use separate storage)
- [ ] Add pre-market/after-hours data
- [ ] Alert when positions hit stop-loss levels

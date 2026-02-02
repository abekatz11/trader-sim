# Trader-Sim HOW-TO

Quick reference for starting and using the trading simulator.

## Prerequisites

- Python 3 installed
- Dependencies: `pip install -r requirements.txt`

## Starting the Program

You have three ways to run the simulator:

### 1. Web Dashboard (Recommended for browsing)
```bash
cd /Users/abekatz/trader-sim
python3 app.py
```
Then open http://localhost:8080 in your browser.

**Features:**
- View portfolio, holdings, P&L
- Execute trades via web form
- See transaction history
- Browse market data and stock screener

### 2. Claude Auto-Trader (Autonomous AI trading)
```bash
cd /Users/abekatz/trader-sim
./start_trader.sh
```
or
```bash
python3 claude_trader.py // This is the most important command.
```

**Options:**
- `--once` - Make one trading decision and exit
- `--force` - Trade even outside market hours (for testing)

**What it does:**
- Analyzes portfolio and market conditions
- Asks Claude for trading recommendations
- Validates trades against guardrails
- Executes approved trades
- Runs continuously (Ctrl+C to stop)

### 3. CLI Mode (For manual commands)
```bash
cd /Users/abekatz/trader-sim
python3 main.py status          # Show portfolio
python3 main.py prices          # Show stock prices
python3 main.py trade BUY TSLA 10   # Execute trade
python3 main.py analyze         # Market analysis
```

## Background Automation

GitHub Actions runs `refresh_data.py` every 5 minutes during market hours (9:30 AM - 4:00 PM ET, Mon-Fri) to update stock prices. This does NOT execute trades - it just refreshes market data.

## Checking if Running

```bash
ps aux | grep -E "python.*app.py|python.*claude_trader"
```

If you see output, the program is running. If not, nothing is active on your machine.

## Stopping the Program

Press `Ctrl+C` in the terminal where you started it.

## Quick Start Checklist

1. Open terminal
2. `cd /Users/abekatz/trader-sim`
3. Choose:
   - Web UI: `python3 app.py` → browse to http://localhost:8080
   - Auto-trader: `./start_trader.sh` → runs autonomously
   - CLI: `python3 main.py status` → view portfolio

## Files to Know

- `data/portfolio.json` - Current portfolio state (cash, holdings, trades)
- `data/market_data.json` - Latest stock prices
- `strategy_config.py` - Claude trader strategy and guardrails
- `claude.md` - Project documentation

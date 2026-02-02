# Summary

This is a realtime stock trading simulator.

It uses GitActions to check stock prices every 5 minutes and place buy/sell orders.
It logs its trades in data/portfolio.json.
The main executable is main.py (CLI) or app.py (Web UI).

## Running the Application

### CLI Mode
```bash
python main.py status      # Show portfolio status
python main.py prices      # Show current stock prices
python main.py trade BUY NVDA 5   # Execute a trade
python main.py analyze     # Generate market analysis
```

### Web UI Mode
```bash
python app.py              # Starts web server on port 8080
```
Then open http://localhost:8080 in your browser.

## Web UI Features
- Dashboard with portfolio value, cash, holdings, and P&L
- Quick trade form for buy/sell orders
- Holdings table with real-time prices and sell buttons
- Transaction history
- Market overview with gainers/losers and all stocks
- Stock screener with filtering criteria
- Stock detail modals with technical indicators (RSI, SMA, ATR)

## Project Structure
- `app.py` - Flask web server with REST API endpoints
- `main.py` - CLI entry point
- `portfolio.py` - Portfolio state management
- `market_data.py` - Yahoo Finance data fetching
- `trades.py` - Trade execution and validation
- `analyzer.py` - Market analysis and screening
- `config.py` - Configuration settings
- `templates/index.html` - Web UI dashboard
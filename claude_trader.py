#!/usr/bin/env python3
"""
Claude-Powered Auto Trader

This script:
1. Fetches current market data
2. Gets portfolio state
3. Asks Claude for trading decisions
4. Validates against guardrails
5. Executes approved trades
6. Logs everything

Runs locally using your Claude Pro subscription via the claude CLI.
"""

import subprocess
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pytz

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from portfolio import Portfolio
from market_data import get_stock_analysis, get_current_price
from trades import execute_trade, get_max_shares
from config import STOCK_UNIVERSE
from strategy_config import GUIDANCE, GUARDRAILS, SCHEDULE, LOGGING


# Track daily trades
_daily_trades = {"date": None, "count": 0, "buys": 0}


def is_market_hours() -> bool:
    """Check if we're within trading hours."""
    try:
        et = pytz.timezone('US/Eastern')
        now = datetime.now(et)

        # Check day of week
        if now.weekday() not in SCHEDULE["trade_days"]:
            return False

        # Parse market hours
        open_h, open_m = map(int, SCHEDULE["market_open"].split(":"))
        close_h, close_m = map(int, SCHEDULE["market_close"].split(":"))

        market_open = now.replace(hour=open_h, minute=open_m, second=0)
        market_close = now.replace(hour=close_h, minute=close_m, second=0)

        # Apply skip periods
        effective_open = market_open.replace(
            minute=open_m + SCHEDULE["skip_first_minutes"]
        )
        effective_close = market_close.replace(
            minute=close_m - SCHEDULE["skip_last_minutes"]
        )

        return effective_open <= now <= effective_close
    except Exception as e:
        print(f"Error checking market hours: {e}")
        return False


def check_internet() -> bool:
    """Check if we have internet connectivity."""
    try:
        import requests
        requests.get("https://query1.finance.yahoo.com", timeout=5)
        return True
    except Exception:
        return False


def reset_daily_trades_if_needed():
    """Reset daily trade counter if it's a new day."""
    global _daily_trades
    today = datetime.now().strftime("%Y-%m-%d")
    if _daily_trades["date"] != today:
        _daily_trades = {"date": today, "count": 0, "buys": 0}


def get_market_snapshot() -> Dict:
    """Get current market data for all stocks."""
    snapshot = {}
    for symbol in STOCK_UNIVERSE:
        analysis = get_stock_analysis(symbol)
        if analysis:
            snapshot[symbol] = analysis
    return snapshot


def build_claude_prompt(portfolio: Portfolio, market_data: Dict) -> str:
    """Build the prompt for Claude."""

    # Get portfolio status
    status = portfolio.get_status()

    # Format holdings
    holdings_str = "None" if not status['holdings'] else "\n".join([
        f"  {h['symbol']}: {h['shares']} shares @ ${h['avg_price']:.2f} "
        f"(current: ${h['current_price']:.2f}, P&L: {h['pnl_pct']:+.1f}%)"
        for h in status['holdings']
    ])

    # Format market data
    market_lines = []
    for symbol, data in sorted(market_data.items(), key=lambda x: x[1].get('daily_change', 0), reverse=True):
        rsi_note = ""
        if data['rsi'] < 30:
            rsi_note = " [OVERSOLD]"
        elif data['rsi'] > 70:
            rsi_note = " [OVERBOUGHT]"

        trend = []
        if data.get('above_sma_10'): trend.append("10")
        if data.get('above_sma_20'): trend.append("20")
        if data.get('above_sma_50'): trend.append("50")
        trend_str = f"above SMA {','.join(trend)}" if trend else "below all SMAs"

        market_lines.append(
            f"  {symbol}: ${data['price']:.2f} | "
            f"Daily: {data['daily_change']:+.1f}% | "
            f"Weekly: {data['weekly_change']:+.1f}% | "
            f"RSI: {data['rsi']:.0f}{rsi_note} | "
            f"{trend_str}"
        )
    market_str = "\n".join(market_lines)

    # Calculate max shares for each stock
    buying_power_lines = []
    for symbol, data in market_data.items():
        max_shares = get_max_shares(portfolio, symbol, data['price'])
        if max_shares > 0:
            buying_power_lines.append(f"  {symbol}: max {max_shares} shares (${data['price']:.2f} each)")
    buying_power_str = "\n".join(buying_power_lines[:15])  # Top 15 affordable

    prompt = f"""You are an autonomous stock trader. Analyze the current market and portfolio, then decide what trades to make.

## YOUR TRADING STRATEGY
{GUIDANCE}

## CURRENT PORTFOLIO
Cash: ${status['cash']:.2f}
Total Value: ${status['total_value']:.2f}
Positions: {status['num_holdings']}/{GUARDRAILS['max_positions']}

Holdings:
{holdings_str}

## MARKET DATA (sorted by daily change)
{market_str}

## BUYING POWER
{buying_power_str}

## GUARDRAILS (enforced by system)
- Max position size: {GUARDRAILS['max_position_pct']*100:.0f}% of portfolio
- Max positions: {GUARDRAILS['max_positions']}
- Max daily trades remaining: {GUARDRAILS['max_daily_trades'] - _daily_trades['count']}
- Max daily buys remaining: {GUARDRAILS['max_daily_buys'] - _daily_trades['buys']}
- Min cash reserve: ${GUARDRAILS['min_cash_reserve']}
- Force sell if position down more than {GUARDRAILS['max_single_loss_pct']}%

## YOUR TASK
Based on the strategy and current conditions, decide what trades to make RIGHT NOW.

Respond with ONLY a JSON object in this exact format:
{{
  "analysis": "Brief 1-2 sentence market assessment",
  "trades": [
    {{
      "action": "BUY" or "SELL",
      "symbol": "TICKER",
      "shares": number,
      "reasoning": "Why this trade fits the strategy"
    }}
  ],
  "hold_reasoning": "If no trades, explain why holding is the right choice"
}}

If no trades should be made, return an empty trades array with hold_reasoning.
Only suggest trades that respect the guardrails.
Be decisive - if you see a good opportunity, take it."""

    return prompt


def call_claude(prompt: str) -> Optional[Dict]:
    """Call Claude CLI and parse response."""
    try:
        # Write prompt to temp file to avoid shell escaping issues
        prompt_file = "/tmp/claude_trader_prompt.txt"
        with open(prompt_file, "w") as f:
            f.write(prompt)

        # Call claude CLI
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )

        if result.returncode != 0:
            print(f"Claude CLI error: {result.stderr}")
            return None

        response = result.stdout.strip()

        # Extract JSON from response (Claude might include extra text)
        json_start = response.find("{")
        json_end = response.rfind("}") + 1

        if json_start == -1 or json_end == 0:
            print(f"No JSON found in response: {response[:200]}")
            return None

        json_str = response[json_start:json_end]
        return json.loads(json_str)

    except subprocess.TimeoutExpired:
        print("Claude CLI timed out")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to parse Claude response as JSON: {e}")
        print(f"Response was: {response[:500]}")
        return None
    except Exception as e:
        print(f"Error calling Claude: {e}")
        return None


def validate_trade(trade: Dict, portfolio: Portfolio, market_data: Dict) -> Tuple[bool, str]:
    """Validate a trade against guardrails."""
    symbol = trade.get("symbol", "").upper()
    action = trade.get("action", "").upper()
    shares = trade.get("shares", 0)

    # Basic validation
    if not symbol or not action or shares <= 0:
        return False, "Invalid trade format"

    if symbol in GUARDRAILS.get("blocked_symbols", []):
        return False, f"{symbol} is blocked"

    if symbol not in market_data:
        return False, f"No market data for {symbol}"

    price = market_data[symbol]["price"]

    # Check daily trade limits
    if _daily_trades["count"] >= GUARDRAILS["max_daily_trades"]:
        return False, "Max daily trades reached"

    if action == "BUY":
        if _daily_trades["buys"] >= GUARDRAILS["max_daily_buys"]:
            return False, "Max daily buys reached"

        total_cost = shares * price

        # Check cash reserve
        if portfolio.cash - total_cost < GUARDRAILS["min_cash_reserve"]:
            return False, f"Would violate min cash reserve (${GUARDRAILS['min_cash_reserve']})"

        # Check min position value
        if total_cost < GUARDRAILS["min_position_value"]:
            return False, f"Position too small (min ${GUARDRAILS['min_position_value']})"

        # Check max position size
        new_position_value = total_cost
        if symbol in portfolio.holdings:
            new_position_value += portfolio.holdings[symbol].shares * price

        max_allowed = portfolio.get_total_value() * GUARDRAILS["max_position_pct"]
        if new_position_value > max_allowed:
            return False, f"Would exceed max position size ({GUARDRAILS['max_position_pct']*100:.0f}%)"

        # Check max positions
        if symbol not in portfolio.holdings and len(portfolio.holdings) >= GUARDRAILS["max_positions"]:
            return False, f"Max positions ({GUARDRAILS['max_positions']}) reached"

        # Check if we can afford it
        max_shares = get_max_shares(portfolio, symbol, price)
        if shares > max_shares:
            return False, f"Can only afford {max_shares} shares"

    elif action == "SELL":
        if symbol not in portfolio.holdings:
            return False, f"Don't own {symbol}"

        if shares > portfolio.holdings[symbol].shares:
            return False, f"Only own {portfolio.holdings[symbol].shares} shares"

    return True, "OK"


def execute_validated_trade(trade: Dict, portfolio: Portfolio) -> bool:
    """Execute a validated trade."""
    global _daily_trades

    symbol = trade["symbol"].upper()
    action = trade["action"].upper()
    shares = trade["shares"]

    result = execute_trade(portfolio, action, symbol, shares)

    if result.success:
        _daily_trades["count"] += 1
        if action == "BUY":
            _daily_trades["buys"] += 1
        return True
    else:
        print(f"Trade execution failed: {result.message}")
        return False


def log_trading_session(
    portfolio: Portfolio,
    market_data: Dict,
    claude_response: Optional[Dict],
    executed_trades: List[Dict],
    skipped_trades: List[Tuple[Dict, str]]
):
    """Log the trading session."""
    timestamp = datetime.now().isoformat()

    session = {
        "timestamp": timestamp,
        "portfolio_value": portfolio.get_total_value(),
        "cash": portfolio.cash,
        "positions": len(portfolio.holdings),
        "claude_analysis": claude_response.get("analysis") if claude_response else None,
        "executed_trades": executed_trades,
        "skipped_trades": [{"trade": t, "reason": r} for t, r in skipped_trades],
        "hold_reasoning": claude_response.get("hold_reasoning") if claude_response else None,
    }

    # Append to log file
    log_file = LOGGING["log_file"]
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    try:
        with open(log_file, "r") as f:
            log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log = {"sessions": []}

    log["sessions"].append(session)

    # Keep last 1000 sessions
    log["sessions"] = log["sessions"][-1000:]

    with open(log_file, "w") as f:
        json.dump(log, f, indent=2)

    # Print to console if verbose
    if LOGGING["verbose"]:
        print(f"\n{'='*60}")
        print(f"TRADING SESSION - {timestamp}")
        print(f"{'='*60}")
        print(f"Portfolio: ${portfolio.get_total_value():.2f} | Cash: ${portfolio.cash:.2f}")

        if claude_response:
            print(f"\nClaude's Analysis: {claude_response.get('analysis', 'N/A')}")

        if executed_trades:
            print(f"\nEXECUTED TRADES:")
            for t in executed_trades:
                print(f"  {t['action']} {t['shares']} {t['symbol']}: {t['reasoning']}")

        if skipped_trades:
            print(f"\nSKIPPED TRADES:")
            for t, reason in skipped_trades:
                print(f"  {t.get('action')} {t.get('symbol')}: {reason}")

        if claude_response and claude_response.get("hold_reasoning"):
            print(f"\nHold Reasoning: {claude_response['hold_reasoning']}")

        print(f"{'='*60}\n")


def run_trading_cycle():
    """Run one trading cycle."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting trading cycle...")

    # Check internet
    if not check_internet():
        print("No internet connection. Skipping cycle.")
        return

    # Reset daily counters if needed
    reset_daily_trades_if_needed()

    # Load portfolio
    portfolio = Portfolio()

    # Get market data
    print("Fetching market data...")
    market_data = get_market_snapshot()

    if not market_data:
        print("Failed to fetch market data. Skipping cycle.")
        return

    print(f"Got data for {len(market_data)} stocks")

    # Check for forced sells (stop loss)
    forced_sells = []
    for symbol, holding in list(portfolio.holdings.items()):
        if symbol in market_data:
            current_price = market_data[symbol]["price"]
            pnl_pct = ((current_price - holding.avg_price) / holding.avg_price) * 100
            if pnl_pct < -GUARDRAILS["max_single_loss_pct"]:
                print(f"STOP LOSS triggered for {symbol} ({pnl_pct:.1f}%)")
                result = execute_trade(portfolio, "SELL", symbol, holding.shares)
                if result.success:
                    forced_sells.append({
                        "action": "SELL",
                        "symbol": symbol,
                        "shares": holding.shares,
                        "reasoning": f"Stop loss triggered at {pnl_pct:.1f}%"
                    })
                    _daily_trades["count"] += 1

    # Build prompt and call Claude
    print("Consulting Claude for trading decisions...")
    prompt = build_claude_prompt(portfolio, market_data)
    claude_response = call_claude(prompt)

    executed_trades = forced_sells.copy()
    skipped_trades = []

    if claude_response and claude_response.get("trades"):
        for trade in claude_response["trades"]:
            valid, reason = validate_trade(trade, portfolio, market_data)

            if valid:
                success = execute_validated_trade(trade, portfolio)
                if success:
                    executed_trades.append(trade)
                else:
                    skipped_trades.append((trade, "Execution failed"))
            else:
                skipped_trades.append((trade, reason))

    # Log session
    log_trading_session(
        portfolio, market_data, claude_response,
        executed_trades, skipped_trades
    )

    print(f"Cycle complete. Executed {len(executed_trades)} trades.")


def run_continuous():
    """Run continuous trading during market hours."""
    print("=" * 60)
    print("CLAUDE AUTO-TRADER")
    print("=" * 60)
    print(f"Strategy loaded from strategy_config.py")
    print(f"Trading {len(STOCK_UNIVERSE)} stocks")
    print(f"Check interval: {SCHEDULE['check_interval_minutes']} minutes")
    print("=" * 60)

    while True:
        try:
            if is_market_hours():
                run_trading_cycle()
            else:
                et = pytz.timezone('US/Eastern')
                now = datetime.now(et)
                print(f"[{now.strftime('%H:%M:%S')} ET] Outside market hours. Waiting...")

            # Wait for next cycle
            time.sleep(SCHEDULE["check_interval_minutes"] * 60)

        except KeyboardInterrupt:
            print("\nStopping trader...")
            break
        except Exception as e:
            print(f"Error in trading cycle: {e}")
            time.sleep(60)  # Wait a minute before retrying


def run_once():
    """Run a single trading cycle (for testing)."""
    if not check_internet():
        print("No internet connection.")
        return

    run_trading_cycle()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Claude Auto-Trader")
    parser.add_argument("--once", action="store_true", help="Run once then exit")
    parser.add_argument("--force", action="store_true", help="Run even outside market hours")
    args = parser.parse_args()

    if args.once:
        if args.force or is_market_hours():
            run_once()
        else:
            print("Outside market hours. Use --force to run anyway.")
    else:
        run_continuous()

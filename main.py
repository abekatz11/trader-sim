#!/usr/bin/env python3
"""Trader-Sim: Stock Trading Simulator CLI."""

import sys
import argparse
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from portfolio import Portfolio
from market_data import get_current_prices, get_stock_analysis, is_using_sample_data
from trades import execute_trade, get_max_shares
from analyzer import generate_analysis, get_screened_opportunities
from config import STOCK_UNIVERSE, SIMULATION_DAYS, STARTING_CASH


def get_console():
    """Get rich console if available."""
    if RICH_AVAILABLE:
        return Console()
    return None


def print_header(text: str):
    """Print a header."""
    console = get_console()
    if console:
        console.print(Panel(text, style="bold blue"))
    else:
        print(f"\n{'='*50}")
        print(text)
        print('='*50)


def cmd_status(portfolio: Portfolio):
    """Show portfolio status."""
    print_header("Portfolio Status")

    status = portfolio.get_status()
    console = get_console()

    if console and RICH_AVAILABLE:
        # Summary table
        table = Table(title="Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Day", f"{status['day']} of {SIMULATION_DAYS}")
        table.add_row("Cash", f"${status['cash']:.2f}")
        table.add_row("Holdings Value", f"${status['holdings_value']:.2f}")
        table.add_row("Total Value", f"${status['total_value']:.2f}")

        return_style = "green" if status['total_return'] >= 0 else "red"
        table.add_row("Total Return", f"[{return_style}]{status['total_return']:+.2f}%[/{return_style}]")
        table.add_row("Positions", f"{status['num_holdings']}/5")
        table.add_row("Transactions", str(status['num_transactions']))

        console.print(table)

        # Holdings table
        if status['holdings']:
            console.print("")
            holdings_table = Table(title="Current Holdings")
            holdings_table.add_column("Symbol", style="cyan")
            holdings_table.add_column("Shares", justify="right")
            holdings_table.add_column("Avg Price", justify="right")
            holdings_table.add_column("Current", justify="right")
            holdings_table.add_column("Value", justify="right")
            holdings_table.add_column("P&L", justify="right")
            holdings_table.add_column("P&L %", justify="right")

            for h in status['holdings']:
                pnl_style = "green" if h['pnl'] >= 0 else "red"
                holdings_table.add_row(
                    h['symbol'],
                    str(h['shares']),
                    f"${h['avg_price']:.2f}",
                    f"${h['current_price']:.2f}",
                    f"${h['current_value']:.2f}",
                    f"[{pnl_style}]${h['pnl']:.2f}[/{pnl_style}]",
                    f"[{pnl_style}]{h['pnl_pct']:+.2f}%[/{pnl_style}]"
                )

            console.print(holdings_table)
        else:
            console.print("\n[yellow]No holdings yet. Use 'trade BUY <symbol> <shares>' to start trading.[/yellow]")
    else:
        # Plain text output
        print(f"\nDay: {status['day']} of {SIMULATION_DAYS}")
        print(f"Cash: ${status['cash']:.2f}")
        print(f"Holdings Value: ${status['holdings_value']:.2f}")
        print(f"Total Value: ${status['total_value']:.2f}")
        print(f"Total Return: {status['total_return']:+.2f}%")
        print(f"Positions: {status['num_holdings']}/5")

        if status['holdings']:
            print("\nCurrent Holdings:")
            print("-" * 60)
            for h in status['holdings']:
                print(f"  {h['symbol']}: {h['shares']} shares @ ${h['avg_price']:.2f} "
                      f"-> ${h['current_price']:.2f} (P&L: {h['pnl_pct']:+.2f}%)")
        else:
            print("\nNo holdings yet.")


def cmd_prices(symbols: Optional[list] = None):
    """Show current stock prices."""
    print_header("Current Prices")

    if symbols is None:
        symbols = STOCK_UNIVERSE

    print("Fetching prices...")
    prices = get_current_prices(symbols)

    console = get_console()
    if is_using_sample_data():
        if console and RICH_AVAILABLE:
            console.print("[yellow]Note: Using simulated data (Yahoo Finance API unavailable)[/yellow]\n")
        else:
            print("Note: Using simulated data (Yahoo Finance API unavailable)\n")

    if console and RICH_AVAILABLE:
        table = Table(title=f"Prices for {len(prices)} stocks")
        table.add_column("Symbol", style="cyan")
        table.add_column("Price", justify="right", style="green")

        for symbol in sorted(prices.keys()):
            table.add_row(symbol, f"${prices[symbol]:.2f}")

        console.print(table)
    else:
        for symbol in sorted(prices.keys()):
            print(f"  {symbol}: ${prices[symbol]:.2f}")


def cmd_trade(portfolio: Portfolio, action: str, symbol: str, shares: float):
    """Execute a trade."""
    print_header(f"Executing {action.upper()}")

    result = execute_trade(portfolio, action, symbol, shares)

    console = get_console()
    if result.success:
        if console and RICH_AVAILABLE:
            console.print(f"[green]SUCCESS:[/green] {result.message}")
            console.print(f"Total: ${result.total:.2f}")
        else:
            print(f"SUCCESS: {result.message}")
            print(f"Total: ${result.total:.2f}")
    else:
        if console and RICH_AVAILABLE:
            console.print(f"[red]FAILED:[/red] {result.message}")
        else:
            print(f"FAILED: {result.message}")


def cmd_analyze(portfolio: Portfolio):
    """Generate full market analysis."""
    print_header("Market Analysis")
    analysis = generate_analysis(portfolio)
    print(analysis)


def cmd_screen(portfolio: Portfolio):
    """Show screened stock opportunities."""
    print_header("Screened Opportunities")
    result = get_screened_opportunities(portfolio)
    print(result)


def cmd_history(portfolio: Portfolio, limit: int = 10):
    """Show transaction history."""
    print_header("Transaction History")

    transactions = portfolio.transactions[-limit:]

    if not transactions:
        print("No transactions yet.")
        return

    console = get_console()
    if console and RICH_AVAILABLE:
        table = Table(title=f"Last {len(transactions)} Transactions")
        table.add_column("Time", style="dim")
        table.add_column("Action", style="cyan")
        table.add_column("Symbol")
        table.add_column("Shares", justify="right")
        table.add_column("Price", justify="right")
        table.add_column("Total", justify="right")

        for t in transactions:
            action_style = "green" if t.action == "BUY" else "red"
            table.add_row(
                t.timestamp[:19],
                f"[{action_style}]{t.action}[/{action_style}]",
                t.symbol,
                str(t.shares),
                f"${t.price:.2f}",
                f"${t.total:.2f}"
            )

        console.print(table)
    else:
        for t in transactions:
            print(f"  {t.timestamp[:19]} | {t.action:4} | {t.symbol:5} | "
                  f"{t.shares} shares @ ${t.price:.2f} = ${t.total:.2f}")


def cmd_quote(symbol: str):
    """Get detailed quote for a symbol."""
    print_header(f"Quote: {symbol.upper()}")

    analysis = get_stock_analysis(symbol.upper())

    if analysis is None:
        print(f"Could not fetch data for {symbol}")
        return

    console = get_console()
    if console and RICH_AVAILABLE:
        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Price", f"${analysis['price']:.2f}")
        table.add_row("Daily Change", f"{analysis['daily_change']:+.2f}%")
        table.add_row("Weekly Change", f"{analysis['weekly_change']:+.2f}%")
        table.add_row("Monthly Change", f"{analysis['monthly_change']:+.2f}%")
        table.add_row("RSI", f"{analysis['rsi']:.1f}")
        table.add_row("ATR", f"${analysis['atr']:.2f}")
        table.add_row("SMA 10", f"${analysis['sma_10']:.2f}")
        table.add_row("SMA 20", f"${analysis['sma_20']:.2f}")
        table.add_row("SMA 50", f"${analysis['sma_50']:.2f}")
        table.add_row("Avg Volume", f"{analysis['avg_volume']:,}")

        console.print(table)
    else:
        print(f"  Price: ${analysis['price']:.2f}")
        print(f"  Daily Change: {analysis['daily_change']:+.2f}%")
        print(f"  Weekly Change: {analysis['weekly_change']:+.2f}%")
        print(f"  Monthly Change: {analysis['monthly_change']:+.2f}%")
        print(f"  RSI: {analysis['rsi']:.1f}")
        print(f"  ATR: ${analysis['atr']:.2f}")
        print(f"  SMA 10/20/50: ${analysis['sma_10']:.2f} / ${analysis['sma_20']:.2f} / ${analysis['sma_50']:.2f}")


def cmd_reset(portfolio: Portfolio):
    """Reset portfolio to initial state."""
    print_header("Reset Portfolio")

    confirm = input(f"This will reset your portfolio to ${STARTING_CASH} cash and no holdings. Confirm? (yes/no): ")
    if confirm.lower() == 'yes':
        portfolio.reset()
        print("Portfolio reset successfully.")
    else:
        print("Reset cancelled.")


def cmd_next_day(portfolio: Portfolio):
    """Advance to next trading day."""
    if portfolio.day >= SIMULATION_DAYS:
        print_header("Simulation Complete!")
        print(f"You've completed all {SIMULATION_DAYS} days.")
        cmd_status(portfolio)
        return

    portfolio.advance_day()
    print_header(f"Day {portfolio.day}")
    print(f"Advanced to day {portfolio.day} of {SIMULATION_DAYS}")
    cmd_status(portfolio)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Trader-Sim: Stock Trading Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status              Show portfolio status
  prices              Show current stock prices
  trade ACTION SYM N  Execute trade (e.g., trade BUY AAPL 5)
  analyze             Generate full market analysis
  screen              Show screened opportunities
  quote SYMBOL        Get detailed quote for a symbol
  history             Show transaction history
  next-day            Advance to next trading day
  reset               Reset portfolio to initial state

Examples:
  python main.py status
  python main.py trade BUY AAPL 5
  python main.py trade SELL AAPL 2
  python main.py quote MSFT
  python main.py analyze
        """
    )

    parser.add_argument('command', nargs='?', default='status',
                        help='Command to execute')
    parser.add_argument('args', nargs='*', help='Command arguments')

    args = parser.parse_args()

    # Initialize portfolio
    portfolio = Portfolio()

    command = args.command.lower()

    try:
        if command == 'status':
            cmd_status(portfolio)

        elif command == 'prices':
            symbols = args.args if args.args else None
            cmd_prices(symbols)

        elif command == 'trade':
            if len(args.args) < 3:
                print("Usage: trade <BUY|SELL> <SYMBOL> <SHARES>")
                print("Example: trade BUY AAPL 5")
                sys.exit(1)
            action, symbol, shares = args.args[0], args.args[1], float(args.args[2])
            cmd_trade(portfolio, action, symbol, shares)

        elif command == 'analyze':
            cmd_analyze(portfolio)

        elif command == 'screen':
            cmd_screen(portfolio)

        elif command == 'quote':
            if not args.args:
                print("Usage: quote <SYMBOL>")
                sys.exit(1)
            cmd_quote(args.args[0])

        elif command == 'history':
            limit = int(args.args[0]) if args.args else 10
            cmd_history(portfolio, limit)

        elif command == 'next-day':
            cmd_next_day(portfolio)

        elif command == 'reset':
            cmd_reset(portfolio)

        else:
            print(f"Unknown command: {command}")
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

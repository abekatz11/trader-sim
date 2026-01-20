"""Trade analysis and suggestion generation."""

from typing import Dict, List
from datetime import datetime

from portfolio import Portfolio
from market_data import get_market_summary, get_stock_analysis, screen_stocks
from trades import get_max_shares
from config import RISK, SIMULATION_DAYS


def format_portfolio_summary(portfolio: Portfolio, prices: Dict[str, float] = None) -> str:
    """Format portfolio status for analysis."""
    status = portfolio.get_status(prices)

    lines = [
        "=" * 50,
        "PORTFOLIO STATUS",
        "=" * 50,
        f"Day: {status['day']} of {SIMULATION_DAYS}",
        f"Cash: ${status['cash']:.2f}",
        f"Holdings Value: ${status['holdings_value']:.2f}",
        f"Total Value: ${status['total_value']:.2f}",
        f"Total Return: {status['total_return']:+.2f}%",
        f"Positions: {status['num_holdings']}/{RISK['max_positions']}",
        ""
    ]

    if status['holdings']:
        lines.append("CURRENT HOLDINGS:")
        lines.append("-" * 40)
        for h in status['holdings']:
            pnl_symbol = "+" if h['pnl'] >= 0 else ""
            lines.append(
                f"  {h['symbol']}: {h['shares']} shares @ ${h['avg_price']:.2f} "
                f"-> ${h['current_price']:.2f} ({pnl_symbol}{h['pnl_pct']:.1f}%)"
            )
        lines.append("")

    return "\n".join(lines)


def format_market_summary(summary: Dict) -> str:
    """Format market summary for analysis."""
    lines = [
        "=" * 50,
        "MARKET SUMMARY",
        "=" * 50,
        f"Stocks Analyzed: {summary['stocks_analyzed']}",
        f"Average Daily Change: {summary['avg_daily_change']:+.2f}%",
        f"Average RSI: {summary['avg_rsi']:.1f}",
        ""
    ]

    lines.append("TOP GAINERS:")
    for stock in summary['top_gainers'][:3]:
        lines.append(f"  {stock['symbol']}: {stock['daily_change']:+.2f}% (RSI: {stock['rsi']:.1f})")

    lines.append("")
    lines.append("TOP LOSERS:")
    for stock in summary['top_losers'][:3]:
        lines.append(f"  {stock['symbol']}: {stock['daily_change']:+.2f}% (RSI: {stock['rsi']:.1f})")

    return "\n".join(lines)


def format_stock_details(stocks: List[Dict]) -> str:
    """Format detailed stock analysis."""
    lines = [
        "",
        "=" * 50,
        "STOCK DETAILS",
        "=" * 50,
    ]

    for stock in stocks:
        trend = []
        if stock['above_sma_10']:
            trend.append("above SMA10")
        if stock['above_sma_20']:
            trend.append("above SMA20")
        if stock['above_sma_50']:
            trend.append("above SMA50")

        trend_str = ", ".join(trend) if trend else "below all SMAs"

        rsi_signal = ""
        if stock['rsi'] < 30:
            rsi_signal = " (OVERSOLD)"
        elif stock['rsi'] > 70:
            rsi_signal = " (OVERBOUGHT)"

        lines.append(f"\n{stock['symbol']} - ${stock['price']:.2f}")
        lines.append(f"  Daily: {stock['daily_change']:+.2f}% | Weekly: {stock['weekly_change']:+.2f}% | Monthly: {stock['monthly_change']:+.2f}%")
        lines.append(f"  RSI: {stock['rsi']:.1f}{rsi_signal} | ATR: ${stock['atr']:.2f}")
        lines.append(f"  Trend: {trend_str}")
        lines.append(f"  Volume: {stock['avg_volume']:,}")

    return "\n".join(lines)


def generate_analysis(portfolio: Portfolio) -> str:
    """Generate full analysis for Claude discussion."""
    print("Fetching market data...")
    market_summary = get_market_summary()

    if "error" in market_summary:
        return f"Error getting market data: {market_summary['error']}"

    # Build prices dict from market summary
    prices = {s['symbol']: s['price'] for s in market_summary['all_stocks']}

    # Format all sections
    portfolio_section = format_portfolio_summary(portfolio, prices)
    market_section = format_market_summary(market_summary)
    details_section = format_stock_details(market_summary['all_stocks'])

    # Add trading context
    status = portfolio.get_status(prices)
    days_remaining = SIMULATION_DAYS - status['day']

    context_lines = [
        "",
        "=" * 50,
        "TRADING CONTEXT",
        "=" * 50,
        f"Days Remaining: {days_remaining}",
        f"Max Position Size: {RISK['max_position_pct']*100:.0f}% of portfolio",
        f"Max Positions: {RISK['max_positions']}",
        f"Available Cash: ${status['cash']:.2f}",
        ""
    ]

    # Show what can be bought
    if status['cash'] > 10:
        context_lines.append("BUYING POWER (max shares at current prices):")
        for stock in sorted(market_summary['all_stocks'], key=lambda x: x['price']):
            max_shares = get_max_shares(portfolio, stock['symbol'], stock['price'])
            if max_shares > 0:
                context_lines.append(f"  {stock['symbol']}: {max_shares} shares (${stock['price']:.2f} each)")
        context_lines.append("")

    context_section = "\n".join(context_lines)

    # Combine all
    full_analysis = "\n".join([
        portfolio_section,
        market_section,
        details_section,
        context_section,
        "",
        "=" * 50,
        "Ready for trading discussion. What would you like to do?",
        "Commands: trade BUY/SELL <symbol> <shares>",
        "=" * 50,
    ])

    return full_analysis


def get_screened_opportunities(portfolio: Portfolio) -> str:
    """Get stocks that pass screening criteria."""
    print("Screening stocks...")
    screened = screen_stocks()

    if not screened:
        return "No stocks currently pass screening criteria."

    lines = [
        "=" * 50,
        "SCREENED OPPORTUNITIES",
        "=" * 50,
        f"Found {len(screened)} stocks passing filters:",
        ""
    ]

    # Sort by momentum (daily change)
    screened_sorted = sorted(screened, key=lambda x: x['daily_change'], reverse=True)

    for stock in screened_sorted:
        max_shares = get_max_shares(portfolio, stock['symbol'], stock['price'])
        lines.append(
            f"{stock['symbol']}: ${stock['price']:.2f} | "
            f"Daily: {stock['daily_change']:+.2f}% | "
            f"RSI: {stock['rsi']:.1f} | "
            f"Max Buy: {max_shares} shares"
        )

    return "\n".join(lines)

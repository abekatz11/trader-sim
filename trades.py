"""Trade execution and validation."""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from portfolio import Portfolio
from market_data import get_current_price
from config import RISK


@dataclass
class TradeResult:
    """Result of a trade attempt."""
    success: bool
    message: str
    symbol: str = ""
    action: str = ""
    shares: float = 0
    price: float = 0
    total: float = 0


def validate_buy(portfolio: Portfolio, symbol: str, shares: float, price: float) -> Tuple[bool, str]:
    """Validate a buy order."""
    # Check if symbol is benchmark-only (not tradeable)
    from config import BENCHMARK_ONLY
    if symbol in BENCHMARK_ONLY:
        return False, f"{symbol} is a benchmark symbol and cannot be traded"

    total_cost = shares * price

    # Check sufficient cash
    if total_cost > portfolio.cash:
        max_shares = int(portfolio.cash / price)
        return False, f"Insufficient cash. Have ${portfolio.cash:.2f}, need ${total_cost:.2f}. Max shares: {max_shares}"

    # Check position size limit
    total_value = portfolio.get_total_value()
    position_value = total_cost
    if symbol in portfolio.holdings:
        position_value += portfolio.holdings[symbol].shares * price

    if position_value / total_value > RISK['max_position_pct']:
        max_pct = RISK['max_position_pct'] * 100
        return False, f"Position would exceed {max_pct}% of portfolio"

    # Check max positions
    if symbol not in portfolio.holdings and len(portfolio.holdings) >= RISK['max_positions']:
        return False, f"Max positions ({RISK['max_positions']}) reached. Sell something first."

    return True, "Valid"


def validate_sell(portfolio: Portfolio, symbol: str, shares: float) -> Tuple[bool, str]:
    """Validate a sell order."""
    if symbol not in portfolio.holdings:
        return False, f"No position in {symbol}"

    holding = portfolio.holdings[symbol]
    if shares > holding.shares:
        return False, f"Insufficient shares. Have {holding.shares}, trying to sell {shares}"

    return True, "Valid"


def execute_buy(portfolio: Portfolio, symbol: str, shares: float, price: float = None) -> TradeResult:
    """Execute a buy order."""
    # Get current price if not provided
    if price is None:
        price = get_current_price(symbol)
        if price is None:
            return TradeResult(
                success=False,
                message=f"Could not fetch price for {symbol}"
            )

    # Validate
    valid, message = validate_buy(portfolio, symbol, shares, price)
    if not valid:
        return TradeResult(success=False, message=message)

    # Execute
    total_cost = shares * price
    portfolio.cash -= total_cost
    portfolio.add_holding(symbol, shares, price)
    portfolio.record_transaction("BUY", symbol, shares, price)
    portfolio.save()

    return TradeResult(
        success=True,
        message=f"Bought {shares} shares of {symbol} at ${price:.2f}",
        symbol=symbol,
        action="BUY",
        shares=shares,
        price=price,
        total=round(total_cost, 2)
    )


def execute_sell(portfolio: Portfolio, symbol: str, shares: float, price: float = None) -> TradeResult:
    """Execute a sell order."""
    # Get current price if not provided
    if price is None:
        price = get_current_price(symbol)
        if price is None:
            return TradeResult(
                success=False,
                message=f"Could not fetch price for {symbol}"
            )

    # Validate
    valid, message = validate_sell(portfolio, symbol, shares)
    if not valid:
        return TradeResult(success=False, message=message)

    # Calculate P&L before selling
    holding = portfolio.holdings[symbol]
    cost_per_share = holding.avg_price
    pnl = (price - cost_per_share) * shares

    # Execute
    total_proceeds = shares * price
    portfolio.cash += total_proceeds
    portfolio.remove_holding(symbol, shares, price)
    portfolio.record_transaction("SELL", symbol, shares, price)
    portfolio.save()

    pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
    return TradeResult(
        success=True,
        message=f"Sold {shares} shares of {symbol} at ${price:.2f} (P&L: {pnl_str})",
        symbol=symbol,
        action="SELL",
        shares=shares,
        price=price,
        total=round(total_proceeds, 2)
    )


def execute_trade(portfolio: Portfolio, action: str, symbol: str, shares: float, price: float = None) -> TradeResult:
    """Execute a trade (buy or sell)."""
    action = action.upper()
    symbol = symbol.upper()

    if action == "BUY":
        return execute_buy(portfolio, symbol, shares, price)
    elif action == "SELL":
        return execute_sell(portfolio, symbol, shares, price)
    else:
        return TradeResult(success=False, message=f"Unknown action: {action}. Use BUY or SELL.")


def get_max_shares(portfolio: Portfolio, symbol: str, price: float = None) -> int:
    """Calculate maximum shares that can be bought."""
    if price is None:
        price = get_current_price(symbol)
        if price is None:
            return 0

    # Based on cash
    max_by_cash = int(portfolio.cash / price)

    # Based on position limit
    total_value = portfolio.get_total_value()
    max_position = total_value * RISK['max_position_pct']
    current_position = 0
    if symbol in portfolio.holdings:
        current_position = portfolio.holdings[symbol].shares * price
    remaining_allocation = max_position - current_position
    max_by_position = int(remaining_allocation / price)

    return max(0, min(max_by_cash, max_by_position))

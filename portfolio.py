"""Portfolio state management and persistence."""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from config import STARTING_CASH, PORTFOLIO_FILE, DATA_DIR
from market_data import get_current_prices


@dataclass
class Holding:
    """Represents a stock holding."""
    symbol: str
    shares: float
    cost_basis: float  # Total cost paid
    avg_price: float   # Average price per share

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Holding':
        return cls(**data)


@dataclass
class Transaction:
    """Represents a trade transaction."""
    timestamp: str
    action: str  # BUY or SELL
    symbol: str
    shares: float
    price: float
    total: float

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Transaction':
        return cls(**data)


class Portfolio:
    """Manages portfolio state, holdings, and transactions."""

    def __init__(self):
        self.cash: float = STARTING_CASH
        self.holdings: Dict[str, Holding] = {}
        self.transactions: List[Transaction] = []
        self.start_date: str = datetime.now().isoformat()
        self.day: int = 1

        # Load existing state if available
        self._load()

    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

    def _load(self):
        """Load portfolio state from file."""
        if os.path.exists(PORTFOLIO_FILE):
            try:
                with open(PORTFOLIO_FILE, 'r') as f:
                    data = json.load(f)
                    self.cash = data.get('cash', STARTING_CASH)
                    self.holdings = {
                        k: Holding.from_dict(v)
                        for k, v in data.get('holdings', {}).items()
                    }
                    self.transactions = [
                        Transaction.from_dict(t)
                        for t in data.get('transactions', [])
                    ]
                    self.start_date = data.get('start_date', datetime.now().isoformat())
                    self.day = data.get('day', 1)
            except Exception as e:
                print(f"Error loading portfolio: {e}")

    def save(self):
        """Save portfolio state to file."""
        self._ensure_data_dir()
        data = {
            'cash': self.cash,
            'holdings': {k: v.to_dict() for k, v in self.holdings.items()},
            'transactions': [t.to_dict() for t in self.transactions],
            'start_date': self.start_date,
            'day': self.day,
        }
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def reset(self):
        """Reset portfolio to initial state."""
        self.cash = STARTING_CASH
        self.holdings = {}
        self.transactions = []
        self.start_date = datetime.now().isoformat()
        self.day = 1
        self.save()

    def add_holding(self, symbol: str, shares: float, price: float):
        """Add shares to a holding (for buys)."""
        total_cost = shares * price

        if symbol in self.holdings:
            existing = self.holdings[symbol]
            new_shares = existing.shares + shares
            new_cost_basis = existing.cost_basis + total_cost
            new_avg_price = new_cost_basis / new_shares
            self.holdings[symbol] = Holding(
                symbol=symbol,
                shares=new_shares,
                cost_basis=new_cost_basis,
                avg_price=round(new_avg_price, 2)
            )
        else:
            self.holdings[symbol] = Holding(
                symbol=symbol,
                shares=shares,
                cost_basis=total_cost,
                avg_price=price
            )

    def remove_holding(self, symbol: str, shares: float, price: float):
        """Remove shares from a holding (for sells)."""
        if symbol not in self.holdings:
            raise ValueError(f"No holding for {symbol}")

        holding = self.holdings[symbol]
        if shares > holding.shares:
            raise ValueError(f"Insufficient shares. Have {holding.shares}, trying to sell {shares}")

        if shares == holding.shares:
            # Selling all shares
            del self.holdings[symbol]
        else:
            # Partial sell - adjust cost basis proportionally
            sell_ratio = shares / holding.shares
            remaining_shares = holding.shares - shares
            remaining_cost_basis = holding.cost_basis * (1 - sell_ratio)
            self.holdings[symbol] = Holding(
                symbol=symbol,
                shares=remaining_shares,
                cost_basis=remaining_cost_basis,
                avg_price=holding.avg_price
            )

    def record_transaction(self, action: str, symbol: str, shares: float, price: float):
        """Record a transaction in history."""
        transaction = Transaction(
            timestamp=datetime.now().isoformat(),
            action=action,
            symbol=symbol,
            shares=shares,
            price=price,
            total=round(shares * price, 2)
        )
        self.transactions.append(transaction)

    def get_holdings_value(self, prices: Dict[str, float] = None) -> float:
        """Calculate total value of all holdings at current prices."""
        if not self.holdings:
            return 0.0

        if prices is None:
            prices = get_current_prices(list(self.holdings.keys()))

        total = 0.0
        for symbol, holding in self.holdings.items():
            if symbol in prices:
                total += holding.shares * prices[symbol]
            else:
                # Use cost basis if price unavailable
                total += holding.shares * holding.avg_price

        return round(total, 2)

    def get_total_value(self, prices: Dict[str, float] = None) -> float:
        """Calculate total portfolio value (cash + holdings)."""
        return round(self.cash + self.get_holdings_value(prices), 2)

    def get_total_return(self, prices: Dict[str, float] = None) -> float:
        """Calculate total return percentage."""
        total = self.get_total_value(prices)
        return round(((total - STARTING_CASH) / STARTING_CASH) * 100, 2)

    def get_holding_pnl(self, symbol: str, current_price: float) -> Dict:
        """Calculate P&L for a specific holding."""
        if symbol not in self.holdings:
            return None

        holding = self.holdings[symbol]
        current_value = holding.shares * current_price
        pnl = current_value - holding.cost_basis
        pnl_pct = (pnl / holding.cost_basis) * 100

        return {
            "symbol": symbol,
            "shares": holding.shares,
            "avg_price": holding.avg_price,
            "current_price": current_price,
            "cost_basis": round(holding.cost_basis, 2),
            "current_value": round(current_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        }

    def get_status(self, prices: Dict[str, float] = None) -> Dict:
        """Get full portfolio status."""
        if prices is None and self.holdings:
            prices = get_current_prices(list(self.holdings.keys()))
        elif prices is None:
            prices = {}

        holdings_detail = []
        for symbol in self.holdings:
            if symbol in prices:
                holdings_detail.append(self.get_holding_pnl(symbol, prices[symbol]))

        return {
            "day": self.day,
            "start_date": self.start_date,
            "cash": round(self.cash, 2),
            "holdings_value": self.get_holdings_value(prices),
            "total_value": self.get_total_value(prices),
            "total_return": self.get_total_return(prices),
            "num_holdings": len(self.holdings),
            "holdings": holdings_detail,
            "num_transactions": len(self.transactions),
        }

    def advance_day(self):
        """Advance to next trading day."""
        self.day += 1
        self.save()

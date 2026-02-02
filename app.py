"""Flask web application for Trader-Sim."""

import os
import json
from flask import Flask, render_template, jsonify, request

from portfolio import Portfolio
from market_data import (
    get_current_prices, get_stock_analysis, get_market_summary,
    screen_stocks, is_using_sample_data, get_data_source_status
)
from trades import execute_trade, get_max_shares
from config import STOCK_UNIVERSE, SIMULATION_DAYS, STARTING_CASH, RISK

app = Flask(__name__)


def get_portfolio():
    """Get fresh portfolio instance."""
    return Portfolio()


@app.route('/')
def index():
    """Serve the main dashboard."""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Get portfolio status."""
    portfolio = get_portfolio()
    status = portfolio.get_status()
    status['starting_cash'] = STARTING_CASH
    status['simulation_days'] = SIMULATION_DAYS
    status['max_positions'] = RISK['max_positions']
    status['data_source'] = get_data_source_status()
    status['using_sample_data'] = is_using_sample_data()
    return jsonify(status)


@app.route('/api/prices')
def api_prices():
    """Get current stock prices."""
    symbols = request.args.getlist('symbols') or STOCK_UNIVERSE
    prices = get_current_prices(symbols)
    return jsonify({
        'prices': prices,
        'data_source': get_data_source_status()
    })


@app.route('/api/quote/<symbol>')
def api_quote(symbol):
    """Get detailed quote for a symbol."""
    analysis = get_stock_analysis(symbol.upper())
    if analysis is None:
        return jsonify({'error': f'Could not fetch data for {symbol}'}), 404

    portfolio = get_portfolio()
    analysis['max_shares'] = get_max_shares(portfolio, symbol.upper(), analysis['price'])
    return jsonify(analysis)


@app.route('/api/market')
def api_market():
    """Get market summary."""
    summary = get_market_summary()
    summary['data_source'] = get_data_source_status()
    return jsonify(summary)


@app.route('/api/screen')
def api_screen():
    """Get screened stock opportunities."""
    screened = screen_stocks()
    portfolio = get_portfolio()

    for stock in screened:
        stock['max_shares'] = get_max_shares(portfolio, stock['symbol'], stock['price'])

    screened_sorted = sorted(screened, key=lambda x: x['daily_change'], reverse=True)
    return jsonify({
        'stocks': screened_sorted,
        'count': len(screened_sorted)
    })


@app.route('/api/history')
def api_history():
    """Get transaction history."""
    portfolio = get_portfolio()
    limit = request.args.get('limit', 50, type=int)
    transactions = portfolio.transactions[-limit:]
    return jsonify({
        'transactions': [t.to_dict() for t in reversed(transactions)],
        'total': len(portfolio.transactions)
    })


@app.route('/api/trade', methods=['POST'])
def api_trade():
    """Execute a trade."""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    action = data.get('action', '').upper()
    symbol = data.get('symbol', '').upper()
    shares = data.get('shares', 0)

    if action not in ['BUY', 'SELL']:
        return jsonify({'success': False, 'message': 'Action must be BUY or SELL'}), 400

    if not symbol:
        return jsonify({'success': False, 'message': 'Symbol is required'}), 400

    try:
        shares = float(shares)
        if shares <= 0:
            return jsonify({'success': False, 'message': 'Shares must be positive'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid shares value'}), 400

    portfolio = get_portfolio()
    result = execute_trade(portfolio, action, symbol, shares)

    return jsonify({
        'success': result.success,
        'message': result.message,
        'symbol': result.symbol,
        'action': result.action,
        'shares': result.shares,
        'price': result.price,
        'total': result.total
    })


@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Reset portfolio to initial state."""
    portfolio = get_portfolio()
    portfolio.reset()
    return jsonify({'success': True, 'message': 'Portfolio reset successfully'})


@app.route('/api/config')
def api_config():
    """Get configuration info."""
    return jsonify({
        'stock_universe': STOCK_UNIVERSE,
        'starting_cash': STARTING_CASH,
        'simulation_days': SIMULATION_DAYS,
        'risk': RISK
    })


@app.route('/api/value-history')
def api_value_history():
    """Get portfolio value history for charting."""
    history = []

    # First, try to load from trade_log.json (created by claude_trader.py)
    trade_log_file = 'data/trade_log.json'
    if os.path.exists(trade_log_file):
        try:
            with open(trade_log_file, 'r') as f:
                trade_log = json.load(f)
                for session in trade_log.get('sessions', []):
                    history.append({
                        'timestamp': session.get('timestamp'),
                        'total_value': session.get('portfolio_value', 0),
                        'cash': session.get('cash', 0),
                        'holdings_value': session.get('portfolio_value', 0) - session.get('cash', 0)
                    })
        except (json.JSONDecodeError, IOError):
            pass

    # Also include any snapshots from portfolio.value_history (from web UI trades)
    portfolio = get_portfolio()
    for snapshot in portfolio.get_value_history():
        history.append(snapshot)

    # Sort by timestamp and remove duplicates
    history.sort(key=lambda x: x.get('timestamp', ''))

    return jsonify({
        'history': history,
        'starting_cash': STARTING_CASH,
        'count': len(history)
    })


@app.route('/data/trade_log.json')
def serve_trade_log():
    """Serve the trade log JSON file."""
    trade_log_file = 'data/trade_log.json'
    if os.path.exists(trade_log_file):
        with open(trade_log_file, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({'sessions': []}), 404


@app.route('/data/portfolio.json')
def serve_portfolio():
    """Serve the portfolio JSON file."""
    portfolio_file = 'data/portfolio.json'
    if os.path.exists(portfolio_file):
        with open(portfolio_file, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)

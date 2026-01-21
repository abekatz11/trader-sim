#!/bin/bash
# Start the Claude Auto-Trader
# Usage: ./start_trader.sh [--once] [--force]

cd "$(dirname "$0")"

echo "Starting Claude Auto-Trader..."
echo "Press Ctrl+C to stop"
echo ""

python3 claude_trader.py "$@"

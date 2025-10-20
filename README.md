# zen-options-Bot

An intelligent, trigger-based options trading framework that automates signal detection, strike selection, and order execution.

### 🔧 Features
- **Breakout trigger logic** (detects up/down momentum)
- **Dynamic strike selection** based on price direction & thresholds
- **Configurable DUMMY / LIVE modes** for safe testing or IBKR trading
- **Smart order placement** with take-profit, stop-loss, and partial-sell (OCA group)
- **Automatic end-of-day cleanup** for open positions or orders
- **Full logging support** (file + console)

### ⚙️ Environment Variables
SYMBOLS=SPY
POSITION_USD=10000
MODE=DUMMY
TAKE_PROFIT_PCT=0.10
STOP_LOSS_PCT=0.10
EOD_TIME=15:50

yaml
Copy code

### 🧠 Logic Overview
1. Fetch 5-min bars (dummy or IBKR live)
2. Detect direction trigger (momentum breakout)
3. Select near-the-money strike based on direction
4. Place orders with TP/SL and partial exits
5. Auto-cleanup at EOD

---

Built with ❤️ for algorithmic traders experimenting with options strategies.

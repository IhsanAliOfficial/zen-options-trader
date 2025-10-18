
**Options Trading Algorithm**

This repository implements a strategy based on 5-minute stock price candles, executing options orders via Interactive Brokers TWS.

## Features
- Ignores the first 15 minutes of trading
- Trades only between 07:45 and 10:00 MST
- Identifies a trigger candle and confirms entry on a wick-break pattern
- Positions sized to \$10,000 per trade in next-day expiration options < \$1 OTM
- Take profit at 10% (sell 90%), hold 10% until EOD or 10% SL
- IB TWS integration with clean code and basic logging

## Requirements
- Python 3.8+
- `ib_insync`, `pandas`, `pytz`, `schedule`

## Installation
```bash
pip install ib_insync pandas pytz schedule
```

## Configuration
Edit the `CONFIG` section in `strategy.py` for symbol and IB connection parameters.

## Usage
```bash
python strategy.py
```

## Output
```bash
Trigger found at: 2025-04-21 07:20:00+00:00

Contract sizing tests:
  Price = 2.5 → Contracts = 40
  Price = 0 → Contracts = 0
  Price = -1 → Contracts = 0

```

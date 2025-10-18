import os
import math
import pytz
import logging
import sys
import numpy as np  # <-- numpy import
from datetime import datetime, timedelta, time
from dotenv import load_dotenv
import pandas as pd
from ib_insync import IB, Stock, Option, MarketOrder, LimitOrder, util

# ----------------- LOAD ENV -----------------
load_dotenv()

C = {
    "symbols": os.getenv("SYMBOLS", "SPY").split(","),
    "position_usd": float(os.getenv("POSITION_USD", 10000)),
    "ignore_minutes": int(os.getenv("IGNORE_MINUTES", 15)),
    "otm_threshold": float(os.getenv("OTM_THRESHOLD", 1.0)),
    "exp_days_ahead": int(os.getenv("EXP_DAYS_AHEAD", 1)),
    "timezone": os.getenv("TIMEZONE", "US/Mountain"),
    "mode": os.getenv("MODE", "DUMMY"),
    "take_profit_pct": float(os.getenv("TAKE_PROFIT_PCT", 0.10)),
    "partial_sell_pct": float(os.getenv("PARTIAL_SELL_PCT", 0.90)),
    "stop_loss_pct": float(os.getenv("STOP_LOSS_PCT", 0.10)),
    "eod_time": os.getenv("EOD_TIME", "15:50"),
    "ib_host": os.getenv("IB_HOST", "127.0.0.1"),
    "ib_port": int(os.getenv("IB_PORT", 7497)),
    "ib_client_id": int(os.getenv("IB_CLIENT_ID", 1)),
    "log_file": os.getenv("LOG_FILE", "strategy.log")
}

tz = pytz.timezone(C["timezone"])

# ----------------- LOGGING (FILE + CONSOLE) -----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(C["log_file"]),
        logging.StreamHandler(sys.stdout)
    ]
)

# ----------------- IB CONNECTION -----------------
def connect_ib():
    ib = IB()
    if C["mode"] != "DUMMY":
        ib.connect(C["ib_host"], C["ib_port"], clientId=C["ib_client_id"])
        logging.info("Connected to IB")
    else:
        logging.info("Running in DUMMY mode (no live connection)")
    return ib

# ----------------- GET BARS -----------------
def get_bars(ib, sym):
    if C["mode"] == "DUMMY":
        # Generate dummy bars (1 day, 5min intervals)
        times = pd.date_range(datetime.now() - timedelta(hours=6), periods=72, freq='5min', tz='UTC')
        prices = pd.Series(400 + np.random.randn(len(times)).cumsum(), index=times)  # <-- fix
        df = pd.DataFrame({"open": prices, "high": prices + 1, "low": prices - 1, "close": prices})
    else:
        bars = ib.reqHistoricalData(
            Stock(sym,'SMART','USD'), '', '1 D', '5 mins',
            'TRADES', True, 1
        )
        df = util.df(bars)
        df.index = pd.to_datetime(df.date)
        df.index = df.index.tz_localize('UTC') if df.index.tz is None else df.index.tz_convert('UTC')
        df = df[['open','high','low','close']]
    return df

# ----------------- TRIGGER LOGIC -----------------
def find_trigger(df):
    df2 = df[df.index >= df.index[0] + pd.Timedelta(minutes=C["ignore_minutes"])]
    if df2.empty: return None, None

    trigger = df2.iloc[0]
    for curr in df2.iloc[1:].itertuples():
        prev = trigger
        prev_dir = 'up' if prev.close > prev.open else 'down'
        curr_dir = 'up' if curr.close > curr.open else 'down'

        if prev_dir == curr_dir:
            if (prev_dir == 'up' and curr.close > prev.high) or \
               (prev_dir == 'down' and curr.close < prev.low):
                return curr.Index, prev_dir
        trigger = df2.loc[curr.Index]
    return None, None

# ----------------- POSITION SIZING -----------------
def size(price):
    return int(C["position_usd"] / (price * 100)) if price and price > 0 else 0

# ----------------- OPTION SELECTION -----------------
def select_option(ib, sym, direction, bars):
    price = bars['close'].iloc[-1]
    exp = (datetime.now(tz).date() + timedelta(days=C["exp_days_ahead"])).strftime('%Y%m%d')
    strike = math.ceil(price) if direction=='up' else math.floor(price)
    if abs(strike - price) > C["otm_threshold"]:
        strike = int(price) + (1 if direction=='up' else -1)
    right = 'CALL' if direction=='up' else 'PUT'
    return Option(sym, exp, strike, right, 'SMART')

# ----------------- PLACE ORDERS -----------------
def place_orders(ib, contract, qty):
    if qty < 1:
        logging.warning(f"{contract.symbol} qty {qty}<1, skipping")
        return

    if C["mode"] == "DUMMY":
        msg = f"[DUMMY] BUY {qty}@{contract.symbol} {contract.strike} {contract.right}"
        logging.info(msg)
        print(msg)
    else:
        tr = ib.placeOrder(contract, MarketOrder('BUY', qty))
        ib.sleep(1)
        fill = tr.orderStatus.avgFillPrice
        logging.info(f"ENTERED {qty}@{fill:.2f} {contract.symbol} {contract.strike} {contract.right}")
        tp = fill * (1 + C["take_profit_pct"])
        sl = fill * (1 - C["stop_loss_pct"])
        tp_qty = int(qty * C["partial_sell_pct"])
        oca = f"OCA_{datetime.now(tz).strftime('%H%M%S')}"
        for q, price in [(tp_qty, tp), (qty, sl)]:
            order = LimitOrder('SELL', q, price)
            order.ocaGroup = oca; order.ocaType = 2
            ib.placeOrder(contract, order)
        logging.info(f"TP@{tp:.2f} SL@{sl:.2f} placed for {contract.symbol}")

# ----------------- EOD CLEANUP -----------------
def eod_cleanup(ib):
    now = datetime.now(tz)
    cutoff = tz.localize(datetime.combine(now.date(), time.fromisoformat(C["eod_time"])))
    if now < cutoff: return
    if C["mode"] == "DUMMY":
        logging.info("[DUMMY] EOD cleanup - no live orders to cancel")
        print("[DUMMY] EOD cleanup - no live orders to cancel")
    else:
        for o in ib.openOrders(): ib.cancelOrder(o)
        for pos in ib.positions():
            if pos.position:
                side = 'SELL' if pos.position>0 else 'BUY'
                ib.placeOrder(pos.contract, MarketOrder(side, abs(int(pos.position))))
        ib.disconnect()
        logging.info("EOD cleanup completed")

# ----------------- STRATEGY RUN -----------------
def run_strategy():
    logging.info("=== Strategy started ===")
    print("=== Strategy started ===")
    ib = connect_ib()
    for sym in C["symbols"]:
        try:
            bars = get_bars(ib, sym)
            t_time, direction = find_trigger(bars)
            if not t_time:
                logging.info(f"{sym} no trigger")
                print(f"{sym} no trigger")
                continue

            local_time = t_time.astimezone(tz).strftime('%H:%M:%S %Z')
            logging.info(f"{sym} trigger at {local_time}, dir={direction}")
            print(f"{sym} trigger at {local_time}, dir={direction}")

            contract = select_option(ib, sym, direction, bars)
            qty = size(bars['close'].iloc[-1])
            if qty < 1:
                logging.warning(f"{sym} qty {qty}<1, skipping")
                print(f"{sym} qty {qty}<1, skipping")
                continue
            place_orders(ib, contract, qty)

        except Exception as e:
            logging.error(f"Error processing {sym}: {e}")
            print(f"Error processing {sym}: {e}")

    eod_cleanup(ib)
    logging.info("=== Strategy completed ===")
    print("=== Strategy completed ===")

if __name__ == "__main__":
    run_strategy()

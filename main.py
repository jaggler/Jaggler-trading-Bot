import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import sqlite3
import time
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier

#############################################
# CONFIG
#############################################

SYMBOLS = ["EURUSD","GBPUSD","XAUUSD"]
TIMEFRAME = mt5.TIMEFRAME_M5
BARS = 500

LOT = 0.10
MAX_TRADES_PER_DAY = 5

#############################################
# DATABASE
#############################################

conn = sqlite3.connect("trades.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS trades(
id INTEGER PRIMARY KEY AUTOINCREMENT,
symbol TEXT,
direction TEXT,
price REAL,
sl REAL,
tp REAL,
lot REAL,
confidence REAL,
volatility REAL,
time TEXT
)
""")

conn.commit()

#############################################
# DAILY TRADE LIMIT
#############################################

def trades_today():

    today = datetime.utcnow().date()

    cursor.execute("SELECT time FROM trades")

    rows = cursor.fetchall()

    count = 0

    for r in rows:

        trade_time = datetime.fromisoformat(r[0]).date()

        if trade_time == today:
            count += 1

    return count


#############################################
# SESSION FILTER
#############################################

def session_filter():

    hour = datetime.utcnow().hour

    # London + NY
    if 7 <= hour <= 11 or 13 <= hour <= 17:
        return True

    return False


#############################################
# CHECK OPEN POSITION
#############################################

def position_open(symbol):

    positions = mt5.positions_get(symbol=symbol)

    if positions:
        return True

    return False


#############################################
# LOG TRADE
#############################################

def log_trade(symbol,direction,price,sl,tp,lot,confidence,volatility):

    cursor.execute("""
    INSERT INTO trades
    (symbol,direction,price,sl,tp,lot,confidence,volatility,time)
    VALUES (?,?,?,?,?,?,?,?,?)
    """,(symbol,direction,price,sl,tp,lot,confidence,volatility,str(datetime.utcnow())))

    conn.commit()


#############################################
# FEATURES
#############################################

def add_features(df):

    df["return"] = df["close"].pct_change()

    df["volatility_20"] = df["return"].rolling(20).std()

    df["ma_fast"] = df["close"].rolling(10).mean()
    df["ma_slow"] = df["close"].rolling(50).mean()

    df["trend"] = df["ma_fast"] > df["ma_slow"]

    # RSI
    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df["rsi"] = 100 - (100/(1+rs))

    df = df.dropna()

    return df


#############################################
# ATR
#############################################

def add_atr(df):

    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = abs(high-close.shift())
    tr3 = abs(low-close.shift())

    tr = pd.concat([tr1,tr2,tr3],axis=1).max(axis=1)

    df["atr_14"] = tr.rolling(14).mean()

    return df


#############################################
# GET DATA
#############################################

def get_data(symbol):

    rates = mt5.copy_rates_from_pos(symbol,TIMEFRAME,0,BARS)

    df = pd.DataFrame(rates)

    df["time"] = pd.to_datetime(df["time"],unit="s")

    return df


#############################################
# SEND ORDER
#############################################

def send_order(symbol,order_type,lot,price,sl,tp):

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol":symbol,
        "volume":lot,
        "type":order_type,
        "price":price,
        "sl":sl,
        "tp":tp,
        "deviation":20,
        "magic":1001,
        "comment":"ML BOT",
        "type_time":mt5.ORDER_TIME_GTC,
        "type_filling":mt5.ORDER_FILLING_IOC
    }

    result = mt5.order_send(request)

    print("ORDER RESULT:",result)


#############################################
# MAIN PIPELINE
#############################################

def run_bot(symbol):

    print("====================================")
    print("SCANNING:",symbol)
    print("====================================")

    if not session_filter():

        print("Outside trading session")
        return

    if position_open(symbol):

        print("Position already open")
        return

    if trades_today() >= MAX_TRADES_PER_DAY:

        print("Daily trade limit reached")
        return

    df = get_data(symbol)

    df = add_features(df)

    df = add_atr(df)

    if len(df) < 100:

        print("Not enough data")
        return

    # TARGET
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)

    features = df[["volatility_20","trend","rsi"]]

    X = features
    y = df["target"]

    model = RandomForestClassifier(n_estimators=150)

    model.fit(X,y)

    latest = X.tail(1)

    proba = model.predict_proba(latest)[0][1]

    direction = "LONG" if proba > 0.5 else "SHORT"

    # SNIPER FILTER
    if proba < 0.55:

        print("Weak signal")
        return

    atr = df["atr_14"].iloc[-1]

    if atr < df["atr_14"].mean():

        print("Low volatility")
        return

    tick = mt5.symbol_info_tick(symbol)

    if direction == "LONG":

        price = tick.ask

    else:

        price = tick.bid

    sl_dist = atr * 1.5
    tp_dist = atr * 3

    if direction == "LONG":

        sl = price - sl_dist
        tp = price + tp_dist
        order_type = mt5.ORDER_TYPE_BUY

    else:

        sl = price + sl_dist
        tp = price - tp_dist
        order_type = mt5.ORDER_TYPE_SELL

    send_order(symbol,order_type,LOT,price,sl,tp)

    log_trade(
        symbol,
        direction,
        price,
        sl,
        tp,
        LOT,
        proba,
        latest["volatility_20"].values[0]
    )

    print("TRADE EXECUTED")


#############################################
# START MT5
#############################################

if not mt5.initialize():

    print("MT5 INIT FAILED")
    quit()

#############################################
# RUN LOOP
#############################################

while True:

    for symbol in SYMBOLS:

        run_bot(symbol)

    print("Sleeping 300 seconds...\n")

    time.sleep(300)
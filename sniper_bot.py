
# Create a completely clean version without any multiline f-strings

clean_bot_code = '''# -*- coding: utf-8 -*-
"""
SNIPER BOT V4 - CLEAN VERSION
Forex Trading Bot for 5,000 KSh Daily Target
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import sqlite3
import time
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURATION
# =============================================================================

ACCOUNT_CURRENCY = "USD"
DAILY_PROFIT_TARGET = 50
DAILY_LOSS_LIMIT = 30
RISK_PER_TRADE = 1.5
MIN_CONFIDENCE = 0.65

SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]
TIMEFRAME = mt5.TIMEFRAME_H1

# =============================================================================
# DATABASE
# =============================================================================

def init_db():
    conn = sqlite3.connect("trades.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY,
            time TEXT, symbol TEXT, direction TEXT,
            entry REAL, sl REAL, tp REAL, lot REAL,
            confidence REAL, result TEXT DEFAULT 'OPEN'
        )
    """)
    conn.commit()
    conn.close()

def log_trade(symbol, direction, entry, sl, tp, lot, confidence):
    conn = sqlite3.connect("trades.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trades (time, symbol, direction, entry, sl, tp, lot, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(datetime.now()), symbol, direction, entry, sl, tp, lot, confidence))
    conn.commit()
    conn.close()

# =============================================================================
# SESSION FILTER
# =============================================================================

def check_session(symbol):
    hour = datetime.utcnow().hour
    if 7 <= hour <= 20:
        return True
    if symbol == "XAUUSD" and 8 <= hour <= 19:
        return True
    return False

# =============================================================================
# FEATURES
# =============================================================================

def get_features(df):
    df['return'] = df['close'].pct_change()
    df['ema_10'] = df['close'].ewm(span=10).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    df['trend'] = (df['ema_10'] > df['ema_50']).astype(int)
    
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df.dropna()

# =============================================================================
# SNIPER SIGNAL
# =============================================================================

def get_sniper_signal(symbol):
    if not check_session(symbol):
        return None
    
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, 500)
    if rates is None or len(rates) < 100:
        return None
    
    df = pd.DataFrame(rates)
    df = get_features(df)
    
    if len(df) < 50:
        return None
    
    df['target'] = (df['close'].shift(-3) > df['close']).astype(int)
    df = df.dropna()
    
    X = df[['return', 'trend', 'rsi', 'atr']]
    y = df['target']
    
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    test_proba = model.predict_proba(X_test)[:, 1]
    high_conf_mask = test_proba > MIN_CONFIDENCE
    
    if high_conf_mask.sum() > 0:
        precision = precision_score(y_test[high_conf_mask], 
                                   (test_proba[high_conf_mask] > 0.5).astype(int))
    else:
        precision = 0
    
    if precision < 0.60:
        print("  " + symbol + ": Model precision too low (" + str(round(precision*100,1)) + "%), skipping")
        return None
    
    latest = X.tail(1)
    proba = model.predict_proba(latest)[0, 1]
    
    direction = "LONG" if proba > 0.5 else "SHORT"
    confidence = proba if direction == "LONG" else (1 - proba)
    
    if confidence < MIN_CONFIDENCE:
        return None
    
    current_price = df['close'].iloc[-1]
    current_atr = df['atr'].iloc[-1]
    
    if direction == "LONG":
        sl = current_price - (current_atr * 1.5)
        tp = current_price + (current_atr * 3.0)
    else:
        sl = current_price + (current_atr * 1.5)
        tp = current_price - (current_atr * 3.0)
    
    risk = abs(current_price - sl)
    reward = abs(tp - current_price)
    rr = reward / risk if risk > 0 else 0
    
    if rr < 2.0:
        return None
    
    return {
        'symbol': symbol,
        'direction': direction,
        'confidence': confidence,
        'entry': current_price,
        'sl': sl,
        'tp': tp,
        'rr': rr,
        'precision': precision
    }

# =============================================================================
# EXECUTION
# =============================================================================

def calculate_lot(symbol, entry, sl):
    account = mt5.account_info()
    if account is None:
        return 0.01
    
    balance = account.balance
    risk_amount = balance * (RISK_PER_TRADE / 100)
    
    stop_distance = abs(entry - sl)
    if stop_distance == 0:
        return 0.01
    
    if symbol == "XAUUSD":
        point_value = 1.0
        stop_points = stop_distance / 0.01
    else:
        point_value = 10.0
        pip_size = 0.0001
        stop_points = stop_distance / pip_size
    
    lot = risk_amount / (stop_points * point_value)
    lot = min(lot, 0.1)
    lot = max(lot, 0.01)
    
    return round(lot, 2)

def execute_trade(signal):
    symbol = signal['symbol']
    direction = signal['direction']
    
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return False
    
    price = tick.ask if direction == "LONG" else tick.bid
    lot = calculate_lot(symbol, price, signal['sl'])
    
    order_type = mt5.ORDER_TYPE_BUY if direction == "LONG" else mt5.ORDER_TYPE_SELL
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": signal['sl'],
        "tp": signal['tp'],
        "deviation": 20,
        "magic": 1001,
        "comment": "SNIPER",
        "type_time": mt5.TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }
    
    result = mt5.order_send(request)
    
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print("[OK] TRADE EXECUTED: " + symbol + " " + direction)
        print("     Price: " + str(round(price,5)) + ", Lot: " + str(lot) + ", RR: " + str(round(signal['rr'],1)) + ":1")
        log_trade(symbol, direction, price, signal['sl'], signal['tp'], lot, signal['confidence'])
        return True
    else:
        print("[FAIL] Order failed: " + str(result.retcode if result else 'None'))
        return False

# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    print("="*60)
    print("SNIPER BOT V4 - 5,000 KSh Daily Target")
    print("="*60)
    
    init_db()
    
    if not mt5.initialize():
        print("[FAIL] MT5 not running")
        return
    
    account = mt5.account_info()
    if account:
        print("[OK] Connected: " + str(account.login))
        print("     Balance: $" + str(round(account.balance, 2)))
    
    print("")
    print("Settings:")
    print("  Daily Target: $" + str(DAILY_PROFIT_TARGET))
    print("  Daily Loss Limit: $" + str(DAILY_LOSS_LIMIT))
    print("  Risk Per Trade: " + str(RISK_PER_TRADE) + "%")
    print("  Min Confidence: " + str(MIN_CONFIDENCE))
    print("  Symbols: " + ", ".join(SYMBOLS))
    print("")
    print("[OK] Bot started - Press Ctrl+C to stop")
    print("")
    
    try:
        while True:
            now = datetime.now()
            print("[" + now.strftime('%H:%M:%S') + "] Scanning...")
            
            for symbol in SYMBOLS:
                signal = get_sniper_signal(symbol)
                
                if signal:
                    print("  [SIGNAL] " + symbol + ": " + signal['direction'] + " | Conf: " + str(round(signal['confidence']*100,1)) + "% | RR: " + str(round(signal['rr'],1)) + ":1")
                    execute_trade(signal)
                else:
                    print("  " + symbol + ": No setup")
            
            print("  Sleeping 30 minutes...")
            print("")
            time.sleep(1800)
            
    except KeyboardInterrupt:
        print("")
        print("[OK] Stopping bot...")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()
'''

with open('sniper_bot_fixed.py', 'w', encoding='utf-8') as f:
    f.write(clean_bot_code)

print("[OK] Created sniper_bot_fixed.py")
print("This version has NO multiline f-strings - completely clean")
print("\nTo run:")
print("python sniper_bot_fixed.py")

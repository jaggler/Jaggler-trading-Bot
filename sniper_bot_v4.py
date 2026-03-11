# -*- coding: utf-8 -*-
"""
SNIPER ENTRY BOT V4
High-Precision Forex Trading for 5,000 KSh Daily Target
Optimized for: EURUSD, GBPUSD, XAUUSD on H1 timeframe
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import sqlite3
import time
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURATION - ADJUST FOR YOUR ACCOUNT
# =============================================================================

# Account Settings
ACCOUNT_CURRENCY = "USD"  # Change to KES if your account is in KSh
DAILY_PROFIT_TARGET = 50 if ACCOUNT_CURRENCY == "USD" else 5000  # ~50 USD = ~5,000 KSh
DAILY_LOSS_LIMIT = 30 if ACCOUNT_CURRENCY == "USD" else 3000      # Stop trading at this loss
RISK_PER_TRADE_PERCENT = 1.5  # Risk 1.5% per trade
MIN_RISK_REWARD_RATIO = 2.0   # Only trades with 2:1 RR or better

# Trading Settings
SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]  # Your watchlist
TIMEFRAME = mt5.TIMEFRAME_H1              # H1 for sniper precision (not M5)
BARS_HISTORY = 2000                         # 3+ months of H1 data
CHECK_INTERVAL_MINUTES = 30                 # Check every 30 min (not 5)

# Sniper Thresholds - HIGH PRECISION
MIN_PRIMARY_CONFIDENCE = 0.55      # Directional confidence
MIN_META_CONFIDENCE = 0.65         # Sniper threshold (was 0.40!)
MIN_MODEL_PRECISION = 0.60       # Must prove 60%+ in backtest

# Session Settings (London/NY overlap best)
ALLOWED_HOURS_UTC = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]  # 7am-8pm UTC
XAUUSD_HOURS_UTC = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]  # Gold: 8am-7pm

# =============================================================================
# DATABASE SETUP
# =============================================================================

def init_database():
    """Initialize SQLite with enhanced tracking for daily P&L"""
    conn = sqlite3.connect("sniper_trades.db")
    cursor = conn.cursor()
    
    # Main trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            stop_loss REAL,
            take_profit REAL,
            lot_size REAL,
            primary_conf REAL,
            meta_conf REAL,
            model_precision REAL,
            volatility REAL,
            atr REAL,
            status TEXT DEFAULT 'OPEN',
            exit_price REAL,
            profit_loss REAL,
            exit_timestamp TEXT,
            exit_reason TEXT,
            pips_gained REAL
        )
    """)
    
    # Daily performance tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_performance (
            date TEXT PRIMARY KEY,
            trades_count INTEGER,
            wins INTEGER,
            losses INTEGER,
            gross_profit REAL,
            gross_loss REAL,
            net_pnl REAL,
            target_reached BOOLEAN,
            stopped_out BOOLEAN
        )
    """)
    
    conn.commit()
    conn.close()
    print("[OK] Database initialized: sniper_trades.db")

# =============================================================================
# ENHANCED SESSION FILTER
# =============================================================================

def session_filter(symbol):
    """
    Strict session filter - only trade during high liquidity hours
    London: 8-17 UTC, NY: 13-22 UTC, Overlap: 13-17 UTC (BEST)
    """
    now = datetime.utcnow()
    hour = now.hour
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    # No trading on weekends
    if weekday >= 5:
        print(f"[BLOCK] Weekend - markets closed or low liquidity")
        return False
    
    # Symbol-specific hours
    if symbol == "XAUUSD":
        if hour not in XAUUSD_HOURS_UTC:
            print(f"[BLOCK] {symbol}: Outside gold trading hours (UTC {hour}, allowed {XAUUSD_HOURS_UTC[0]}-{XAUUSD_HOURS_UTC[-1]})")
            return False
    else:
        if hour not in ALLOWED_HOURS_UTC:
            print(f"[BLOCK] Outside forex trading hours (UTC {hour}, best 13-17 overlap)")
            return False
    
    # Check for major news events (simplified - you can enhance this)
    if hour in [12, 13] and weekday in [2, 3]:  # Wed/Thu around noon UTC (US news)
        print(f"[WARN] Potential high-impact news period - reduced size recommended")
    
    return True

# =============================================================================
# ADVANCED FEATURE ENGINEERING
# =============================================================================

def add_advanced_features(df):
    """
    Professional feature set for sniper entries
    """
    # Returns
    df['return'] = df['close'].pct_change()
    df['return_5'] = df['close'].pct_change(5)
    
    # Volatility (ATR-based)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr_14'] = tr.rolling(14).mean()
    df['atr_ratio'] = df['atr_14'] / df['close']  # Normalized ATR
    
    # Trend indicators (multiple timeframes)
    df['ema_10'] = df['close'].ewm(span=10).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    df['ema_200'] = df['close'].ewm(span=200).mean()
    
    # Trend strength
    df['trend_fast'] = df['ema_10'] > df['ema_50']
    df['trend_slow'] = df['ema_50'] > df['ema_200']
    df['trend_aligned'] = df['trend_fast'] & df['trend_slow']
    
    # Momentum
    df['rsi_14'] = calculate_rsi(df['close'], 14)
    df['rsi_7'] = calculate_rsi(df['close'], 7)
    
    # Mean reversion signals (for sniper entries)
    df['bb_upper'], df['bb_lower'] = calculate_bollinger_bands(df['close'])
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # Volume/liquidity proxy (tick volume)
    df['volume_ma'] = df['tick_volume'].rolling(20).mean()
    df['volume_ratio'] = df['tick_volume'] / df['volume_ma']
    
    # Clean up
    df = df.dropna()
    return df

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, lower

# =============================================================================
# SMART POSITION SIZING
# =============================================================================

def calculate_lot_size(symbol, entry, stop_loss, risk_percent=RISK_PER_TRADE_PERCENT):
    """
    Dynamic lot sizing based on account balance, risk %, and stop distance
    """
    account_info = mt5.account_info()
    if account_info is None:
        return 0.01
    
    balance = account_info.balance
    risk_amount = balance * (risk_percent / 100)
    
    # Calculate stop distance in price terms
    stop_distance = abs(entry - stop_loss)
    
    if stop_distance == 0:
        return 0.01
    
    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return 0.01
    
    # Calculate lot size
    # For forex: 1.0 lot = $10 per pip (standard), 0.1 lot = $1, 0.01 lot = $0.10
    # For XAUUSD: 1.0 lot = $1 per point (usually)
    
    if symbol == "XAUUSD":
        # Gold: 1 lot = $1 per point (0.01 move)
        point_value = 1.0
        stop_points = stop_distance / 0.01
        lot_size = risk_amount / (stop_points * point_value)
    else:
        # Forex: 1 pip = 0.0001 for most pairs
        pip_size = 0.0001 if 'JPY' not in symbol else 0.01
        pips = stop_distance / pip_size
        pip_value = 10.0  # $10 per pip for 1.0 lot on standard account
        lot_size = risk_amount / (pips * pip_value)
    
    # Apply limits
    lot_size = min(lot_size, 0.1)   # Max 0.1 lot (conservative)
    lot_size = max(lot_size, 0.01)  # Min 0.01 lot
    
    return round(lot_size, 2)

# =============================================================================
# META-LABELING MODEL (High Precision)
# =============================================================================

def train_meta_model(X, y):
    """
    Train meta-labeling model to identify high-probability setups
    """
    # Split for validation (time-series aware)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    if len(X_test) < 100:
        return None, 0, 0.5
    
    # Primary model (direction)
    primary = RandomForestClassifier(
        n_estimators=100, max_depth=5, min_samples_leaf=50,
        class_weight='balanced', random_state=42
    )
    primary.fit(X_train, y_train)
    
    train_proba = primary.predict_proba(X_train)[:, 1]
    test_proba = primary.predict_proba(X_test)[:, 1]
    
    # Meta model (confidence)
    meta_y = ((train_proba > 0.5).astype(int) == y_train).astype(int)
    meta_X = pd.DataFrame({
        'primary_conf': train_proba,
        'volatility': X_train['atr_ratio'].values if 'atr_ratio' in X_train.columns else np.zeros(len(X_train)),
        'trend': X_train['trend_aligned'].values if 'trend_aligned' in X_train.columns else np.ones(len(X_train))
    })
    
    meta_model = RandomForestClassifier(
        n_estimators=50, max_depth=3, min_samples_leaf=100,
        class_weight='balanced', random_state=42
    )
    meta_model.fit(meta_X, meta_y)
    
    # Find optimal threshold
    meta_test_proba = meta_model.predict_proba(pd.DataFrame({
        'primary_conf': test_proba,
        'volatility': X_test['atr_ratio'].values if 'atr_ratio' in X_test.columns else np.zeros(len(X_test)),
        'trend': X_test['trend_aligned'].values if 'trend_aligned' in X_test.columns else np.ones(len(X_test))
    }))[:, 1]
    
    best_prec, best_thresh = 0, 0.65
    for thresh in [0.60, 0.65, 0.70, 0.75, 0.80]:
        mask = (test_proba > 0.5) & (meta_test_proba > thresh)
        if mask.sum() >= 10:
            prec = precision_score(y_test[mask], (test_proba[mask] > 0.5).astype(int), zero_division=0)
            if prec > best_prec:
                best_prec = prec
                best_thresh = thresh
    
    return (primary, meta_model), best_prec, best_thresh

# =============================================================================
# SNIPER SIGNAL GENERATION
# =============================================================================

def generate_sniper_signal(symbol, models, threshold, required_precision=MIN_MODEL_PRECISION):
    """
    Generate high-precision trading signal
    """
    # Get data
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, BARS_HISTORY)
    if rates is None or len(rates) < 200:
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Add features
    df = add_advanced_features(df)
    
    if len(df) < 100:
        return None
    
    # Target: next bar direction (for quick scalping) or 3-bar forward
    df['target'] = (df['close'].shift(-3) > df['close']).astype(int)
    df = df.dropna()
    
    if models is None:
        # Train mode
        features = ['atr_ratio', 'trend_aligned', 'rsi_14', 'bb_position', 'volume_ratio']
        available = [f for f in features if f in df.columns]
        if len(available) < 3:
            return None
        
        X = df[available]
        y = df['target']
        
        models, precision, thresh = train_meta_model(X, y)
        return {'models': models, 'precision': precision, 'threshold': thresh}
    
    # Prediction mode
    primary_model, meta_model = models
    
    features = ['atr_ratio', 'trend_aligned', 'rsi_14', 'bb_position', 'volume_ratio']
    available = [f for f in features if f in df.columns]
    if len(available) < 3:
        return None
    
    X = df[available]
    latest = X.tail(1)
    
    # Primary prediction
    primary_proba = primary_model.predict_proba(latest)[0, 1]
    primary_direction = "LONG" if primary_proba > 0.5 else "SHORT"
    
    # Meta prediction
    meta_input = pd.DataFrame({
        'primary_conf': [primary_proba],
        'volatility': [latest['atr_ratio'].values[0]] if 'atr_ratio' in latest.columns else [0],
        'trend': [latest['trend_aligned'].values[0]] if 'trend_aligned' in latest.columns else [1]
    })
    meta_proba = meta_model.predict_proba(meta_input)[0, 1]
    
    # Sniper criteria
    meets_primary = primary_proba > MIN_PRIMARY_CONFIDENCE if primary_direction == "LONG" else primary_proba < (1 - MIN_PRIMARY_CONFIDENCE)
    meets_meta = meta_proba > threshold
    
    # Calculate ATR-based stops
    current_atr = df['atr_14'].iloc[-1]
    current_price = df['close'].iloc[-1]
    
    if primary_direction == "LONG":
        sl = current_price - (current_atr * 1.5)
        tp = current_price + (current_atr * 3.0)  # 2:1 RR
    else:
        sl = current_price + (current_atr * 1.5)
        tp = current_price - (current_atr * 3.0)
    
    # Check RR ratio
    risk = abs(current_price - sl)
    reward = abs(tp - current_price)
    rr_ratio = reward / risk if risk > 0 else 0
    
    signal = {
        'symbol': symbol,
        'direction': primary_direction,
        'primary_conf': primary_proba,
        'meta_conf': meta_proba,
        'threshold': threshold,
        'entry': current_price,
        'sl': sl,
        'tp': tp,
        'atr': current_atr,
        'rr_ratio': rr_ratio,
        'should_trade': meets_primary and meets_meta and (rr_ratio >= MIN_RISK_REWARD_RATIO),
        'volatility': latest['atr_ratio'].values[0] if 'atr_ratio' in latest.columns else 0
    }
    
    return signal

# =============================================================================
# DAILY P&L TRACKING
# =============================================================================

def check_daily_limits():
    """Check if daily profit target reached or loss limit hit"""
    conn = sqlite3.connect("sniper_trades.db")
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Get today's closed trades
    cursor.execute("""
        SELECT SUM(profit_loss) as net_pnl, 
               SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses
        FROM trades 
        WHERE date(timestamp) = ? AND status = 'CLOSED'
    """, (today,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0] is not None:
        net_pnl = result[0]
        wins = result[1] or 0
        losses = result[2] or 0
        
        print(f"[INFO] Today's P&L: {net_pnl:.2f} {ACCOUNT_CURRENCY} | Wins: {wins} | Losses: {losses}")
        
        # Check target reached
        if net_pnl >= DAILY_PROFIT_TARGET:
            print(f"[TARGET] Daily profit target reached! ({net_pnl:.2f} >= {DAILY_PROFIT_TARGET})")
            print(f"[TARGET] Stopping trading for today.")
            return False  # Stop trading
            
        # Check loss limit
        if net_pnl <= -DAILY_LOSS_LIMIT:
            print(f"[STOP] Daily loss limit hit! ({net_pnl:.2f} <= -{DAILY_LOSS_LIMIT})")
            print(f"[STOP] Stopping trading for today.")
            return False  # Stop trading
    
    return True  # Continue trading

# =============================================================================
# EXECUTION
# =============================================================================

def execute_sniper_trade(signal):
    """Execute trade with full logging"""
    symbol = signal['symbol']
    direction = signal['direction']
    
    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"[FAIL] Cannot get price for {symbol}")
        return None
    
    price = tick.ask if direction == "LONG" else tick.bid
    
    # Recalculate lot size based on actual stop distance
    lot = calculate_lot_size(symbol, price, signal['sl'])
    
    # Check if we can afford this trade
    account_info = mt5.account_info()
    if account_info and account_info.margin_free < 100:
        print(f"[FAIL] Insufficient free margin: {account_info.margin_free}")
        return None
    
    # Send order
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
        "comment": f"SNIPER_{direction}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }
    
    result = mt5.order_send(request)
    
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"[FAIL] Order failed: {result.retcode if result else 'None'}")
        return None
    
    # Success - log to database
    conn = sqlite3.connect("sniper_trades.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trades (timestamp, symbol, direction, entry_price, stop_loss, take_profit, 
                           lot_size, primary_conf, meta_conf, volatility, atr, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
    """, (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        symbol, direction, price, signal['sl'], signal['tp'], lot,
        signal['primary_conf'], signal['meta_conf'], signal['volatility'], signal['atr']
    ))
    conn.commit()
    conn.close()
    
    print(f"[OK] SNIPER TRADE EXECUTED: {symbol} {direction}")
    print(f"     Ticket: {result.order}, Volume: {lot}, Price: {price:.5f}")
    print(f"     SL: {signal['sl']:.5f}, TP: {signal['tp']:.5f}, RR: {signal['rr_ratio']:.1f}:1")
    
    return result.order

# =============================================================================
# MAIN BOT LOOP
# =============================================================================

def run_sniper_bot():
    """Main bot execution loop"""
    print("="*60)
    print("SNIPER ENTRY BOT V4 - 5,000 KSh Daily Target")
    print("="*60)
    print(f"Account Currency: {ACCOUNT_CURRENCY}")
    print(f"Daily Profit Target: {DAILY_PROFIT_TARGET} {ACCOUNT_CURRENCY}")
    print(f"Daily Loss Limit: {DAILY_LOSS_LIMIT} {ACCOUNT_CURRENCY}")
    print(f"Risk Per Trade: {RISK_PER_TRADE_PERCENT}%")
    print(f"Min Risk/Reward: {MIN_RISK_REWARD_RATIO}:1")
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print(f"Timeframe: H1 (Sniper Precision)")
    print("="*60)
    
    # Initialize
    init_database()
    
    if not mt5.initialize():
        print("[FAIL] MT5 initialization failed")
        return
    
    account_info = mt5.account_info()
    if account_info:
        print(f"[OK] Connected: {account_info.login}")
        print(f"     Balance: {account_info.balance:.2f} {ACCOUNT_CURRENCY}")
        print(f"     Equity: {account_info.equity:.2f} {ACCOUNT_CURRENCY}")
    
    # Pre-train models for each symbol
    print("
[TRAIN] Pre-training models...")
    symbol_models = {}
    for symbol in SYMBOLS:
        result = generate_sniper_signal(symbol, None, 0.65)
        if result and result['models']:
            symbol_models[symbol] = {
                'models': result['models'],
                'precision': result['precision'],
                'threshold': result['threshold']
            }
            print(f"[OK] {symbol}: Precision={result['precision']:.1%}, Threshold={result['threshold']:.2f}")
        else:
            print(f"[FAIL] {symbol}: Model training failed")
    
    if not symbol_models:
        print("[FAIL] No models trained - cannot continue")
        mt5.shutdown()
        return
    
    print("
[OK] Sniper Bot Ready - Entering main loop...")
    print(f"[INFO] Checking every {CHECK_INTERVAL_MINUTES} minutes")
    print("[INFO] Press Ctrl+C to stop
")
    
    try:
        while True:
            now = datetime.now()
            print(f"
[{now.strftime('%H:%M:%S')}] Scanning...")
            
            # Check daily limits first
            if not check_daily_limits():
                print("[INFO] Daily limits reached - waiting for next day...")
                time.sleep(3600)  # Check again in 1 hour
                continue
            
            # Check each symbol
            for symbol in SYMBOLS:
                if symbol not in symbol_models:
                    continue
                    
                model_data = symbol_models[symbol]
                
                # Session filter
                if not session_filter(symbol):
                    continue
                
                # Generate signal
                signal = generate_sniper_signal(
                    symbol, 
                    model_data['models'], 
                    model_data['threshold']
                )
                
                if signal is None:
                    continue
                
                print(f"  {symbol}: {signal['direction']} | "
                      f"Primary: {signal['primary_conf']:.1%} | "
                      f"Meta: {signal['meta_conf']:.1%} | "
                      f"RR: {signal['rr_ratio']:.1f}:1 | "
                      f"Trade: {signal['should_trade']}")
                
                # Execute if valid signal
                if signal['should_trade']:
                    execute_sniper_trade(signal)
            
            # Wait before next scan
            print(f"[INFO] Sleeping {CHECK_INTERVAL_MINUTES} minutes...")
            time.sleep(CHECK_INTERVAL_MINUTES * 60)
            
    except KeyboardInterrupt:
        print("
[INFO] Stopping Sniper Bot...")
    finally:
        mt5.shutdown()
        print("[OK] Disconnected")

if __name__ == "__main__":
    run_sniper_bot()

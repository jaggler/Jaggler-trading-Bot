# -*- coding: utf-8 -*-
"""
Forex ML Trading System - V3 MULTI-SYMBOL
Equipped with Master Ledger and Demo Execution for EURUSD, GBPUSD, and XAUUSD.
"""
import sys
import yaml
import requests
import warnings
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score
import MetaTrader5 as mt5

# Internal Imports
sys.path.append(str(Path(__file__).parent / "src"))
from src.data.mt5_connector import MT5Connector
from src.data.feature_engineering import FeatureEngineer
from src.risk.position_sizing import calculate_lot_size
from src.execution.order_manager import OrderManager

warnings.filterwarnings('ignore')

def send_telegram_msg(message):
    """Send status updates to Telegram with stable timeout handling."""
    try:
        with open("config/settings.yaml", "r") as f:
            config = yaml.safe_load(f)
        token = config['telegram']['token']
        chat_id = config['telegram']['chat_id']
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram Alert Failed: {e}")

class PurgedWalkForwardCV:
    """Lopez de Prado's purged cross-validation logic."""
    def __init__(self, n_splits=5, purge_gap=10):
        self.n_splits = n_splits
        self.purge_gap = purge_gap
        
    def split(self, X):
        n = len(X)
        fold_size = n // (self.n_splits + 1)
        for i in range(1, self.n_splits + 1):
            train_end = i * fold_size
            test_start = train_end + self.purge_gap
            test_end = min((i + 1) * fold_size, n)
            if test_start < test_end:
                yield (np.arange(0, train_end), np.arange(test_start, test_end))

def run_meta_labeling_v3(X, y, cv, symbol):
    """V3 Selective Strategy Research."""
    meta_results = []
    splits = list(cv.split(X))
    
    for fold, (train_idx, test_idx) in enumerate(splits):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        
        primary = RandomForestClassifier(n_estimators=100, max_depth=5, min_samples_leaf=50, 
                                        class_weight='balanced', random_state=42, n_jobs=-1)
        primary.fit(X_train, y_train)
        
        train_proba = primary.predict_proba(X_train)[:, 1]
        test_proba = primary.predict_proba(X_test)[:, 1]
        
        meta_y_train = ((train_proba > 0.5).astype(int) == y_train).astype(int)
        meta_X_train = pd.DataFrame({'primary_conf': train_proba, 'volatility': X_train['volatility_20'].values})
        meta_X_test = pd.DataFrame({'primary_conf': test_proba, 'volatility': X_test['volatility_20'].values})
        
        meta_model = RandomForestClassifier(n_estimators=50, max_depth=3, min_samples_leaf=100, 
                                            class_weight='balanced', random_state=42)
        meta_model.fit(meta_X_train, meta_y_train)
        meta_proba = meta_model.predict_proba(meta_X_test)[:, 1]
        
        mask = (test_proba > 0.5) & (meta_proba > 0.65)
        prec = precision_score(y_test[mask], (test_proba[mask] > 0.5).astype(int), zero_division=0) if mask.sum() > 0 else 0
        
        meta_results.append({'fold': fold + 1, 'meta_precision': prec, 'trades_taken': mask.sum()})
        
    return pd.DataFrame(meta_results)

def run_research_pipeline(symbol):
    print(f"\n{'='*60}\nSCANNING ASSET: {symbol}\n{'='*60}")
    
    connector = MT5Connector()
    engineer = FeatureEngineer()
    executor = OrderManager()
    
    df = connector.fetch_data(symbol, mt5.TIMEFRAME_H1, datetime.now()-timedelta(days=730), datetime.now())
    if df is None: return

    features = engineer.create_features(df)
    engineer.fit_regime_model(features.iloc[:len(features)//2])
    features = engineer.get_regime_specific_features(features)
    
    features['target'] = (features['close'].pct_change(5).shift(-5) > 0).astype(int)
    features = features.dropna()
    
    X_cols = ['ema_50', 'rsi_14', 'bull_fvg', 'bear_fvg', 'volatility_20', 'rsi_regime']
    X, y = features[X_cols], features['target']

    meta_df = run_meta_labeling_v3(X, y, PurgedWalkForwardCV(), symbol)
    if meta_df.empty: return

    m_prec = meta_df[meta_df['meta_precision'] > 0]['meta_precision'].mean()

    # Train Production
    p_model = RandomForestClassifier(n_estimators=200, max_depth=5, min_samples_leaf=50, class_weight='balanced', random_state=42)
    p_model.fit(X, y)
    
    p_proba_full = p_model.predict_proba(X)[:, 1]
    m_y_full = ((p_proba_full > 0.5).astype(int) == y).astype(int)
    m_X_full = pd.DataFrame({'primary_conf': p_proba_full, 'volatility': X['volatility_20'].values})
    
    m_model = RandomForestClassifier(n_estimators=50, max_depth=3, min_samples_leaf=100, class_weight='balanced', random_state=42)
    m_model.fit(m_X_full, m_y_full)

    # Signal Logic
    latest = X.tail(1)
    p_proba = p_model.predict_proba(latest)[0, 1]
    m_proba = m_model.predict_proba(pd.DataFrame({'primary_conf': [p_proba], 'volatility': [latest['volatility_20'].values[0]]}))[0, 1]
    
    direction = "LONG" if p_proba > 0.5 else "SHORT"
    should_trade = (p_proba > 0.5) and (m_proba > 0.60)
    lot = calculate_lot_size(symbol) if should_trade else 0.0

    # EXECUTION Logic (Custom Stops for Gold)
    if should_trade and lot > 0:
        price = mt5.symbol_info_tick(symbol).ask if direction == "LONG" else mt5.symbol_info_tick(symbol).bid
        
        # SL/TP Adjustments
        if symbol == "XAUUSD":
            sl_dist, tp_dist = 500 * mt5.symbol_info(symbol).point, 1000 * mt5.symbol_info(symbol).point
        else:
            sl_dist, tp_dist = 200 * mt5.symbol_info(symbol).point, 400 * mt5.symbol_info(symbol).point
            
        sl = price - sl_dist if direction == "LONG" else price + sl_dist
        tp = price + tp_dist if direction == "LONG" else price - tp_dist
        executor.send_order(symbol, mt5.ORDER_TYPE_BUY if direction=="LONG" else mt5.ORDER_TYPE_SELL, lot, price, sl, tp)

    # Logging
    meta_df['run_time'], meta_df['symbol'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S'), symbol
    meta_df.to_csv("master_validation_log.csv", mode='a', index=False, header=not Path("master_validation_log.csv").exists())
    
    msg = f"🤖 *V3 Multi-Scan: {symbol}*\nSignal: {direction}\nMeta Confidence: {m_proba:.1%}\nAction: {'🚀 TRADE FIRED' if should_trade else '❄️ NO TRADE'}\nAvg Precision: {m_prec:.1%}"
    send_telegram_msg(msg)
    print(f"--- {symbol} Scan Complete ---")

if __name__ == "__main__":
    watch_list = ["EURUSD", "GBPUSD", "XAUUSD"]
    for asset in watch_list:
        try:
            run_research_pipeline(asset)
        except Exception as e:
            print(f"⚠️ Error scanning {asset}: {e}")
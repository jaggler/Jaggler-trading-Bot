# -*- coding: utf-8 -*-
"""
MT5 Data Connector with caching - Safe Version
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import pickle

class MT5Connector:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.connected = False

    def connect(self):
        """Initialize MT5 connection"""
        if not mt5.initialize():
            print("CRITICAL: MT5 initialization failed. Ensure MT5 is open.")
            return False
        self.connected = True
        print(f"Connected to MT5: {mt5.terminal_info().name}")
        return True

    def disconnect(self):
        mt5.shutdown()
        self.connected = False
        print("Disconnected from MT5.")

    def fetch_data(self, symbol, timeframe, start_date, end_date, cache=True):
        """
        Fetch historical data with caching to local storage
        """
        # Create a safe filename for the cache
        file_tag = f"{symbol}_{timeframe}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        cache_file = self.data_dir / f"{file_tag}.pkl"

        if cache and cache_file.exists():
            print(f"Loading cached data for {symbol}...")
            return pd.read_pickle(cache_file)

        if not self.connected:
            if not self.connect():
                return None

        print(f"Fetching {symbol} from MT5...")
        rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)

        if rates is None or len(rates) == 0:
            print(f"ERROR: No data returned for {symbol}. Check symbol name.")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        if cache:
            df.to_pickle(cache_file)
            print(f"Data cached to: {cache_file}")

        return df

if __name__ == "__main__":
    conn = MT5Connector()
    if conn.connect():
        # Test fetch: Last 30 days of EURUSD
        end = datetime.now()
        start = end - timedelta(days=30)
        df = conn.fetch_data("EURUSD", mt5.TIMEFRAME_H1, start, end)
        if df is not None:
            print(f"SUCCESS: Fetched {len(df)} rows of EURUSD H1 data.")
        conn.disconnect()
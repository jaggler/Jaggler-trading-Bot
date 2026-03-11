# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

class FeatureEngineer:
    def __init__(self):
        self.scaler = StandardScaler()
        self.regime_thresholds = None

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss.replace(0, np.nan))
        return (100 - (100 / (1 + rs))).fillna(50)

    def create_features(self, df):
        features = df.copy()
        features['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        features['rsi_14'] = self.calculate_rsi(df['close'])
        
        # Volatility as a regime proxy
        features['log_return'] = np.log(df['close'] / df['close'].shift(1))
        features['volatility_20'] = features['log_return'].rolling(20).std()
        
        # Signal Gaps (FVG)
        features['bull_fvg'] = (df['low'] > df['high'].shift(2)).astype(int)
        features['bear_fvg'] = (df['high'] < df['low'].shift(2)).astype(int)
        
        return features.dropna()

    def fit_regime_model(self, features_df):
        """Calculates volatility regimes based on quantiles."""
        self.regime_thresholds = features_df['volatility_20'].quantile([0.33, 0.66]).values
        print(f"  Regime thresholds set: {self.regime_thresholds}")

    def get_regime_specific_features(self, df):
        """Assigns market regime (0=Low, 1=Med, 2=High Volatility)."""
        if self.regime_thresholds is None:
            df['regime'] = 1
            return df
            
        df['regime'] = 0
        df.loc[df['volatility_20'] > self.regime_thresholds[0], 'regime'] = 1
        df.loc[df['volatility_20'] > self.regime_thresholds[1], 'regime'] = 2
        
        # Interaction feature: RSI * Regime
        df['rsi_regime'] = df['rsi_14'] * df['regime']
def add_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr_14'] = true_range.rolling(period).mean()
        return df
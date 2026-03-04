import os

# 1. Define the professional folder structure
folders = [
    "src/data",
    "src/models",
    "src/validation",
    "src/risk",
    "src/execution",
    "data",
    "config",
    "logs",
    "tests"
]

# 2. Create the directories and __init__.py files for package handling
for folder in folders:
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "__init__.py"), "w") as f:
        pass

# 3. Create the feature engineering logic (Self-sufficient, no broken libraries)
feature_eng_content = """
import pandas as pd
import numpy as np

class FeatureEngineer:
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
        return features.dropna()

if __name__ == "__main__":
    print("✅ Feature Engineering Module is LIVE.")
"""

with open("src/data/feature_engineering.py", "w") as f:
    f.write(feature_eng_content.strip())

# 4. Create the entry point file
with open("main.py", "w") as f:
    f.write("print('🚀 Forex ML Trader Initialized!')")

print("✅ Project Structure and Initial Files Created successfully!")
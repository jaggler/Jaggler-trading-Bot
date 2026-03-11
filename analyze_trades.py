import sqlite3
import pandas as pd

DB_PATH = "trades.db"

conn = sqlite3.connect(DB_PATH)

df = pd.read_sql("SELECT * FROM trades", conn)

conn.close()

if len(df) < 50:
    print("Not enough trades yet for analysis")
    exit()


print("\n===== ANALYZING TRADES =====\n")


# -----------------------
# BEST PAIR
# -----------------------

pair_stats = df.groupby("symbol")["profit"].agg(["count","mean","sum"])

print("\nBEST PAIRS:")
print(pair_stats.sort_values("mean", ascending=False))


# -----------------------
# BEST HOUR
# -----------------------

df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour

hour_stats = df.groupby("hour")["profit"].mean()

print("\nBEST HOURS:")
print(hour_stats.sort_values(ascending=False))


# -----------------------
# BEST CONFIDENCE
# -----------------------

confidence_bins = pd.cut(df["confidence"], bins=5)

conf_stats = df.groupby(confidence_bins)["profit"].mean()

print("\nBEST CONFIDENCE RANGE:")
print(conf_stats.sort_values(ascending=False))


# -----------------------
# BEST VOLATILITY
# -----------------------

if "atr" in df.columns:

    atr_bins = pd.cut(df["atr"], bins=5)

    atr_stats = df.groupby(atr_bins)["profit"].mean()

    print("\nBEST VOLATILITY RANGE:")
    print(atr_stats.sort_values(ascending=False))
import sqlite3

def init_trade_db():
    conn = sqlite3.connect("trade_history.db")
    cursor = conn.cursor()
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
        model_confidence REAL,
        volatility REAL,
        result TEXT,
        profit REAL
    )
    """)
    conn.commit()
    conn.close()
    print("✅ Database 'trade_history.db' initialized successfully.")

if __name__ == "__main__":
    init_trade_db()
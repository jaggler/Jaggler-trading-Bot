
import sqlite3

# Connect to database
conn = sqlite3.connect("trades.db")
cursor = conn.cursor()

# Check current schema
cursor.execute("PRAGMA table_info(trades)")
columns = cursor.fetchall()
print("Current columns:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# If 'entry' column doesn't exist, we need to recreate the table
has_entry = any(col[1] == 'entry' for col in columns)

if not has_entry:
    print("\n[FIX] Recreating table with correct schema...")
    
    # Backup existing data
    try:
        cursor.execute("SELECT * FROM trades")
        old_data = cursor.fetchall()
        print(f"[INFO] Backing up {len(old_data)} existing trades")
    except:
        old_data = []
    
    # Drop old table
    cursor.execute("DROP TABLE IF EXISTS trades")
    
    # Create new table with correct schema
    cursor.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY,
            time TEXT, 
            symbol TEXT, 
            direction TEXT,
            entry REAL, 
            sl REAL, 
            tp REAL, 
            lot REAL,
            confidence REAL, 
            result TEXT DEFAULT 'OPEN'
        )
    """)
    
    conn.commit()
    print("[OK] Table recreated successfully")
else:
    print("\n[OK] Table schema is correct")

conn.close()
print("\nDatabase fixed. Run your bot again.")

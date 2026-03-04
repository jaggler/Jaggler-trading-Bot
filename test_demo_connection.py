"""
Test MT5 Demo Account Connection
"""
import MetaTrader5 as mt5
import pandas as pd

def test_connection():
    print("=" * 50)
    print("TESTING MT5 DEMO CONNECTION")
    print("=" * 50)

    # Initialize
    if not mt5.initialize():
        print("❌ MT5 initialization failed")
        print("Make sure MT5 is running with AutoTrading enabled")
        return False

    # Account info
    account_info = mt5.account_info()
    if account_info is None:
        print("❌ Failed to get account info")
        mt5.shutdown()
        return False

    print(f"\n✅ Connected successfully!")
    print(f"Account: {account_info.login}")
    print(f"Name: {account_info.name}")
    print(f"Server: {account_info.server}")
    print(f"Balance: ${account_info.balance:.2f}")

    # Check if demo
    if "demo" in account_info.server.lower() or account_info.login > 100000000:
        print(f"\n✅ DEMO ACCOUNT CONFIRMED")
    else:
        print(f"\n⚠️ WARNING: This appears to be a LIVE account!")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() != "yes":
            mt5.shutdown()
            return False

    # Test symbol
    symbol = "EURUSD"
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"\n❌ {symbol} not found in Market Watch")
        mt5.shutdown()
        return False

    print(f"\n{symbol} info:")
    print(f"  Bid: {symbol_info.bid} | Ask: {symbol_info.ask}")
    mt5.shutdown()
    return True

if __name__ == "__main__":
    test_connection()
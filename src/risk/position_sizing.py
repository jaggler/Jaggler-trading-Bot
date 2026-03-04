# -*- coding: utf-8 -*-
import MetaTrader5 as mt5

def calculate_lot_size(symbol, risk_percent=0.01):
    account = mt5.account_info()
    if not account:
        return 0.01

    balance = account.balance
    risk_amount = balance * risk_percent

    # Get symbol properties
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        return 0.01

    # We assume a fixed Stop Loss of 200 points for this calculation
    # In a real bot, this would be dynamic based on ATR
    sl_points = 200 
    tick_value = symbol_info.trade_tick_value

    if sl_points == 0 or tick_value == 0:
        return symbol_info.volume_min

    lot = risk_amount / (sl_points * tick_value)

    # Align with broker's step requirements
    step = symbol_info.volume_step
    lot = round(lot / step) * step

    return max(symbol_info.volume_min, min(lot, symbol_info.volume_max))

if __name__ == "__main__":
    print("SUCCESS: Position Sizing module ready.")
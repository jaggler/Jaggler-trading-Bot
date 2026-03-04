"""
Safe Demo Trading Module with Strict Risk Controls
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

class DemoTrader:
    def __init__(self, max_risk_percent=1.0, max_daily_loss=3.0):
        self.max_risk = max_risk_percent / 100
        self.max_daily_loss = max_daily_loss / 100
        self.starting_equity = 0

    def connect(self):
        if not mt5.initialize():
            return False
        info = mt5.account_info()
        if info is None: return False
        self.starting_equity = info.equity
        return True

    def check_safety_limits(self):
        info = mt5.account_info()
        if info is None: return False, "No account info"

        daily_return = (info.equity - self.starting_equity) / self.starting_equity
        if daily_return < -self.max_daily_loss:
            return False, f"Daily loss limit hit: {daily_return:.2%}"
        return True, "OK"

    def execute_trade(self, symbol, direction, confidence, meta_threshold=0.60):
        safe, reason = self.check_safety_limits()
        if not safe:
            print(f"❌ Trade blocked: {reason}")
            return False

        if confidence < meta_threshold:
            print(f"❌ Low Confidence: {confidence:.1%}")
            return False

        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if direction == "BUY" else tick.bid

        # Position Size Calculation (Hardcoded 0.01 for safety first)
        lots = 0.01 

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lots,
            "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "magic": 123456,
            "comment": "V3 Bot Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Order Failed: {result.comment}")
            return False

        print(f"✅ TRADE EXECUTED: {direction} {lots} lots at {price}")
        return True
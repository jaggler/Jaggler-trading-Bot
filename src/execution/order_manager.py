# -*- coding: utf-8 -*-
import MetaTrader5 as mt5

class OrderManager:
    def __init__(self, magic_number=123456):
        self.magic = magic_number

    def send_order(self, symbol, order_type, lot, price, sl, tp):
        """Sends a trade request to MT5"""
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": self.magic,
            "comment": "ML Sniper Signal",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"FAILED: Order error code {result.retcode}")
            return False

        print(f"SUCCESS: Trade opened on {symbol} at {price}")
        return True
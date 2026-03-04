# -*- coding: utf-8 -*-
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time

def get_daily_performance():
    # Define the start of today (00:00)
    today_start = datetime.combine(datetime.now().date(), time.min)
    today_end = datetime.now()

    # Fetch all deals (closed trades) for today
    deals = mt5.history_deals_get(today_start, today_end)

    if deals is None or len(deals) == 0:
        return "No trades closed today."

    # Convert to DataFrame for easy calculation
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())

    # Filter for actual trades (exclude balance deposits/withdrawals)
    # Entry 1 = DEAL_ENTRY_OUT (the closing part of a trade)
    trades = df[df['entry'] == 1].copy()

    if trades.empty:
        return "No closed positions found for today."

    net_pnl = trades['profit'].sum() + trades['commission'].sum() + trades['swap'].sum()
    total_trades = len(trades)
    wins = len(trades[trades['profit'] > 0])
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0

    summary = (
        f"📊 *Daily Performance Summary*\n"
        f"Net P/L: `${net_pnl:.2f}`\n"
        f"Total Trades: `{total_trades}`\n"
        f"Win Rate: `{win_rate:.1f}%` ({wins}/{total_trades})\n"
        f"Commissions: `${trades['commission'].sum():.2f}`"
    )
    return summary
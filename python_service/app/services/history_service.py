import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta, time as dt_time

def get_performance_overview():
    """Get profit/loss for today, this week, and this month."""
    now = datetime.now()
    
    # Today
    today_start = datetime.combine(now.date(), dt_time.min)
    
    # This Week (starts Monday)
    week_start = today_start - timedelta(days=now.weekday())
    
    # This Month
    month_start = today_start.replace(day=1)
    
    stats = {
        "today": calculate_profit(today_start, now),
        "week": calculate_profit(week_start, now),
        "month": calculate_profit(month_start, now)
    }
    return stats

def calculate_profit(from_date, to_date):
    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None or len(deals) == 0:
        return 0.0
    
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    if not df.empty and 'entry' in df.columns:
        exit_deals = df[(df['entry'].isin([1, 2])) & (df['type'].isin([0, 1]))]
        return float(exit_deals['profit'].sum() + exit_deals['commission'].sum() + exit_deals['swap'].sum())
    return 0.0

def get_daily_aggregated_stats(from_date: datetime, to_date: datetime):
    # Get current account balance to backtrack
    account = mt5.account_info()
    current_balance = account.balance if account else 0.0
    
    # Get all deals from from_date to now to backtrack balance
    all_deals = mt5.history_deals_get(from_date, datetime.now())
    
    if all_deals is None or len(all_deals) == 0:
        return []
    
    total_df = pd.DataFrame(list(all_deals), columns=all_deals[0]._asdict().keys())
    total_df['date_norm'] = pd.to_datetime(total_df['time'], unit='s').dt.normalize()
    
    # Filter for the requested range for the table
    start_ts = from_date.timestamp()
    end_ts = to_date.timestamp()
    mask = (total_df['time'] >= start_ts) & (total_df['time'] <= end_ts)
    df = total_df[mask].copy()
    
    # Calculate daily aggregation
    result = []
    total_df['net_change'] = total_df['profit'] + total_df['commission'] + total_df['swap']
    daily_changes = total_df.groupby('date_norm')['net_change'].sum()
    
    # Calculate balance at the end of each day
    sorted_dates = sorted(daily_changes.index, reverse=True)
    balances = {}
    running_balance = current_balance
    for d in sorted_dates:
        balances[d] = running_balance
        running_balance -= daily_changes[d]
    
    # Now build the stats for the requested range
    if not df.empty:
        df['date_norm'] = pd.to_datetime(df['time'], unit='s').dt.normalize()
        trade_df = df[df['type'].isin([0, 1])]
        
        for date_ts, group in trade_df.groupby('date_norm'):
            date_str = date_ts.strftime('%Y-%m-%d')
            
            # Profit only from exits
            exit_group = group[group['entry'].isin([1, 2])]
            profit = float(exit_group['profit'].sum() + exit_group['commission'].sum() + exit_group['swap'].sum())
            
            total_lots = float(group['volume'].sum())
            min_lot = float(group['volume'].min())
            max_lot = float(group['volume'].max())
            trades_count = int(len(group[group['entry'] == 0]))
            
            day_end_balance = balances.get(date_ts, 0.0)
            day_start_balance = day_end_balance - daily_changes.get(date_ts, 0.0)
            
            profit_pct = (profit / day_start_balance * 100) if day_start_balance > 0 else 0
            
            result.append({
                "date": date_str,
                "total_lots": round(total_lots, 2),
                "min_lot": round(min_lot, 2),
                "max_lot": round(max_lot, 2),
                "trades_count": trades_count,
                "profit": round(profit, 2),
                "profit_pct": round(profit_pct, 2),
                "balance": round(day_end_balance, 2)
            })
    
    result.sort(key=lambda x: x['date'], reverse=True)
    return result

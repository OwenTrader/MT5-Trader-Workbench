import pandas as pd
import numpy as np
import MetaTrader5 as mt5

TIMEFRAME_MAP = {
    'M1': mt5.TIMEFRAME_M1,
    'M5': mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1': mt5.TIMEFRAME_H1,
    'H4': mt5.TIMEFRAME_H4,
    'D1': mt5.TIMEFRAME_D1,
}

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_indicator_value(symbol: str, timeframe_str: str, indicator_type: str, period: int):
    tf = TIMEFRAME_MAP.get(timeframe_str, mt5.TIMEFRAME_M1)
    
    # We need enough bars for the calculation (period * 2 is a safe bet for RSI)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, period * 3)
    if rates is None or len(rates) < period:
        return None
        
    df = pd.DataFrame(rates)
    
    if indicator_type.upper() == 'RSI':
        rsi_series = calculate_rsi(df['close'], period)
        return rsi_series.iloc[-1]
    
    return None

import sqlite3
import os
import time
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'storage', 'kline_data.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # K-line data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS klines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            time INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            tick_volume INTEGER,
            UNIQUE(symbol, timeframe, time)
        )
    ''')
    
    # Review sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS review_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            start_time INTEGER NOT NULL,
            end_time INTEGER NOT NULL,
            initial_balance REAL NOT NULL,
            current_balance REAL NOT NULL,
            current_time INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )
    ''')
    
    # Review trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS review_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            open_time INTEGER NOT NULL,
            open_price REAL NOT NULL,
            close_time INTEGER,
            close_price REAL,
            lots REAL NOT NULL,
            profit REAL,
            FOREIGN KEY(session_id) REFERENCES review_sessions(id)
        )
    ''')
    
    # Indices for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_klines_symbol_tf_time ON klines(symbol, timeframe, time)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_review_trades_session ON review_trades(session_id)')
    
    conn.commit()
    conn.close()

# --- K-line Data Management ---

def save_klines(symbol: str, timeframe: str, klines_data: List[Dict[str, Any]]):
    if not klines_data:
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Use REPLACE to update if exists
    cursor.executemany('''
        INSERT OR REPLACE INTO klines (symbol, timeframe, time, open, high, low, close, tick_volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', [
        (symbol, timeframe, k['time'], k['open'], k['high'], k['low'], k['close'], k.get('tick_volume', 0))
        for k in klines_data
    ])
    
    conn.commit()
    conn.close()

def get_kline_summary() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT symbol, timeframe, COUNT(*) as count, MIN(time) as min_time, MAX(time) as max_time
        FROM klines
        GROUP BY symbol, timeframe
        ORDER BY symbol, timeframe
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def delete_klines(symbol: str, timeframe: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM klines WHERE symbol = ? AND timeframe = ?', (symbol, timeframe))
    
    conn.commit()
    conn.close()

def get_klines(symbol: str, timeframe: str, start_time: int, end_time: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM klines
        WHERE symbol = ? AND timeframe = ? AND time >= ? AND time <= ?
        ORDER BY time ASC
    ''', (symbol, timeframe, start_time, end_time))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_next_klines(symbol: str, timeframe: str, current_time: int, limit: int = 1) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM klines
        WHERE symbol = ? AND timeframe = ? AND time > ?
        ORDER BY time ASC
        LIMIT ?
    ''', (symbol, timeframe, current_time, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# --- Trading Review Management ---

def create_review_session(symbol: str, timeframe: str, start_time: int, end_time: int, initial_balance: float) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    
    now = int(time.time())
    cursor.execute('''
        INSERT INTO review_sessions (symbol, timeframe, start_time, end_time, initial_balance, current_balance, current_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (symbol, timeframe, start_time, end_time, initial_balance, initial_balance, start_time, now))
    
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return session_id

def get_review_sessions() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM review_sessions ORDER BY created_at DESC')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_review_session(session_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM review_sessions WHERE id = ?', (session_id,))
    row = cursor.fetchone()
    
    conn.close()
    return dict(row) if row else None

def update_review_session_time(session_id: int, new_current_time: int):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE review_sessions SET current_time = ? WHERE id = ?', (new_current_time, session_id))
    
    conn.commit()
    conn.close()

def update_review_session_balance(session_id: int, new_balance: float):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE review_sessions SET current_balance = ? WHERE id = ?', (new_balance, session_id))
    
    conn.commit()
    conn.close()

def delete_review_session(session_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM review_trades WHERE session_id = ?', (session_id,))
    cursor.execute('DELETE FROM review_sessions WHERE id = ?', (session_id,))
    
    conn.commit()
    conn.close()

def open_trade(session_id: int, trade_type: str, open_time: int, open_price: float, lots: float) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO review_trades (session_id, type, open_time, open_price, lots)
        VALUES (?, ?, ?, ?, ?)
    ''', (session_id, trade_type, open_time, open_price, lots))
    
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return trade_id

def close_trade(trade_id: int, close_time: int, close_price: float, profit: float):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE review_trades 
        SET close_time = ?, close_price = ?, profit = ?
        WHERE id = ?
    ''', (close_time, close_price, profit, trade_id))
    
    conn.commit()
    conn.close()

def get_session_trades(session_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM review_trades WHERE session_id = ? ORDER BY open_time ASC', (session_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

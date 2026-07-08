from .kline_db import init_db

# Initialize database on module import
try:
    init_db()
except Exception as e:
    print(f"Failed to initialize kline_db: {e}")

from .kline_db import init_db
import logging

logger = logging.getLogger(__name__)

# Initialize database on module import
try:
    init_db()
except Exception as e:
    logger.warning(f"Failed to initialize kline_db: {e}")

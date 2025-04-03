import sqlite3
import time
from datetime import datetime

from utils.constants import INFO, DEBUG, WARNING, ERROR
from utils.utilities import log_leaving_function, log_entering_function


def initialize_database(self, logger):
    """Initialize the SQLite database and create the trades table if it doesn't exist."""
    start_time = time.time()
    log_entering_function('initialize_database', logger, INFO)

    try:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    profit TEXT DEFAULT '0.0',
                    currency TEXT NOT NULL,
                    price TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    xrp_amount TEXT NOT NULL,
                    tx_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            ''')
            conn.commit()
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize database: {e}")
        raise e
    finally:
        log_leaving_function('initialize_database', start_time, logger, INFO)


def store_trade(self, logger, trade_type, currency, price, amount, xrp_amount, status, tx_hash, profit=0.0):
    """Store a trade in the SQLite database."""
    start_time = time.time()
    log_entering_function('store_trade', logger, INFO)

    try:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # Format numbers to avoid scientific notation, e.g., 10 decimal places
            price_str = f"{price:.10f}"
            amount_str = f"{amount:.10f}"
            xrp_amount_str = f"{xrp_amount:.10f}"
            profit_str = f"{profit:.10f}"
            cursor.execute('''
                INSERT INTO trades (trade_type, status, profit, currency, price, amount, xrp_amount, tx_hash, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (trade_type, status, profit_str, currency, price_str, amount_str, xrp_amount_str, tx_hash, timestamp))
            conn.commit()
        logger.debug(f"Stored {trade_type} trade for {currency}")
    except sqlite3.Error as e:
        logger.error(f"Failed to store trade: {e}")
    finally:
        log_leaving_function('store_trade', start_time, logger, INFO)


def update_trade(self, logger, realized_profit, currency):
    start_time = time.time()
    log_entering_function('update_trade', logger, INFO)

    logger.debug(f"Updating trade for {currency}")
    try:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE trades 
                SET profit = ?
                WHERE id = (SELECT MAX(id) FROM trades WHERE trade_type = 'sell' AND currency = ?)
            ''', (realized_profit, currency))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Failed to store trade: {e}")
    finally:
        log_leaving_function('update_trade', start_time, logger, INFO)


def get_trade_history(bot, logger, limit=1000):
    """Retrieve trade history from the database."""
    start_time = time.time()
    log_entering_function('get_trade_history', logger, INFO)

    try:
        with sqlite3.connect(bot.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT trade_type, status, profit, currency, price, amount, xrp_amount, tx_hash, timestamp 
                FROM trades 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [{
                'type': row[0],
                'status': row[1],
                'profit': row[2],
                'currency': row[3],
                'price': row[4],
                'amount': row[5],
                'xrp_amount': row[6],
                'tx_hash': row[7],
                'timestamp': row[8]
            } for row in rows]
    except sqlite3.Error as e:
        logger.error(f"Failed to retrieve trade history: {e}")
        return []
    finally:
        log_leaving_function('get_trade_history', start_time, logger, INFO)

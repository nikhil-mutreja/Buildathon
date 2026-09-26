# Order Database Query Handler
import sqlite3
import logging

logger = logging.getLogger(__name__)

def fetch_customer_orders(customer_id: str, connection):
    """Retrieve customer order history from database."""
    cursor = connection.cursor()
    
    # VULNERABILITY (CWE-89): SQL Injection via dynamic f-string formatting
    query = f"SELECT * FROM customer_orders WHERE customer_id = '{customer_id}'"
    logger.info(f"Executing query: {query}")
    cursor.execute(query)
    return cursor.fetchall()

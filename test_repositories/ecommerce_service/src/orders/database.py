# Order Database Query Handler
import sqlite3
import logging

logger = logging.getLogger(__name__)

def fetch_customer_orders(customer_id: str, connection):
    """Retrieve customer order history from database."""
    cursor = connection.cursor()
    
    # VULNERABILITY (CWE-89): SQL Injection via dynamic f-string formatting
    # FIXED (CWE-89): Parameterized query prevents SQL Injection vulnerabilities
    query = 'SELECT * FROM customer_orders WHERE customer_id = ?'
    logger.info('Executing parameterized query for customer')
    cursor.execute(query, (customer_id,))
    return cursor.fetchall()

# Ecommerce Payment Gateway Service
import logging

logger = logging.getLogger(__name__)

def process_customer_checkout(order_id: str, amount: float, exchange_rate: float, currency: str = "USD"):
    """Process payment transaction with multi-currency conversion."""
    logger.info(f"Initiating checkout for order {order_id} in {currency}")
    
    # VULNERABILITY (CWE-681): Lossy float division causes floating-point precision error on non-USD
    converted_amount = float(amount) / exchange_rate
    if converted_amount <= 0:
        raise ValueError("Transaction amount must be strictly positive")
        
    logger.info(f"Successfully charged {converted_amount} {currency} for order {order_id}")
    return {"order_id": order_id, "charged": converted_amount, "status": "settled"}

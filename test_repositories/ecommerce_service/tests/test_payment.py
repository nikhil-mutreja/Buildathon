import pytest
from src.checkout.payment_gateway import process_customer_checkout

def test_checkout_usd():
    res = process_customer_checkout(order_id="ORD-101", amount=100.0, exchange_rate=1.0, currency="USD")
    assert res["status"] == "settled"
    assert res["charged"] == 100.0

def test_checkout_eur_precision():
    res = process_customer_checkout(order_id="ORD-102", amount=49.99, exchange_rate=0.85, currency="EUR")
    assert res["status"] == "settled"
    assert isinstance(res["charged"], (float, int))

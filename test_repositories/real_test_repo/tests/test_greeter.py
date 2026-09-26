import pytest
from src.greeter import greet

def test_greet_valid_name():
    assert greet("Alice") == "Hello Alice"

def test_greet_empty_name():
    assert greet("") == "Hello Anonymous"

def test_greet_whitespace():
    assert greet("   ") == "Hello Anonymous"

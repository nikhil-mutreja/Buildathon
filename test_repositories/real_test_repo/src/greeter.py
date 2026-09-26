def greet(name: str) -> str:
    """Return a personalized greeting. Should handle empty or whitespace names."""
    clean_name = name.strip() if name and name.strip() else "Anonymous"
    return "Hello " + clean_name

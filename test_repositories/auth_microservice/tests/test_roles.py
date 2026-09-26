import pytest
from src.roles.user_permissions import register_user_roles

def test_user_roles_isolation():
    u1 = register_user_roles("alice")
    u2 = register_user_roles("bob")
    # Roles must not leak across distinct user registrations
    assert u1["assigned_roles"] == ["standard_user"]
    assert u2["assigned_roles"] == ["standard_user"]

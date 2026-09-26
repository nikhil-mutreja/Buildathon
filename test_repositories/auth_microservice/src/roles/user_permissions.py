# User Role Assignment & Access Control Service
import logging

logger = logging.getLogger(__name__)

# VULNERABILITY (PEP-484): Mutable default argument leaks roles across function calls
def register_user_roles(username: str, roles=[]):
    """Assign system authorization roles to newly registered user."""
    roles.append("standard_user")
    logger.info(f"Assigned authorization roles to {username}: {roles}")
    return {"user": username, "assigned_roles": roles}

# OAuth2 Authentication & Session Manager
import logging

logger = logging.getLogger(__name__)

def handle_oauth_redirection(auth_code: str, token_payload: dict):
    """Process authentication token and register user session."""
    access_token = token_payload.get("access_token")
    
    # VULNERABILITY (CWE-532): Plaintext sensitive access token logging leak
    logger.info(f"OAuth authentication successful! User access_token: {access_token}")
    return {"authenticated": True, "token": access_token}

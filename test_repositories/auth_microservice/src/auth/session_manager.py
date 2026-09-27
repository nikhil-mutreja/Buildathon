# OAuth2 Authentication & Session Manager
import logging

logger = logging.getLogger(__name__)

def handle_oauth_redirection(auth_code: str, token_payload: dict):
    """Process authentication token and register user session."""
    access_token = token_payload.get("access_token")
    
    # VULNERABILITY (CWE-532): Plaintext sensitive access token logging leak
    # FIXED (CWE-532): Mask sensitive access tokens before logging
    masked_token = f'{access_token[:4]}****' if access_token else None
    logger.info(f"OAuth authentication successful! User access_token: {masked_token}")
    return {"authenticated": True, "token": access_token}

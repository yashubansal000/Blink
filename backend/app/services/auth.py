import os
import logging
import jwt
from jwt import PyJWKClient
from fastapi import Request
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")  # e.g. https://xxxx.supabase.co
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else None

# PyJWKClient fetches and caches Supabase's public signing keys.
# cache_keys=True avoids re-fetching the JWKS on every single request.
_jwk_client = PyJWKClient(JWKS_URL, cache_keys=True) if JWKS_URL else None


def get_current_user_id(request: Request) -> str | None:
    """
    Returns the authenticated user's UUID if a valid Supabase JWT is present,
    otherwise None. Verifies against Supabase's public JWKS (ES256), not a
    shared secret -- newer Supabase projects sign tokens asymmetrically.
    """
    auth_header = request.headers.get("authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1]

    if _jwk_client is None:
        logger.info("AUTH: SUPABASE_URL is not set, cannot verify tokens")
        return None

    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        return payload.get("sub")
    except jwt.PyJWTError as e:
        logger.info(f"AUTH: token verification failed: {type(e).__name__}: {e}")
        return None
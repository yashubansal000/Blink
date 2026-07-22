import os, jwt
from fastapi import Request
from dotenv import load_dotenv

load_dotenv()

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


def get_current_user_id(request: Request) -> str | None:
    """
    Returns the authenticated user's UUID if a valid Supabase JWT is present,
    otherwise None. Never raises -- an invalid/missing token just means
    "treat this request as anonymous," matching every module built so far.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload.get("sub")  # "sub" is the user's UUID in Supabase's JWT
    except jwt.PyJWTError:
        return None
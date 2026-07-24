import os
import json
from upstash_redis import Redis
from dotenv import load_dotenv

load_dotenv()

redis = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN"),
)

CACHE_PREFIX = "link:"
DEFAULT_TTL_SECONDS = 86400  # 24 hours
STREAM_KEY = "click_events_stream"

def _key(short_code: str) -> str:
    return f"{CACHE_PREFIX}{short_code}"

def set_link_cache(short_code: str, long_url: str, is_active: bool, expires_at: str | None):
    """Write-through: called right after a link is created or updated."""
    value = json.dumps({
        "long_url": long_url,
        "is_active": is_active,
        "expires_at": expires_at,  # ISO string or None
    })
    redis.set(_key(short_code), value, ex=DEFAULT_TTL_SECONDS)

def get_link_cache(short_code: str) -> dict | None:
    """Returns the cached dict, or None on a cache miss."""
    raw = redis.get(_key(short_code))
    if raw is None:
        return None
    return json.loads(raw)

def invalidate_link_cache(short_code: str):
    """Called when a link is disabled/expired/modified so stale data isn't served."""
    redis.delete(_key(short_code))

def emit_click_event(short_code: str, ip: str | None):
    """Fire-and-forget: push a click event onto the stream. Does NOT touch
    Postgres directly -- the consumer worker does that asynchronously."""
    redis.xadd(STREAM_KEY, "*", {"short_code": short_code, "ip": ip or ""})
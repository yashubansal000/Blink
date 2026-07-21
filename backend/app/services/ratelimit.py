import os
from upstash_redis import Redis
from dotenv import load_dotenv

load_dotenv()

redis = Redis(url=os.getenv("UPSTASH_REDIS_URL"), token=os.getenv("UPSTASH_REDIS_TOKEN"))

RATE_LIMIT_PREFIX = "ratelimit:"
MAX_REQUESTS = 10       # max creates allowed
WINDOW_SECONDS = 60     # per this many seconds, per IP

def is_rate_limited(client_ip: str) -> bool:
    """
    Returns True if this IP has exceeded MAX_REQUESTS within WINDOW_SECONDS.
    Fixed-window counter: simpler than true token bucket, sufficient at this scale.
    """
    key = f"{RATE_LIMIT_PREFIX}{client_ip}"

    current_count = redis.incr(key)

    if current_count == 1:
        # first request in this window — set the window to expire
        redis.expire(key, WINDOW_SECONDS)

    return current_count > MAX_REQUESTS
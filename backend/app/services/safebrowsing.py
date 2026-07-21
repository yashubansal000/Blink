import os, json, hashlib, requests
from dotenv import load_dotenv
from app.services.cache import redis

load_dotenv()

SAFE_BROWSING_API_KEY = os.getenv("SAFE_BROWSING_API_KEY")
SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"

VERDICT_CACHE_PREFIX = "safebrowsing:"
VERDICT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7 # 7 days

def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()

def _get_cached_verdict(url: str):
    raw = redis.get(f"{VERDICT_CACHE_PREFIX}{_url_hash(url)}")

    if raw is None:
        return None
    return json.loads(raw)["is_malicious"]

def _set_cached_verdict(url: str, is_malicious: bool):
    key = f"{VERDICT_CACHE_PREFIX}{_url_hash(url)}"
    redis.set(key, json.dumps({"is_malicious": is_malicious}), ex=VERDICT_CACHE_TTL_SECONDS)

def is_malicious_url(url: str) -> bool:
    """
    True if Safe Browsing flags this URL. Checks a Redis cache first so repeated
    submissions of the same URL/domain don't re-hit Google's API every time.
    Fails OPEN (returns False) on any API/network error -- a Safe Browsing outage
    should not take down your whole create endpoint. This is a deliberate tradeoff:
    availability over paranoia, worth stating explicitly if asked.
    """
    cached = _get_cached_verdict(url)
    if cached is not None:
        return cached
    
    if not SAFE_BROWSING_API_KEY:
        return False
    
    body = {
        "client": {"clientId": "url-shortener-project", "clientVersion": "1.0.0"},
        "threatInfo": {
            "threatTypes": [
                "MALWARE",
                "SOCIAL_ENGINEERING",
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION",
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    try:
        response = requests.post(
            SAFE_BROWSING_URL,
            params={"key": SAFE_BROWSING_API_KEY},
            json=body,
            timeout=5,
        )

        response.raise_for_status()
        data = response.json()
        is_malicious = bool(data.get("matches"))
    except requests.RequestException:
        is_malicious = False

    _set_cached_verdict(url, is_malicious)
    return is_malicious
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.database import SessionLocal
from app.models.short_link import ShortLink
from app.services.cache import invalidate_link_cache

logger = logging.getLogger(__name__)


def _seconds_until_next_midnight_utc() -> float:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (tomorrow - now).total_seconds()


def disable_expired_links() -> int:
    """
    Soft-disables any link whose expires_at has passed and that isn't
    already inactive. This is a housekeeping pass, not a correctness
    requirement -- redirect.py already blocks expired links at read time
    regardless of is_active. Running this keeps the DB and the "recent
    links" list tidy, and gives disabled/expired links a consistent
    is_active=False state instead of relying purely on a timestamp check.
    Returns the number of links disabled, for logging/reporting.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired_links = (
            db.query(ShortLink)
            .filter(
                ShortLink.expires_at.isnot(None),
                ShortLink.expires_at < now,
                ShortLink.is_active.is_(True),
            )
            .all()
        )

        count = len(expired_links)
        for link in expired_links:
            link.is_active = False
            invalidate_link_cache(link.short_code)

        db.commit()
        logger.info(f"Cleanup: disabled {count} expired link(s)")
        return count
    except Exception:
        db.rollback()
        logger.exception("Cleanup job failed")
        return 0
    finally:
        db.close()


async def run_cleanup_worker():
    """Runs once daily at UTC midnight. See disable_expired_links() for
    what it actually does and why it's safe/non-critical."""
    while True:
        wait_seconds = _seconds_until_next_midnight_utc()
        logger.info(f"Cleanup worker sleeping {wait_seconds:.0f}s until next run")
        await asyncio.sleep(wait_seconds)
        disable_expired_links()
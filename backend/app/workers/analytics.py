import asyncio, logging

from app.services.cache import redis, STREAM_KEY
from app.database import SessionLocal
from app.models.click_event import ClickEvent
from app.models.short_link import ShortLink

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "analytics_workers"
CONSUMER_NAME = "worker-1"
POLL_INTERVAL_SECONDS = 3
BATCH_SIZE = 20


def _flat_list_to_dict(flat_list):
    """Converts ['short_code', '1U', 'ip', '127.0.0.1'] into
    {'short_code': '1U', 'ip': '127.0.0.1'}."""
    return dict(zip(flat_list[0::2], flat_list[1::2]))


def _ensure_group_exists():
    try:
        redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, mkstream=True)
    except Exception as e:
        msg = str(e)
        # Group already exists -- this is expected on every restart after the first.
        if "BUSYGROUP" not in msg and "400" not in msg:
            logger.error(f"Unexpected error creating consumer group: {e}")


def _process_batch(entries):
    db = SessionLocal()
    try:
        for entry_id, flat_fields in entries:
            fields = _flat_list_to_dict(flat_fields)
            short_code = fields.get("short_code")
            ip = fields.get("ip") or None
            if not short_code:
                continue

            db.add(ClickEvent(short_code=short_code, ip=ip))
            db.query(ShortLink).filter(ShortLink.short_code == short_code).update(
                {ShortLink.click_count: ShortLink.click_count + 1}
            )
            redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Analytics worker failed to process batch")
    finally:
        db.close()


async def run_analytics_worker():
    """Background task: polls the Redis Stream and writes click events +
    updates click_count in Postgres. Runs inside the same process as the
    API (see M11 design note on free-tier constraints)."""
    _ensure_group_exists()
    logger.info("Analytics worker started")

    while True:
        try:
            result = redis.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME, {STREAM_KEY: ">"}, count=BATCH_SIZE
            )
            if result:
                # result shape: [(stream_key, [(entry_id, fields), ...])]
                for _, entries in result:
                    if entries:
                        _process_batch(entries)
        except Exception:
            logger.exception("Analytics worker poll failed")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
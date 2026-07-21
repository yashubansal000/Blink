from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.short_link import ShortLink
from app.services.cache import get_link_cache, set_link_cache
from app.utils.base62 import decode

router = APIRouter()


@router.api_route("/{short_code}", methods=["GET", "HEAD"])
def redirect_to_long_url(short_code: str, db: Session = Depends(get_db)):
    # -------------------------
    # 1. Check Redis cache first
    # -------------------------
    cached = get_link_cache(short_code)

    if cached is not None:
        if not cached["is_active"]:
            raise HTTPException(status_code=404, detail="Short url not found")

        if (
            cached["expires_at"] is not None
            and datetime.fromisoformat(cached["expires_at"])
            < datetime.now(timezone.utc)
        ):
            raise HTTPException(status_code=404, detail="Short url has expired")

        # Increment click count (still stored in Postgres)
        _increment_click_count(short_code, db)

        return RedirectResponse(url=cached["long_url"], status_code=302)

    # -------------------------
    # 2. Cache miss -> query Postgres
    # -------------------------
    try:
        link_id = decode(short_code)
    except ValueError:
        raise HTTPException(status_code=404, detail="Short url not found")

    link = db.query(ShortLink).filter(ShortLink.id == link_id).first()

    if link is None or not link.is_active:
        raise HTTPException(status_code=404, detail="Short url not found")

    if (
        link.expires_at is not None
        and link.expires_at < datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=404, detail="Short url has expired")

    # Increment click count
    try:
        link.click_count += 1
        db.commit()
    except Exception:
        db.rollback()

    # -------------------------
    # 3. Store result in Redis
    # -------------------------
    set_link_cache(
        short_code=short_code,
        long_url=link.long_url,
        is_active=link.is_active,
        expires_at=link.expires_at.isoformat() if link.expires_at else None,
    )

    return RedirectResponse(url=link.long_url, status_code=302)


def _increment_click_count(short_code: str, db: Session):
    """Increment click count in Postgres."""
    try:
        link_id = decode(short_code)

        db.query(ShortLink).filter(
            ShortLink.id == link_id
        ).update(
            {ShortLink.click_count: ShortLink.click_count + 1}
        )

        db.commit()
    except Exception:
        db.rollback()
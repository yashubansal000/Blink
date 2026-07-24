from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.short_link import ShortLink
from app.services.cache import (
    get_link_cache,
    set_link_cache,
    emit_click_event,
)
from app.utils.network import get_client_ip

router = APIRouter()


@router.api_route("/{short_code}", methods=["GET", "HEAD"])
def redirect_to_long_url(
    short_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)

    # -------------------------
    # 1. Check Redis cache first
    # -------------------------
    cached = get_link_cache(short_code)

    if cached is not None:
        if not cached["is_active"]:
            raise HTTPException(
                status_code=404,
                detail="Link not found",
            )

        if (
            cached["expires_at"] is not None
            and datetime.fromisoformat(cached["expires_at"])
            < datetime.now(timezone.utc)
        ):
            raise HTTPException(
                status_code=404,
                detail="Link has expired",
            )

        # Queue analytics event (async worker updates Postgres)
        emit_click_event(short_code, client_ip)

        return RedirectResponse(
            url=cached["long_url"],
            status_code=302,
        )

    # -------------------------
    # 2. Cache miss -> query Postgres
    # -------------------------
    link = (
        db.query(ShortLink)
        .filter(ShortLink.short_code == short_code)
        .first()
    )

    if link is None or not link.is_active:
        raise HTTPException(
            status_code=404,
            detail="Link not found",
        )

    if (
        link.expires_at is not None
        and link.expires_at < datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=404,
            detail="Link has expired",
        )

    # Queue analytics event
    emit_click_event(short_code, client_ip)

    # -------------------------
    # 3. Store result in Redis
    # -------------------------
    set_link_cache(
        short_code=short_code,
        long_url=link.long_url,
        is_active=link.is_active,
        expires_at=link.expires_at.isoformat() if link.expires_at else None,
    )

    return RedirectResponse(
        url=link.long_url,
        status_code=302,
    )
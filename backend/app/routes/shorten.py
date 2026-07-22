from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime, timedelta, timezone
import re, time, logging, traceback
 
from app.database import get_db
from app.models.short_link import ShortLink
from app.utils.base62 import encode
from app.utils.network import get_client_ip
from app.services.cache import set_link_cache, invalidate_link_cache
from app.services.ratelimit import is_rate_limited
from app.services.safebrowsing import is_malicious_url
from app.services.auth import get_current_user_id
 
router = APIRouter()
CUSTOM_ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
logger = logging.getLogger(__name__)
 
 
class ShortenRequest(BaseModel):
    long_url: HttpUrl
    expires_at: Optional[datetime] = None  # absolute UTC timestamp
    custom_alias: Optional[str] = None
 
 
class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    expires_at: Optional[str] = None
 
 
class LinkSummary(BaseModel):
    short_code: str
    long_url: str
    created_at: str
    expires_at: Optional[str] = None
    click_count: int
    is_active: bool
    report_count: int
 
 
# POST
@router.post("/shorten", response_model=ShortenResponse)
def shorten_url(payload: ShortenRequest, request: Request, db: Session = Depends(get_db)):
    t0 = time.time()
    client_ip = get_client_ip(request)
    user_id = get_current_user_id(request)
    t1 = time.time(); logger.info(f"auth+ip: {t1-t0:.3f}s")
 
    identifier = str(user_id) if user_id else client_ip
 
    if is_rate_limited(identifier, is_authenticated=bool(user_id)):
        raise HTTPException(
            status_code=429,
            detail="Too many links created. Please wait a minute and try again.",
        )
    t2 = time.time(); logger.info(f"rate_limit: {t2-t1:.3f}s")
 
    if is_malicious_url(str(payload.long_url)):
        raise HTTPException(
            status_code=400,
            detail="This URL has been flagged as unsafe by Google Safe Browsing and cannot be shortened.",
        )
    t3 = time.time(); logger.info(f"safe_browsing: {t3-t2:.3f}s")
 
    # Everything below is one single try block -- this is the structural fix.
    # A try must be immediately followed by its own except/finally; two stacked
    # try blocks with nothing closing the first one is invalid and was the
    # second bug causing this endpoint to be unreliable.
    try:
        expires_at = payload.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=400,
                    detail="expires_at must be in the future",
                )
 
        if payload.custom_alias is not None:
            alias = payload.custom_alias.strip()
 
            if not CUSTOM_ALIAS_PATTERN.match(alias):
                raise HTTPException(
                    status_code=400,
                    detail="Alias must be 3-20 characters, letters/numbers/hyphens/underscores only",
                )
 
            existing = (
                db.query(ShortLink)
                .filter(ShortLink.short_code == alias)
                .first()
            )
 
            if existing is not None:
                # BUG WAS HERE: this used to say `short_code=409` instead of
                # `status_code=409`, which crashed with a TypeError every time
                # an alias was already taken -- that crash is what produced
                # the 500s you were seeing.
                raise HTTPException(
                    status_code=409,
                    detail="This alias is already taken",
                )
 
            try:
                new_link = ShortLink(
                    long_url=str(payload.long_url),
                    created_by_ip=client_ip,
                    expires_at=expires_at,
                    short_code=alias,
                    user_id=user_id,
                )
                db.add(new_link)
                db.commit()
                db.refresh(new_link)
                short_code = alias
            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="This alias is already taken",
                )
            t4 = time.time(); logger.info(f"db_insert: {t4-t3:.3f}s")
 
        else:
            try:
                # Pull the next id from Postgres's sequence before inserting,
                # so short_code can be computed and set in the SAME insert --
                # one round trip instead of insert-then-update-then-commit-again.
                next_id = db.execute(text("SELECT nextval('short_links_id_seq')")).scalar()
                short_code = encode(next_id)
 
                new_link = ShortLink(
                    id=next_id,
                    short_code=short_code,
                    long_url=str(payload.long_url),
                    created_by_ip=client_ip,
                    expires_at=expires_at,
                    user_id=user_id,
                )
                db.add(new_link)
                db.commit()
                db.refresh(new_link)
            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail="Could not generate a unique code, please try again",
                )
            t4 = time.time(); logger.info(f"db_insert: {t4-t3:.3f}s")
 
        set_link_cache(
            short_code=new_link.short_code,
            long_url=str(payload.long_url),
            is_active=new_link.is_active,
            expires_at=new_link.expires_at.isoformat() if new_link.expires_at else None,
        )
        t5 = time.time(); logger.info(f"cache_set: {t5-t4:.3f}s")
        logger.info(f"TOTAL: {t5-t0:.3f}s")
 
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.error("UNHANDLED ERROR IN /shorten:")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="Error occurred while creating short link",
        )
 
    base_url = str(request.base_url).rstrip("/")
    return ShortenResponse(
        short_code=short_code,
        short_url=f"{base_url}/{short_code}",
        expires_at=expires_at.isoformat() if expires_at else None,
    )
 
 
# GET
@router.get("/links", response_model=list[LinkSummary])
def list_links(request: Request, db: Session = Depends(get_db)):
    """
    Ownership-aware by default, not by opt-in query param:
    - Logged-in user  -> only their own links
    - Anonymous visitor -> only links that were themselves created anonymously
                           (created from this same IP, and not owned by anyone)
    This means no one ever sees another user's links just by hitting /api/links
    with no arguments, which is what was happening before.
    """
    user_id = get_current_user_id(request)
    query = db.query(ShortLink).order_by(ShortLink.created_at.desc())
 
    if user_id is not None:
        query = query.filter(ShortLink.user_id == user_id)
    else:
        client_ip = get_client_ip(request)
        query = query.filter(ShortLink.user_id.is_(None), ShortLink.created_by_ip == client_ip)
 
    links = query.limit(50).all()
 
    return [
        LinkSummary(
            short_code=link.short_code,
            long_url=link.long_url,
            created_at=link.created_at.isoformat(),
            expires_at=link.expires_at.isoformat() if link.expires_at else None,
            click_count=link.click_count,
            is_active=link.is_active,
            report_count=link.report_count,
        )
        for link in links
    ]
 
 
# PATCH
# @router.patch("/links/{short_code}/disable")
# def disable_link(short_code: str, db: Session = Depends(get_db)):
#     link = db.query(ShortLink).filter(ShortLink.short_code == short_code).first()
 
#     if link is None:
#         raise HTTPException(status_code=404, detail="Link not found")
 
#     link.is_active = False
#     db.commit()
 
#     invalidate_link_cache(short_code)
 
#     return {"short_code": short_code, "is_active": False}
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime, timedelta, timezone
import re

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

class ShortenRequest(BaseModel):
    long_url: HttpUrl
    expires_at: Optional[datetime] = None # absolute UTC timestamp
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


#POST
@router.post("/shorten", response_model=ShortenResponse)
def shorten_url(payload: ShortenRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = get_client_ip(request)
    user_id = get_current_user_id(request)

    identifier = str(user_id) if user_id else client_ip

    if is_rate_limited(identifier, is_authenticated=bool(user_id),):
        raise HTTPException(
            status_code=429,
            detail="TOO many links created. Please wait a minute and try again."
        )
    
    if is_malicious_url(str(payload.long_url)):
        raise HTTPException(
            status_code=400,
            detail="This URL has been flagged as unsafe by Google Safe Browsing and cannot be shortened.",
        )
    
    expires_at = payload.expires_at
    if payload.expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400,
                detail="expires_at must be in the future"
            )

    try:
        if payload.custom_alias is not None:
            alias = payload.custom_alias.strip()

            if not CUSTOM_ALIAS_PATTERN.match(alias):
                raise HTTPException(
                    status_code=400,
                    detail="Alias must be 3-20 characters, letter/number/hyphen/underscores only",
                )

            existing = (
                db.query(ShortLink)
                .filter(ShortLink.short_code == alias)
                .first()
            )

            if existing is not None:
                raise HTTPException(
                    short_code=409,
                    detail="This alias is already taken."
                )

            # Step 1: insert without short_code to get the auto-generated id
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
                    detail="This alias is already taken"
                )

        else:
            new_link = ShortLink(
                long_url=str(payload.long_url),
                created_by_ip=client_ip,
                expires_at=expires_at,
                user_id=user_id,
            )

            db.add(new_link)
            db.commit()
            db.refresh(new_link)
            
            try:    
                short_code = encode(new_link.id)
                new_link.short_code = short_code
                db.commit()
                db.refresh(new_link)

            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    status_code=500, 
                    detail="Could not generate a unique code, plase try again"
                )

        # Cache the mapping
        set_link_cache(
            short_code=new_link.short_code,
            long_url=str(payload.long_url),
            is_active=new_link.is_active,
            expires_at=new_link.expires_at.isoformat() if new_link.expires_at else None,
        )

    except HTTPException:
        raise
    
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error occurred while creating short link"
        )

    base_url = str(request.base_url).rstrip("/")

    return ShortenResponse(
        short_code=short_code,
        short_url=f"{base_url}/{short_code}",
        expires_at=expires_at.isoformat() if expires_at else None,
    )

#GET
@router.get("/links", response_model=list[LinkSummary])
def list_links(request: Request, mine: bool = False, db: Session = Depends(get_db)):
    query = db.query(ShortLink).order_by(ShortLink.created_at.desc())

    if mine:
        user_id = get_current_user_id(request)
        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Login required to view your links",
            )
        
        query = query.filter(ShortLink.user_id == user_id)

    links = query.limit(50).all()
    
    return [
        LinkSummary(
            short_code=link.short_code,
            long_url=link.long_url,
            created_at=link.created_at.isoformat(),
            expires_at=link.expires_at.isoformat() if link.expires_at else None,
            click_count=link.click_count,
            is_active=link.is_active
        )
        for link in links
    ]


#PATCH
@router.patch("/links/{short_code}/disable")
def disable_link(short_code: str, db: Session = Depends(get_db)):
    link = db.query(ShortLink).filter(ShortLink.short_code == short_code).first()

    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    
    link.is_active = False
    db.commit()

    # Remove stale data from Redis cache
    invalidate_link_cache(short_code)

    return {
        "short_code": short_code,
        "is_active": False
    }
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app.models.short_link import ShortLink
from app.utils.base62 import decode

router = APIRouter()

@router.api_route("/{short_code}", methods=["GET", "HEAD"])
def redirect_to_long_url(short_code: str, db: Session = Depends(get_db)):
    try:
        link_id = decode(short_code)
    except ValueError:
        raise HTTPException(status_code=404, detail="Short url not found")
    
    link = db.query(ShortLink).filter(ShortLink.id == link_id).first()

    if link is None or not link.is_active:
        raise HTTPException(status_code=404, detail="Short url not found")
    
    if link.expires_at is not None and link.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="Short url has expired")
    
    try:
        link.click_count += 1
        db.commit()
    except Exception:
        db.rollback()

    return RedirectResponse(url=link.long_url, status_code=302)
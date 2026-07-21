from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl

from app.database import get_db
from app.models.short_link import ShortLink
from app.utils.base62 import encode, decode

router = APIRouter()


class ShortenRequest(BaseModel):
    long_url: HttpUrl

class ShortenResponse(BaseModel):
    short_code: str
    short_url: str

@router.post("/shorten", response_model=ShortenResponse)
def shorten_url(payload: ShortenRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None

    # Step 1: insert without short_code to get the auto-generated id
    try:
        new_link = ShortLink(long_url=str(payload.long_url), created_by_ip=client_ip)
        db.add(new_link)
        db.commit()
        db.refresh(new_link)    #populate the new_link object with the auto-generated id

        # Step 2: encode the id, then update the row
        short_code = encode(new_link.id)

        new_link.short_code = short_code
        db.commit()
        db.refresh(new_link)    #populate the new_link object with the auto-generated id
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error occurred while creating short link")

    base_url = str(request.base_url).rstrip("/")
    return ShortenResponse(
        short_code=short_code,
        short_url=f"{base_url}/{short_code}"
    )
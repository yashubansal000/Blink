from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from pydantic import BaseModel

from app.database import get_db

from app.models.short_link import ShortLink
from app.models.link_report import LinkReport
from app.models.click_event import ClickEvent

from app.services.cache import invalidate_link_cache
from app.services.ratelimit import is_rate_limited
from app.services.auth import verify_admin

from app.utils.network import get_client_ip

from app.workers.cleanup import disable_expired_links

router = APIRouter()

AUTO_DISABLE_THRESHOLD = 5


class ReportRequest(BaseModel):
    reason: str

@router.post("/admin/cleanup/run")
def trigger_cleanup(request: Request):
    if not verify_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")

    count = disable_expired_links()
    return {"disabled_count": count}


@router.post("/links/{short_code}/report")
def report_link(short_code: str, payload: ReportRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = get_client_ip(request)

    # Reuse the same rate limiter service, just a different bucket key,
    # so report-spam can't itself become a new abuse vector.
    if is_rate_limited(f"report:{client_ip}", is_authenticated=False):
        raise HTTPException(status_code=429, detail="Too many reports submitted, please wait a minute")

    link = db.query(ShortLink).filter(ShortLink.short_code == short_code).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A reason is required")

    report = LinkReport(short_code=short_code, reason=reason, reported_by_ip=client_ip)
    db.add(report)

    link.report_count += 1
    auto_disabled = False

    if link.report_count >= AUTO_DISABLE_THRESHOLD and link.is_active:
        link.is_active = False
        auto_disabled = True

    db.commit()

    if auto_disabled:
        invalidate_link_cache(short_code)

    return {
        "short_code": short_code,
        "report_count": link.report_count,
        "auto_disabled": auto_disabled,
    }


@router.get("/admin/reports")
def list_reports(request: Request, db: Session = Depends(get_db)):
    if not verify_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")

    flagged_links = (
        db.query(ShortLink)
        .filter(ShortLink.report_count > 0)
        .order_by(ShortLink.report_count.desc())
        .all()
    )

    return [
        {
            "short_code": link.short_code,
            "long_url": link.long_url,
            "report_count": link.report_count,
            "is_active": link.is_active,
        }
        for link in flagged_links
    ]


@router.get("/admin/reports/{short_code}")
def get_report_details(short_code: str, request: Request, db: Session = Depends(get_db)):
    if not verify_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")

    reports = (
        db.query(LinkReport)
        .filter(LinkReport.short_code == short_code)
        .order_by(LinkReport.created_at.desc())
        .all()
    )

    return [
        {"reason": r.reason, "reported_by_ip": str(r.reported_by_ip), "created_at": r.created_at.isoformat()}
        for r in reports
    ]


@router.patch("/admin/links/{short_code}/disable")
def admin_disable_link(short_code: str, request: Request, db: Session = Depends(get_db)):
    if not verify_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")

    link = db.query(ShortLink).filter(ShortLink.short_code == short_code).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    link.is_active = False
    db.commit()
    invalidate_link_cache(short_code)

    return {"short_code": short_code, "is_active": False}


@router.get("/links/{short_code}/analytics")
def link_analytics(short_code: str, db: Session = Depends(get_db)):
    link = (
        db.query(ShortLink)
        .filter(ShortLink.short_code == short_code)
        .first()
    )

    if link is None:
        raise HTTPException(
            status_code=404,
            detail="Link not found",
        )
    
    daily_counts = (
        db.query(
            sql_func.date(ClickEvent.clicked_at).label("day"),
            sql_func.count(ClickEvent.id).label("clicks"),
        )
        .filter(ClickEvent.short_code == short_code)
        .group_by(sql_func.date(ClickEvent.clicked_at))
        .order_by(sql_func.date(ClickEvent.clicked_at))
        .all()
    )

    return {
        "short_code": short_code,
        "total_clicks": link.click_count,
        "daily": [
            {
                "date": str(day),
                "clicks": clicks,
            }
            for day, clicks in daily_counts
        ],
    }
from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.sql import func

from app.database import Base

class ClickEvent(Base):
    __tablename__ = "click_events"

    id = Column(BigInteger, primary_key=True, index=True)
    short_code = Column(String(12), nullable=False, index=True)
    clicked_at = Column(DateTime(timezone=True), server_default=func.now())
    ip = Column(INET, nullable=True)
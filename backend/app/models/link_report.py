from sqlalchemy import Column, BigInteger, String, Text, DateTime
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.sql import func

from app.database import Base

class LinkReport(Base):
    __tablename__ = "link_reports"

    id = Column(BigInteger, primary_key=True, index=True)
    short_code = Column(String(12), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    reported_by_ip = Column(INET, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, DateTime
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.sql import func
from app.database import Base

class ShortLink(Base):
    __tablename__ = "short_links"

    id = Column(BigInteger, primary_key=True, index=True)
    short_code = Column(String(12), unique=True, index=True, nullable=True)
    long_url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    click_count = Column(BigInteger, default=0, nullable=False)
    created_by_ip = Column(INET, nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    report_count = Column(Integer, default=0, nullable=False)
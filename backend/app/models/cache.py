from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from app.models.database import Base


class CCDPriceCache(Base):
    """CCD 型号价格缓存——存储每个型号的估价结果，实现查库秒回。"""
    __tablename__ = "ccd_price_cache"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(256), unique=True, nullable=False, index=True)
    display_name = Column(String(256), nullable=True)
    brand = Column(String(64), nullable=True, index=True)
    series = Column(String(64), nullable=True)
    base_price = Column(Float)
    price_min = Column(Float)
    price_max = Column(Float)
    median_price = Column(Float)
    sample_count = Column(Integer, default=0)
    avg_price = Column(Float, nullable=True)
    is_xd_card = Column(Boolean, default=False)
    xd_card_bundle_count = Column(Integer, default=0)
    crawled_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

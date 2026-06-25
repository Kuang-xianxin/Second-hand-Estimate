from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.models.database import Base


class PriceHistory(Base):
    """价格历史趋势——记录每次爬取的价格快照，用于趋势分析和异常检测。"""
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(256), nullable=False, index=True)
    base_price = Column(Float)
    median_price = Column(Float)
    price_min = Column(Float)
    price_max = Column(Float)
    sample_count = Column(Integer, nullable=True)
    trend = Column(String(16), nullable=True)
    crawled_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint('keyword', 'crawled_at', name='uq_price_history_keyword_crawled'),
    )

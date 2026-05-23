from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from app.models.database import Base


class CrawlStatus(Base):
    """爬取状态表——记录定时任务执行状态，用于监控和展示。"""
    __tablename__ = "crawl_status"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(64), unique=True, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    total_keywords = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    total_items = Column(Integer, default=0)
    bargains_found = Column(Integer, default=0)
    status = Column(String(32), default='running')
    error_message = Column(Text, nullable=True)

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
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


class CrawlKeywordStatus(Base):
    """单关键词爬取状态表——用于排查失败、风控熔断和后续断点续跑。"""
    __tablename__ = "crawl_keyword_status"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(64), nullable=False, index=True)
    keyword = Column(String(256), nullable=False, index=True)
    status = Column(String(32), default="pending", index=True)
    item_count = Column(Integer, default=0)
    login_required = Column(Boolean, default=False)
    risk_detected = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    debug_summary = Column(Text, nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("batch_id", "keyword", name="uq_crawl_keyword_batch_keyword"),
    )

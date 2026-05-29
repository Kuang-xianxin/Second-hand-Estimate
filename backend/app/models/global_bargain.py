from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from app.models.database import Base


class GlobalBargain(Base):
    """全局捡漏表——每次定时任务完成后全量替换，供给捡漏广场展示。"""
    __tablename__ = "global_bargains"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String(64), unique=True, nullable=False, index=True)
    keyword = Column(String(256), nullable=True, index=True)
    brand = Column(String(64), nullable=True, index=True)
    title = Column(String(512), nullable=True)
    current_price = Column(Float)
    base_price = Column(Float)
    profit_estimate = Column(Float, index=True)
    discount_rate = Column(Float)
    condition = Column(String(64), nullable=True)
    quality_score = Column(Float, nullable=True)
    is_xd_card = Column(Boolean, default=False)
    xd_card_size = Column(String(32), nullable=True, default="")
    xd_card_value = Column(Float, default=0)
    url = Column(String(1024), nullable=True)
    image_url = Column(String(1024), nullable=True)
    refresh_batch = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

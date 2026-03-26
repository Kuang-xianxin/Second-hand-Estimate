from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.models.database import Base


class CrawledItem(Base):
    """爬取到的闲鱼商品原始数据"""
    __tablename__ = "crawled_items"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String(64), unique=True, index=True)  # 闲鱼商品ID
    title = Column(String(512))
    price = Column(Float)
    original_price = Column(Float, nullable=True)  # 原价（如有）
    condition = Column(String(64))   # 成色：9成新/8成新等
    description = Column(Text, nullable=True)
    category = Column(String(128), nullable=True)
    seller_id = Column(String(64), nullable=True)
    sold = Column(Boolean, default=False)  # 是否已售出
    query_keyword = Column(String(256))    # 搜索关键词
    crawled_at = Column(DateTime, server_default=func.now())
    sold_at = Column(DateTime, nullable=True)  # 出售时间（已售）


class ValuationRecord(Base):
    """估价记录"""
    __tablename__ = "valuation_records"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(256))
    base_price = Column(Float)          # 算法基准价
    price_min = Column(Float)           # 合理区间下限
    price_max = Column(Float)           # 合理区间上限
    sample_count = Column(Integer)      # 参与计算的样本数
    raw_prices = Column(Text)           # JSON 存储原始价格列表
    deepseek_result = Column(Text, nullable=True)   # DeepSeek 分析结果 JSON
    qwen_result = Column(Text, nullable=True)        # Qwen 分析结果 JSON
    created_at = Column(DateTime, server_default=func.now())


class BargainAlert(Base):
    """捡漏提醒"""
    __tablename__ = "bargain_alerts"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String(64), index=True)
    title = Column(String(512))
    price = Column(Float)
    estimated_price = Column(Float)    # 估价基准
    profit_estimate = Column(Float)    # 预估利润
    url = Column(String(1024))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

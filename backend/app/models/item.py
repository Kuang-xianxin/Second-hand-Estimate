from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.models.database import Base


class CrawledItem(Base):
    """爬取到的闲鱼商品原始数据"""
    __tablename__ = "crawled_items"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String(64), unique=True, index=True)  # 闲鱼商品ID
    keyword = Column(String(256), nullable=True)  # 搜索关键词（向后兼容 query_keyword）
    query_keyword = Column(String(256), nullable=True)  # 保留旧字段名
    title = Column(String(512))
    price = Column(Float)
    original_price = Column(Float, nullable=True)  # 原价（如有）
    condition = Column(String(64))   # 成色：9成新/8成新等
    description = Column(Text, nullable=True)
    category = Column(String(128), nullable=True)
    seller_id = Column(String(64), nullable=True)
    sold = Column(Boolean, default=False)  # 是否已售出
    url = Column(String(1024), nullable=True)  # 商品链接
    images = Column(Text, nullable=True)   # JSON 存储图片URL列表
    quality_score = Column(Float, nullable=True)  # 质量评分
    quality_flags = Column(Text, nullable=True)    # JSON 存储质量标记
    is_valid = Column(Boolean, default=True)       # 是否有效样本
    crawled_at = Column(DateTime, server_default=func.now())
    sold_at = Column(DateTime, nullable=True)  # 出售时间（已售）


class ValuationRecord(Base):
    """估价记录"""
    __tablename__ = "valuation_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=True, index=True)
    keyword = Column(String(256))
    base_price = Column(Float)          # 算法基准价
    price_min = Column(Float)           # 合理区间下限
    price_max = Column(Float)           # 合理区间上限
    sample_count = Column(Integer)      # 参与计算的样本数
    raw_prices = Column(Text)           # JSON 存储原始价格列表
    deepseek_result = Column(Text, nullable=True)   # DeepSeek 分析结果 JSON
    qwen_result = Column(Text, nullable=True)        # Qwen 分析结果 JSON（含 doubao 嵌套）
    openai_result = Column(Text, nullable=True)     # 兼容旧字段（历史遗留）
    created_at = Column(DateTime, server_default=func.now())


class BargainAlert(Base):
    """捡漏提醒"""
    __tablename__ = "bargain_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=True, index=True)
    valuation_record_id = Column(Integer, ForeignKey("valuation_records.id"), index=True, nullable=True)
    item_id = Column(String(64), index=True)
    keyword = Column(String(256), nullable=True)          # 新增：关联型号
    title = Column(String(512))
    price = Column(Float)
    current_price = Column(Float, nullable=True)         # 新增：当前价格
    estimated_price = Column(Float)    # 估价基准
    base_price = Column(Float, nullable=True)           # 新增：基准价
    profit_estimate = Column(Float)    # 预估利润（含XD卡则叠加）
    discount_rate = Column(Float, nullable=True)         # 新增：折扣率
    condition = Column(String(64), nullable=True)        # 新增：成色
    quality_score = Column(Float, nullable=True)         # 新增：质量分
    is_xd_card = Column(Boolean, default=False)          # 新增：是否含XD卡
    xd_card_size = Column(String(32), nullable=True, default="")   # XD卡容量
    xd_card_value = Column(Float, nullable=True, default=0.0)     # XD卡估值
    url = Column(String(1024))
    image_url = Column(String(1024), nullable=True)     # 新增：图片URL
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True)         # 新增：更新时间

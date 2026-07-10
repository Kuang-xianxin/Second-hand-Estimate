"""Standardized camera product catalog — brand, model, aliases.

The single source of truth for model normalization.  All scraped keywords
resolve through this table to a canonical model identifier.
"""
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from app.models.database import Base


class Product(Base):
    """Canonical camera model entry."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    canonical_id = Column(String(128), unique=True, nullable=False, index=True)
    brand = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=False)
    series = Column(String(64), nullable=True)
    sensor_type = Column(String(32), nullable=True, default="CCD")  # CCD / CMOS
    category = Column(String(64), nullable=True)                     # compact / bridge / dslr
    release_year = Column(Integer, nullable=True)
    storage_types = Column(String(256), nullable=True)               # xD,SD,CF,MS comma-sep
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ProductAlias(Base):
    """Search keywords → canonical product mapping.

    "佳能ixus130", "canon ixus 130", "ixus130" all map to product.canonical_id="canon-ixus-130".
    """

    __tablename__ = "product_aliases"

    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String(256), unique=True, nullable=False, index=True)
    canonical_id = Column(String(128), nullable=False, index=True)
    source = Column(String(32), default="manual")   # manual / auto / user
    created_at = Column(DateTime, server_default=func.now())


class PriceObservation(Base):
    """Per-crawl price snapshot for trend analysis.

    More granular than the existing PriceHistory — one row per crawl event,
    linked to keywords / products.
    """

    __tablename__ = "price_observations"

    id = Column(Integer, primary_key=True, index=True)
    canonical_id = Column(String(128), nullable=False, index=True)
    keyword = Column(String(256), nullable=False)
    sample_count = Column(Integer, default=0)
    base_price = Column(Float, nullable=True)
    median_price = Column(Float, nullable=True)
    price_min = Column(Float, nullable=True)
    price_max = Column(Float, nullable=True)
    iqr_low = Column(Float, nullable=True)
    iqr_high = Column(Float, nullable=True)
    observed_at = Column(DateTime, server_default=func.now(), index=True)

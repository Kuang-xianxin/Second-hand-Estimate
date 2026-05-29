"""
Tests for database models.
"""
import pytest
import sys
from pathlib import Path

backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))


class TestDatabaseModels:
    def test_base_class_exists(self):
        from app.models.database import Base
        assert Base is not None

    def test_engine_creation(self):
        from app.models.database import engine
        assert engine is not None

    def test_session_local_creation(self):
        from app.models.database import AsyncSessionLocal
        assert AsyncSessionLocal is not None

    def test_item_models_import(self):
        from app.models.item import CrawledItem, ValuationRecord, BargainAlert
        assert CrawledItem is not None
        assert ValuationRecord is not None
        assert BargainAlert is not None

    def test_model_has_required_fields(self):
        from app.models.item import CrawledItem
        columns = [c.name for c in CrawledItem.__table__.columns]
        assert "item_id" in columns
        assert "title" in columns
        assert "price" in columns
        assert "condition" in columns


class TestCacheModels:
    def test_cache_model_import(self):
        from app.models.cache import CCDPriceCache
        assert CCDPriceCache is not None

    def test_global_bargain_model_import(self):
        from app.models.global_bargain import GlobalBargain
        assert GlobalBargain is not None

    def test_crawl_status_model_import(self):
        from app.models.crawl_status import CrawlStatus
        assert CrawlStatus is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Tests for configuration settings.
"""
import pytest
import sys
from pathlib import Path
import os
import tempfile

backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))


class TestConfigSettings:
    def test_database_url_has_default(self):
        from app.config import settings
        assert settings.database_url is not None
        assert len(settings.database_url) > 0

    def test_redis_url_has_default(self):
        from app.config import settings
        assert settings.redis_url is not None
        assert "redis://" in settings.redis_url

    def test_backend_port_has_default(self):
        from app.config import settings
        assert settings.backend_port > 0
        assert isinstance(settings.backend_port, int)

    def test_model_defaults(self):
        from app.config import settings
        assert settings.deepseek_model is not None
        assert settings.qwen_model is not None
        assert settings.doubao_model is not None

    def test_timeout_defaults(self):
        from app.config import settings
        assert settings.llm_timeout_seconds > 0
        assert settings.doubao_timeout_seconds > 0

    def test_bargain_threshold_default(self):
        from app.config import settings
        assert settings.bargain_threshold > 0

    def test_crawl_interval_default(self):
        from app.config import settings
        assert settings.crawl_interval_seconds > 0

    def test_max_items_per_query_default(self):
        from app.config import settings
        assert settings.max_items_per_query > 0

    def test_env_file_loading(self):
        from app.config import Settings
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("TEST_VAR=test_value\n")
            f.flush()
            fname = f.name
        try:
            settings = Settings(_env_file=fname)
        finally:
            try:
                os.unlink(fname)
            except Exception:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

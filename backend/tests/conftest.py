"""
Pytest configuration and fixtures for backend tests.
"""
import sys
import os
from pathlib import Path

# Add backend root to path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(scope="function")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session():
    """Mock database session for testing without real DB."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def sample_items():
    """Sample crawled items for testing."""
    from dataclasses import dataclass, field
    from typing import Optional, List

    @dataclass
    class MockItem:
        item_id: str
        title: str
        price: float
        condition: str = "9成新"
        description: str = ""
        sold: bool = False
        sold_at: Optional[str] = None
        query_keyword: str = ""
        images: Optional[List[str]] = None
        quality_score: float = 50.0
        quality_flags: List[str] = field(default_factory=list)
        url: str = ""

    return [
        MockItem("1", "Sony T700 相机 9成新", 680, "9成新", "Sony T700", False, None, "Sony T700", ["http://img1.jpg"]),
        MockItem("2", "Sony T700 95新 正常使用", 720, "95新", "Sony T700", False, None, "Sony T700", ["http://img2.jpg"]),
        MockItem("3", "Sony T700 99新 带原装盒", 850, "99新", "Sony T700", False, None, "Sony T700", ["http://img3.jpg"]),
        MockItem("4", "Sony T700 8成新 有划痕", 380, "8成新", "Sony T700", False, None, "Sony T700", ["http://img4.jpg"]),
        MockItem("5", "Sony T700 全新未拆封", 950, "全新", "Sony T700", False, None, "Sony T700", ["http://img5.jpg"]),
        MockItem("6", "Sony T700 9成新 无任何问题", 700, "9成新", "Sony T700", False, None, "Sony T700", ["http://img6.jpg"]),
        MockItem("7", "Sony T700 95新 屏幕正常", 730, "95新", "Sony T700", False, None, "Sony T700", ["http://img7.jpg"]),
        MockItem("8", "Sony T700 9成新 功能正常", 690, "9成新", "Sony T700", False, None, "Sony T700", ["http://img8.jpg"]),
    ]

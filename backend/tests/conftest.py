"""Pytest configuration for 估二手 backend tests."""
import asyncio
import sys
from pathlib import Path

import pytest

# Ensure backend root is on sys.path for test discovery
_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))


@pytest.fixture(scope="function")
def event_loop():
    """Create a fresh event loop per test function.

    Required for pytest-asyncio 0.26+ compatibility.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

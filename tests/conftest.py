"""
tests/conftest.py
=================
Reusable Pytest fixtures for EcoRecon AI enterprise testing.
"""

import asyncio
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.database.db import init_db, close_db
from app.main import create_application

# Force testing database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.core.config import get_settings
get_settings.cache_clear()

import app.database.db as db
db._engine = None
db._session_factory = None

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def test_app():
    """Provide a fresh instance of the FastAPI application with an initialized DB."""
    from app.core.config import get_settings
    get_settings.cache_clear()
    
    import app.database.db as db
    db._engine = None
    db._session_factory = None
    
    # Ensure a fresh in-memory DB per test
    await init_db()
    app = create_application()
    yield app
    await close_db()
    
    # Reset singletons to ensure the next test creates a fresh engine
    db._engine = None
    db._session_factory = None

@pytest_asyncio.fixture(scope="function")
async def test_client(test_app):
    """Provide an HTTPX AsyncClient for endpoint testing."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client

@pytest.fixture
def mock_declaration_payload():
    """Reusable mock declaration data."""
    return {
        "producer_id": "TEST-PRODUCER",
        "month": "2026-04",
        "declared_quantities_kg": {
            "rigid_plastic": 1000,
            "flexible_plastic": 500,
            "multilayer_plastic": 200,
        }
    }

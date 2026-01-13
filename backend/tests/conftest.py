import pytest
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import db


@pytest.fixture
def mock_db():
    """Mock database for testing without real DB connection."""
    mock = AsyncMock()
    mock.execute_query = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_llm_response():
    """Mock LLM service response."""
    return {
        "success": True,
        "sql": "SELECT category, SUM(total_amount) as total FROM sales GROUP BY category",
        "chart_type": "bar"
    }


@pytest.fixture
async def client(mock_db):
    """Async test client with mocked database."""
    # Replace db with mock
    app.state.db = mock_db

    # Mock the db.connect and db.disconnect
    original_connect = db.connect
    original_disconnect = db.disconnect
    db.connect = AsyncMock()
    db.disconnect = AsyncMock()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    # Restore
    db.connect = original_connect
    db.disconnect = original_disconnect

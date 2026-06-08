"""Pytest configuration and fixtures."""
import pytest


@pytest.fixture
def mock_user_id():
    """Mock user ID for testing."""
    return "test-user-123"

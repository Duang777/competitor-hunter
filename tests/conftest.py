"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Configure pytest-asyncio to use the event_loop fixture
pytest_plugins = ("pytest_asyncio",)


"""Pytest configuration and shared fixtures.

This module contains pytest configuration settings and shared fixtures
used across the test suite.
"""

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Configure asyncio as the async backend for tests.

    Returns:
        str: The async backend name to use for testing.
    """
    return "asyncio"

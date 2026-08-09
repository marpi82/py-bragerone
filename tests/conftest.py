"""Pytest configuration and shared fixtures.

This module contains pytest configuration settings and shared fixtures
used across the test suite.
"""

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the --run-live option for tests that require internet access."""
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run tests marked needs_internet (require network access)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip needs_internet tests unless --run-live or RUN_LIVE_TESTS=1 is given."""
    if config.getoption("--run-live") or os.environ.get("RUN_LIVE_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="requires internet; pass --run-live or set RUN_LIVE_TESTS=1")
    for item in items:
        if "needs_internet" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Configure asyncio as the async backend for tests.

    Returns:
        str: The async backend name to use for testing.
    """
    return "asyncio"

# mypy: disable-error-code=no-untyped-def
import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

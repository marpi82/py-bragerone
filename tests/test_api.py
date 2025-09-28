"""Tests for API client and gateway functionality.

This module contains tests for the main API client and gateway classes,
verifying their construction, public interface, and basic functionality.
"""

import pytest

from pybragerone import BragerOneApiClient
from pybragerone import BragerOneGateway


def test_gateway_is_exposed_on_top_level() -> None:
    """Test that BragerOneGateway is properly exported at the top level.

    Verifies that the BragerOneGateway class is available for import
    from the main package namespace and is properly exposed as a class type.
    """
    import pybragerone

    assert hasattr(pybragerone, "BragerOneGateway"), "BragerOneGateway is not exported in __all__"
    # optionally: verify that it's a class
    assert isinstance(BragerOneGateway, type)


@pytest.mark.asyncio
async def test_api_construct() -> None:
    """Test basic API client construction.

    Verifies that a new BragerOneApiClient instance can be created
    and has the expected initial state with no token.
    """
    a = BragerOneApiClient()
    assert a._token is None


@pytest.mark.asyncio
async def test_api_close() -> None:
    """Test API client cleanup functionality.

    Verifies that the API client can be properly closed and cleaned up,
    which should close any underlying HTTP session.
    """
    api = BragerOneApiClient()
    await api.close()  # Should not raise any exception

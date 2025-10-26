"""Tests for Permission model with auto-conversion."""

import pytest
from pydantic import BaseModel

from pybragerone.models.api import Permission


def test_permission_from_string() -> None:
    """Test creating Permission from string name."""
    perm = Permission(name="DISPLAY_MENU_OBJECTS")
    assert perm.name == "DISPLAY_MENU_OBJECTS"
    assert str(perm) == "DISPLAY_MENU_OBJECTS"


def test_permission_model_validate_string() -> None:
    """Test Permission.model_validate with string."""
    perm = Permission.model_validate("SUBMISSION_CREATE")
    assert perm.name == "SUBMISSION_CREATE"
    assert isinstance(perm, Permission)


def test_permission_model_validate_dict() -> None:
    """Test Permission.model_validate with dict."""
    perm = Permission.model_validate({"name": "DISPLAY_PARAMETER_LEVEL_1"})
    assert perm.name == "DISPLAY_PARAMETER_LEVEL_1"


def test_permission_model_validate_permission() -> None:
    """Test Permission.model_validate with Permission instance."""
    original = Permission(name="COMPANY_REGISTER")
    validated = Permission.model_validate(original)
    assert validated is original  # Should return same instance


def test_permission_equality() -> None:
    """Test Permission equality comparisons."""
    perm1 = Permission(name="DISPLAY_MENU_DHW")
    perm2 = Permission(name="DISPLAY_MENU_DHW")
    perm3 = Permission(name="DISPLAY_MENU_CIRCUITS")

    assert perm1 == perm2
    assert perm1 != perm3
    assert perm1 == "DISPLAY_MENU_DHW"  # Can compare with string
    assert perm1 != "DISPLAY_MENU_CIRCUITS"


def test_permission_hashable() -> None:
    """Test Permission can be used in sets."""
    perm1 = Permission(name="DISPLAY_MENU_ALERTS")
    perm2 = Permission(name="DISPLAY_MENU_ALERTS")
    perm3 = Permission(name="DISPLAY_MENU_ACTIVITY")

    perms = {perm1, perm2, perm3}
    assert len(perms) == 2  # perm1 and perm2 are same


def test_permission_in_list() -> None:
    """Test Permission in list - manual conversion needed."""
    # Pydantic doesn't auto-convert list items, so we convert manually
    strings = [
        "DISPLAY_MENU_CIRCUITS",
        "DISPLAY_MENU_CIRCUIT_CH0",
        "DISPLAY_PARAMETER_LEVEL_1",
    ]
    perms = [Permission.model_validate(s) for s in strings]

    assert len(perms) == 3
    assert all(isinstance(p, Permission) for p in perms)
    assert perms[0].name == "DISPLAY_MENU_CIRCUITS"
    assert perms[1].name == "DISPLAY_MENU_CIRCUIT_CH0"
    assert perms[2].name == "DISPLAY_PARAMETER_LEVEL_1"


def test_permission_invalid_type() -> None:
    """Test Permission.model_validate with invalid type."""
    with pytest.raises(ValueError, match="Cannot convert"):
        Permission.model_validate(123)

    with pytest.raises(ValueError, match="Cannot convert"):
        Permission.model_validate([])


def test_permission_list_from_api_response() -> None:
    """Test parsing permissions from API response format."""

    class ApiPermissions(BaseModel):
        """Simulated API response."""

        permissions: list[str]

    # Simulate API response with list of permission strings
    api_data = {
        "permissions": [
            "DISPLAY_MENU_OBJECTS",
            "DISPLAY_MENU_MODULES",
            "DISPLAY_MENU_ALERTS",
            "SUBMISSION_CREATE",
        ]
    }
    api_response = ApiPermissions.model_validate(api_data)

    # Convert to Permission objects
    perms = [Permission.model_validate(p) for p in api_response.permissions]

    assert len(perms) == 4
    assert all(isinstance(p, Permission) for p in perms)
    assert perms[0].name == "DISPLAY_MENU_OBJECTS"
    assert perms[3].name == "SUBMISSION_CREATE"

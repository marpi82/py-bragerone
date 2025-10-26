"""API endpoint URL builders for BragerOne REST client.

This module contains functions that build properly formatted URLs for various
BragerOne API endpoints, including authentication, user management, objects,
and modules. All URLs are URL-encoded for safety.
"""

from __future__ import annotations

from urllib.parse import quote, urlencode

from .constants import API_BASE

API_SYSTEM = f"{API_BASE}/system"
API_AUTH = f"{API_BASE}/auth"
API_USER = f"{API_BASE}/user"
API_OBJECTS = f"{API_BASE}/objects"
API_MODULES = f"{API_BASE}/modules"


def system_version_url(container: str = "BragerOne", platform: int = 0) -> str:
    """Get URL for system version endpoint.

    Args:
        container: The container name (default: "BragerOne").
        platform: The platform identifier (default: 0).

    Returns:
        URL for GET requests to fetch system version information.
    """
    params = {"container": container, "platform": platform}
    return f"{API_SYSTEM}/version?{urlencode(params)}"


def auth_user_url() -> str:
    """Get URL for user authentication endpoint.

    Returns:
        URL for POST requests to authenticate a user.
    """
    return f"{API_AUTH}/user"


def auth_revoke_url() -> str:
    """Get URL for token revocation endpoint.

    Returns:
        URL for POST requests to revoke authentication token.
    """
    return f"{API_AUTH}/revoke"


def user_url() -> str:
    """Get URL for user info endpoint.

    Returns:
        URL for GET requests to fetch current user information.
    """
    return f"{API_USER}"


def user_permissions_url() -> str:
    """Get URL for user permissions endpoint.

    Returns:
        URL for GET requests to fetch current user's permissions.
    """
    return f"{API_USER}/permissions"


def objects_url() -> str:
    """Get URL for objects collection endpoint.

    Returns:
        URL for GET requests to fetch all objects/groups.
    """
    return f"{API_OBJECTS}"


def object_url(object_id: int) -> str:
    """Get URL for specific object endpoint.

    Args:
        object_id: The ID of the object/group.

    Returns:
        URL for GET/POST requests to fetch or modify specific object.
    """
    return f"{API_OBJECTS}/{quote(str(object_id))}"


def object_permissions_url(object_id: int) -> str:
    """Get URL for object permissions endpoint.

    Args:
        object_id: The ID of the object/group.

    Returns:
        URL for GET requests to fetch permissions for specific object.
    """
    return f"{API_OBJECTS}/{quote(str(object_id))}/permissions"


def modules_url(object_id: int, page: int = 1, limit: int = 999) -> str:
    """Get URL for modules collection endpoint with pagination.

    Args:
        object_id: The ID of the object/group to get modules for.
        page: Page number for pagination (default: 1).
        limit: Number of items per page (default: 999).

    Returns:
        URL for GET requests to fetch modules with query parameters.
    """
    params = {"page": page, "limit": limit, "group_id": object_id}
    return f"{API_MODULES}?{urlencode(params)}"


def modules_connect_url() -> str:
    """Get URL for modules connection endpoint.

    Returns:
        URL for WebSocket connection to modules.
    """
    return f"{API_MODULES}/connect"


def modules_parameters_url() -> str:
    """Get URL for all modules parameters endpoint.

    Returns:
        URL for GET requests to fetch parameters for all modules.
    """
    return f"{API_MODULES}/parameters"


def modules_activity_quantity_url() -> str:
    """Get URL for modules activity quantity endpoint.

    Returns:
        URL for GET requests to fetch activity quantity statistics.
    """
    return f"{API_MODULES}/activity/quantity"


def module_url(module_id: str) -> str:
    """Get URL for specific module endpoint.

    Args:
        module_id: The ID of the module.

    Returns:
        URL for GET/POST requests to fetch or modify specific module.
    """
    return f"{API_MODULES}/{quote(module_id)}"


def module_card_url(module_id: str) -> str:
    """Get URL for module card data endpoint.

    Args:
        module_id: The ID of the module.

    Returns:
        URL for GET requests to fetch module card/dashboard data.
    """
    return f"{API_MODULES}/{quote(module_id)}/card"

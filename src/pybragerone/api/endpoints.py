"""API endpoint URL builders for BragerOne REST client.

This module contains functions that build properly formatted URLs for various
BragerOne API endpoints, including authentication, user management, objects,
and modules. All URLs are URL-encoded for safety.
"""

from __future__ import annotations

from urllib.parse import quote, urlencode

from .constants import API_BASE


def _base(api_base: str) -> str:
    return api_base.rstrip("/")


def system_version_url(*, api_base: str = API_BASE, container: str = "BragerOne", platform: int = 0) -> str:
    """Get URL for system version endpoint.

    Args:
        api_base: Base URL for the REST API.
        container: The container name (default: "BragerOne").
        platform: The platform identifier (default: 0).

    Returns:
        URL for GET requests to fetch system version information.
    """
    params = {"container": container, "platform": platform}
    return f"{_base(api_base)}/system/version?{urlencode(params)}"


def auth_user_url(*, api_base: str = API_BASE) -> str:
    """Get URL for user authentication endpoint.

    Returns:
        URL for POST requests to authenticate a user.
    """
    return f"{_base(api_base)}/auth/user"


def auth_revoke_url(*, api_base: str = API_BASE) -> str:
    """Get URL for token revocation endpoint.

    Returns:
        URL for POST requests to revoke authentication token.
    """
    return f"{_base(api_base)}/auth/revoke"


def user_url(*, api_base: str = API_BASE) -> str:
    """Get URL for user info endpoint.

    Returns:
        URL for GET requests to fetch current user information.
    """
    return f"{_base(api_base)}/user"


def user_permissions_url(*, api_base: str = API_BASE) -> str:
    """Get URL for user permissions endpoint.

    Returns:
        URL for GET requests to fetch current user's permissions.
    """
    return f"{_base(api_base)}/user/permissions"


def objects_url(*, api_base: str = API_BASE) -> str:
    """Get URL for objects collection endpoint.

    Returns:
        URL for GET requests to fetch all objects/groups.
    """
    return f"{_base(api_base)}/objects"


def object_url(object_id: int, *, api_base: str = API_BASE) -> str:
    """Get URL for specific object endpoint.

    Args:
        object_id: The ID of the object/group.
        api_base: Base URL for the REST API.

    Returns:
        URL for GET/POST requests to fetch or modify specific object.
    """
    return f"{_base(api_base)}/objects/{quote(str(object_id))}"


def object_permissions_url(object_id: int, *, api_base: str = API_BASE) -> str:
    """Get URL for object permissions endpoint.

    Args:
        object_id: The ID of the object/group.
        api_base: Base URL for the REST API.

    Returns:
        URL for GET requests to fetch permissions for specific object.
    """
    return f"{_base(api_base)}/objects/{quote(str(object_id))}/permissions"


def modules_url(object_id: int, page: int = 1, limit: int = 999, *, api_base: str = API_BASE) -> str:
    """Get URL for modules collection endpoint with pagination.

    Args:
        object_id: The ID of the object/group to get modules for.
        page: Page number for pagination (default: 1).
        limit: Number of items per page (default: 999).
        api_base: Base URL for the REST API.

    Returns:
        URL for GET requests to fetch modules with query parameters.
    """
    params = {"page": page, "limit": limit, "group_id": object_id}
    return f"{_base(api_base)}/modules?{urlencode(params)}"


def modules_connect_url(*, api_base: str = API_BASE) -> str:
    """Get URL for modules connection endpoint.

    Returns:
        URL for WebSocket connection to modules.
    """
    return f"{_base(api_base)}/modules/connect"


def modules_parameters_url(*, api_base: str = API_BASE) -> str:
    """Get URL for all modules parameters endpoint.

    Returns:
        URL for GET requests to fetch parameters for all modules.
    """
    return f"{_base(api_base)}/modules/parameters"


def modules_activity_quantity_url(*, api_base: str = API_BASE) -> str:
    """Get URL for modules activity quantity endpoint.

    Returns:
        URL for GET requests to fetch activity quantity statistics.
    """
    return f"{_base(api_base)}/modules/activity/quantity"


def module_url(module_id: str, *, api_base: str = API_BASE) -> str:
    """Get URL for specific module endpoint.

    Args:
        module_id: The ID of the module.
        api_base: Base URL for the REST API.

    Returns:
        URL for GET/POST requests to fetch or modify specific module.
    """
    return f"{_base(api_base)}/modules/{quote(module_id)}"


def module_card_url(module_id: str, *, api_base: str = API_BASE) -> str:
    """Get URL for module card data endpoint.

    Args:
        module_id: The ID of the module.
        api_base: Base URL for the REST API.

    Returns:
        URL for GET requests to fetch module card/dashboard data.
    """
    return f"{_base(api_base)}/modules/{quote(module_id)}/card"


def module_command_raw_url(*, api_base: str = API_BASE) -> str:
    """Get URL for raw module command endpoint.

    Returns:
        URL for POST requests to dispatch symbolic commands to module firmware.
    """
    return f"{_base(api_base)}/module/command/raw"


def module_command_url(*, api_base: str = API_BASE) -> str:
    """Get URL for module command endpoint.

    Returns:
        URL for POST requests to write parameter-like command payloads.
    """
    return f"{_base(api_base)}/module/command"

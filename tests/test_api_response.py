"""Tests for ApiResponse generic wrapper."""

from datetime import datetime

from pybragerone.models.api import ApiResponse, User


def test_api_response_success() -> None:
    """Test ApiResponse with successful status."""
    user = User(
        id=1,
        name="Test User",
        email="test@example.com",
        language="en",
        allow_email_type_informations=True,
        allow_email_type_alarms=True,
        allow_email_type_marketing=False,
        allow_email_type_warnings=True,
        activated_at=datetime(2025, 1, 1),
        show_rate_us_modal=False,
    )

    response: ApiResponse[User] = ApiResponse(status=200, data=user)

    assert response.is_success
    assert not response.is_error
    assert not response.is_client_error
    assert not response.is_server_error
    assert response.data == user
    assert response.status == 200


def test_api_response_client_error() -> None:
    """Test ApiResponse with 4xx client error."""
    response: ApiResponse[dict[str, str]] = ApiResponse(
        status=404,
        data={"message": "Not found"},
    )

    assert not response.is_success
    assert response.is_error
    assert response.is_client_error
    assert not response.is_server_error
    assert response.status == 404
    assert response.data["message"] == "Not found"


def test_api_response_server_error() -> None:
    """Test ApiResponse with 5xx server error."""
    response: ApiResponse[dict[str, str]] = ApiResponse(
        status=500,
        data={"message": "Internal server error"},
    )

    assert not response.is_success
    assert response.is_error
    assert not response.is_client_error
    assert response.is_server_error
    assert response.status == 500


def test_api_response_list() -> None:
    """Test ApiResponse with list data."""
    users = [
        User(
            id=i,
            name=f"User{i}",
            email=f"user{i}@example.com",
            language="en",
            allow_email_type_informations=True,
            allow_email_type_alarms=True,
            allow_email_type_marketing=False,
            allow_email_type_warnings=True,
            activated_at=datetime(2025, 1, 1),
            show_rate_us_modal=False,
        )
        for i in range(3)
    ]

    response: ApiResponse[list[User]] = ApiResponse(status=200, data=users)

    assert response.is_success
    assert len(response.data) == 3
    assert all(isinstance(u, User) for u in response.data)


def test_api_response_with_headers() -> None:
    """Test ApiResponse with headers."""
    response: ApiResponse[str] = ApiResponse(
        status=200,
        data="OK",
        headers={"Content-Type": "text/plain", "X-Request-ID": "12345"},
    )

    assert response.is_success
    assert response.headers is not None
    assert response.headers["Content-Type"] == "text/plain"
    assert response.headers["X-Request-ID"] == "12345"

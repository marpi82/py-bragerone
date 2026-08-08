"""Property-based fuzz tests for public parsing / validation helpers."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from pybragerone.cli import _parse_cli_value
from pybragerone.models.api.common import Permission
from pybragerone.models.token import Token


@given(st.text(min_size=0, max_size=64))
@settings(max_examples=50, deadline=None)
def test_permission_from_string_never_crashes(name: str) -> None:
    """Permission.model_validate(str) should always return a Permission."""
    perm = Permission.model_validate(name)
    assert isinstance(perm, Permission)
    assert perm.name == name


@given(
    st.one_of(
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.none(),
        st.lists(st.integers(), max_size=3),
    )
)
@settings(max_examples=40, deadline=None)
def test_permission_rejects_unsupported_types(obj: Any) -> None:
    """Unsupported types should raise ValueError, not crash unexpectedly."""
    with pytest.raises(ValueError, match="Cannot convert"):
        Permission.model_validate(obj)


@given(
    st.fixed_dictionaries(
        {
            "accessToken": st.text(max_size=64),
        },
        optional={
            "refreshToken": st.one_of(st.none(), st.text(max_size=64)),
            "type": st.sampled_from(["bearer", "Bearer", "token"]),
            "expiresAt": st.one_of(
                st.none(),
                st.from_regex(r"202[0-9]-0[1-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z", fullmatch=True),
                st.text(max_size=32),
            ),
            "user": st.one_of(
                st.none(),
                st.fixed_dictionaries({}, optional={"id": st.one_of(st.none(), st.integers(min_value=0))}),
                st.text(max_size=16),
            ),
            "objects": st.one_of(
                st.none(), st.lists(st.dictionaries(st.text(max_size=8), st.integers(), max_size=2), max_size=3)
            ),
        },
    )
)
@settings(max_examples=50, deadline=None)
def test_token_from_login_payload_is_resilient(payload: dict[str, Any]) -> None:
    """Token.from_login_payload should tolerate messy API-shaped dicts."""
    token = Token.from_login_payload(payload)
    assert isinstance(token, Token)
    assert token.access_token is None or isinstance(token.access_token, str)


@given(st.text(max_size=128))
@settings(max_examples=60, deadline=None)
def test_parse_cli_value_never_crashes(raw: str) -> None:
    """CLI value parsing should always return something without raising."""
    result = _parse_cli_value(raw)
    assert result is None or isinstance(result, (bool, int, float, str, list, dict))


@given(st.dictionaries(st.text(max_size=16), st.text(max_size=32), max_size=5))
@settings(max_examples=30, deadline=None)
def test_permission_from_dict_shapes(data: dict[str, str]) -> None:
    """Dict-shaped Permission input either validates or raises ValidationError/ValueError."""
    try:
        perm = Permission.model_validate(data)
    except (ValidationError, ValueError, TypeError):
        return
    assert isinstance(perm, Permission)
    assert isinstance(perm.name, str)

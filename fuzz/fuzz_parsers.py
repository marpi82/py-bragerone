"""Atheris harness for OpenSSF Scorecard Fuzzing detection.

Scorecard detects Python fuzzing via ``import atheris``. This harness also
exercises the same resilient parsers covered by Hypothesis property tests.

Run (optional, requires the ``fuzz`` dependency group)::

    uv run --group fuzz python fuzz/fuzz_parsers.py
"""

from __future__ import annotations

import contextlib
import sys

import atheris
from pydantic import ValidationError

with atheris.instrument_imports():
    from pybragerone.cli import _parse_cli_value
    from pybragerone.models.api.common import Permission
    from pybragerone.models.token import Token

# Expected validation / typing failures only — unexpected errors must reach Atheris.
_EXPECTED = (ValidationError, ValueError, TypeError)


def TestOneInput(data: bytes) -> None:
    """Fuzz Permission / Token / CLI parsers with arbitrary bytes."""
    text = data.decode("utf-8", errors="ignore")
    with contextlib.suppress(*_EXPECTED):
        Permission.model_validate(text)

    with contextlib.suppress(*_EXPECTED):
        Permission.model_validate({"name": text[:64]})

    with contextlib.suppress(*_EXPECTED):
        Token.from_login_payload(
            {
                "accessToken": text[:128],
                "refreshToken": text[:64],
                "expiresAt": text[:32],
                "user": {"id": len(data)},
                "objects": [],
            }
        )

    # _parse_cli_value is intentionally total: it should not raise on any str.
    _parse_cli_value(text[:256])


def main() -> None:
    """Entry point for continuous / local Atheris runs."""
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()

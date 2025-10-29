"""Tests for package version validation.

This module contains tests to ensure the package version string
is properly formatted and parseable according to PEP 440.
"""

from importlib.metadata import PackageNotFoundError, version

from packaging.version import Version

PKG = "py-bragerone"


def test_version_string_is_parseable() -> None:
    """Test that the package version string is parseable according to PEP 440.

    Verifies that the version can be retrieved from package metadata
    or falls back to the module's __version__ attribute, and that
    the version string conforms to PEP 440 format.
    """
    try:
        v = version(PKG)
    except PackageNotFoundError:
        # fallback: import without installation — version from __init__.py
        import pybragerone as m

        v = getattr(m, "__version__", "2025.0.0.dev0")
    # parseable according to PEP 440 (e.g. 0.3.0.dev1+gabcdef)
    Version(v)  # will not raise exception if valid

"""Tests for resolving labels from the `app` translations namespace.

The official BragerOne app stores some UI strings in the `app` language bundle
(e.g. one.boilerStatus table, one.devicePumpStatus field label).

We resolve those dynamically using the `index-*.js` language mapping, rather
than hardcoding strings.
"""

from __future__ import annotations

from pybragerone.models.catalog import LiveAssetsCatalog


def test_lookup_app_one_paths() -> None:
    """Resolve dotted paths in the `app` translation bundle."""
    translations = {
        "one": {
            "devicePumpStatus": "Status pompy",
            "boilerStatus": {0: "Stop", 1: "Praca", 14: "Nadzór", "name": "Status kotła"},
        }
    }

    assert LiveAssetsCatalog._lookup_path(translations, "app.one.devicePumpStatus") == "Status pompy"
    assert LiveAssetsCatalog._lookup_path(translations, "one.devicePumpStatus") == "Status pompy"
    assert LiveAssetsCatalog._lookup_path(translations, "app.one.boilerStatus.name") == "Status kotła"
    assert LiveAssetsCatalog._lookup_path(translations, "app.one.boilerStatus.14") is None

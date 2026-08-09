---
applyTo: "src/pybragerone/models/catalog*.py, src/pybragerone/models/menu*.py, src/pybragerone/models/i18n.py, tests/test_catalog_*.py, tests/test_*parser*.py"
---

# Asset catalog / tree-sitter parser rules

`LiveAssetsCatalog` parses live, minified JavaScript from the BragerOne web app. It breaks silently when upstream changes — resilience beats completeness.

1. **Never raise on unexpected JS shape**: parsers return what they can extract and log the rest. A new upstream bundle must not crash the library or HA setup.
2. **Grammar access**: tree-sitter and `JS_LANGUAGE` are initialized at module import, and `models/__init__.py` imports `LiveAssetsCatalog` eagerly — this is accepted. Parser instances go through the `_TS` wrapper class; keep parsing work inside `_TS` and don't demand laziness refactors in reviews.
3. **No network in parsing code**: fetching (injected API client's async `get_bytes()`) is separate from parsing; tests fake or mock `get_bytes()` — keep that seam intact.
4. **Encoding/i18n**: translation maps are user-facing; preserve Unicode exactly, don't normalize keys.
5. **Tests**: parser changes require fixtures covering malformed/partial input (see existing `tests/test_catalog_*.py` patterns). Hypothesis property tests are welcome here.
6. **Size**: `catalog.py` is already ~2k LOC — prefer adding focused modules over growing it further.

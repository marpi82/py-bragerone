# Asset catalog / pure JS parser rules

When reviewing or changing `src/pybragerone/models/catalog.py` (LiveAssetsCatalog, `_Parser`, i18n/units/ParamMap extraction):

1. **Never raise on unexpected JS shape from public catalog operations**: parsers return what they can extract and log the rest. A new upstream bundle must not crash the library or HA setup. Internal helpers may raise on malformed shapes when the calling public method catches, logs, and degrades to `None`/partial data (e.g. `_parse_language_config_from_js()` raises; `get_language_config()` converts that to `None`).
2. **Parser scope**: keep parsing work inside the pure-Python `_Parser` / `collect_bindings` / `extract_root_*` helpers — no `eval`, no native grammars.

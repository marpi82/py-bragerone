---

### `CHANGELOG.md`

# Changelog

All notable changes to this project will be documented in this file.

## [0.2.6] - 2025-09-12
### Added
- **Live label/unit fetching** from frontend bundles via `AssetClient` (`index-*.js`, language chunks, `PARAM_*.js`).
- `LabelFetcher` now bootstraps labels/units in-memory (no local files) and exposes `ParamCatalog`.
- `ParamCatalog` binds units using current `uN` values from snapshot and formats enums/units for CLI/HA.
- Tests for asset fetching and Unicode handling (diacritics).
- GitHub Actions: CI (lint+tests) and optional Release/Docs workflows.

### Changed
- CLI logs show **human-friendly** values with units/enums right after initial snapshot.
- Refactor of parsing utilities in `jsparse.py` (robust JSON-ish normalization, alias parsing, Unicode safety).
- `Gateway.initial_snapshot(prefetch_assets: bool = False)` to optionally fetch assets before binding.

### Fixed
- Unicode decoding issues (e.g. `kotÅ‚a` → `kotła`) in parameter labels and unit enums.
- Safer parsing of `PARAM_*.js` (handles `icon`, `status`, `componentType`, `raw`, conditional blocks).

## [0.2.5] - 2025-09-09
### Added
- Labels cache extended: support for unit IDs, plain unit labels, and enum maps.
- CLI `labels` subcommands:
  - `set-param`, `set-alias`, `set-param-unit`, `set-unit-label`, `show`.
- Pretty-print values with unit or enum label in snapshot and WS changes.
- Task events (`app:module:task:*`) handled and logged in WS client.

### Changed
- CLI refactored: now has subcommands (`run`, `labels`) instead of only flags.
- `Gateway` split into `login()` + `pick_modules()` (explicit module selection).
- Ctrl-C handling is graceful, without traceback.

### Fixed
- Stable WS disconnect/close.
- Clean shutdown sequence (`Gateway.close()` closes WS + API).
- CancelledError on exit suppressed.

## [0.2.0] - 2025-09-08
### Added
- Split into modules: `api.py`, `ws.py`, `gateway.py`, `labels.py`, `const.py`.
- CLI entrypoint `bragerone` with `--email/--password/--object-id/--lang/--log-level`.
- Initial snapshot fetch and WS subscription (parameters & activity).
- Human-readable change logs with previous → new value.

### Changed
- Refactor: Gateway orchestrates REST + WS; API handles REST; WS handles socket wiring; labels kept standalone.
- Logging cleanup and levels clarified (INFO/DEBUG).

### Fixed
- Stable WS connect (namespace `/ws`, correct socket.io path, auth header).
- Robust modules listing and device selection.

## [0.1.0] - 2025-09-01
### Added
- Initial working version (REST + WS combined).

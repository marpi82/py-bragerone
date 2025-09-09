---

### `CHANGELOG.md`

```markdown
# Changelog

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

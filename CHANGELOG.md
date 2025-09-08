---

## `CHANGELOG.md`

```markdown
# Changelog

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

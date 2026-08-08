# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Calendar Versioning](https://calver.org/) (`YYYY.M.PATCH`).

## [Unreleased]

### Security

- Harden GitHub Actions workflows (pin actions by SHA, least-privilege permissions).
- Trigger releases from tag pushes instead of `workflow_run` checkout.
- Add Hypothesis property-based tests and an Atheris fuzz harness for parsers.

### Changed

- Normalize `asyncio` imports in the gateway module for CodeQL maintainability.

## [2026.4.5] - 2026-04-14

### Fixed

- Support numeric `deviceMenu` route chunks in index parsing.
- Apply menu parser resilience fixes from review feedback.

### Changed

- Dependency lockfile maintenance.

## [2026.4.4] - 2026-04-10

### Changed

- Maintenance and dependency updates for the 2026.4.4 release train.

## [2026.4.3] - 2026-04-08

### Changed

- Maintenance and dependency updates for the 2026.4.3 release train.

## [2026.4.2] - 2026-04-06

### Changed

- Maintenance and dependency updates for the 2026.4.2 release train.

## [2026.4.1] - 2026-04-06

### Changed

- Maintenance and dependency updates for the 2026.4.1 release train.

## [2026.2.0b1] - 2026-02-26

### Changed

- Pre-release updates toward the 2026.2 line.

## Earlier releases

See [GitHub Releases](https://github.com/marpi82/py-bragerone/releases) for older tags and artifacts.

[Unreleased]: https://github.com/marpi82/py-bragerone/compare/2026.4.5...HEAD
[2026.4.5]: https://github.com/marpi82/py-bragerone/releases/tag/2026.4.5
[2026.4.4]: https://github.com/marpi82/py-bragerone/releases/tag/2026.4.4
[2026.4.3]: https://github.com/marpi82/py-bragerone/releases/tag/2026.4.3
[2026.4.2]: https://github.com/marpi82/py-bragerone/releases/tag/2026.4.2
[2026.4.1]: https://github.com/marpi82/py-bragerone/releases/tag/2026.4.1
[2026.2.0b1]: https://github.com/marpi82/py-bragerone/releases/tag/2026.2.0b1

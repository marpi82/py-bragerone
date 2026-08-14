# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Calendar Versioning](https://calver.org/) (`YYYY.M.PATCH`).

## [Unreleased]

### Fixed

- Parse quoted object keys in the live (obfuscated) language-config object so
  ``list_language_config()`` works against the current ``index-*.js`` bundle.
- Resolve i18n chunks whose Vite hash contains or ends with a hyphen
  (``info-Bpu026-3.js``, ``tariff-Db9Vj8s-.js``).
- Warn when the units descriptor table, an i18n namespace, or leftover ``\\x`` /
  ``\\u`` sequences indicate that upstream assets changed shape.
- Make the scheduled upstream-assets watch fail when language config, the
  descriptor table, or the ``units`` namespace parse empty.
- Apply the unit-66 HH:MM formatter to the obfuscated live spelling
  (``Math['floor']``, ``['padStart'](0x2, ...)``), not only the readable
  ``e === 0`` special case.
- Parse shift-only numeric transforms such as unit 47 (``x => x - 127`` /
  ``_0xac50fa=>_0xac50fa-0x7f``).
- Route the string-based catalog JS-value helpers through the bytes parsers so
  quoted keys and hex literals cannot drift between the two copies.

## [2026.8.1] - 2026-08-08

### Security

- Harden GitHub Actions workflows (pin actions by SHA, least-privilege permissions).
- Trigger releases from tag pushes instead of `workflow_run` checkout.
- Add Hypothesis property-based tests and an Atheris fuzz harness for parsers.
- Install `uv` in setup scripts from a version- and SHA256-pinned GitHub release
  (no `curl | sh` / unpinned `pip install`); verify the GitHub CLI apt keyring digest.
- Add OpenSSF Best Practices badge and supporting project docs (`CHANGELOG`,
  `CONTRIBUTING`, `CODE_OF_CONDUCT`, `CODEOWNERS`).

### Changed

- Normalize `asyncio` imports in the gateway module for CodeQL maintainability.
- Tighten supported Python range to `>=3.13.2,<3.15`.

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

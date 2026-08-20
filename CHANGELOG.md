# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Calendar Versioning](https://calver.org/) (`YYYY.M.PATCH`).

## [Unreleased]

### Changed

- Publish pre-release tags (``aN`` / ``bN`` / ``rcN``) to **PyPI** instead of
  TestPyPI, so Home Assistant and other consumers can pin
  ``py-bragerone==YYYY.M.NrcN`` from the primary index. GitHub Releases for those
  tags are marked ``prerelease=true``.

### Added

- Expose library↔cloud Socket.IO health as :class:`CloudSessionConnectivity` via
  ``BragerOneGateway.on_cloud_session`` (distinct from module↔cloud
  ``connectedAt`` / :class:`ModuleConnectivity`). Session drops stay detectable
  and self-heal; module offline remains observe-only (#319).

### Fixed

- Multi-register parameters (e.g. ``PARAM_P4_59`` "Czas pracy podajnika") whose
  SPA mapping addresses more than one register as `` {group, number, use[,
  convert, times]}`` selectors were misclassified as STATUS computed rules and
  fell back to reading only the primary register, yielding a signed int16 word
  (``-27473``) instead of the web UI's composed unsigned value (``38063``).
  ``ParamResolver`` now tells address-selector lists apart from STATUS
  ``if``/``elseif`` rule lists and exposes the composition as the public
  ``ParamResolver.compose_mapping_register_value()`` classmethod (#327).
- Engine.IO abort (aiohttp ``WSMsgType.CLOSED``) can skip the Socket.IO
  ``disconnect`` callback and deadlock leftover ``disconnect()``. The supervisor
  now notifies ``CloudSessionConnectivity(up=False)`` immediately, bounds
  transport teardown, and replaces the Socket.IO client when disconnect hangs so
  reconnect and REST-prime can proceed.
- REST-prime when no ``ParamUpdate`` has been published for 180s even if Socket.IO
  still reports up (zombie session). ``BragerOneGateway.last_param_update_age_s()``
  exposes the gap for Home Assistant diagnostics.

- Tolerate degraded ``GET /v1/modules`` rows (empty ``gateway``, ``connectedAt:
  null``) so connectivity refresh can mark the module offline instead of skipping
  the listing and leaving Home Assistant on a stale **Connected** state (#319).
- Reset leftover Engine.IO sessions after a connect timeout so the supervisor
  does not retry ``connect()`` on a half-open client (#319).
- REST-prime parameters from the connectivity poll while the Socket.IO session
  is down, so push consumers keep receiving snapshots until WS reconnects (#319).

## [2026.8.8] - 2026-08-15

### Fixed

- Keep channel index ``0`` when formatting command-rule / status targets
  (``number: 0`` was dropped by falsy ``number or index`` coalescing, so bit-gated
  switches such as boiler start/stop lost their ``targets`` and could not match) (#315).

## [2026.8.7] - 2026-08-15

### Added

- Expose per-module cloud connectivity on ``BragerOneGateway``: REST ``connectedAt``
  priming, Socket.IO ``app:module:connection:status:changed``, background
  ``get_modules`` poll/diff, ``on_module_connectivity`` / ``module_online`` /
  ``module_connected_at``, and SPA ``module.connection`` i18n helpers for Home
  Assistant connectivity entities (#312).

### Fixed

- Align UI / parameter visibility with the manufacturer SPA
  (``isParameterVisible`` + side-menu gating). Recover index-inline
  ``ParameterStatus['INVISIBLE']`` leftovers, match ``INVISIBLE`` /
  ``DEVICE_AVAILABLE`` case-insensitively, and honor installer denylist /
  ancestor gating so ``web_ui_only`` can exclude service panels (#310, closed
  #307).

### Changed

- Document Stable status and that GitHub Pages defaults to ``/latest/`` rather
  than ``/dev/`` (#308).

## [2026.8.6] - 2026-08-14

### Fixed

- Map unit option keys such as ``BoilerState['STOP']`` to cleaned computed tags
  (``STOP``) when resolving STATUS value labels, then follow i18n tokens like
  ``app.one.burnerState.0``. Without this, ``STATUS_P5_0`` kept ``value_label=None``
  and Home Assistant showed raw ``STOP`` (and after first-letter lowercasing,
  ``sTOP``) instead of ``Stop`` / ``Praca`` (#301).
- Reject ``wn.<digits>`` strings in ``I18nResolver.normalize_unit_value`` so
  bootstrap probes like ``wn.9998`` are not treated as display units (#301).
- Evaluate index-inline STATUS rule leftovers such as ``ClauseOperation['equalTo']``
  and ``DiodeState['OFF']`` / ``ThreeWayValveState['DISABLED']``. Dedicated
  ``STATUS_*.js`` assets already emit cleaned ``equalTo`` / ``ON`` tokens, so those
  kept working while six inline statuses (``STATUS_P5_10/11/12/19/20/21``) resolved
  to ``None`` and were dropped at HA bootstrap as ``no_display_value`` (#302).

## [2026.8.5] - 2026-08-14

### Fixed

- Evaluate nullish coalescing, ``void`` / ``undefined``, equality and ternary
  expressions in parameter factory builders so optional ``name`` defaults expand to
  ``parameters.PARAM_*`` tokens. Without this, factory-built classic params kept
  leftover source such as ``_0x…??'parameters.PARAM_'+n`` and Home Assistant entity
  labels stayed raw ``PARAM_10`` despite i18n entries (#298).
- Include bare ``MAINMENU_*`` / ``MENUSERWIS_*`` / ``MENU_*`` menu routes as
  all-panels candidates. Those routes carry classic ``PARAM_*`` tokens on live
  device menus; treating only ``modules.menu.*`` as module-item panels dropped
  bootstrap candidates from 466 to 292 and cut a fresh install to ~32 entities
  instead of ~100 (#299).

## [2026.8.4] - 2026-08-14

### Fixed

- Evaluate statement-block parameter factory builders such as
  ``basicParameterBuilder_P*({…})`` in ``index-*.js``. Upstream replaced inline
  parameter object literals with these calls; without statement-block bodies,
  destructuring defaults, object spread and string ``+``, a fresh bootstrap on a
  live device kept only 17 of ~100 entity descriptors (#295, closed #293).
- Resolve bare ``MAINMENU_*`` / ``MENUSERWIS_*`` / ``MENU_*`` panel-title tokens
  from their dedicated string-default i18n namespaces (and the ``menu`` pack).
  Parent segments such as ``MAINMENU_MENU_TERMOSTATU`` used to leak into Home
  Assistant entity names built as ``"{panel_path} - {label}"`` while child
  ``routes.modules.menu.*`` segments already translated (#296, closed #294).

## [2026.8.3] - 2026-08-14

### Fixed

- Decode JavaScript escape sequences (``\xNN``, ``\uNNNN``, ``\u{...}``, surrogate
  pairs and the simple forms) when parsing web-app assets. Escapes survived verbatim,
  so a space inside a label rendered as a literal ``\x20``; 1303 of 1339 parameter
  labels were affected on the live bundle.
- Parse the numeric literal forms the obfuscated bundle actually emits — radix
  prefixes (``0x9``, ``0o17``, ``0b1010``), digit separators (``1_000``) and the
  BigInt marker (``10n``). The hex-keyed unit descriptor table used to parse to zero
  entries, losing every unit resolved through indirection (kW among them).
- Parse quoted object keys in the live (obfuscated) language-config object so
  ``list_language_config()`` works against the current ``index-*.js`` bundle.
- Resolve i18n chunks whose Vite hash contains or ends with a hyphen
  (``info-Bpu026-3.js``, ``tariff-Db9Vj8s-.js``).
- Warn when the units descriptor table, an i18n namespace, or leftover ``\\xNN`` /
  ``\\uNNNN`` / ``\\u{...}`` sequences indicate that upstream assets changed shape.
- Make the scheduled upstream-assets watch fail when language config, the
  descriptor table, or the ``units`` namespace parse empty.
- Apply the unit-66 HH:MM formatter to the obfuscated live spelling
  (``Math['floor']``, ``['padStart'](0x2, ...)``), not only the readable
  ``e === 0`` special case.
- Parse shift-only numeric transforms such as unit 47 (``x => x - 127`` /
  ``_0xac50fa=>_0xac50fa-0x7f``).
- Route the string-based catalog JS-value helpers through the bytes parsers so
  quoted keys and hex literals cannot drift between the two copies.
- Collapse ``_0x…['DISPLAY_*']`` / ``_0x…['equalTo']`` to the public name, but keep
  ``arr['map']`` and ``Math['floor']`` as leftover source for menu ``array['map']``
  unwrapping.
- Evaluate ``['PARAM_45', …]['map'](x => ({…}))`` in menu chunks instead of leaving
  the call as source text. ``MenuProcessor`` used to iterate that string character by
  character, so ``get_module_menu()`` raised thousands of validation errors for
  ``deviceMenu`` 153 and 2190 even with ``permissions=None``.
- Recover ``PARAM_*`` / ``STATUS_*`` tokens from leftover ``array['map']`` source in
  either quote style, and never treat other quoted upper-case literals as parameters.
- Collapse obfuscated helper calls only for ``_0x…(READ|WRITE|STATUS, PARAM_*|STATUS_*)``,
  so a readable ``foo('WRITE', 'PARAM_45')`` keeps its semantics.
- Resolve computed property names (``{[_0x4d7e32['INVISIBLE']]: …}``) to the public
  key, so ``PARAM_*`` status conditions are addressable.
- Normalize the minified boolean spellings ``![]`` and ``!![]`` alongside ``!0`` /
  ``!1``, and accept ``useComponent`` as an alias for ``componentType``.
- Make the upstream-assets watch fail when a sampled ``PARAM_*`` map still carries
  ``_0x…['…']`` text in its component type, status keys, or command operations —
  previously any parsed object counted as success.

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

[Unreleased]: https://github.com/marpi82/py-bragerone/compare/2026.8.8...HEAD
[2026.8.8]: https://github.com/marpi82/py-bragerone/releases/tag/2026.8.8
[2026.8.7]: https://github.com/marpi82/py-bragerone/releases/tag/2026.8.7
[2026.8.6]: https://github.com/marpi82/py-bragerone/releases/tag/2026.8.6
[2026.8.5]: https://github.com/marpi82/py-bragerone/releases/tag/2026.8.5
[2026.8.4]: https://github.com/marpi82/py-bragerone/releases/tag/2026.8.4
[2026.8.3]: https://github.com/marpi82/py-bragerone/releases/tag/2026.8.3
[2026.8.1]: https://github.com/marpi82/py-bragerone/releases/tag/2026.8.1
[2026.4.5]: https://github.com/marpi82/py-bragerone/releases/tag/2026.4.5
[2026.4.4]: https://github.com/marpi82/py-bragerone/releases/tag/2026.4.4
[2026.4.3]: https://github.com/marpi82/py-bragerone/releases/tag/2026.4.3
[2026.4.2]: https://github.com/marpi82/py-bragerone/releases/tag/2026.4.2
[2026.4.1]: https://github.com/marpi82/py-bragerone/releases/tag/2026.4.1
[2026.2.0b1]: https://github.com/marpi82/py-bragerone/releases/tag/2026.2.0b1

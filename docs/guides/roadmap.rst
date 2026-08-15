Roadmap
=======

Direction for the next ~12 months. This is a statement of intent, not a
commitment — items may move or drop as upstream (BragerOne web app,
Home Assistant) evolves.

Planned
-------

- **Keep the public API stable** (``BragerOneApiClient``, ``BragerOneGateway``,
  ``ParamStore``): prefer additive changes; call out breaking changes in the
  changelog and release notes.
- **Keep pace with upstream assets**: the live catalog parser depends on
  BragerOne's web-app bundles; ongoing work is resilience to upstream changes
  (tree-sitter grammars, menu/i18n shapes).
- **Home Assistant integration parity**: extend ``ha-bragerone`` coverage of
  the parameter catalog as new modules/panels are discovered.
- **Release cadence**: CalVer stable releases as changes land; security fixes
  as soon as practical.

Not planned
-----------

- Official ``climate`` platform logic in the library (belongs to the HA
  integration layer).
- Support for Python < 3.13.
- Local (LAN) protocol reverse-engineering — the library targets the
  BragerOne cloud API only.

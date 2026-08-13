# Captured BragerOne JS assets (parse only)

Drop minified files saved from the web app, then:

```bash
uv run --group test pytest tests/test_catalog_captured_assets.py -q
```

This is **tree-sitter parsing of local bytes**. No login, no Socket.IO, no
`get_module_menu()`, no permission filtering, no i18n label resolve.

`*.js` under these directories is **gitignored**. Keep dumps on the machine that
runs the tests; do not commit vendor UI bundles.

Empty directories skip.

| Directory | Typical dumps | What the test does |
|-----------|----------------|--------------------|
| `index/` | `index-<hash>.js` | Build asset index + language config from the file |
| `params/` | `PARAM_*-<hash>.js`, `STATUS_*-<hash>.js` | Parse a ParamMap object |
| `menus/` | `module.menu-<hash>.js` | Parse raw route dicts from the JS export |
| `i18n/` | `parameters-<hash>.js`, `units-<hash>.js` | Parse `export default { ... }` translations |

Do not commit credentials.

CI does not use these dumps. A scheduled workflow
(`.github/workflows/upstream-assets.yml`) fetches public
`GET /v1/system/version` and the live `index-*.js` without login, parses only
when that fingerprint changes, and comments on a rolling GitHub issue.

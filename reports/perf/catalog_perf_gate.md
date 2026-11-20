# Catalog parser perf gate (#506)

Asset: `tests/assets/index/index-1TABHy-0.js` (1308198 bytes)

## Speed (pure vs tree-sitter on origin/main)

| Case | Pure mean (ms) | TS mean (ms) | Speedup |
|---|---:|---:|---:|
| language_config_from_index | 21.962 | 118.606 | 5.401x |
| units_descriptor_table_from_index | 248.422 | 462.201 | 1.861x |
| index_token_raw_maps | 482.156 | 570.776 | 1.184x |
| index_bootstrap_bundle | 743.114 | 1120.705 | 1.508x |

Pure is faster on every HA bootstrap case. No native deps.

## Accuracy vs `release/2026.11.2`

- Language default / units table (144 keys): match
- PARAM_* (1269) + STATUS_* (20): match
- Intentional delta: drop non-param pool keys `P4`/`P6`/`P10`/`P12` (unit-pool tables with `u0`… keys) that the eager path over-ingested

## Quality

- `poe patch-cov`: 100% patch
- `tests/test_catalog_captured_assets.py`: passed

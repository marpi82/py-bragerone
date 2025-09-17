# pybragerone

[![CI](https://github.com/<owner>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<owner>/<repo>/actions/workflows/ci.yml)
[![Release](https://github.com/<owner>/<repo>/actions/workflows/release.yml/badge.svg)](https://github.com/<owner>/<repo>/actions/workflows/release.yml)
[![Docs](https://github.com/<owner>/<repo>/actions/workflows/docs.yml/badge.svg)](https://github.com/<owner>/<repo>/actions/workflows/docs.yml)

Python library for integration with **Home Assistant**, designed to support the BragerOne ecosystem.

---

## Features

- ✅ Implements stable API for Home Assistant integration
- ✅ Type-annotated (PEP 484/585/604/695)
- ✅ Continuous testing on Python 3.13 and 3.14-dev
- ✅ Automatic CalVer versioning with pre-releases and dev builds
- ✅ Docs built with Sphinx and deployed with `mike`

---

## Installation

Stable releases are published on **PyPI**:

```bash
pip install pybragerone
```

Pre-release and dev builds are available on **TestPyPI**:

```bash
pip install --index-url https://test.pypi.org/simple/ pybragerone
```

---

## Development

1. Clone the repository and install dependencies with [Poetry](https://python-poetry.org/):
   ```bash
   poetry install
   ```
2. Run tests:
   ```bash
   poetry run pytest
   ```
3. Run type checks:
   ```bash
   poetry run mypy src/
   ```

---

## Versioning

- **Final releases** follow CalVer: `YYYY.M.D` (e.g., `2025.9.1`).
- **Pre-releases**: `YYYYaN`, `YYYY.MaN` (e.g., `2025a1`, `2025.9rc1`).
- **Dev builds**: automatically suffixed with `.devN`.

See [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) for full details.

---

## License

[MIT](LICENSE) © Your Name

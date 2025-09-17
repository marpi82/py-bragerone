# Project Workflows

This repository uses three main GitHub Actions workflows that work together to ensure code quality, packaging, and documentation deployment.

## 1. CI (`ci.yml`)

**Triggered:** on every push and pull request.

**Jobs:**
- **lint**: Run `ruff` against the codebase.
- **typecheck**: Run `mypy` for static type checking.
- **tests**: Run `pytest` on a matrix of Python versions:
  - 3.13 (stable)
  - 3.14-dev (nightly)
- **docs-verify**: Build Sphinx docs (check they compile).
- **build**: Depends on all of the above.
  - Builds package with `poetry build`.
  - Uploads `dist/*` as artifacts.

Artifacts can be downloaded from the Actions run page.

---

## 2. Release (`release.yml`)

**Triggered:** only after `CI` finishes successfully (`workflow_run`).

**Logic:**
- Checks out the same commit (`head_sha`) tested in CI.
- Detects whether this commit has a Git tag.

**Publishing rules:**
- **Always publish to TestPyPI** (stable, pre-release `a/b/rc`, or `dev` builds without tags).
- **Publish to PyPI** only when a valid tag is present:
  - Finals: `YYYY.M.D` (e.g., `2025.9.1`)
  - Pre-releases: `YYYYaN`, `YYYY.MaN` (e.g., `2025a1`, `2025.9rc1`)
- **Never publish** `dev` builds to PyPI.
- Guards prevent accidental PyPI publishing without a tag.
- Creates a GitHub Release (attaching artifacts) when a valid tag is found.

---

## 3. Docs (`docs.yml`)

**Triggered:** only after `CI` finishes successfully (`workflow_run`).

**Logic:**
- Checks out the same commit tested in CI.
- Validates branch/tag format:
  - Allowed branches (without tag): only `main`.
  - Allowed tags: same rules as Release (finals + pre).
- Builds Sphinx docs and deploys with `mike`.

**Deployment rules:**
- **Stable docs**: when the commit has a final tag (`YYYY.M.D`).  
  Deployed under that version number and aliased as `latest`.
- **Dev docs**: when building from `main` without a tag, or from pre-release tags.  
  Deployed under the alias `dev`.

---

## Secrets

These workflows require the following secrets configured in the repository:

- `PYPI_API_TOKEN` – API token for publishing to PyPI.
- `TEST_PYPI_API_TOKEN` – API token for publishing to TestPyPI.

---

## Summary

- **CI** ensures code quality and uploads build artifacts.
- **Release** takes over only on green CI and manages TestPyPI/PyPI + GitHub Release.
- **Docs** deploys documentation only after green CI, with stable/dev separation.

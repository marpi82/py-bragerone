---
applyTo: "docs/**, README.rst, examples/**, AGENTS.md"
---

# Documentation rules

1. **Docs describe the code as it is, not as it should be**: before editing a documented behavior, command, or example, verify it against `src/pybragerone/`. Code changes that alter documented behavior must update the docs in the same PR — drift in either direction is a defect.
2. **Examples must be runnable**: CLI invocations, env vars, and code snippets in docs/README must work copy-paste; prefer forms that are exercised in tests.
3. **Version/pin references** (Python, dependencies, HA integration contract) must match `pyproject.toml` and `uv.lock`.
4. **Sphinx builds with `-W` in CI**: no broken cross-references, every new page added to a toctree.

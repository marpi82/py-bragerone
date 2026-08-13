# Contributing to py-bragerone

Thanks for helping improve py-bragerone.

## How to contribute

1. Open an issue describing the bug or enhancement (optional but appreciated) — use the [issue templates](https://github.com/marpi82/py-bragerone/issues/new/choose).
2. Fork the repository and create a feature branch from `main`.
3. Make your changes with tests where practical.
4. Open a pull request against `main` (the [PR template](.github/PULL_REQUEST_TEMPLATE.md) is applied automatically).

The project uses GitHub Issues and Pull Requests for discussion and review. Do **not** file security issues publicly — see [SECURITY.md](SECURITY.md).

## Requirements for acceptable contributions

- **Tests**: major new functionality MUST come with tests; bug fixes should add a regression test where practical. All tests must pass offline (`pytest --run-live` is opt-in only).
- **Style**: `ruff format` + `ruff check` clean, `mypy --strict` clean, English only in code and docs, Google-style docstrings. Run `uv run --group dev --group test poe validate` before pushing.
- **DCO**: every commit MUST be signed off (`git commit -s`) to certify the [Developer Certificate of Origin](https://developercertificate.org/) — i.e. that you are legally authorized to contribute the change under the project's MIT license.

## Development setup

```bash
uv sync --locked --group dev --group test
uv run pre-commit install
```

Useful commands:

```bash
uv run ruff check .
uv run ruff format --check
uv run mypy
uv run pytest -q
uv run --group dev poe security
```

## Coding standards

- Target Python 3.13+.
- Format and lint with **Ruff**; type-check with **mypy** (strict).
- Prefer small, focused PRs with clear commit messages.
- Add or update tests for new behavior (see `docs/guides/tests_guidelines.rst`).

## Security reports

Do **not** open a public issue for vulnerabilities. Follow [SECURITY.md](SECURITY.md)
and email `marpi82.dev@google.com`.

## License

By contributing, you agree that your contributions are licensed under the MIT License.

## Branch protection

See [.github/branch-protection-checklist.md](.github/branch-protection-checklist.md) for recommended `main` protection settings.

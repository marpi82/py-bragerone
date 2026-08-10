Security assurance case
=======================

This document is the security assurance case for py-bragerone: it justifies
why the project's security requirements are met. It describes the threat
model, identifies trust boundaries, argues that secure design principles are
applied, and shows how common implementation security weaknesses are
countered.

Threat model
------------

Assets at risk:

- **User credentials** (BragerOne account email/password) and the resulting
  **access/refresh tokens**, handled at runtime by the library.
- **Integrity of parameter writes** sent to heating controllers (a wrong
  value can change physical heating behavior).
- **Integrity of the library itself** (supply chain: dependencies, build and
  release pipeline).

Threats considered:

1. *Network attacker (MITM)* reading or altering API traffic.
2. *Malicious or compromised server responses* (REST snapshots, Socket.IO
   deltas, web-app JS assets) crashing or misleading the client.
3. *Credential/token leakage* through logs, diagnostics, or the repository.
4. *Supply-chain attacks* via compromised dependencies or a compromised
   CI/CD pipeline.
5. *Tampered release artifacts* (PyPI/GitHub Releases).

Trust boundaries
----------------

1. **Library ↔ BragerOne cloud API** — all data crossing this boundary is
   untrusted input: the primary REST DTOs (auth, objects, modules) are
   validated with pydantic models, while some snapshot/prime endpoints
   deliberately return raw data for flexibility; live JS assets are always
   parsed defensively (tree-sitter, no code execution, soft-fail on
   unexpected shapes).
2. **Library ↔ host application** (e.g. Home Assistant integration) — the
   public API (``BragerOneApiClient``, ``BragerOneGateway``) is the only
   intended surface; internal modules are not re-exported.
3. **Repository/CI ↔ package publishing** — PyPI publishes only from the
   tag-triggered release workflow via OIDC trusted publishing (no stored
   PyPI token); separately, the docs workflow may deploy GitHub Pages
   (``pages: write`` scoped to documentation).

Secure design principles applied
--------------------------------

- **Secure defaults**: TLS certificate verification is on by default
  (httpx ``verify=True``); it is never disabled internally — a caller may
  only weaken it explicitly via the public ``verify`` parameter, e.g. for
  local diagnostics. Tokens auto-refresh without caller involvement.
- **Least privilege**: every workflow declares explicit ``permissions:``
  (default ``contents: read``). PR-triggered jobs have no access to
  long-lived secrets (none are stored for CI); they use only the
  short-lived, per-run ``GITHUB_TOKEN``. Write scopes are granted narrowly:
  ``pull-requests: write`` (+ ``contents: write`` only in the Dependabot
  auto-merge job) and ``security-events: write`` in CodeQL for uploading
  results. Package-publishing rights exist only in the tag-triggered
  release workflow.
- **Fail-safe defaults**: parsers return partial results or ``None`` instead
  of raising on unexpected upstream shapes; a new upstream bundle must not
  crash the library or dependent HA setups.
- **Economy of mechanism**: the library is a thin async client; protocol
  complexity is isolated in ``api/`` and ``models/`` with a small public API.
- **Mediation on writes**: the CLI checks numeric writes against the
  catalog's min/max range and applies the numeric transform before
  dispatch; nonnumeric values are passed through without range checks, and
  enum handling is left to callers. The low-level ``BragerOneApiClient``
  write methods are intentionally a thin raw transport; callers building on
  them (e.g. the Home Assistant integration) are expected to implement the
  full validation layer (enum label→raw, inverse transform, range/route
  checks), and the integration does.

Countering common implementation weaknesses
--------------------------------------------

- **Injection**: no ``eval``/``exec`` and no shell invocation on untrusted
  runtime data; JavaScript assets are parsed with tree-sitter, never
  executed. (One deliberate exception: the Sphinx build ``exec``es a
  trusted, repo-generated version file in ``docs/conf.py``.)
- **Secrets exposure**: in-repo controls: gitleaks runs in CI and
  pre-commit, and nothing sensitive is stored in the repository. The CLI
  takes account credentials from ``--email``/``--password`` or the
  ``PYBO_EMAIL``/``PYBO_PASSWORD`` environment variables, and prompts
  securely (hidden ``getpass`` input) when the password is omitted in an
  interactive terminal — argv should be avoided, as it can leak via shell
  history and process inspection. Its token store
  keeps the resulting access/refresh tokens in the system keyring with a
  file fallback. Log/diagnostic redaction is available and configurable.
  As a hosting-layer control, the GitHub repository additionally has
  secret scanning with push protection enabled.
- **Broken crypto**: the library implements no cryptography itself; transport
  security is delegated to Python's TLS stack (TLS 1.2+).
- **Memory safety**: the library itself is pure Python, but it relies on the
  native ``tree-sitter``/``tree-sitter-javascript`` extensions for asset
  parsing; that native boundary handles untrusted JS bytes and is covered
  by the parser-resilience test suite (malformed-shape fixtures) and by the
  catalog fuzz harness (``fuzz/fuzz_catalog.py``).
- **Vulnerable dependencies**: dependencies are declared in
  ``pyproject.toml`` and pinned in ``uv.lock``; Dependabot and Renovate keep
  them current; pip-audit scans them in CI; security exceptions (if any) are
  documented and tracked in ``SECURITY.md``.
- **Static/dynamic analysis**: CodeQL and pip-audit run in GitHub Actions;
  bandit and Ruff flake8-bandit (``S``) rules run in pre-commit hooks and via
  the local ``poe security`` / ``poe lint`` tasks; ``mypy --strict`` and ruff
  enforce type and code discipline; a fuzz harness (atheris) plus Hypothesis
  property tests exercise the parsers.
- **Release integrity**: releases are built in CI from the tagged commit and
  ship with SHA256 checksums, a CycloneDX SBOM, and Sigstore
  build-provenance attestations verifiable with ``gh attestation verify``.

Residual risk
-------------

The library depends on the undocumented, evolving BragerOne cloud API and
web assets; upstream changes can break parsing (mitigated by defensive
parsing and test coverage) and the service's own security is outside this
project's control. The CLI still accepts a password via ``--password``
argv, which can persist in shell history and process listings; prefer the
``PYBO_PASSWORD`` environment variable or the interactive prompt.

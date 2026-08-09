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
   untrusted input: REST payloads are validated with pydantic models, and
   live JS assets are parsed defensively (tree-sitter, no code execution,
   soft-fail on unexpected shapes).
2. **Library ↔ host application** (e.g. Home Assistant integration) — the
   public API (``BragerOneApiClient``, ``BragerOneGateway``) is the only
   intended surface; internal modules are not re-exported.
3. **Repository/CI ↔ PyPI and GitHub Releases** — only the tagged release
   workflow may publish, via OIDC trusted publishing (no stored PyPI token).

Secure design principles applied
--------------------------------

- **Secure defaults**: TLS certificate verification is on by default
  (httpx ``verify=True``); it is never disabled internally — a caller may
  only weaken it explicitly via the public ``verify`` parameter, e.g. for
  local diagnostics. Tokens auto-refresh without caller involvement.
- **Least privilege**: every CI workflow declares minimal ``permissions:``
  (default ``contents: read``); PR-triggered jobs have no access to secrets;
  publishing rights exist only in the tag-triggered release workflow.
- **Fail-safe defaults**: parsers return partial results or ``None`` instead
  of raising on unexpected upstream shapes; a new upstream bundle must not
  crash the library or dependent HA setups.
- **Economy of mechanism**: the library is a thin async client; protocol
  complexity is isolated in ``api/`` and ``models/`` with a small public API.
- **Complete mediation on writes**: every parameter write goes through one
  validated path (enum label→raw conversion, inverse numeric transform,
  min/max range checks) before dispatch.

Countering common implementation weaknesses
--------------------------------------------

- **Injection**: no ``eval``/``exec``, no shell invocation with untrusted
  data; JavaScript assets are parsed with tree-sitter, never executed.
- **Secrets exposure**: gitleaks runs in CI and pre-commit; GitHub secret
  scanning with push protection is enabled; credentials are sourced from
  environment/keyring, never stored in the repository; logs and diagnostics
  redact credentials.
- **Broken crypto**: the library implements no cryptography itself; transport
  security is delegated to Python's TLS stack (TLS 1.2+).
- **Memory safety**: pure Python — no native code is produced or shipped.
- **Vulnerable dependencies**: dependencies are declared in
  ``pyproject.toml`` and pinned in ``uv.lock``; Dependabot and Renovate keep
  them current; pip-audit scans them in CI; security exceptions (if any) are
  documented and tracked in ``SECURITY.md``.
- **Static/dynamic analysis**: bandit, semgrep and CodeQL run in CI;
  ``mypy --strict`` and ruff enforce type and code discipline; a fuzz
  harness (atheris) plus Hypothesis property tests exercise the parsers.
- **Release integrity**: releases are built in CI from the tagged commit and
  ship with SHA256 checksums, a CycloneDX SBOM, and Sigstore
  build-provenance attestations verifiable with ``gh attestation verify``.

Residual risk
-------------

The library depends on the undocumented, evolving BragerOne cloud API and
web assets; upstream changes can break parsing (mitigated by defensive
parsing and test coverage) and the service's own security is outside this
project's control.

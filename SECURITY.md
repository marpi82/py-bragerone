# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in py-bragerone, please report it by emailing marpi82.dev@google.com. Please do not create a public GitHub issue for security vulnerabilities.

## Dependency Security

This project uses several security scanning tools to monitor dependencies:

- **bandit**: Security linting for Python code
- **semgrep**: Static analysis for security patterns
- **pip-audit**: Dependency vulnerability scanning

### Known Security Exceptions

The following vulnerabilities are currently accepted with documented justification:

#### GHSA-7gcm-g887-7qv7 (CVE-2026-0994) - protobuf JSON recursion depth bypass

- **Severity**: High (CVSS 8.2)
- **Affected Package**: `protobuf` (all versions <= 6.33.4)
- **Status**: No patched version available as of 2026-01-26
- **Upstream Fix**: [protocolbuffers/protobuf#25239](https://github.com/protocolbuffers/protobuf/pull/25239) (PR open but not merged)
- **Dependency Chain**: `semgrep` (dev dependency) → `opentelemetry-*` → `protobuf@4.25.8`
- **Risk Assessment**: Low
  - Only affects development dependencies (not runtime)
  - Requires attacker to control JSON input to semgrep's telemetry
  - semgrep is not exposed in production environments
- **Mitigation**: Temporary exception added to `pip-audit` configuration
- **Action Required**: Remove exception from `pyproject.toml` once a patched protobuf version is released
- **Monitoring**: Check [PR #25239](https://github.com/protocolbuffers/protobuf/pull/25239) status regularly

#### GHSA-4xh5-x5gv-qwph

- **Status**: Previously documented exception (see git history for details)

## Security Best Practices

When using py-bragerone:

1. **Keep Dependencies Updated**: Regularly update dependencies using `uv sync --upgrade`
2. **Review Security Scans**: Run `uv run --group dev poe security` before releases
3. **Secure Credentials**: Never commit credentials to the repository. Use environment variables or keyring.
4. **Home Assistant Integration**: Follow Home Assistant's security guidelines for custom components

## Security Scanning

To run all security checks:

```bash
uv run --group dev poe security
```

This runs:
- `bandit -r src -q` - Python security linting
- `semgrep --config p/ci --error .` - Static analysis
- `pip-audit --skip-editable --progress-spinner off --ignore-vuln <exceptions>` - Dependency scanning

## Update Schedule

Security exceptions should be reviewed:
- Before each release
- Monthly during active development
- When upstream patches are announced

## Contact

For security concerns, contact: marpi82.dev@google.com

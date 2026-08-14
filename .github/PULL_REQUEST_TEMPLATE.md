## Summary

<!-- What does this PR change and why? Link related issues with "Fixes #N" / "Closes #N" when applicable. -->

## Type of change

<!-- Check all that apply. -->

- [ ] Bug fix (non-breaking)
- [ ] New feature / enhancement (non-breaking)
- [ ] Breaking change to the **public API** (`BragerOneApiClient`, `BragerOneGateway`, or anything documented in `docs/reference/ha_integration.rst`) — call this out explicitly for `ha-bragerone`
- [ ] Docs only
- [ ] Tests / CI / tooling / chore

## Checklist

- [ ] Commits are signed off (`git commit -s`) — [DCO](https://developercertificate.org/)
- [ ] English only in code, comments, and docs; Google-style docstrings
- [ ] `uv run --group dev --group test poe validate` passes locally (fmt + lint + mypy --strict + security + tests)
- [ ] Tests added / updated where practical (regression test for bug fixes; major features MUST have tests). Offline tests pass; live API remains `@pytest.mark.needs_internet`
- [ ] Docs updated when public behavior changes (`docs/` + Sphinx `-W` clean)
- [ ] No secrets / credentials / real device dumps committed
- [ ] Ran Cursor `/review-bugbot` (or `/review`) on the final diff before push when using Cursor 3.7+ (see `.cursor/BUGBOT.md`)

## Test plan

<!-- How did you verify this? Commands run, scenarios covered. -->

```bash
uv run --group dev ruff check .
uv run --group dev poe typecheck
uv run --group dev --group test poe test
```

## Notes for reviewers

<!-- Trade-offs, follow-ups, HA integration impact, upstream JS asset caveats, etc. -->

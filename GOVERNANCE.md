# Governance

## Model

py-bragerone is a single-maintainer project: the owner (@marpi82) makes all final decisions on direction, releases, and dispute resolution (benevolent-dictator model). This may evolve if regular co-maintainers join.

## Roles and responsibilities

| Role | Who | Responsibilities |
| --- | --- | --- |
| Maintainer / owner | @marpi82 | Reviews and merges PRs, triages issues, cuts releases, owns security response (see `SECURITY.md`), manages repository settings and access |
| Contributors | anyone | Open issues and PRs, follow `CONTRIBUTING.md` and the code of conduct |

Only the maintainer has access to sensitive resources (repository settings, PyPI trusted publishing, security advisories).

## Access changes

Escalated permissions (e.g. collaborator with write access) are granted only after a track record of reviewed contributions, and are reviewed when activity changes.

## Decisions

- Day-to-day: decided in GitHub issues/PR discussions.
- Breaking changes to the public API (`pybragerone.__all__`, documented in `docs/reference/ha_integration.rst`) require an explicit maintainer decision recorded in the PR.

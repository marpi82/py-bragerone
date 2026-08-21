# Branch and tag protection checklist

Scorecard `BranchProtection` / `CodeReview` alerts need GitHub Settings changes
(not only repository files). `CODEOWNERS` is already in `.github/CODEOWNERS`.

Release channel policy (enforced in CI by `.github/workflows/release.yml`):

- **`main`**: stable CalVer tags and pre-releases (`aN` / `bN` / `rcN`)
- **`release/*`**: pre-releases only — stable tags fail the release workflow unless
  the tagged commit is already on `origin/main`

Rulesets below are hardening around that policy; the workflow remains the source
of truth for “stable ⇒ commit on main”.

## Branch ruleset: `main`

Open: https://github.com/marpi82/py-bragerone/settings/branches

(or Rules → https://github.com/marpi82/py-bragerone/settings/rules )

Recommended rules for `main`:

1. Require a pull request before merging
2. Require approvals: at least **1**
3. Dismiss stale pull request approvals when new commits are pushed
4. Require review from Code Owners
5. Require conversation resolution before merging
6. Do **not** allow force pushes
7. Do **not** allow deletions
8. Optionally require status checks to pass (CI, CodeQL)

## Branch ruleset: `release/**` (release trains)

Open: https://github.com/marpi82/py-bragerone/settings/rules

Create a ruleset targeting `release/**` (or `release/*`):

1. Require a pull request before merging into the train
2. Do **not** allow force pushes
3. Restrict deletions (allow maintainers only after the train is closed)
4. Optionally require the same status checks as `main` (CI)

Trains are named `release/YYYY.M` or `release/YYYY.M.N` (for example
`release/2026.9`). Cut pre-release tags from the train tip; merge to `main`
before any unsuffixed stable tag.

## Tag ruleset (CalVer)

Open: https://github.com/marpi82/py-bragerone/settings/rules

Create a **tag** ruleset (patterns `20*` and optionally `v20*`):

1. Restrict tag creations to maintainers / selected actors
2. Block tag deletions
3. Block force updates of existing tags

Note: GitHub cannot bind “this tag must point at `main`” the way the release
workflow does. Use the tag ruleset to limit who can create/overwrite tags; rely
on **Enforce release channel** in `release.yml` to refuse stable publishes from
commits not on `main`.

## After enabling

Re-run the **Security Checks** workflow so Scorecard re-evaluates
BranchProtection / CodeReview.

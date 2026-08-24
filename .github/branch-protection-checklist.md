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

## BragerOne triage bot (issues, PRs, user project)

Workflows: `bragerone-triage.yml`, `pull-request-labeler.yml`, `label-sync.yml`
(reusable triage logic lives in `bragerone-triage-reusable.yml`).

### One-time setup

1. **Project number** — from `https://github.com/users/marpi82/projects/<N>`.
2. **Field IDs** — after `gh auth refresh -s read:project,project`:

   ```bash
   ./scripts/github_project_setup.sh marpi82 <N>
   ```

3. **Repository variables** (Settings → Actions → Variables) in **both**
   `py-bragerone` and `ha-bragerone`:

   - `BRAGERONE_PROJECT_NUMBER` — integer from the project URL (`…/projects/2` → `2`)
   - `BRAGERONE_STATUS_FIELD_ID` — opaque string (for example `PVTSSF_lAHOB…`)
   - `BRAGERONE_STATUS_TODO_OPTION_ID` — maps to board **Backlog** (opaque string)
   - `BRAGERONE_STATUS_READY_OPTION_ID` — board **Ready** (dependency bots)
   - `BRAGERONE_STATUS_IN_PROGRESS_OPTION_ID` — board **In progress**
   - `BRAGERONE_STATUS_IN_REVIEW_OPTION_ID` — board **In review**
   - `BRAGERONE_STATUS_DONE_OPTION_ID` — board **Done**

   Status option IDs are **not** numeric counters — GitHub Projects v2 uses opaque
   strings. The board UI only shows names (Backlog, Ready, …); IDs come from
   `./scripts/github_project_setup.sh marpi82 2` or `--set-vars`.

   If status variables are omitted, the workflow resolves option names via GraphQL
   (`Backlog`, `Ready`, `In progress`, `In review`, `Done`).

4. **Project access (user-owned project)** — **cannot** link repositories in
   project Manage access (that UI is for organization projects only). Create a
   **fine-grained PAT** scoped to your account with **Projects: Read and write**,
   then add it as secret **`PROJECTS_TOKEN`** in both repos. The reusable triage
   workflow uses `PROJECTS_TOKEN` when present, otherwise `GITHUB_TOKEN`.

5. **Workflow permissions** — each repo → Actions → General → Read and write.

### Behaviour

- Issues: template type labels + `py-bragerone`; project Status **Backlog** (closed → **Done**).
- PRs: path labels (`documentation`, `python`, …) + type from linked issue or title
  prefix (`bug:`, `feat:`, `docs:`) + repo label; draft → **Backlog**, open → **In progress**,
  `ready_for_review` → **In review**, merged → **Done**; Dependabot/Renovate → **Ready**.
- Skips rolling `[upstream-assets]` / `[live-contract]` issues.

`ha-bragerone` calls `marpi82/py-bragerone/.github/workflows/bragerone-triage-reusable.yml@main`
— merge triage workflows to `main` before HA triage runs on `main`.

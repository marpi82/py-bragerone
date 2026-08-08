# Branch protection checklist (`main`)

Scorecard `BranchProtection` / `CodeReview` alerts need GitHub Settings changes
(not only repository files). `CODEOWNERS` is already in `.github/CODEOWNERS`.

Open: https://github.com/marpi82/py-bragerone/settings/branches

Recommended rules for `main`:

1. Require a pull request before merging
2. Require approvals: at least **1**
3. Dismiss stale pull request approvals when new commits are pushed
4. Require review from Code Owners
5. Require conversation resolution before merging
6. Do **not** allow force pushes
7. Do **not** allow deletions
8. Optionally require status checks to pass (CI, CodeQL)

After enabling the rules, re-run the **Security Checks** workflow so Scorecard
re-evaluates BranchProtection / CodeReview.

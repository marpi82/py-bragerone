#!/usr/bin/env bash
# Pre-push test gates: 80% project coverage (library runtime) + 100% patch vs main (Codecov parity).
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "${repo_root}"

uv run --group test pytest --maxfail=1 --disable-warnings -q \
  --cov=pybragerone \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=xml \
  --cov-fail-under=80

if ! git rev-parse --verify origin/main >/dev/null 2>&1; then
  echo "patch coverage: skip (origin/main unavailable)"
  exit 0
fi

compare_ref="$(git merge-base HEAD origin/main)"
echo "patch coverage vs ${compare_ref}"
uv run --group test diff-cover coverage.xml \
  --compare-branch="${compare_ref}" \
  --fail-under=100 \
  --show-uncovered

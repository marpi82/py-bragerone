#!/usr/bin/env bash
# Print BragerOne GitHub Project v2 field IDs for Actions repository variables.
#
# Usage:
#   ./scripts/github_project_setup.sh [owner] <project_number> [--set-vars]
#
# Example:
#   gh auth refresh -s read:project,project
#   ./scripts/github_project_setup.sh 2
#   ./scripts/github_project_setup.sh marpi82 2 --set-vars
#
# Status option IDs are opaque strings (for example f75ad846), not integers.
# The board shows names (Backlog, Ready, …); IDs only appear via this script / API.
set -euo pipefail

SET_VARS=""
if [[ $# -ge 1 && "${!#}" == "--set-vars" ]]; then
  SET_VARS="--set-vars"
  set -- "${@:1:$#-1}"
fi

if [[ $# -eq 1 && "$1" =~ ^[0-9]+$ ]]; then
  OWNER="marpi82"
  PROJECT_NUMBER="$1"
elif [[ $# -eq 2 ]]; then
  OWNER="$1"
  PROJECT_NUMBER="$2"
else
  echo "Usage: $0 [owner] project_number [--set-vars]" >&2
  echo "       $0 project_number [--set-vars]  (defaults owner to marpi82)" >&2
  exit 1
fi

if [[ "${PROJECT_NUMBER}" == "--set-vars" ]]; then
  echo "Usage: $0 [owner] project_number [--set-vars]" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Run gh auth login first." >&2
  exit 1
fi

echo "== BragerOne project #${PROJECT_NUMBER} (${OWNER}) =="
gh project view "${PROJECT_NUMBER}" --owner "${OWNER}" --format json | python3 -c '
import json, sys
p = json.load(sys.stdin)
print("title:", p.get("title", "?"))
print("url:", p.get("url", "?"))
print("project id:", p.get("id", "?"))
'
echo

echo "== Project fields =="
FIELD_JSON="$(gh project field-list "${PROJECT_NUMBER}" --owner "${OWNER}" --format json)"
SETUP_OUTPUT="$(FIELD_JSON="${FIELD_JSON}" PROJECT_NUMBER="${PROJECT_NUMBER}" python3 <<'PY'
import json
import os
import sys

raw = os.environ["FIELD_JSON"]
project_number = os.environ["PROJECT_NUMBER"]
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print(raw)
    sys.exit(1)

fields = data.get("fields", data if isinstance(data, list) else [])
status_field = None
for field in fields:
    name = field.get("name", "")
    fid = field.get("id", "")
    print(f"- {name}: {fid}")
    if name == "Status":
        status_field = field

if not status_field:
    print("\nNo Status field found. Create a single-select Status field in the project UI.")
    sys.exit(0)

options = status_field.get("options", [])
if not options:
    print("\nStatus field has no options.")
    sys.exit(0)

print("\n== Status options (board name → opaque ID; copy the ID string) ==")
print("These are NOT numbers you can see in the UI — only names are shown there.")
for option in options:
    print(f"- {option.get('name')}: {option.get('id')}")

lookup = {option.get("name", "").strip().lower(): option.get("id") for option in options}


def pick(names):
    for name in names:
        oid = lookup.get(name.strip().lower())
        if oid:
            return name, oid
    return None, None


pairs = [
    ("BRAGERONE_PROJECT_NUMBER", project_number),
    ("BRAGERONE_STATUS_FIELD_ID", status_field.get("id")),
    ("BRAGERONE_STATUS_TODO_OPTION_ID", None),
    ("BRAGERONE_STATUS_READY_OPTION_ID", None),
    ("BRAGERONE_STATUS_IN_PROGRESS_OPTION_ID", None),
    ("BRAGERONE_STATUS_IN_REVIEW_OPTION_ID", None),
    ("BRAGERONE_STATUS_DONE_OPTION_ID", None),
]

backlog_name, backlog_id = pick(["Backlog", "Todo", "New"])
ready_name, ready_id = pick(["Ready"])
prog_name, prog_id = pick(["In progress", "In Progress"])
review_name, review_id = pick(["In review", "In Review", "Review"])
done_name, done_id = pick(["Done", "Complete", "Closed"])

pairs[2] = ("BRAGERONE_STATUS_TODO_OPTION_ID", backlog_id)
pairs[3] = ("BRAGERONE_STATUS_READY_OPTION_ID", ready_id)
pairs[4] = ("BRAGERONE_STATUS_IN_PROGRESS_OPTION_ID", prog_id)
pairs[5] = ("BRAGERONE_STATUS_IN_REVIEW_OPTION_ID", review_id)
pairs[6] = ("BRAGERONE_STATUS_DONE_OPTION_ID", done_id)

print("\n== Suggested repository variables (set in both repos) ==")
for key, value in pairs:
    if value:
        print(f"{key}={value}")
    else:
        print(f"{key}=<missing — pick from Status options above>")

if backlog_name:
    print(f"\nBacklog/Todo mapped from option: {backlog_name}")
if ready_name:
    print(f"Ready mapped from option: {ready_name}")
if prog_name:
    print(f"In progress mapped from option: {prog_name}")
if review_name:
    print(f"In review mapped from option: {review_name}")
if done_name:
    print(f"Done mapped from option: {done_name}")

print("\n__VARS__")
for key, value in pairs:
    if value:
        print(f"{key}\t{value}")
PY
)"

echo "${SETUP_OUTPUT}" | sed '/^__VARS__$/,$d'

echo
echo "== Project access (user-owned project) =="
echo "User projects do NOT support linking repositories in Manage access (org projects only)."
echo "Create a classic PAT (https://github.com/settings/tokens) with scopes project + repo,"
echo "add it as secret PROJECTS_TOKEN in py-bragerone and ha-bragerone."
echo "Fine-grained PATs cannot access user-owned Projects v2."
echo
echo "In each repo: Settings → Actions → General → Workflow permissions → Read and write."

if [[ "${SET_VARS}" == "--set-vars" ]]; then
  echo
  echo "== Setting repository variables =="
  while IFS=$'\t' read -r key value; do
    [[ -z "${key}" || "${key}" == "__VARS__" ]] && continue
    for repo in marpi82/py-bragerone marpi82/ha-bragerone; do
      echo "gh variable set ${key} --repo ${repo}"
      gh variable set "${key}" --repo "${repo}" --body "${value}"
    done
  done < <(echo "${SETUP_OUTPUT}" | awk '/^__VARS__$/{f=1; next} f && NF')
fi

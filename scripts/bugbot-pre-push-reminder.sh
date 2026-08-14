#!/usr/bin/env bash
# Soft pre-push reminder: Cursor Bugbot has no CLI/hook yet ("coming soon").
# Local review is an agent slash command, not something this hook can enforce.
set -euo pipefail

cat <<'EOF'
============================================================
Reminder: run Cursor Bugbot locally before push (discipline, not a gate).
  In Cursor agent input (3.7+ / cursor.com/agents): /review-bugbot
  Or: /review  (Bugbot + Security Review menu)
  Rules: .cursor/BUGBOT.md  |  Docs: https://cursor.com/docs/bugbot
  Same patch ID => GitHub Bugbot can skip a duplicate PR review.
  CLI/hook support is not available yet — this hook always exits 0.
============================================================
EOF

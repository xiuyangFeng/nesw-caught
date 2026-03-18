#!/usr/bin/env bash

set -euo pipefail

SKILL_SCRIPT="/Users/xiuyang/.codex/skills/brainstorming/scripts/start-server.sh"

if [[ ! -x "$SKILL_SCRIPT" ]]; then
  echo "Error: missing brainstorming start-server script at $SKILL_SCRIPT" >&2
  exit 1
fi

exec "$SKILL_SCRIPT" "$@"

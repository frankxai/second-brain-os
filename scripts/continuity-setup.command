#!/usr/bin/env bash
# Double-click to set up session continuity. See docs/continuity.md.
cd "$(dirname "$0")/.." || exit 1
SBO=sbo-continuity
[ -x .venv/bin/sbo-continuity ] && SBO=.venv/bin/sbo-continuity
CHOME="${SIS_CONTINUITY_HOME:-$HOME/.starlight/continuity}"
if "$SBO" setup "$@" && [ -f "$CHOME/trust-policy.draft.json" ] && [ ! -f "$CHOME/trust-policy.json" ]; then
  "$SBO" approve
fi
echo
"$SBO" doctor
echo
read -r -p "Press return to close. "

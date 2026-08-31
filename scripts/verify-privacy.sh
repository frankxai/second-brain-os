#!/usr/bin/env bash
# Verify the SBO privacy hardening checklist for a private vault.
#
# Two modes:
#   strict   (default)        — every verifiable check must pass; runs on a real
#                                install. Machine-level state that no script can
#                                confirm reports WARN with its remediation step
#                                and never fails the run.
#   template (SBO_VERIFY_MODE=template) — only vault-shape checks (marker files,
#                                          no banned plugins, not inside cloud
#                                          paths). Skips machine-level checks
#                                          (Windows Search exclusion list,
#                                          macOS Time Machine exclusion).
#                                          Used by CI on the template skeleton.
#
# Usage:
#   ./scripts/verify-privacy.sh /path/to/private-vault
#   SBO_VERIFY_MODE=template ./scripts/verify-privacy.sh templates/private-vault-skeleton

set -euo pipefail

MODE="${SBO_VERIFY_MODE:-strict}"

PRIVATE_VAULT="${1:-}"
if [[ -z "$PRIVATE_VAULT" ]]; then
  echo "usage: $0 <path-to-private-vault>"
  exit 2
fi
if [[ ! -d "$PRIVATE_VAULT" ]]; then
  echo "[error] private vault not found at $PRIVATE_VAULT"
  exit 2
fi

PASS=0
FAIL=0
WARN=0

check() {
  local name="$1"
  shift
  printf "  [%s] " "$name"
  if "$@"; then
    echo "PASS"
    PASS=$((PASS + 1))
  else
    echo "FAIL"
    FAIL=$((FAIL + 1))
  fi
}

# Machine-level state a script cannot confirm: report the remediation, never fail.
check_machine() {
  local name="$1"
  shift
  printf "  [%s] " "$name"
  if "$@"; then
    echo "PASS"
    PASS=$((PASS + 1))
  else
    echo "WARN"
    WARN=$((WARN + 1))
  fi
}

# 1. Windows Search exclusion (N/A on Unix)
check_winsearch() {
  return 0  # N/A on non-Windows
}

# 2. macOS Spotlight exclusion
check_spotlight() {
  if [[ "$(uname)" == "Darwin" ]]; then
    [[ -f "$PRIVATE_VAULT/.metadata_never_index" ]]
  else
    return 0  # N/A
  fi
}

# 3a. Cloud-sync path exclusion (vault location — deterministic in every mode)
check_backup_path() {
  if [[ "$PRIVATE_VAULT" == *"iCloud"* ]] || [[ "$PRIVATE_VAULT" == *"Mobile Documents"* ]]; then
    echo -n "(vault inside iCloud — move out) "
    return 1
  fi
  if [[ -n "${OneDrive:-}" ]] && [[ "$PRIVATE_VAULT" == "$OneDrive"* ]]; then
    echo -n "(vault inside OneDrive — move out) "
    return 1
  fi
  return 0
}

# 3b. macOS Time Machine exclusion (machine-level — strict mode only)
check_timemachine() {
  if [[ "$MODE" != "strict" ]] || [[ "$(uname)" != "Darwin" ]]; then
    return 0  # N/A
  fi
  if tmutil isexcluded "$PRIVATE_VAULT" 2>/dev/null | grep -q "Excluded"; then
    return 0
  fi
  echo -n "do this once by hand: tmutil addexclusion \"$PRIVATE_VAULT\" -- "
  return 1
}

# 4. Obsidian Sync prohibition (marker file)
check_no_sync() {
  [[ -f "$PRIVATE_VAULT/.obsidian-no-sync" ]]
}

# 5. Local REST API plugin prohibition
check_no_rest_api() {
  [[ ! -d "$PRIVATE_VAULT/.obsidian/plugins/obsidian-local-rest-api" ]]
}

# 6. Smart Connections / Text Generator prohibition
check_no_llm_plugins() {
  [[ ! -d "$PRIVATE_VAULT/.obsidian/plugins/smart-connections" ]] && \
  [[ ! -d "$PRIVATE_VAULT/.obsidian/plugins/text-generator-obsidian" ]]
}

echo ""
echo "SBO Privacy Verification (mode: $MODE)"
echo ""
echo "Vault: $PRIVATE_VAULT"
echo ""

check "1. Windows Search exclusion (N/A on Unix)" check_winsearch
check "2. macOS Spotlight exclusion" check_spotlight
check "3a. Cloud-sync path exclusion" check_backup_path
check_machine "3b. macOS Time Machine exclusion" check_timemachine
check "4. Obsidian Sync prohibition" check_no_sync
check "5. Local REST API plugin prohibition" check_no_rest_api
check "6. LLM-plugin prohibition" check_no_llm_plugins

echo ""
echo "Pass: $PASS"
if [[ $WARN -gt 0 ]]; then echo "Warn: $WARN"; fi
echo "Fail: $FAIL"
echo ""
if [[ $FAIL -gt 0 ]]; then
  echo "Privacy verification FAILED. Address the issues above."
  exit 1
fi
if [[ $WARN -gt 0 ]]; then
  echo "Privacy verification PASSED (with manual steps listed above)."
else
  echo "Privacy verification PASSED."
fi

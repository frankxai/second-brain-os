#!/usr/bin/env bash
# Verify the 6-item SBO privacy hardening checklist for a private vault.
#
# Usage: ./scripts/verify-privacy.sh /path/to/private-vault

set -euo pipefail

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

# 3. Cloud-backup exclusion
check_backup() {
  # macOS Time Machine
  if [[ "$(uname)" == "Darwin" ]]; then
    if tmutil isexcluded "$PRIVATE_VAULT" 2>/dev/null | grep -q "Excluded"; then
      return 0
    fi
    echo -n "(macOS: add via tmutil addexclusion) "
    return 1
  fi
  # iCloud Drive check
  if [[ "$PRIVATE_VAULT" == *"iCloud"* ]] || [[ "$PRIVATE_VAULT" == *"Mobile Documents"* ]]; then
    echo -n "(vault inside iCloud — move out) "
    return 1
  fi
  return 0
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
echo "SBO Privacy Verification"
echo ""
echo "Vault: $PRIVATE_VAULT"
echo ""

check "1. Windows Search exclusion (N/A on Unix)" check_winsearch
check "2. macOS Spotlight exclusion" check_spotlight
check "3. Cloud-backup exclusion" check_backup
check "4. Obsidian Sync prohibition" check_no_sync
check "5. Local REST API plugin prohibition" check_no_rest_api
check "6. LLM-plugin prohibition" check_no_llm_plugins

echo ""
echo "Pass: $PASS"
echo "Fail: $FAIL"
echo ""
if [[ $FAIL -gt 0 ]]; then
  echo "Privacy verification FAILED. Address the issues above."
  exit 1
fi
echo "Privacy verification PASSED."

#!/usr/bin/env bash
# SBO interactive setup for macOS + Linux.
#
# Usage: ./scripts/setup.sh [vault-parent-dir]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VAULT_PARENT="${1:-$HOME/second-brain}"
BRAIN_PATH="$VAULT_PARENT/brain"
PRIVATE_PATH="$VAULT_PARENT/private"

echo ""
echo "Second Brain OS -- Setup"
echo ""

if [[ -d "$BRAIN_PATH" || -d "$PRIVATE_PATH" ]]; then
  echo "Vault already exists at $VAULT_PARENT. Aborting to avoid overwrite."
  exit 1
fi

echo "Creating brain/ at $BRAIN_PATH ..."
cp -r "$REPO_ROOT/templates/brain-vault-skeleton" "$BRAIN_PATH"
echo "Creating private/ at $PRIVATE_PATH ..."
cp -r "$REPO_ROOT/templates/private-vault-skeleton" "$PRIVATE_PATH"

echo ""
echo "Running privacy verification ..."
bash "$REPO_ROOT/scripts/verify-privacy.sh" "$PRIVATE_PATH"

cat <<EOF

Next steps:

1. Open Obsidian and add your new brain vault at:
     $BRAIN_PATH

2. Install community plugins (Obsidian will prompt). Required:
     - Local REST API
     - Templater
     - Dataview
     - QuickAdd
     - Smart Connections
     - Tasks
     - Periodic Notes + Calendar
     - Excalidraw
     - Omnisearch

3. In Local REST API plugin settings: copy the API key.

4. Add this snippet to your Claude Desktop config
   (~/.config/claude/claude_desktop_config.json on Linux,
    ~/Library/Application Support/Claude/claude_desktop_config.json on macOS,
    %APPDATA%\\Claude\\claude_desktop_config.json on Windows):

   {
     "mcpServers": {
       "sbo-obsidian": {
         "command": "uvx",
         "args": ["mcp-obsidian"],
         "env": {
           "OBSIDIAN_API_KEY": "<from Local REST API plugin in brain vault>",
           "OBSIDIAN_HOST": "https://localhost:27124"
         }
       }
     }
   }

5. Add your private vault at $PRIVATE_PATH as a SEPARATE Obsidian vault.

6. Request your Claude.ai data export:
     Settings > Privacy > Export data
   (delivered via email within 24h)

7. Request your ChatGPT export:
     Settings > Data Controls > Export

8. When exports arrive, run:
     export SBO_BRAIN_VAULT_ROOT="$BRAIN_PATH"
     export SBO_PRIVATE_VAULT_ROOT="$PRIVATE_PATH"
     export ANTHROPIC_API_KEY="<your-key>"
     sbo-ingest path/to/conversations.json

Setup complete.
EOF

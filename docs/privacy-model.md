# Privacy Model

> The full threat model + 6-item OS-level hardening checklist for SBO.

## The privacy contract

> **MCP never has a path to `private/`. The boundary is filesystem, not config.**

Your `private/` vault and your `brain/` vault are independent Obsidian vaults at separate filesystem paths. Your MCP server's vault root is `~/second-brain/brain/`. Filesystem operations within that server cannot escape the vault root. The `private/` path is unreachable.

The ONE bridge is `private/_distill/pending/` → `brain/patterns/`. You move content across this bridge by **manual copy-paste only**. There is no script. There is no automation.

## What this protects against

- Accidental LLM read of sensitive content via MCP.
- A vault-walking script following `[[wiki-links]]` into `private/`.
- A misconfigured agent that "helpfully" indexes everything.

## What this DOES NOT protect against — and what to do

### 1. OS-level file indexing (Windows Search, macOS Spotlight)

Both Windows and macOS index ALL files by default. If both vaults are on the same machine, both end up in the indexed search surface — even though MCP can't cross.

**Fix:**
- **Windows:** Settings → Search → Searching Windows → Add an excluded folder → add your private vault path.
- **macOS:** Ship `.metadata_never_index` marker (SBO does this). Verify with `mdutil -s ~/second-brain/private`.

### 2. Cloud backup (OneDrive, iCloud Drive, Dropbox, Google Drive)

If your vault parent is inside a cloud-sync folder, your private vault is in someone else's cloud.

**Fix:**
- Move `~/second-brain/` outside any cloud-sync folder.
- For Windows OneDrive: even if outside the OneDrive folder, check that you haven't enabled "Backup folders" for Documents/Desktop with the vault inside.
- For macOS iCloud: ensure the vault is not in `~/Library/Mobile Documents/` or under "Desktop & Documents" iCloud sync.

### 3. System backup (Time Machine, File History, restic)

Backup tools snapshot everything they can read.

**Fix:**
- **macOS Time Machine:** System Settings → General → Time Machine → Options → exclude `~/second-brain/private`.
- **Windows File History:** Settings → Update & Security → Backup → exclude the private vault folder.
- **Personal backup tools (restic, borg, etc.):** add `~/second-brain/private` to exclude patterns. Or backup the private vault with a separate, more-protected key.

### 4. Obsidian Sync in the private vault

Obsidian Sync is end-to-end encrypted but sends your data through Obsidian's servers. The `.obsidian-no-sync` marker file is SBO's assertion that you have not enabled Sync. The startup script checks for it.

**Fix:** Never enable Sync in the private vault. If you need cross-device access for the private vault, use Syncthing (P2P, no third party) or a personal git remote with `git-crypt`.

### 5. LLM-calling plugins in the private vault

Smart Connections, Text Generator, Copilot for Obsidian — these send vault content to external APIs.

**Fix:** Never install these in the private vault. The setup script enforces this.

### 6. Clipboard history

Windows Clipboard History (Win+V), macOS Universal Clipboard, and clipboard managers retain copy-paste contents across sessions. Your private→brain distillation moves leave a trail.

**Fix:** After each private→brain distillation:
- **Windows:** Win+V → click the three-dot menu → Clear all.
- **macOS:** `pbcopy < /dev/null` in a terminal.
- Consider disabling clipboard history in Settings → System → Clipboard → Clipboard history.

## What this protects against ONLY if you do these

- **Disk encryption:** Hibernation files, swap files, and pagefile.sys can contain unencrypted vault content if the disk isn't encrypted at rest. Enable BitLocker (Windows) or FileVault (macOS).
- **Lock-screen discipline:** Anyone with physical access to an unlocked machine has both vaults. This is true of everything.
- **Plugin auditing:** Obsidian community plugins are sandboxed at the JS-runtime level, not OS level. A malicious plugin in `brain/` cannot directly read `private/` (separate vault), but it can call out to the internet. Audit plugins you install.

## Threat model — explicit assumptions

| Threat | In scope | Out of scope |
|---|---|---|
| Accidental LLM access via MCP | YES — filesystem boundary | — |
| OS-level file indexing | Documented (you mitigate) | — |
| Cloud backup leak | Documented (you mitigate) | — |
| Compromised host | — | Disk encryption + lock-screen discipline (your responsibility) |
| Malicious Obsidian plugin in brain/ | Partial — Obsidian sandbox + you audit installs | Network egress from any plugin |
| Targeted attacker with physical access | — | Out of scope; same caveat as everything |
| Subpoena or legal compulsion | — | Not a threat SBO addresses |
| You paste private content into Claude.ai chat | — | User discretion |

## Verification

Run `scripts/verify-privacy.{ps1,sh}` on your private vault on every Sunday Palace Review.

## If you suspect a leak

1. Audit Sync history in the private vault: Obsidian → Settings → Sync → History.
2. Audit `_inbox/` in the brain vault: is anything there that shouldn't be?
3. Audit cloud sync apps: when did they last touch the private vault parent?
4. Treat affected data as compromised; rotate credentials, etc.

Built on SIP.

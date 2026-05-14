# Contributing to Second Brain OS

Thanks for considering a contribution. SBO is a template, not a framework — the goal is to stay small, opinionated, and honest about its limits.

## Before you open an issue or PR

1. **Read [`README.md`](README.md), [`docs/architecture.md`](docs/architecture.md), and [`docs/privacy-model.md`](docs/privacy-model.md).** Most questions are answered there.
2. **Run the tests locally** (`pytest -v`) — green is the entry condition.
3. **Run the privacy verifier** if you touched anything under `scripts/`, `templates/`, or `src/sbo_ingestion/dual_write.py`:
   ```bash
   bash scripts/verify-privacy.sh templates/private-vault-skeleton
   ```

## What we welcome

- **Bug reports** with a minimal reproduction (export filename, command run, expected vs. actual).
- **Privacy hardening proposals** that survive the threat model in `docs/privacy-model.md`.
- **New handlers** for export formats from other LLM products (Gemini, local-LLM chat logs, etc.) — follow the `claude_ai.py` / `chatgpt.py` shape exactly.
- **Documentation improvements**, especially worked examples.
- **Cross-platform compatibility fixes** (Windows, macOS, Linux).

## What we don't accept

- **Anything that lets MCP touch `private/`.** The two-vault filesystem boundary is non-negotiable.
- **Mandatory cloud dependencies.** The OSS template must work fully local.
- **AI-slop phrases** in docs (delve, dive into, it's worth noting, certainly, absolutely, etc.). See `src/sbo_ingestion/voice_check.py`.
- **Breaking changes** to `SKILL.md` / `AGENTS.md` / `CANON.md` / `mcp.json` schema without an SIP-level discussion first.

## Development setup

```bash
git clone https://github.com/frankxai/second-brain-os
cd second-brain-os
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate
pip install -e .
pytest -v
```

## Pull request checklist

- [ ] `pytest -v` is green on your machine
- [ ] If you touched ingestion, you added a test that fails on `main` and passes with your change
- [ ] If you touched the private-vault skeleton, `bash scripts/verify-privacy.sh templates/private-vault-skeleton` is 6/6
- [ ] Commits follow the existing `feat:` / `fix:` / `docs:` / `chore:` style
- [ ] No new mandatory cloud or paid-tier dependencies in the OSS template

## Composition note (for FrankX users)

The paid-tier `@frankx/second-brain-pro` package lives in a separate repo. PRs that try to upstream paid-tier agents into this OSS template will be redirected. The OSS line is set in `docs/paid-tier.md`.

## License

By contributing, you agree your contributions are licensed MIT.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md) v2.1.

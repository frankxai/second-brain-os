## What

<!-- One sentence describing the change. -->

## Why

<!-- The problem this solves. If you're not sure why this matters, slow down before opening the PR. -->

## Test plan

- [ ] `pytest -v` green
- [ ] `bash scripts/verify-privacy.sh templates/private-vault-skeleton` is 6/6 (if you touched private-vault skeleton or `dual_write.py`)
- [ ] New behavior has a test that fails on `main` and passes here

## Privacy impact

- [ ] No new path from MCP / LLM tools to `private/`
- [ ] No new mandatory cloud dependency

## Scope

- [ ] OSS template (this repo)
- [ ] (Paid-tier proposal — should go to the `second-brain-pro` repo instead)

## Composition note

<!-- If this changes anything about how SBO composes the SIP substrate, link the SIP discussion. -->

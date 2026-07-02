# /reflect — Run the Reflection Engine over brain/

Run the reflection procedure end to end. This is not a summarizer — it produces questions and lenses, never verdicts.

1. **Gather** ~100 highest-signal notes: last-30-day notes + evergreen notes + high link-degree notes. Rank by frontmatter only (dates, tags, backlink count) — no per-note LLM call at this stage. Cheap pass, wide net.
2. **Question** — generate 3-5 salient questions the corpus raises. Questions, not summaries. Read `patterns/{prior-week}-reflection.md` if present and deliberately diversify away from its themes — a reflection that just confirms last week's frame is confirmation-lock, not insight.
3. **Retrieve** cited evidence per question. Every question carries a list of `{source_path, anchor}` pairs pointing at the actual notes that raised it. No evidence, no question.
4. **Synthesize** a lens per question — a way of looking at the evidence, not a conclusion about what's true or what to do. A lens opens a question back up; a verdict closes it. If your synthesis reads like advice or a judgment, rewrite it as a lens.
5. **Verify** — hard gate, no exceptions. Run `/sbo-verify` reflection mode (citation-real / contradiction-queued-for-human / lens-framing / privacy). Anything that fails is dropped, not softened.
6. **Write** survivors to `patterns/{YYYY}-W{ww}-reflection.md`, each question + evidence + lens, closing with the SIP attestation block (`sip_attestation` YAML, see `/sbo-verify`).
7. **Log** a reflection-delta entry: which questions survived, which were rejected and why. The next `/reflect` run loads this delta as context so themes actually move instead of looping.

## Rule

No citation, no lens, no privacy pass — no write. Any candidate question that fails any one of the four verify checks does not reach the file, full stop.

## Notes

- Step 1 is deliberately cheap (frontmatter ranking) so step 2-4 compute goes where it matters — the corpus is the same 100 notes every time, not a re-read of the whole vault.
- Step 5 must run as a distinct critic pass, not a self-check by the model that generated the lenses. See `/sbo-verify`.
- This command never touches `private/`. If a question can only be answered by evidence that lives in `private/`, drop the question — it is not this engine's to answer.

Built on SIP.

---
name: sbo-images
description: >
  Ingest a folder of images into a Second Brain OS vault using Claude vision. 
  Classifies each image, transcribes handwriting, extracts structure, and writes 
  markdown stubs to brain/_inbox/images/. Triggers on: "ingest my notebook photos", 
  "process these images", "import my notebook scans", "classify my photos", 
  "add these screenshots to my vault", "sbo-images", or when the user shares 
  a folder of notebook/note images.
---

# SBO Image Ingestion

Classify and extract thousands of images into your second brain vault using Claude vision.

## Supported sources

- Notebook photos (iPhone camera roll, scanner output)
- Notion page screenshots or HTML exports (contain inline images)
- Obsidian canvas screenshots
- Any JPEG, PNG, GIF, or WEBP

## What I need

1. **Image folder path** — where are the images? (drag-and-drop the folder or provide path)
2. **Vault roots** — `brain/` and `private/` directories
3. **API key** — vision processing requires Anthropic API

## If sbo-images CLI is available

```bash
sbo-images /path/to/image-folder \
  --brain-root "$SBO_BRAIN_VAULT_ROOT" \
  --private-root "$SBO_PRIVATE_VAULT_ROOT" \
  --api-key "$ANTHROPIC_API_KEY" \
  [--recursive]
```

Preview first with `--dry-run`.

## Direct Cowork processing

For each image file in the folder (use bash to list: `ls /path/to/folder/*.{jpg,jpeg,png,webp,gif}`):

Read the image and classify it. For each image, write a stub to `brain/_inbox/images/YYYY-MM-DD-{slug}.md`:

```yaml
---
title: [extracted title — infer from content]
date: [today YYYY-MM-DD]
source_type: image
content_type: [handwritten_note|typed_text|sketch|table|todo_list|journal_entry|meeting_notes|diagram|mixed|illegible]
confidence: [0.0-1.0]
status: triage
tags: [2-6 topic tags, image-import]
people: [names visible in image]
projects: [projects referenced]
date_visible: [date written in image, if any]
private_file: private/images/{content_type}/YYYY-MM-DD-{hash}.jpg
---

[extracted/transcribed content in markdown]

---
*Imported via sbo-images. Review and promote to notes/ via /sbo-distill.*

Built on SIP.
```

Copy the original image to `private/images/{content_type}/YYYY-MM-DD-{hash}{ext}`.

## Content type guide

| Type | Description |
|------|-------------|
| `handwritten_note` | Handwriting — transcribe exactly |
| `typed_text` | Printed/digital text — extract fully |
| `sketch` | Drawing/diagram — describe elements |
| `table` | Tabular data — render as markdown table |
| `todo_list` | Checkboxes/task list — render as `- [ ]` items |
| `journal_entry` | Personal journal — transcribe fully |
| `meeting_notes` | Meeting notes — preserve structure |
| `diagram` | Flow/system/concept diagram — describe + extract labels |
| `mixed` | Multiple types — handle each section appropriately |
| `illegible` | Cannot read — describe what's visible |

## Batch processing note

For large batches (100+ images), process in parallel where possible. Low-confidence images (< 70%) are flagged with `status: needs-review` for manual inspection.

## After ingestion

Run `/sbo-distill` to review stubs and promote to atomic notes.

Built on SIP.

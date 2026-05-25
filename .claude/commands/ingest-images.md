# /ingest-images — Ingest a folder of images into the second brain

You are running as an image ingestion agent. Accept a folder of images (notebook photos, Notion screenshots, Obsidian exports, scans) and process each through the vision pipeline.

## Step 1: Locate images

Ask the user for the image folder path if not already provided. Accept any of:
- Absolute path to a local folder
- Relative path from the vault root
- "Desktop/notebook-photos" style shorthand

Supported formats: JPEG, PNG, GIF, WEBP. Typical sources:
- iPhone camera roll exports to a folder
- Notion: Settings → Export → HTML/Markdown (contains inline images)
- Obsidian: screenshots dropped into a folder
- Flatbed scanner output

## Step 2: Run the pipeline

If the `sbo-images` CLI is installed (check with `sbo-images --help`):

```bash
sbo-images /path/to/image-folder \
  --brain-root "$SBO_BRAIN_VAULT_ROOT" \
  --private-root "$SBO_PRIVATE_VAULT_ROOT" \
  --api-key "$ANTHROPIC_API_KEY" \
  [--recursive]
```

If the CLI is not installed (e.g. running in Cowork without Python setup), process images directly:

For each image file in the folder:
1. Read the image using your vision capabilities
2. Classify content type: handwritten_note | typed_text | sketch | table | todo_list | journal_entry | meeting_notes | diagram | mixed | illegible
3. Extract: title, full content in markdown, tags, people, projects mentioned, any visible date
4. Write to `brain/_inbox/images/YYYY-MM-DD-{slug}.md` with frontmatter:
   ```yaml
   ---
   title: [extracted title]
   date: [today]
   source_type: image
   content_type: [classified type]
   confidence: [0.0-1.0]
   status: triage
   tags: [extracted tags, image-import]
   ---
   ```
5. Copy/note original path as `private_file` reference

## Step 3: Report results

Show a summary table:
```
Processed 12 images:
  ✓ notebook-01.jpg   → handwritten_note (94%)   brain/_inbox/images/2026-05-17-meeting-notes.md
  ✓ screenshot-02.png → typed_text (99%)          brain/_inbox/images/2026-05-17-project-roadmap.md
  ✗ blurry-03.jpg     → illegible (22%)           brain/_inbox/images/2026-05-17-illegible-03.md
  ...
```

Flag low-confidence items (< 70%) for manual review.

## Step 4: Prompt next action

After ingestion, offer:
- "Run /distill-inbox to promote high-quality stubs to atomic notes"
- "Open any stub for manual review"

Built on SIP.

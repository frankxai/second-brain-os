"""sbo-images CLI — ingest a folder of images into the second brain vault.

Pipeline per image:
  1. Classify + extract via Claude vision (Haiku by default)
  2. Copy original to private/images/{content_type}/YYYY-MM-DD-{hash}{ext}
  3. Write markdown stub to brain/_inbox/images/YYYY-MM-DD-{slug}.md
  4. Append event to private/_distill/audit.jsonl

Usage:
  sbo-images /path/to/photos \\
    --brain-root ~/second-brain/brain \\
    --private-root ~/second-brain/private \\
    [--api-key sk-ant-...] [--recursive] [--dry-run]

Env vars:
  ANTHROPIC_API_KEY     — API key (required)
  SBO_BRAIN_VAULT_ROOT  — brain vault root
  SBO_PRIVATE_VAULT_ROOT — private vault root
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import click
import frontmatter

from sbo_ingestion.audit import append as audit_append
from sbo_ingestion.handlers.image import ImageCapture, parse_image_folder


@dataclass
class ImageWriteResult:
    source_path: Path
    private_path: Path
    brain_path: Path
    content_type: str
    title: str
    dry_run: bool


def _slug(text: str) -> str:
    """Simple URL-safe slug from arbitrary text."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")


def _file_hash(path: Path) -> str:
    """Short SHA-1 content hash (8 chars) for deduplication."""
    return hashlib.sha1(path.read_bytes()).hexdigest()[:8]


def _build_brain_body(capture: ImageCapture) -> str:
    """Build the markdown body for the brain _inbox stub."""
    lines: list[str] = []
    if capture.people:
        lines.append(f"**People:** {', '.join(capture.people)}")
    if capture.projects:
        lines.append(f"**Projects:** {', '.join(capture.projects)}")
    if capture.date_visible:
        lines.append(f"**Date in image:** {capture.date_visible}")
    if lines:
        lines.append("")
    lines.append(capture.body_md)
    lines.append("")
    lines.append("---")
    lines.append(
        "*Imported via sbo-images. "
        "Review and promote to notes/ when ready via /distill-inbox.*"
    )
    lines.append("")
    lines.append("Built on SIP.")
    return "\n".join(lines)


def write_image_pair(
    capture: ImageCapture,
    *,
    brain_root: Path,
    private_root: Path,
    dry_run: bool = False,
) -> ImageWriteResult:
    """Write private image copy + brain markdown stub for one ImageCapture."""
    today = date.today().isoformat()
    file_hash = _file_hash(capture.source_path)
    suffix = capture.source_path.suffix.lower()
    slug = _slug(capture.title) or file_hash

    private_dir = private_root / "images" / capture.content_type
    private_path = private_dir / f"{today}-{file_hash}{suffix}"

    brain_dir = brain_root / "_inbox" / "images"
    brain_path = brain_dir / f"{today}-{slug}.md"

    if not dry_run:
        private_dir.mkdir(parents=True, exist_ok=True)
        brain_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(capture.source_path, private_path)

        status = "triage" if capture.confidence >= 0.7 else "needs-review"
        post = frontmatter.Post(
            content=_build_brain_body(capture),
            title=capture.title,
            date=today,
            source_type="image",
            content_type=capture.content_type,
            confidence=round(capture.confidence, 2),
            private_file=str(
                private_path.relative_to(private_root.parent)
            ).replace("\\", "/"),
            status=status,
            tags=list(capture.tags) + ["image-import"],
            people=list(capture.people) or None,
            projects=list(capture.projects) or None,
            date_visible=capture.date_visible or None,
        )
        brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")

        audit_append(
            private_root,
            {
                "action": "ingest",
                "conversation_id": file_hash,
                "mode": "api",
                "format": "image",
                "content_type": capture.content_type,
                "raw_path": str(private_path.relative_to(private_root)).replace(
                    "\\", "/"
                ),
                "brain_path": str(brain_path.relative_to(brain_root)).replace(
                    "\\", "/"
                ),
                "confidence": round(capture.confidence, 2),
            },
        )

    return ImageWriteResult(
        source_path=capture.source_path,
        private_path=private_path,
        brain_path=brain_path,
        content_type=capture.content_type,
        title=capture.title,
        dry_run=dry_run,
    )


@click.command()
@click.argument(
    "image_folder",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--brain-root",
    envvar="SBO_BRAIN_VAULT_ROOT",
    required=True,
    type=click.Path(path_type=Path),
    help="Path to brain/ vault root.",
)
@click.option(
    "--private-root",
    envvar="SBO_PRIVATE_VAULT_ROOT",
    required=True,
    type=click.Path(path_type=Path),
    help="Path to private/ vault root.",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default="",
    help="Anthropic API key (required for vision processing).",
)
@click.option(
    "--model",
    default="claude-haiku-4-5-20251001",
    show_default=True,
    help="Claude vision model to use.",
)
@click.option(
    "--recursive",
    is_flag=True,
    default=False,
    help="Walk subdirectories of IMAGE_FOLDER.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview without writing any files.",
)
def cli(
    image_folder: Path,
    brain_root: Path,
    private_root: Path,
    api_key: str,
    model: str,
    recursive: bool,
    dry_run: bool,
) -> None:
    """Ingest a folder of images into the second brain vault.

    For each supported image (JPEG, PNG, GIF, WEBP):
    classifies content type, extracts text/structure via Claude vision,
    copies original to private/images/, writes markdown stub to brain/_inbox/images/.
    """
    if not api_key:
        raise click.UsageError(
            "API key required. Set ANTHROPIC_API_KEY or pass --api-key."
        )

    if dry_run:
        click.echo("[dry-run] No files will be written.\n")

    captures = list(
        parse_image_folder(
            image_folder, api_key=api_key, model=model, recursive=recursive
        )
    )

    if not captures:
        click.echo(
            "No supported images found in folder.\n"
            "Supported formats: JPEG, PNG, GIF, WEBP"
        )
        return

    click.echo(f"Found {len(captures)} image(s). Processing...\n")

    results: list[ImageWriteResult] = []
    errors: list[tuple[Path, Exception]] = []

    for i, capture in enumerate(captures, 1):
        label = f"[{i}/{len(captures)}] {capture.source_path.name}"
        click.echo(
            f"  {label:50s} → {capture.content_type} ({capture.confidence:.0%})"
        )
        try:
            result = write_image_pair(
                capture,
                brain_root=brain_root,
                private_root=private_root,
                dry_run=dry_run,
            )
            results.append(result)
        except Exception as exc:
            errors.append((capture.source_path, exc))
            click.echo(f"    ERROR: {exc}", err=True)

    prefix = "[dry-run] " if dry_run else ""
    click.echo(f"\n{prefix}Done.")
    click.echo(f"  Processed: {len(results)} image(s)")
    if errors:
        click.echo(f"  Errors:    {len(errors)}")
    if not dry_run and results:
        click.echo(f"\n  Brain stubs → {brain_root / '_inbox' / 'images'}/")
        click.echo(f"  Originals   → {private_root / 'images'}/")
        click.echo("\nRun /distill-inbox to review and promote stubs to notes/.")

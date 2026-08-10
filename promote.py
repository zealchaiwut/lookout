"""
promote.py — vault inbox promote command for Lookout.

Converts a triaged inbox file into a structured vault artifact.

Types:
  idea   → vault/ideas/<YYYY-MM-DD>-<slug>.md  (frontmatter note)
  sprint → vault/packs/<YYYY-MM-DD>-<slug>.md  (bulk-create pack)

Usage:
  python promote.py <inbox-file> --type {idea,sprint} [--vault <dir>]

Exit codes:
  0 — success
  1 — file not found, destination exists, or invalid arguments
"""
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent


class PromoteError(ValueError):
    """Raised when promotion cannot proceed."""


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:60]


def _extract_title(content: str, stem: str) -> str:
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return stem.replace("-", " ").replace("_", " ").title()


def _extract_frontmatter_field(content: str, field: str):
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if m:
        fm_match = re.search(rf"^{field}:\s*(.+)$", m.group(1), re.MULTILINE)
        if fm_match:
            return fm_match.group(1).strip()
    return None


def _extract_tags(content: str) -> list:
    raw = _extract_frontmatter_field(content, "tags")
    if raw:
        tags = re.findall(r"[\w-]+", raw)
        return tags
    return []


def _strip_frontmatter(content: str) -> str:
    if content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            return content[end + 5:]
    return content


def _build_idea_note(inbox_content: str, stem: str, now: datetime) -> str:
    title = _extract_title(inbox_content, stem)
    date_str = now.strftime("%Y-%m-%d")
    tags = _extract_tags(inbox_content)
    status = "draft"

    body = _strip_frontmatter(inbox_content).strip()

    lines = [
        "---",
        f"title: {title}",
        f"date: {date_str}",
        f"tags: {tags}",
        f"status: {status}",
        "---",
        "",
        body,
        "",
    ]
    return "\n".join(lines)


def _split_prompts(content: str) -> list:
    """Split inbox content on --- separators, excluding leading context block."""
    parts = re.split(r"(?m)^---$", content)
    return [p.strip() for p in parts if p.strip()]


def _extract_context_and_prompts(inbox_content: str) -> tuple:
    """Return (context_text, [prompt_text, ...])."""
    body = _strip_frontmatter(inbox_content).strip()

    # Remove the first # heading line
    body = re.sub(r"^#\s+.+\n?", "", body, count=1).strip()

    parts = re.split(r"(?m)^---$", body)
    parts = [p.strip() for p in parts]

    if len(parts) <= 1:
        return parts[0] if parts else "", []

    context = parts[0]
    prompts = [p for p in parts[1:] if p]
    return context, prompts


def _build_sprint_pack(inbox_content: str, stem: str, now: datetime) -> str:
    title = _extract_title(inbox_content, stem)
    date_str = now.strftime("%Y-%m-%d")

    sprint_label = _extract_frontmatter_field(inbox_content, "sprint") or "NEW"
    default_labels = _extract_frontmatter_field(inbox_content, "labels") or "enhancement"

    context, prompts = _extract_context_and_prompts(inbox_content)

    prompts_block = "\n\n---\n\n".join(prompts) if prompts else ""

    lines = [
        f"# {title}",
        "",
        f"**Date:** {date_str}",
        f"**Sprint label:** {sprint_label}",
        f"**Default labels:** {default_labels}",
        "**Status:** drafted",
        "",
        "## Context",
        "",
        context if context else "_No context provided._",
        "",
        "## Prompts",
        "",
        "```",
        prompts_block,
        "```",
        "",
        "## Posted issues",
        "",
        "| # | Title | Size |",
        "|---|-------|------|",
        "",
    ]
    return "\n".join(lines)


def validate_bulk_create_pack(content: str) -> list:
    """Return a list of validation error strings; empty list means valid."""
    errors = []

    required_fields = [
        (r"\*\*Date:\*\*", "**Date:**"),
        (r"\*\*Sprint label:\*\*", "**Sprint label:**"),
        (r"\*\*Default labels:\*\*", "**Default labels:**"),
        (r"\*\*Status:\*\*", "**Status:**"),
    ]
    for pattern, label in required_fields:
        if not re.search(pattern, content):
            errors.append(f"Missing required field: {label}")

    if "## Prompts" not in content:
        errors.append("Missing ## Prompts section")
    elif not re.search(r"```", content):
        errors.append("## Prompts section missing fenced code block")

    if "## Posted issues" not in content:
        errors.append("Missing ## Posted issues section")
    elif not re.search(r"\|[-| ]+\|", content):
        errors.append("## Posted issues section missing table separator row")

    return errors


def promote(
    inbox_file: Path,
    promote_type: str,
    vault_dir: Path = None,
    now: datetime = None,
) -> Path:
    """Promote an inbox file to a structured vault artifact.

    Raises:
        FileNotFoundError: inbox_file does not exist
        PromoteError: destination already exists or invalid type
    """
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    if now is None:
        now = datetime.now(timezone.utc)

    if not inbox_file.exists():
        raise FileNotFoundError(f"Inbox file not found: {inbox_file}")

    content = inbox_file.read_text()
    stem = inbox_file.stem
    date_str = now.strftime("%Y-%m-%d")
    slug = _slugify(_extract_title(content, stem))

    if promote_type == "idea":
        dest_dir = vault_dir / "ideas"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{date_str}-{slug}.md"
        if dest.exists():
            raise PromoteError(f"Destination already exists: {dest}")
        dest.write_text(_build_idea_note(content, stem, now))
        return dest

    if promote_type == "sprint":
        dest_dir = vault_dir / "packs"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{date_str}-{slug}.md"
        if dest.exists():
            raise PromoteError(f"Destination already exists: {dest}")
        dest.write_text(_build_sprint_pack(content, stem, now))
        return dest

    raise PromoteError(f"Unknown promote type: {promote_type!r}. Must be 'idea' or 'sprint'.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote a vault inbox file to a structured artifact"
    )
    parser.add_argument("inbox_file", help="Path to the inbox file to promote")
    parser.add_argument(
        "--type", dest="promote_type", required=True,
        choices=["idea", "sprint"],
        help="Type of artifact to generate",
    )
    parser.add_argument(
        "--vault",
        default=str(REPO_ROOT / "vault"),
        help="Path to vault directory",
    )
    args = parser.parse_args()

    inbox_file = Path(args.inbox_file)
    vault_dir = Path(args.vault)

    try:
        result = promote(inbox_file, args.promote_type, vault_dir=vault_dir)
        print(f"Promoted: {result}")
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except PromoteError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

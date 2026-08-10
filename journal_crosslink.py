"""
journal_crosslink.py — journal cross-link writer for Lookout.

Reads journal_delta.json, finds entries that mention each registered target,
and for each target with mentions:
  1. Updates vault/projects/<target>/SKILL.md with a "## From the journal"
     section containing one dated link per distinct date.
  2. Appends new rows to vault/journal/index.md, one per distinct date,
     tagged with the target name.

Dated link format in SKILL.md:
  [YYYY-MM-DD](relative/path/to/entry.md) — one-line gist

Row format in vault/journal/index.md:
  - [YYYY-MM-DD](path) target-name — gist

Usage:
  python journal_crosslink.py [--delta <path>] [--vault <dir>]

Exit codes:
  0 — always
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_SECTION_HEADER = "## From the journal"
_GIST_MAX = 100


def _load_targets_from_yaml(targets_yaml: Path) -> dict:
    with open(targets_yaml) as f:
        data = yaml.safe_load(f)
    return data.get("targets", {})


def _entries_for_target(entries: list, target_name: str) -> list:
    """Return entries where target_lines mentions the target (case-insensitive)."""
    lower = target_name.lower()
    result = []
    for entry in entries:
        for line in entry.get("target_lines", []):
            if lower in line.lower():
                result.append(entry)
                break
    return result


def _gist_for_target(entry: dict, target_name: str) -> str:
    """Return the first target_line that mentions target, truncated to _GIST_MAX chars."""
    lower = target_name.lower()
    for line in entry.get("target_lines", []):
        if lower in line.lower():
            gist = line.strip()
            if len(gist) > _GIST_MAX:
                gist = gist[:_GIST_MAX] + "…"
            return gist
    return ""


def _deduplicate_by_date(entries: list) -> list:
    """Return one entry per distinct date (earliest path wins)."""
    seen = {}
    for entry in sorted(entries, key=lambda e: e.get("date", "")):
        date = entry.get("date", "")
        if date and date not in seen:
            seen[date] = entry
    return list(seen.values())


def _build_skill_md_section(entries: list, target_name: str) -> str:
    """Build the From the journal section content (without the header)."""
    lines = []
    for entry in entries:
        date = entry.get("date", "")
        path = entry.get("path", "")
        # Path relative from vault/projects/<target>/SKILL.md to journal entry
        link_path = f"../../journal/entries/{path}" if path else "#"
        gist = _gist_for_target(entry, target_name)
        lines.append(f"[{date}]({link_path}) — {gist}")
    return "\n".join(lines)


def _update_skill_md(skill_md_path: Path, section_body: str) -> None:
    """Update or create SKILL.md, replacing or appending the From the journal section."""
    skill_md_path.parent.mkdir(parents=True, exist_ok=True)

    if skill_md_path.exists():
        content = skill_md_path.read_text()
    else:
        content = f"# {skill_md_path.parent.name}\n\n"

    new_section = f"{_SECTION_HEADER}\n\n{section_body}\n"

    if _SECTION_HEADER in content:
        # Replace existing section — from header to next ## heading or end of file
        content = re.sub(
            r"## From the journal\n.*?(?=\n## |\Z)",
            new_section,
            content,
            flags=re.DOTALL,
        )
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"\n{new_section}"

    skill_md_path.write_text(content)


def _already_in_index(index_content: str, date: str, target_name: str) -> bool:
    """True if vault/journal/index.md already has a row for this date+target."""
    for line in index_content.splitlines():
        if date in line and target_name in line:
            return True
    return False


def _append_index_rows(index_path: Path, entries: list, target_name: str) -> None:
    """Append new rows to vault/journal/index.md for each entry date."""
    if not index_path.exists():
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("# Journal\n")

    content = index_path.read_text()

    new_rows = []
    for entry in entries:
        date = entry.get("date", "")
        path = entry.get("path", "")
        gist = _gist_for_target(entry, target_name)
        link_path = f"entries/{path}" if path else "#"

        if _already_in_index(content, date, target_name):
            continue

        row = f"- [{date}]({link_path}) {target_name} — {gist}"
        new_rows.append(row)

    if new_rows:
        if content and not content.endswith("\n"):
            content += "\n"
        content += "\n".join(new_rows) + "\n"
        index_path.write_text(content)


def crosslink(
    delta: dict | None = None,
    delta_path: Path | None = None,
    vault_dir: Path | None = None,
    targets: dict | None = None,
    targets_yaml: Path | None = None,
) -> None:
    """Run the journal cross-link step.

    Args:
        delta: parsed journal_delta.json data (or read from delta_path)
        delta_path: path to journal_delta.json (default: REPO_ROOT/journal_delta.json)
        vault_dir: path to the vault directory (default: REPO_ROOT/vault)
        targets: dict mapping target names to config (or read from targets_yaml)
        targets_yaml: path to targets.yaml (default: TARGETS_YAML)
    """
    if delta is None:
        if delta_path is None:
            delta_path = REPO_ROOT / "journal_delta.json"
        try:
            delta = json.loads(delta_path.read_text())
        except (OSError, json.JSONDecodeError):
            return

    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"

    if targets is None:
        _yaml = targets_yaml or TARGETS_YAML
        try:
            targets = _load_targets_from_yaml(_yaml)
        except (OSError, Exception):
            targets = {}

    entries = delta.get("entries", [])
    if not entries:
        return

    index_path = vault_dir / "journal" / "index.md"

    for target_name in targets:
        target_entries = _entries_for_target(entries, target_name)
        if not target_entries:
            continue

        unique_entries = _deduplicate_by_date(target_entries)
        section_body = _build_skill_md_section(unique_entries, target_name)

        skill_md = vault_dir / "projects" / target_name / "SKILL.md"
        _update_skill_md(skill_md, section_body)
        _append_index_rows(index_path, unique_entries, target_name)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write journal cross-links into SKILL.md and vault/journal/index.md"
    )
    parser.add_argument(
        "--delta",
        default=str(REPO_ROOT / "journal_delta.json"),
        help="Path to journal_delta.json",
    )
    parser.add_argument(
        "--vault",
        default=str(REPO_ROOT / "vault"),
        help="Path to vault directory",
    )
    args = parser.parse_args()

    crosslink(
        delta_path=Path(args.delta),
        vault_dir=Path(args.vault),
    )


if __name__ == "__main__":
    main()

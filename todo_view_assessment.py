"""
todo_view_assessment.py — Enriches todo-view.md with effort and blocked-by annotations.

Reads todo-view.md, matches each Notion todo against atlas features in the vault,
and appends lookout annotation comments (<!-- lookout: ... -->) with:
  - effort: S, M, or L — derived from atlas feature file count (grounded evidence)
  - blocked-by: <files> — derived from Mermaid flowchart edges in the atlas note

No Notion API write calls are made. This is a pure read-and-annotate pass.

Annotation format:
  <!-- lookout: effort: M | source: perf-coach/atlas/weight-tracking -->
  <!-- lookout: blocked-by: weight_ewma.py, weight_trend_rate.py | source: perf-coach/atlas/weight-tracking -->

File header added once to document the annotation convention.

Usage:
  python todo_view_assessment.py [--todo-view <path>] [--vault <path>] [--output <path>]
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent

_LOOKOUT_LINE_RE = re.compile(r"\s*<!--\s*lookout:.*?-->\s*\n?")
_TODO_LINE_RE = re.compile(r"^([ \t]*- \[[ x]\] )(.+)$", re.MULTILINE)
_FM_RE = re.compile(r"^---\n(.*?)---\n", re.DOTALL)
_MERMAID_EDGE_RE = re.compile(
    r"\[([^\]]+)\]\s*-->\s*\w+\[([^\]]+)\]"
)
_MERMAID_BLOCK_RE = re.compile(
    r"```mermaid\n(.*?)```", re.DOTALL
)

_CONVENTION_HEADER = (
    "<!-- lookout-annotations: effort and blocked-by are derived from atlas evidence "
    "in vault/projects/*/atlas/; managed by todo_view_assessment.py — do not edit manually -->"
)


# ---------------------------------------------------------------------------
# Atlas note parsing
# ---------------------------------------------------------------------------

def _parse_yaml_list(lines: str) -> list[str]:
    """Parse a simple YAML list (indented '- item' lines)."""
    result = []
    for line in lines.splitlines():
        m = re.match(r"^\s*-\s+(.+)$", line)
        if m:
            result.append(m.group(1).strip())
    return result


def _parse_atlas_frontmatter(text: str) -> dict:
    """Extract fields from atlas note YAML frontmatter."""
    m = _FM_RE.match(text)
    if not m:
        return {}
    fm_body = m.group(1)
    result: dict = {}

    # Handle multi-line fields (files_read as YAML list)
    lines = fm_body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if not rest:
                # Multi-line list follows
                list_lines = []
                i += 1
                while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("-")):
                    list_lines.append(lines[i])
                    i += 1
                result[key] = _parse_yaml_list("\n".join(list_lines))
                continue
            else:
                result[key] = rest
        i += 1
    return result


def _extract_mermaid_targets(text: str) -> list[str]:
    """Return unique filenames that are targets of flowchart edges (dependencies)."""
    targets = []
    for block_match in _MERMAID_BLOCK_RE.finditer(text):
        block = block_match.group(1)
        for edge_match in _MERMAID_EDGE_RE.finditer(block):
            # Group 2 is the target node label (e.g. "weight_ewma.py")
            target_label = edge_match.group(2).strip()
            if target_label not in targets:
                targets.append(target_label)
    return targets


# ---------------------------------------------------------------------------
# Effort derivation
# ---------------------------------------------------------------------------

def _derive_effort(fm: dict) -> str:
    """Return S, M, or L based on atlas evidence."""
    stale = str(fm.get("stale", "true")).lower() == "true"
    if stale:
        return "S"
    files_read = fm.get("files_read", [])
    if not isinstance(files_read, list):
        return "S"
    n = len(files_read)
    if n <= 1:
        return "S"
    if n <= 3:
        return "M"
    return "L"


# ---------------------------------------------------------------------------
# Vault feature index
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, collapse spaces, strip non-alphanumeric."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_atlas_index(vault_dir: Path) -> list[tuple[str, str, Path]]:
    """Return list of (normalized_feature_name, source_ref, atlas_note_path)."""
    index = []
    projects_dir = vault_dir / "projects"
    if not projects_dir.is_dir():
        return index
    for project_dir in sorted(projects_dir.iterdir()):
        atlas_dir = project_dir / "atlas"
        if not atlas_dir.is_dir():
            continue
        for note_path in sorted(atlas_dir.glob("*.md")):
            if note_path.name == "index.md":
                continue
            try:
                text = note_path.read_text(encoding="utf-8")
            except OSError:
                continue
            fm = _parse_atlas_frontmatter(text)
            feature_name = fm.get("feature", "")
            if not feature_name:
                continue
            source_ref = f"{project_dir.name}/atlas/{note_path.stem}"
            index.append((_normalize(feature_name), source_ref, note_path))
    return index


def _find_best_match(
    todo_title: str,
    atlas_index: list[tuple[str, str, Path]],
) -> tuple[str, Path] | None:
    """Return (source_ref, note_path) for the best-matching atlas feature, or None."""
    norm = _normalize(todo_title)
    # Exact match first
    for feat_norm, source_ref, note_path in atlas_index:
        if feat_norm == norm:
            return source_ref, note_path
    # Substring match (todo title contained in feature name or vice versa)
    for feat_norm, source_ref, note_path in atlas_index:
        if norm in feat_norm or feat_norm in norm:
            return source_ref, note_path
    return None


# ---------------------------------------------------------------------------
# Annotation builder
# ---------------------------------------------------------------------------

def _build_annotations(
    todo_title: str,
    atlas_index: list[tuple[str, str, Path]],
) -> list[str]:
    """Return a list of lookout comment lines to append after a todo."""
    match = _find_best_match(todo_title, atlas_index)
    if match is None:
        return []

    source_ref, note_path = match
    try:
        text = note_path.read_text(encoding="utf-8")
    except OSError:
        return []

    fm = _parse_atlas_frontmatter(text)
    effort = _derive_effort(fm)
    targets = _extract_mermaid_targets(text)

    lines = [f"  <!-- lookout: effort: {effort} | source: {source_ref} -->"]
    if targets:
        deps = ", ".join(targets)
        lines.append(f"  <!-- lookout: blocked-by: {deps} | source: {source_ref} -->")

    return lines


# ---------------------------------------------------------------------------
# Core annotation pass
# ---------------------------------------------------------------------------

def annotate_todo_view(content: str, vault_dir: Path) -> str:
    """Annotate todo-view.md content with effort and blocked-by lookout comments.

    Idempotent: strips existing lookout annotations before re-applying.
    """
    # Strip existing lookout annotation lines (idempotency)
    content = re.sub(r"[ \t]*<!--\s*lookout:.*?-->\n?", "", content)
    # Strip existing convention header (and all blank lines it leaves behind)
    content = re.sub(r"<!--\s*lookout-annotations:.*?-->\n*", "", content)

    atlas_index = _build_atlas_index(vault_dir)

    def _replace_todo(m: re.Match) -> str:
        prefix = m.group(1)
        title = m.group(2).strip()
        annotations = _build_annotations(title, atlas_index)
        result = m.group(0)
        if annotations:
            result += "\n" + "\n".join(annotations)
        return result

    annotated = _TODO_LINE_RE.sub(_replace_todo, content)

    # Prepend convention header if any annotations were added
    if "<!-- lookout:" in annotated:
        annotated = _CONVENTION_HEADER + "\n\n" + annotated

    return annotated


# ---------------------------------------------------------------------------
# File-level pass
# ---------------------------------------------------------------------------

def run_todo_view_assessment(
    todo_view_path: Path,
    vault_dir: Path,
    output_path: Path | None = None,
) -> None:
    """Read todo-view.md, annotate, and write back (or to output_path)."""
    content = todo_view_path.read_text(encoding="utf-8")
    annotated = annotate_todo_view(content, vault_dir)
    dest = output_path or todo_view_path
    dest.write_text(annotated, encoding="utf-8")
    print(f"Assessment pass complete: {dest}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enrich todo-view.md with effort and blocked-by annotations from atlas evidence."
    )
    parser.add_argument(
        "--todo-view", type=Path,
        default=REPO_ROOT / "vault" / "todo-view.md",
        help="Path to todo-view.md (default: vault/todo-view.md)",
    )
    parser.add_argument(
        "--vault", type=Path,
        default=REPO_ROOT / "vault",
        help="Path to vault/ root",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output path (default: overwrite --todo-view in place)",
    )
    args = parser.parse_args()

    if not args.todo_view.exists():
        print(f"ERROR: todo-view file not found: {args.todo_view}", file=sys.stderr)
        return 1

    run_todo_view_assessment(args.todo_view, args.vault, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

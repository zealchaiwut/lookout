"""ideas_ledger.py — Idea note validator and ledger regenerator.

Convention:
  One file per idea at vault/ideas/<YYYY-MM-DD>-<slug>.md

Frontmatter fields (all required):
  slug       — string identifier
  created    — ISO date (YYYY-MM-DD)
  status     — one of: idea | assessed | promoted | shipped | parked
  targets    — list of target names
  issues     — list of linked issue numbers
  assessed   — ISO date or null

Body sections:
  Freeform top  — human-written, never machine-edited (everything above the delimiter)
  Assessment    — machine-owned, below <!-- BEGIN MACHINE ASSESSMENT -->

Usage:
  python ideas_ledger.py [--ideas-dir <path>]

Exit codes:
  0 — all notes valid, ledger regenerated
  1 — one or more validation errors
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).parent
_DEFAULT_IDEAS_DIR = REPO_ROOT / "vault" / "ideas"

VALID_STATUSES = {"idea", "assessed", "promoted", "shipped", "parked"}
MACHINE_DELIMITER = "<!-- BEGIN MACHINE ASSESSMENT -->"

_FM_RE = re.compile(r"^---\n(.*?)---\n", re.DOTALL)
_KV_RE = re.compile(r"^(\w+):\s*(.*)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict | None:
    m = _FM_RE.match(text)
    if not m:
        return None
    fm_body = m.group(1)
    result: dict = {}
    for kv in _KV_RE.finditer(fm_body):
        key = kv.group(1)
        val = kv.group(2).strip()
        # Minimal list parsing: [a, b] or []
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                result[key] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
        else:
            result[key] = val if val not in ("null", "~", "") else None
    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ("slug", "created", "status", "targets", "issues", "assessed")


def validate_note(path: Path) -> list[str]:
    """Return a list of human-readable error strings; empty list means valid."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"{path.name}: cannot read file: {exc}"]

    fm = _parse_frontmatter(text)
    errors: list[str] = []

    if fm is None:
        errors.append(f"{path.name}: missing or malformed YAML frontmatter (--- block)")
        return errors

    for field in REQUIRED_FIELDS:
        if field not in fm:
            errors.append(f"{path.name}: missing required frontmatter field '{field}'")

    if "status" in fm:
        status = fm["status"]
        if status not in VALID_STATUSES:
            errors.append(
                f"{path.name}: invalid status '{status}' "
                f"(must be one of: {', '.join(sorted(VALID_STATUSES))})"
            )

    return errors


# ---------------------------------------------------------------------------
# Ledger regeneration
# ---------------------------------------------------------------------------

def _age_string(created_str: str, today: date) -> str:
    try:
        created = date.fromisoformat(str(created_str))
        days = (today - created).days
        return f"{days}d"
    except Exception:
        return "—"


def regenerate_ledger(ideas_dir: Path, today: date | None = None) -> Path:
    """Regenerate vault/ideas/index.md from all .md files in ideas_dir.

    Idea note files are never modified; only index.md is written.
    Returns the path to index.md.
    """
    if today is None:
        today = date.today()

    idea_files = sorted(
        f for f in ideas_dir.glob("*.md") if f.name != "index.md"
    )

    rows: list[dict] = []
    for idea_path in idea_files:
        try:
            text = idea_path.read_text(encoding="utf-8")
        except Exception:
            continue
        fm = _parse_frontmatter(text)
        if not fm:
            continue
        slug = fm.get("slug") or idea_path.stem
        status = fm.get("status") or "—"
        effort = fm.get("effort") or "—"
        blocked_by = fm.get("blocked_by") or "—"
        age = _age_string(fm.get("created"), today)
        rows.append({
            "slug": slug,
            "status": status,
            "effort": effort,
            "blocked_by": blocked_by,
            "age": age,
        })

    lines = ["# Ideas\n", "\n"]
    lines.append("| Idea | Status | Effort | Blocked-by | Age |\n")
    lines.append("|------|--------|--------|------------|-----|\n")
    for row in rows:
        lines.append(
            f"| {row['slug']} | {row['status']} | {row['effort']} "
            f"| {row['blocked_by']} | {row['age']} |\n"
        )

    index_path = ideas_dir / "index.md"
    index_path.write_text("".join(lines), encoding="utf-8")
    return index_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Idea note validator and ledger regenerator")
    parser.add_argument(
        "--ideas-dir",
        type=Path,
        default=_DEFAULT_IDEAS_DIR,
        help=f"Path to vault/ideas/ directory (default: {_DEFAULT_IDEAS_DIR})",
    )
    args = parser.parse_args()

    ideas_dir = args.ideas_dir.resolve()
    if not ideas_dir.is_dir():
        print(f"ERROR: ideas directory not found: {ideas_dir}", file=sys.stderr)
        return 1

    idea_files = sorted(f for f in ideas_dir.glob("*.md") if f.name != "index.md")
    all_errors: list[str] = []
    for idea_path in idea_files:
        errors = validate_note(idea_path)
        all_errors.extend(errors)

    if all_errors:
        for err in all_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    index_path = regenerate_ledger(ideas_dir)
    print(f"Ledger regenerated: {index_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""ship_pass.py — Idea ship tracking pass.

For each idea with status=promoted and a non-empty issues list:
  - Loads the current open/closed state of each linked issue from the latest
    target snapshots in vault/projects/*/raw/<latest>/issues.json.
  - If all listed issues are closed, advances status to 'shipped'.
  - If any issues remain open, keeps status 'promoted' and writes a per-issue
    state table into the Assessment section.

Usage:
  python ship_pass.py [--ideas-dir <path>] [--vault <path>]

Exit codes:
  0 — pass completed
  1 — fatal error (cannot read ideas directory)
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
_DEFAULT_IDEAS_DIR = REPO_ROOT / "vault" / "ideas"
_DEFAULT_VAULT_DIR = REPO_ROOT / "vault"

MACHINE_DELIMITER = "<!-- BEGIN MACHINE ASSESSMENT -->"
MACHINE_END = "<!-- END MACHINE ASSESSMENT -->"

_ISSUE_TABLE_START = "<!-- BEGIN ISSUE STATE TABLE -->"
_ISSUE_TABLE_END = "<!-- END ISSUE STATE TABLE -->"

_FM_RE = re.compile(r"^---\n(.*?)---\n", re.DOTALL)
_KV_RE = re.compile(r"^(\w+):\s*(.*)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Frontmatter helpers
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
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                result[key] = [
                    x.strip().strip("'\"") for x in inner.split(",") if x.strip()
                ]
        else:
            result[key] = val if val not in ("null", "~", "") else None
    return result


def _write_frontmatter_field(text: str, field: str, value: str) -> str:
    m = _FM_RE.match(text)
    if not m:
        return text
    fm_body = m.group(1)
    new_fm_body, count = re.subn(
        rf"^{re.escape(field)}:.*$", f"{field}: {value}", fm_body,
        flags=re.MULTILINE,
    )
    if not count:
        new_fm_body = fm_body.rstrip("\n") + f"\n{field}: {value}\n"
    return f"---\n{new_fm_body}---\n" + text[m.end():]


# ---------------------------------------------------------------------------
# Snapshot reading
# ---------------------------------------------------------------------------

def load_issue_states(vault_dir: Path) -> dict:
    """Return {issue_number: {number, title, state}} from all target snapshots.

    Reads the most recent snapshot directory per target and aggregates all
    issues found in their issues.json files.
    """
    states: dict = {}
    projects_dir = vault_dir / "projects"
    if not projects_dir.exists():
        return states
    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        raw_dir = proj_dir / "raw"
        if not raw_dir.exists():
            continue
        snapshots = [d for d in raw_dir.iterdir() if d.is_dir()]
        if not snapshots:
            continue
        latest = max(snapshots, key=lambda d: d.name)
        issues_json = latest / "issues.json"
        if not issues_json.exists():
            continue
        try:
            data = json.loads(issues_json.read_text(encoding="utf-8"))
            for issue in data.get("issues", []):
                num = issue.get("number")
                if num is not None:
                    states[int(num)] = {
                        "number": int(num),
                        "title": issue.get("title", ""),
                        "state": issue.get("state", "OPEN").upper(),
                    }
        except Exception:
            continue
    return states


# ---------------------------------------------------------------------------
# Issue table rendering
# ---------------------------------------------------------------------------

def build_issue_table(issue_numbers: list, issue_states: dict) -> str:
    """Build a markdown issue state table block for the given issue numbers."""
    rows = []
    for item in issue_numbers:
        try:
            n = int(item)
        except (ValueError, TypeError):
            continue
        info = issue_states.get(n, {"number": n, "title": "(unknown)", "state": "OPEN"})
        state = info.get("state", "OPEN").lower()
        title = info.get("title", "(unknown)")
        rows.append(f"| #{n} | {title} | {state} |")

    lines = [
        f"{_ISSUE_TABLE_START}\n",
        "## Linked Issues\n",
        "\n",
        "| # | Title | State |\n",
        "|---|-------|-------|\n",
    ]
    for row in rows:
        lines.append(row + "\n")
    lines.append(f"{_ISSUE_TABLE_END}\n")
    return "".join(lines)


def _update_machine_block(text: str, table: str | None) -> str:
    """Add or replace the issue table section within the machine assessment block.

    If table is None, removes any existing issue table (used when shipping).
    """
    start = text.find(MACHINE_DELIMITER)
    end = text.find(MACHINE_END)
    if start == -1:
        return text

    block_content = text[start + len(MACHINE_DELIMITER):end if end != -1 else len(text)]

    # Remove existing issue table
    tbl_start = block_content.find(_ISSUE_TABLE_START)
    tbl_end = block_content.find(_ISSUE_TABLE_END)
    if tbl_start != -1 and tbl_end != -1:
        block_content = (
            block_content[:tbl_start]
            + block_content[tbl_end + len(_ISSUE_TABLE_END):]
        )

    if table:
        block_content = block_content.rstrip("\n") + "\n\n" + table

    if end == -1:
        return text[:start] + MACHINE_DELIMITER + block_content
    return (
        text[:start]
        + MACHINE_DELIMITER
        + block_content
        + MACHINE_END
        + text[end + len(MACHINE_END):]
    )


# ---------------------------------------------------------------------------
# Core pass logic
# ---------------------------------------------------------------------------

def _parse_issue_numbers(issues_raw: list) -> list:
    result = []
    for item in (issues_raw or []):
        try:
            result.append(int(item))
        except (ValueError, TypeError):
            pass
    return result


def check_idea(idea_path: Path, issue_states: dict) -> str | None:
    """Process one promoted idea and update it in place.

    Returns 'shipped' if the status advanced, None otherwise.
    """
    try:
        text = idea_path.read_text(encoding="utf-8")
    except Exception:
        return None

    fm = _parse_frontmatter(text)
    if fm is None or fm.get("status") != "promoted":
        return None

    issue_numbers = _parse_issue_numbers(fm.get("issues"))
    if not issue_numbers:
        return None

    all_closed = all(
        issue_states.get(n, {}).get("state", "OPEN").upper() == "CLOSED"
        for n in issue_numbers
    )

    if all_closed:
        text = _write_frontmatter_field(text, "status", "shipped")
        text = _update_machine_block(text, None)
        idea_path.write_text(text, encoding="utf-8")
        return "shipped"

    table = build_issue_table(issue_numbers, issue_states)
    text = _update_machine_block(text, table)
    idea_path.write_text(text, encoding="utf-8")
    return None


def run_ship_pass(ideas_dir: Path, vault_dir: Path) -> list:
    """Scan all ideas and advance promoted→shipped when all linked issues are closed.

    Returns list of idea paths that were shipped this run.
    """
    idea_files = sorted(f for f in ideas_dir.glob("*.md") if f.name != "index.md")
    issue_states = load_issue_states(vault_dir)

    shipped: list = []
    for idea_path in idea_files:
        result = check_idea(idea_path, issue_states)
        if result == "shipped":
            shipped.append(idea_path)
            print(f"Shipped: {idea_path.name}", flush=True)

    return shipped


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Idea ship tracking pass — advances promoted ideas to shipped "
        "when all linked GitHub issues are closed"
    )
    parser.add_argument(
        "--ideas-dir", type=Path, default=_DEFAULT_IDEAS_DIR,
        help=f"Path to vault/ideas/ (default: {_DEFAULT_IDEAS_DIR})",
    )
    parser.add_argument(
        "--vault", type=Path, default=_DEFAULT_VAULT_DIR,
        help=f"Path to vault/ root (default: {_DEFAULT_VAULT_DIR})",
    )
    args = parser.parse_args()

    ideas_dir = args.ideas_dir.resolve()
    vault_dir = args.vault.resolve()

    if not ideas_dir.is_dir():
        print(f"ERROR: ideas directory not found: {ideas_dir}", file=sys.stderr)
        return 1

    run_ship_pass(ideas_dir, vault_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

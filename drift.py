"""
drift.py — drift detection routine for Lookout.

Reads docs_manifest, gitlog, and the brief, then detects contradictions:

Signal types
------------
removed_feature   — a doc asserts a feature/endpoint that git history shows
                    was removed
todo_still_open   — commander marked a todo done but it still appears open
                    in a doc file
schema_name_diverges — a ## heading in SCHEMA.md does not match any migration
                       file name

Usage
-----
    from drift import detect_drift, emit_drift_md
    flags = detect_drift(docs_manifest=dm, gitlog=gl, brief=brief)
    emit_drift_md(flags=flags, output_path=Path("drift.md"))

Or CLI:
    python drift.py <target-name> [--vault <vault_dir>]
"""
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Signal: removed_feature
# ---------------------------------------------------------------------------

_ENDPOINT_PATTERN = re.compile(
    r"`?(GET|POST|PUT|PATCH|DELETE)\s+(/[^\s`'\"]+)`?",
    re.IGNORECASE,
)

_GIT_REMOVE_VERBS = re.compile(
    r"\b(remov|delet|drop|deprecat|strip|disabl)",
    re.IGNORECASE,
)


def _extract_endpoints_from_content(content: str) -> list[str]:
    return [m.group(0).strip("`").strip() for m in _ENDPOINT_PATTERN.finditer(content)]


def _gitlog_removed_endpoints(gitlog: str) -> dict[str, str]:
    """
    Returns {endpoint: git_line} for endpoints mentioned in removal commits.
    """
    removed: dict[str, str] = {}
    for line in gitlog.splitlines():
        if _GIT_REMOVE_VERBS.search(line):
            for m in _ENDPOINT_PATTERN.finditer(line):
                ep = m.group(0).strip("`").strip()
                removed[ep] = line.strip()
    return removed


def _detect_removed_features(files: list[dict], gitlog: str) -> list[dict]:
    """Detect docs claiming endpoints that git history shows were removed."""
    removed_in_git = _gitlog_removed_endpoints(gitlog)
    if not removed_in_git:
        return []

    flags: list[dict] = []
    for file_entry in files:
        path = file_entry.get("path", "")
        content = file_entry.get("content", "")
        if not content:
            continue
        doc_endpoints = _extract_endpoints_from_content(content)
        for ep in doc_endpoints:
            # Normalize for comparison: compare just the path part
            ep_path = re.sub(r"^(GET|POST|PUT|PATCH|DELETE)\s+", "", ep, flags=re.IGNORECASE).strip()
            for removed_ep, git_line in removed_in_git.items():
                removed_path = re.sub(
                    r"^(GET|POST|PUT|PATCH|DELETE)\s+", "", removed_ep, flags=re.IGNORECASE
                ).strip()
                if ep_path == removed_path or ep_path in removed_path or removed_path in ep_path:
                    # Extract a snippet for the claim
                    claim_snippet = _extract_claim_snippet(content, ep)
                    # Extract git ref (first word of commit line, or "unknown")
                    git_ref = git_line.split()[0] if git_line else "unknown"
                    flags.append(
                        {
                            "signal_type": "removed_feature",
                            "claim": claim_snippet,
                            "evidence_path": f"{path} (doc) + {git_ref} (git)",
                            "suggested_fix": (
                                f"Remove or update the `{ep}` entry in `{path}` — "
                                f"git commit {git_ref} indicates this endpoint was removed."
                            ),
                        }
                    )
    return flags


def _extract_claim_snippet(content: str, endpoint: str) -> str:
    """Return the line containing the endpoint as the verbatim claim."""
    for line in content.splitlines():
        if endpoint in line or re.sub(r"^(GET|POST|PUT|PATCH|DELETE)\s+", "", endpoint, flags=re.IGNORECASE).strip() in line:
            return line.strip()
    return endpoint


# ---------------------------------------------------------------------------
# Signal: todo_still_open
# ---------------------------------------------------------------------------

_OPEN_CHECKBOX = re.compile(r"^[-*]\s+\[\s*\]\s+(.+)$", re.MULTILINE)


def _detect_todo_still_open(files: list[dict], brief: dict) -> list[dict]:
    """Detect todos commander marked done that still appear open in docs."""
    completed = {
        t.lower().strip()
        for t in brief.get("completed_todos", [])
        if isinstance(t, str)
    }
    if not completed:
        return []

    flags: list[dict] = []
    for file_entry in files:
        path = file_entry.get("path", "")
        content = file_entry.get("content", "")
        if not content:
            continue
        open_items = _OPEN_CHECKBOX.findall(content)
        for item in open_items:
            if item.lower().strip() in completed:
                flags.append(
                    {
                        "signal_type": "todo_still_open",
                        "claim": f"- [ ] {item}",
                        "evidence_path": path,
                        "suggested_fix": (
                            f"Mark `{item}` as done (`- [x]`) in `{path}` or remove it — "
                            "commander has already recorded this as completed."
                        ),
                    }
                )
    return flags


# ---------------------------------------------------------------------------
# Signal: schema_name_diverges
# ---------------------------------------------------------------------------

_SCHEMA_HEADING = re.compile(r"^##\s+(\S+)", re.MULTILINE)
_MIGRATION_NAME = re.compile(r"(\w+)(?:\.sql|\.py|\.rb)?$", re.IGNORECASE)


def _normalize_migration_name(filename: str) -> str:
    """Strip prefix digits/underscores and extension from migration filename."""
    stem = Path(filename).stem
    stem = re.sub(r"^\d+[_-]", "", stem)
    return stem.lower()


def _detect_schema_name_diverges(files: list[dict], migration_files: list[str]) -> list[dict]:
    """Detect SCHEMA.md headings whose names don't match any migration file."""
    if not migration_files:
        return []

    migration_names = {_normalize_migration_name(f) for f in migration_files}

    flags: list[dict] = []
    for file_entry in files:
        path = file_entry.get("path", "")
        content = file_entry.get("content", "")
        if not content:
            continue
        if "SCHEMA" not in path.upper() and "schema" not in path.lower():
            continue
        headings = _SCHEMA_HEADING.findall(content)
        for heading in headings:
            normalized = heading.lower().strip()
            # Exact match required — users_v2 != users
            matches = any(normalized == mname for mname in migration_names)
            if not matches:
                flags.append(
                    {
                        "signal_type": "schema_name_diverges",
                        "claim": f"## {heading}",
                        "evidence_path": path,
                        "suggested_fix": (
                            f"Schema heading `{heading}` in `{path}` does not match any "
                            f"migration file name. Known migrations: "
                            f"{', '.join(sorted(migration_files))}. "
                            "Rename either the schema heading or the migration file to match."
                        ),
                    }
                )
    return flags


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_drift(
    docs_manifest: dict,
    gitlog: str,
    brief: dict,
) -> list[dict]:
    """
    Detect contradictions between docs, git history, and the brief.

    Parameters
    ----------
    docs_manifest : dict
        Contains 'files' list (each with 'path' and 'content' keys) and
        optionally 'migration_files' list of migration filenames.
    gitlog : str
        Raw git log text (e.g. from `git log --oneline`).
    brief : dict
        Commander brief data. Checked for 'completed_todos' list.

    Returns
    -------
    list of flag dicts (at most 3), each with:
        signal_type    : str
        claim          : str — verbatim excerpt from the doc
        evidence_path  : str — file path and/or git ref contradicting it
        suggested_fix  : str — plain text fix suggestion
    """
    files = docs_manifest.get("files", [])
    migration_files = docs_manifest.get("migration_files", [])

    all_flags: list[dict] = []
    all_flags.extend(_detect_removed_features(files, gitlog))
    all_flags.extend(_detect_todo_still_open(files, brief))
    all_flags.extend(_detect_schema_name_diverges(files, migration_files))

    # Deduplicate by (signal_type, claim)
    seen: set = set()
    deduped: list[dict] = []
    for flag in all_flags:
        key = (flag["signal_type"], flag["claim"])
        if key not in seen:
            seen.add(key)
            deduped.append(flag)

    return deduped[:3]


def emit_drift_md(flags: list[dict], output_path: Path) -> None:
    """Write drift.md to output_path.

    Each flag entry contains the claim, evidence path, and suggested fix.
    """
    lines = ["# Drift Report", ""]
    if not flags:
        lines.append("_No drift signals detected._")
        lines.append("")
    else:
        for i, flag in enumerate(flags, 1):
            lines.append(f"## Flag {i}: {flag['signal_type'].replace('_', ' ').title()}")
            lines.append("")
            lines.append(f"**Claim:** {flag['claim']}")
            lines.append("")
            lines.append(f"**Evidence:** {flag['evidence_path']}")
            lines.append("")
            lines.append(f"**Suggested fix:** {flag['suggested_fix']}")
            lines.append("")
    output_path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _run_cli(target_name: str, vault_dir: Path | None = None) -> Path:
    """Run drift detection for target and write drift.md."""
    if vault_dir is None:
        vault_dir = Path(__file__).parent / "vault"

    project_dir = vault_dir / "projects" / target_name
    snapshot_dir = _find_latest_snapshot(project_dir)

    if snapshot_dir is None:
        print(f"No snapshot found for target '{target_name}'", file=sys.stderr)
        sys.exit(1)

    import json

    docs_manifest: dict = {}
    dm_path = snapshot_dir / "docs_manifest.json"
    if dm_path.exists():
        docs_manifest = json.loads(dm_path.read_text())

    gitlog = ""
    gl_path = snapshot_dir / "gitlog.txt"
    if gl_path.exists():
        gitlog = gl_path.read_text()

    brief: dict = {}
    brief_path = snapshot_dir / "brief.json"
    if brief_path.exists():
        raw = json.loads(brief_path.read_text())
        brief = raw.get("brief", {})

    flags = detect_drift(docs_manifest=docs_manifest, gitlog=gitlog, brief=brief)

    output_path = project_dir / "drift.md"
    emit_drift_md(flags=flags, output_path=output_path)
    print(f"Wrote {output_path} ({len(flags)} flag(s))")
    return output_path


def _find_latest_snapshot(project_dir: Path) -> Path | None:
    raw_dir = project_dir / "raw"
    if not raw_dir.exists():
        return None
    dirs = sorted(
        d for d in raw_dir.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )
    return dirs[-1] if dirs else None


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python drift.py <target-name> [--vault <vault_dir>]", file=sys.stderr)
        sys.exit(1)
    target = sys.argv[1]
    vault_dir = None
    if "--vault" in sys.argv:
        idx = sys.argv.index("--vault")
        vault_dir = Path(sys.argv[idx + 1])
    _run_cli(target, vault_dir)


if __name__ == "__main__":
    main()

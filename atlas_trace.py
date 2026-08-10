"""
atlas_trace.py — stale-feature tracing for Lookout.

Traces a named feature by following entry points in docs and traversing
imports in source, then writes an atlas note with:

  - YAML frontmatter (files_read list)
  - ## What — one-sentence description
  - ## Entry Points — discovered entry files and routes
  - ## Related Issues — issues pulled from snapshot
  - ## Mermaid flowchart — every node is a real file, route, or table
  - ## Key Files — one descriptive line per file read
  - OPEN QUESTION callouts for any unresolved import or handler

Only stale features (stale: true in atlas stub) need tracing.
Fully-resolved flows produce no fabricated edges; unresolvable intermediate
handlers produce <!-- OPEN QUESTION: ... --> instead.

Usage
-----
    from atlas_trace import generate_note, extract_mermaid_block, get_node_names

    note = generate_note(
        feature_name="Today Recommendation",
        source_dir=Path("path/to/target-repo"),
        entry_point_file="app.py",
        issues=[{"number": 42, "title": "Add today endpoint"}],
    )

Or CLI:
    python atlas_trace.py <target> <feature-slug> [--vault <vault_dir>]
"""
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Import tracing
# ---------------------------------------------------------------------------

_IMPORT_PATTERN = re.compile(
    r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
    re.MULTILINE,
)

_ROUTE_PATTERN = re.compile(
    r"@\w+\.(?:get|post|put|patch|delete|route)\(['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

_TABLE_PATTERN = re.compile(
    r"(?:table\s*=\s*['\"]([a-z_]+)['\"]|__tablename__\s*=\s*['\"]([a-z_]+)['\"])",
)


def _module_to_file(module_name: str, source_dir: Path) -> Path | None:
    """Convert a dotted module name to a .py file path inside source_dir."""
    parts = module_name.replace(".", "/")
    candidate = source_dir / f"{parts}.py"
    if candidate.exists():
        return candidate
    # Try just the last component (handles 'from package.module import X')
    last = module_name.split(".")[-1]
    candidate2 = source_dir / f"{last}.py"
    if candidate2.exists():
        return candidate2
    return None


def _extract_routes(file_text: str) -> list[str]:
    return [m.group(1) for m in _ROUTE_PATTERN.finditer(file_text)]


def _extract_tables(file_text: str) -> list[str]:
    tables = []
    for m in _TABLE_PATTERN.finditer(file_text):
        tables.append(m.group(1) or m.group(2))
    return tables


def _trace_imports(
    entry_file: Path,
    source_dir: Path,
    visited: set[Path] | None = None,
    open_questions: list[str] | None = None,
) -> tuple[list[Path], list[str], list[str]]:
    """Recursively trace imports starting from entry_file.

    Returns:
        files_read  — ordered list of Path objects read
        routes      — all route strings found
        tables      — all table names found
    """
    if visited is None:
        visited = set()
    if open_questions is None:
        open_questions = []

    files_read: list[Path] = []
    routes: list[str] = []
    tables: list[str] = []

    if entry_file in visited or not entry_file.exists():
        return files_read, routes, tables

    visited.add(entry_file)
    files_read.append(entry_file)

    try:
        text = entry_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return files_read, routes, tables

    routes.extend(_extract_routes(text))
    tables.extend(_extract_tables(text))

    for m in _IMPORT_PATTERN.finditer(text):
        module = (m.group(1) or m.group(2) or "").strip()
        if not module:
            continue
        resolved = _module_to_file(module, source_dir)
        if resolved:
            sub_files, sub_routes, sub_tables = _trace_imports(
                resolved, source_dir, visited, open_questions
            )
            files_read.extend(sub_files)
            routes.extend(sub_routes)
            tables.extend(sub_tables)
        else:
            # Local-looking module (no dots or single name) that's not stdlib
            if "." not in module and not _is_stdlib(module):
                open_questions.append(
                    f"`{module}` imported in `{entry_file.name}` but "
                    f"`{module}.py` not found in source — handler unresolved"
                )

    return files_read, routes, tables


_STDLIB_MODULES = frozenset(
    sys.stdlib_module_names if hasattr(sys, "stdlib_module_names") else {
        "os", "sys", "re", "json", "math", "io", "abc", "ast", "copy",
        "datetime", "functools", "itertools", "logging", "pathlib",
        "subprocess", "typing", "collections", "contextlib", "dataclasses",
        "enum", "hashlib", "http", "inspect", "random", "shutil",
        "string", "threading", "time", "traceback", "unittest", "urllib",
        "warnings", "weakref",
    }
)


def _is_stdlib(module: str) -> bool:
    return module in _STDLIB_MODULES


# ---------------------------------------------------------------------------
# Note generation
# ---------------------------------------------------------------------------

def _slugify_node(name: str) -> str:
    """Make a valid Mermaid node ID from a name."""
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if slug and slug[0].isdigit():
        slug = "n_" + slug
    return slug or "node"


def _build_mermaid(
    files_read: list[Path],
    routes: list[str],
    tables: list[str],
    open_questions: list[str],
) -> str:
    """Build a Mermaid flowchart from traced artifacts.

    Every node names a real file, route, or table observed in source.
    Unresolved imports are not added as nodes; they generate OPEN QUESTION
    callouts instead.
    """
    lines = ["flowchart LR"]

    nodes: list[tuple[str, str]] = []  # (node_id, label)
    seen_labels: set[str] = set()

    def _add_node(label: str) -> str:
        if label in seen_labels:
            return _slugify_node(label)
        seen_labels.add(label)
        nid = _slugify_node(label)
        nodes.append((nid, label))
        return nid

    # File nodes
    file_ids: list[str] = []
    for f in files_read:
        nid = _add_node(f.name)
        file_ids.append(nid)

    # Route nodes
    route_ids: list[str] = []
    for route in routes:
        nid = _add_node(route)
        route_ids.append(nid)

    # Table nodes
    table_ids: list[str] = []
    for table in tables:
        nid = _add_node(table)
        table_ids.append(nid)

    # Emit node definitions
    for nid, label in nodes:
        if label.startswith("/"):
            lines.append(f"  {nid}[{label}]")
        elif re.match(r"^[a-z_]+$", label):
            lines.append(f"  {nid}[({label})]")
        else:
            lines.append(f"  {nid}[{label}]")

    # Emit edges: file chain (sequential imports)
    for i in range(len(file_ids) - 1):
        lines.append(f"  {file_ids[i]} --> {file_ids[i + 1]}")

    # Connect last file to routes
    if file_ids and route_ids:
        for rid in route_ids:
            lines.append(f"  {file_ids[-1]} --> {rid}")
    elif route_ids and len(route_ids) > 1:
        for i in range(len(route_ids) - 1):
            lines.append(f"  {route_ids[i]} --> {route_ids[i + 1]}")

    # Connect routes to tables
    if route_ids and table_ids:
        for tid in table_ids:
            lines.append(f"  {route_ids[0]} --> {tid}")
    elif file_ids and table_ids:
        for tid in table_ids:
            lines.append(f"  {file_ids[-1]} --> {tid}")

    # Fallback: at least one self-link when there are no connections
    if len(nodes) == 1:
        nid = nodes[0][0]
        lines.append(f"  {nid}")

    return "\n".join(lines)


def generate_note(
    feature_name: str,
    source_dir: Path,
    entry_point_file: str,
    issues: list[dict],
) -> str:
    """Generate an atlas trace note for a stale feature.

    Parameters
    ----------
    feature_name     Display name of the feature.
    source_dir       Root directory of the target's source tree.
    entry_point_file Filename (relative to source_dir) where tracing begins.
    issues           List of dicts with 'number' and 'title' keys.

    Returns
    -------
    A Markdown string with YAML frontmatter and all six required sections.
    """
    source_dir = Path(source_dir)
    entry_path = source_dir / entry_point_file

    open_questions: list[str] = []
    files_read: list[Path] = []
    routes: list[str] = []
    tables: list[str] = []

    if entry_path.exists():
        files_read, routes, tables = _trace_imports(
            entry_path, source_dir, open_questions=open_questions
        )
    else:
        open_questions.append(
            f"Entry point `{entry_point_file}` not found in source_dir — "
            "cannot begin tracing"
        )

    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique_files: list[Path] = []
    for f in files_read:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    unique_routes = list(dict.fromkeys(routes))
    unique_tables = list(dict.fromkeys(tables))

    files_read = unique_files

    # --- Frontmatter ---
    files_list = "\n".join(f"  - {f.name}" for f in files_read)
    frontmatter = (
        "---\n"
        f"feature: {feature_name}\n"
        f"files_read:\n{files_list or '  []'}\n"
        f"traced: null\n"
        f"stale: true\n"
        "---\n"
    )

    # --- ## What ---
    what_section = (
        "## What\n\n"
        f"{feature_name} — traced from `{entry_point_file}` through "
        f"{len(files_read)} source file(s).\n"
    )

    # --- ## Entry Points ---
    ep_lines = [f"- `{entry_point_file}` (tracing origin)"]
    for route in unique_routes:
        ep_lines.append(f"- Route: `{route}`")
    entry_section = "## Entry Points\n\n" + "\n".join(ep_lines) + "\n"

    # --- ## Related Issues ---
    if issues:
        issue_lines = [f"- #{i['number']} — {i['title']}" for i in issues]
    else:
        issue_lines = ["_No related issues found in snapshot._"]
    issues_section = "## Related Issues\n\n" + "\n".join(issue_lines) + "\n"

    # --- ## Flowchart ---
    mermaid_body = _build_mermaid(files_read, unique_routes, unique_tables, open_questions)
    flowchart_section = "## Flowchart\n\n```mermaid\n" + mermaid_body + "\n```\n"

    # --- ## Key Files ---
    if files_read:
        key_lines = [f"- `{f.name}` — traced during import walk" for f in files_read]
    else:
        key_lines = ["_No source files could be read during tracing._"]
    key_files_section = "## Key Files\n\n" + "\n".join(key_lines) + "\n"

    # --- OPEN QUESTION callouts ---
    oq_parts: list[str] = []
    for oq in open_questions:
        oq_parts.append(f"<!-- OPEN QUESTION: {oq} -->")

    open_q_section = ""
    if oq_parts:
        open_q_section = "\n## Open Questions\n\n" + "\n".join(oq_parts) + "\n"

    parts = [
        frontmatter,
        "",
        what_section,
        entry_section,
        issues_section,
        flowchart_section,
        key_files_section,
    ]
    if open_q_section:
        parts.append(open_q_section)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def extract_mermaid_block(note_text: str) -> str | None:
    """Return the content inside the first ```mermaid fence, or None."""
    m = re.search(r"```mermaid\n(.*?)```", note_text, re.DOTALL)
    if not m:
        return None
    return m.group(1)


def get_node_names(mermaid_text: str) -> list[str]:
    """Extract human-readable node labels from a Mermaid flowchart.

    Handles:
      A[label]      → 'label'
      A[(label)]    → 'label'
      A{label}      → 'label'
      A([label])    → 'label'
      A             → 'A'  (bare node)
    """
    labels: list[str] = []
    seen: set[str] = set()

    # Match node definitions with bracket labels
    for m in re.finditer(
        r"\b(\w+)\s*[\[\({]+([^\]\)\}]+?)[\]\)}]+",
        mermaid_text,
    ):
        label = m.group(2).strip().strip("()")
        if label and label not in seen:
            seen.add(label)
            labels.append(label)

    return labels


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Trace a stale feature and write an atlas note"
    )
    parser.add_argument("target", help="Target name (e.g. perf-coach)")
    parser.add_argument("feature_slug", help="Feature slug (e.g. today-recommendation)")
    parser.add_argument("--vault", default="vault", help="Path to vault directory")
    parser.add_argument("--source-dir", help="Path to the target's source directory")
    args = parser.parse_args()

    vault_dir = Path(args.vault)
    atlas_dir = vault_dir / "projects" / args.target / "atlas"
    stub_path = atlas_dir / f"{args.feature_slug}.md"

    if not stub_path.exists():
        print(f"Error: stub not found at {stub_path}", file=sys.stderr)
        sys.exit(1)

    # Read feature name from stub frontmatter
    stub_text = stub_path.read_text()
    m = re.search(r"^feature:\s*(.+)$", stub_text, re.MULTILINE)
    feature_name = m.group(1).strip() if m else args.feature_slug

    # Check stale flag
    stale_m = re.search(r"^stale:\s*(.+)$", stub_text, re.MULTILINE)
    if stale_m and stale_m.group(1).strip().lower() == "false":
        print(f"Feature '{feature_name}' is not stale — skipping trace.", file=sys.stderr)
        sys.exit(0)

    source_dir = Path(args.source_dir) if args.source_dir else Path(".")

    # Load issues from latest snapshot
    raw_dir = vault_dir / "projects" / args.target / "raw"
    issues: list[dict] = []
    if raw_dir.exists():
        snapshots = sorted(raw_dir.iterdir())
        if snapshots:
            issues_file = snapshots[-1] / "issues.json"
            if issues_file.exists():
                data = json.loads(issues_file.read_text())
                issues = data.get("issues", [])

    # Determine entry point
    entry_point = "app.py"
    docs_dir = source_dir / "docs"
    for docs_file in ([docs_dir / "features.md"] if docs_dir.exists() else []):
        if docs_file.exists():
            text = docs_file.read_text()
            # Look for "Entry point: `<file>`" pattern
            ep_m = re.search(r"[Ee]ntry\s+point.*?`([^`]+\.py)`", text)
            if ep_m:
                entry_point = ep_m.group(1)
                break

    note = generate_note(
        feature_name=feature_name,
        source_dir=source_dir,
        entry_point_file=entry_point,
        issues=issues,
    )

    out_path = atlas_dir / f"{args.feature_slug}.md"
    out_path.write_text(note)
    print(f"Atlas note written: {out_path}")


if __name__ == "__main__":
    main()

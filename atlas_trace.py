"""
atlas_trace.py — stale-feature tracing for Lookout.

Traces a named feature by following entry points in docs and traversing
imports in source, then writes an atlas note with:

  - YAML frontmatter (files_read list)
  - ## What — one-sentence description
  - ## Entry Points — discovered entry files and routes
  - ## Related Issues — issues pulled from snapshot (open only, ≤10, feature-matched)
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
    python atlas_trace.py <target> --all-stale [--vault <vault_dir>] [--source-dir <path>]
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

    return "\n".join(lines)


def generate_note(
    feature_name: str,
    source_dir: Path,
    entry_point_file: str | None,
    issues: list[dict],
    traced: str | None = None,
    stale: bool = True,
) -> str:
    """Generate an atlas trace note for a stale feature.

    Parameters
    ----------
    feature_name     Display name of the feature.
    source_dir       Root directory of the target's source tree.
    entry_point_file Filename (relative to source_dir) where tracing begins.
    issues           List of dicts with 'number' and 'title' keys (pre-filtered).
    traced           ISO date string to set in frontmatter, or None for null.
    stale            Whether to mark the note stale in frontmatter.

    Returns
    -------
    A Markdown string with YAML frontmatter and all six required sections.
    """
    source_dir = Path(source_dir)

    open_questions: list[str] = []
    files_read: list[Path] = []
    routes: list[str] = []
    tables: list[str] = []

    entry_path = source_dir / entry_point_file if entry_point_file else None

    if entry_path is None:
        open_questions.append(
            f"No entry point could be discovered for `{feature_name}` — "
            "cannot begin tracing"
        )
    elif entry_path.exists():
        # Remember where this trace's questions begin, so a rejected trace can
        # take its unresolved-import notes with it.
        _q_mark = len(open_questions)
        files_read, routes, tables = _trace_imports(
            entry_path, source_dir, open_questions=open_questions
        )
        # A test file is the route into the feature, not part of it. Keeping it
        # would put `test_visual_sourcing.py` in the diagram and in Key Files,
        # describing the test suite rather than the implementation.
        files_read = [f for f in files_read if not _is_test_path(f, source_dir)]
        if not files_read:
            # A test that drives the app over HTTP (TestClient) imports nothing
            # local, so it resolves as an entry point but traces to nothing.
            open_questions.append(
                f"Entry point `{entry_point_file}` imports no local modules — "
                "no implementation files could be traced"
            )
        elif len(files_read) > _MAX_DIAGRAM_FILES:
            # Reaching this many files means the entry point is the application,
            # not the feature — every feature would get the same picture of the
            # whole program. A diagram that is identical across 28 features is
            # noise wearing the shape of signal, so none is emitted.
            del open_questions[_q_mark:]
            open_questions.append(
                f"Trace from `{entry_point_file}` reached {len(files_read)} files, "
                f"over the {_MAX_DIAGRAM_FILES}-file limit — this entry point "
                f"describes the application, not `{feature_name}`. No diagram "
                "emitted; add a test or a source file named for this feature"
            )
            files_read, routes, tables = [], [], []
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
    traced_val = traced if traced is not None else "null"
    stale_val = "true" if stale else "false"
    frontmatter = (
        "---\n"
        f"feature: {feature_name}\n"
        f"files_read:\n{files_list or '  []'}\n"
        f"traced: {traced_val}\n"
        f"stale: {stale_val}\n"
        "---\n"
    )

    # --- ## What ---
    if entry_point_file:
        what_body = (
            f"{feature_name} — traced from `{entry_point_file}` through "
            f"{len(files_read)} source file(s)."
        )
    else:
        what_body = f"{feature_name} — no entry point could be discovered."
    what_section = f"## What\n\n{what_body}\n"

    # --- ## Entry Points ---
    if entry_point_file:
        ep_lines = [f"- `{entry_point_file}` (tracing origin)"]
    else:
        ep_lines = ["_No entry point discovered._"]
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
# Entry-point discovery
# ---------------------------------------------------------------------------

_EP_PATTERN = re.compile(r"[Ee]ntry\s+point[:\s]*`([^`]+\.py)`")


# Directories that are never worth walking when hunting for a source file.
_SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "site",
    "build", "dist", ".mypy_cache", ".pytest_cache",
}

# Probed in order when a feature yields no specific entry point. The previous
# hardcoded "app.py" matches no project in this fleet — asset-studio's entry is
# server.py — so the application entry is probed rather than assumed.
_APP_ENTRY_CANDIDATES = ("server.py", "main.py", "app.py", "__main__.py")

# A feature diagram must stay readable. Falling back to the application
# entry point traces the entire program — asset-studio yields 267 nodes —
# which describes the app, not the feature. Past this the note records the
# truncation as an open question rather than shipping an unreadable graph.
_MAX_DIAGRAM_FILES = 25


def _slug_variants(feature_slug: str, feature_name: str) -> list[str]:
    """Underscore and hyphen spellings of a feature, for filename matching."""
    name_slug = re.sub(r"[^a-z0-9]+", "-", feature_name.lower()).strip("-")
    out: list[str] = []
    for base in (feature_slug, name_slug):
        for v in (base, base.replace("-", "_")):
            if v and v not in out:
                out.append(v)
    return out


def _is_test_path(path: Path, source_dir: Path | None = None) -> bool:
    """True for a pytest file or anything under the target's tests/ directory.

    Judged relative to `source_dir` when given. An absolute check would misfire
    whenever the source tree itself sits below a directory called `tests` — as
    the trace fixture does — and would then exclude every file it traced.
    """
    if path.name.startswith("test_"):
        return True
    parts = path.parts
    if source_dir is not None:
        try:
            parts = path.relative_to(source_dir).parts
        except ValueError:
            pass
    return "tests" in parts


def _iter_source_files(source_dir: Path):
    for p in source_dir.rglob("*.py"):
        if _SKIP_DIRS & set(p.relative_to(source_dir).parts):
            continue
        yield p


def _find_test_entry_point(
    feature_slug: str, feature_name: str, source_dir: Path
) -> Path | None:
    """Locate the test file that covers a feature.

    `CLAUDE.md` mandates `tests/test_<feature>__<criterion>.py`, so a test file
    names the feature *and* imports its implementation. That makes it the most
    reliable route into the code in this fleet — it exists because of an enforced
    convention rather than by luck.
    """
    tests_dir = source_dir / "tests"
    if not tests_dir.is_dir():
        return None
    variants = _slug_variants(feature_slug, feature_name)
    candidates = sorted(tests_dir.rglob("test_*.py"))
    for variant in variants:
        exact = [c for c in candidates if c.stem == f"test_{variant}"]
        if exact:
            return exact[0]
        # `test_content_queue__101.py` — convention suffixes the criterion/issue.
        prefixed = [c for c in candidates if c.stem.startswith(f"test_{variant}__")]
        if prefixed:
            return prefixed[0]
    return None


def _find_source_by_name(
    feature_slug: str, feature_name: str, source_dir: Path
) -> Path | None:
    """Locate a non-test source file whose name matches the feature."""
    variants = _slug_variants(feature_slug, feature_name)
    files = [p for p in _iter_source_files(source_dir)
             if not _is_test_path(p, source_dir)]
    for variant in variants:
        for p in sorted(files):
            if p.stem == variant:
                return p
    return None


def _find_app_entry(source_dir: Path) -> Path | None:
    """Probe for the project's application entry point."""
    for name in _APP_ENTRY_CANDIDATES:
        p = source_dir / name
        if p.exists():
            return p
    for name in _APP_ENTRY_CANDIDATES:
        for p in sorted(_iter_source_files(source_dir)):
            if p.name == name and not _is_test_path(p, source_dir):
                return p
    return None


def _candidate_entry_points(
    feature_slug: str, feature_name: str, source_dir: Path
) -> list[Path]:
    """Ordered entry-point candidates for a feature, most specific first."""
    out: list[Path] = []

    def _push(p: Path | None):
        if p is not None and p.exists() and p not in out:
            out.append(p)

    docs_dir = source_dir / "docs"
    features_dir = docs_dir / "features"
    doc_files = []
    if features_dir.is_dir():
        doc_files += [
            features_dir / f"{feature_slug}.md",
            features_dir / f"{re.sub(r'[^a-z0-9]+', '-', feature_name.lower())}.md",
        ]
    doc_files.append(docs_dir / "features.md")
    for doc in doc_files:
        if doc.exists():
            m = _EP_PATTERN.search(doc.read_text())
            if m:
                _push(source_dir / m.group(1))

    _push(_find_test_entry_point(feature_slug, feature_name, source_dir))
    _push(_find_source_by_name(feature_slug, feature_name, source_dir))
    _push(_find_app_entry(source_dir))
    return out


def _find_entry_point_for_feature(
    feature_slug: str,
    feature_name: str,
    source_dir: Path,
) -> str | None:
    """Return the entry-point path (relative to source_dir), or None.

    Candidates are tried most-specific first (see _candidate_entry_points) and
    each is *evaluated* rather than trusted: a candidate is accepted only if
    tracing it reaches at least one non-test implementation file.

    That check matters. A test driving the app through FastAPI's TestClient
    imports nothing local, so it resolves as an entry point and then traces to
    nothing — `test_content_queue__101.py` does exactly this. Without
    evaluation the note would claim an origin and show an empty diagram.

    When no candidate traces to anything, the first candidate is returned so the
    note can name what was attempted; generate_note records the open question.
    """
    source_dir = Path(source_dir)
    candidates = _candidate_entry_points(feature_slug, feature_name, source_dir)
    if not candidates:
        return None

    for candidate in candidates:
        traced, _routes, _tables = _trace_imports(candidate, source_dir)
        real = [f for f in traced if not _is_test_path(f, source_dir)]
        if real:
            return str(candidate.relative_to(source_dir))

    return str(candidates[0].relative_to(source_dir))


# ---------------------------------------------------------------------------
# Issue filtering
# ---------------------------------------------------------------------------

def _filter_issues(
    issues: list[dict],
    feature_name: str,
    cap: int = 10,
) -> list[dict]:
    """Return at most `cap` open issues plausibly related to `feature_name`.

    Filtering rules:
      - Exclude issues where state is CLOSED (case-insensitive).
      - Include issues where at least one word from feature_name (≥3 chars)
        appears in the issue title (case-insensitive substring match).
      - Cap result at `cap` (default 10).
    """
    words = [w.lower() for w in feature_name.split() if len(w) >= 3]
    result: list[dict] = []
    for issue in issues:
        state = issue.get("state", "OPEN")
        if isinstance(state, str) and state.upper() == "CLOSED":
            continue
        title = issue.get("title", "").lower()
        if words and not any(w in title for w in words):
            continue
        result.append(issue)
        if len(result) == cap:
            break
    return result


# ---------------------------------------------------------------------------
# Batch tracing
# ---------------------------------------------------------------------------

def trace_all_stale(
    target: str,
    vault_dir: "Path | str",
    source_dir: "Path | str",
    max_batch: int = 3,
) -> list[str]:
    """Trace all stale atlas features for `target`, up to `max_batch`.

    Selects the oldest-traced (or never-traced) stale features first — matching
    the batch-selection order in gather.select_trace_batch. Writes updated notes
    back to disk with stale: false and the current traced date.

    Returns a list of feature slugs that were traced this run.
    """
    import json
    from datetime import date

    vault_dir = Path(vault_dir)
    source_dir = Path(source_dir)
    atlas_dir = vault_dir / "projects" / target / "atlas"
    if not atlas_dir.exists():
        return []

    # Load issues from latest snapshot
    raw_dir = vault_dir / "projects" / target / "raw"
    issues: list[dict] = []
    if raw_dir.exists():
        snapshots = sorted(p for p in raw_dir.iterdir() if p.is_dir())
        if snapshots:
            issues_file = snapshots[-1] / "issues.json"
            if issues_file.exists():
                data = json.loads(issues_file.read_text())
                issues = data.get("issues", [])

    # Collect stale candidates (oldest traced first, then alphabetical)
    candidates: list[tuple[str | None, str]] = []
    for note_path in sorted(atlas_dir.glob("*.md")):
        if note_path.name == "index.md":
            continue
        text = note_path.read_text()
        stale_m = re.search(r"^stale:\s*(.+)$", text, re.MULTILINE)
        is_stale = bool(stale_m and stale_m.group(1).strip().lower() == "true")
        traced_m = re.search(r"^traced:\s*(.+)$", text, re.MULTILINE)
        traced_val = traced_m.group(1).strip() if traced_m else None
        if traced_val in (None, "null", "", "None"):
            traced_val = None
        if is_stale or traced_val is None:
            candidates.append((traced_val, note_path.stem))

    candidates.sort(key=lambda item: ("0000" if item[0] is None else item[0], item[1]))
    batch = [slug for _, slug in candidates[:max_batch]]

    today = date.today().isoformat()
    traced_slugs: list[str] = []

    for slug in batch:
        note_path = atlas_dir / f"{slug}.md"
        text = note_path.read_text()
        fm_m = re.search(r"^feature:\s*(.+)$", text, re.MULTILINE)
        feature_name = fm_m.group(1).strip() if fm_m else slug

        ep = _find_entry_point_for_feature(slug, feature_name, source_dir)
        filtered = _filter_issues(issues, feature_name)

        note = generate_note(
            feature_name=feature_name,
            source_dir=source_dir,
            entry_point_file=ep,
            issues=filtered,
            traced=today,
            stale=False,
        )
        note_path.write_text(note)
        traced_slugs.append(slug)

    return traced_slugs


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
    from datetime import date

    parser = argparse.ArgumentParser(
        description="Trace a stale feature and write an atlas note"
    )
    parser.add_argument("target", help="Target name (e.g. perf-coach)")
    parser.add_argument(
        "feature_slug",
        nargs="?",
        help="Feature slug (e.g. today-recommendation); omit with --all-stale",
    )
    parser.add_argument("--vault", default="vault", help="Path to vault directory")
    parser.add_argument("--source-dir", help="Path to the target's source directory")
    parser.add_argument(
        "--all-stale",
        action="store_true",
        help="Trace all stale features for the target (up to --batch-size)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Max features to trace in one --all-stale run (default 3)",
    )
    args = parser.parse_args()

    vault_dir = Path(args.vault)
    source_dir = Path(args.source_dir) if args.source_dir else Path(".")

    if args.all_stale:
        traced = trace_all_stale(args.target, vault_dir, source_dir, args.batch_size)
        if traced:
            print(f"Traced {len(traced)} feature(s): {', '.join(traced)}")
        else:
            print("No stale features to trace.")
        return

    if not args.feature_slug:
        print("Error: feature_slug is required (or use --all-stale)", file=sys.stderr)
        sys.exit(1)

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

    # Load issues from latest snapshot and filter for this feature
    raw_dir = vault_dir / "projects" / args.target / "raw"
    all_issues: list[dict] = []
    if raw_dir.exists():
        snapshots = sorted(p for p in raw_dir.iterdir() if p.is_dir())
        if snapshots:
            issues_file = snapshots[-1] / "issues.json"
            if issues_file.exists():
                data = json.loads(issues_file.read_text())
                all_issues = data.get("issues", [])

    issues = _filter_issues(all_issues, feature_name)

    # Resolve per-feature entry point
    entry_point = (
        _find_entry_point_for_feature(args.feature_slug, feature_name, source_dir)
    )

    note = generate_note(
        feature_name=feature_name,
        source_dir=source_dir,
        entry_point_file=entry_point,
        issues=issues,
        traced=date.today().isoformat(),
        stale=False,
    )

    out_path = atlas_dir / f"{args.feature_slug}.md"
    out_path.write_text(note)
    print(f"Atlas note written: {out_path}")


if __name__ == "__main__":
    main()

"""Tests for issue #27: Enrich todo-view.md with effort and blocked-by annotations.

Each test maps to a specific AC item from the issue.
Tests run against todo_view_assessment.py at repo root.
"""
import importlib.util
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
TODO_VIEW_ASSESSMENT_PY = REPO_ROOT / "todo_view_assessment.py"
COLLECTORS_DIR = REPO_ROOT / "collectors"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_assessment():
    spec = importlib.util.spec_from_file_location(
        "todo_view_assessment", str(TODO_VIEW_ASSESSMENT_PY)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_vault(
    base_dir: Path,
    project: str = "perf-coach",
    feature_slug: str = "weight-tracking",
    feature_name: str = "Weight tracking",
    files_read: list | None = None,
    stale: bool = False,
    mermaid_edges: list | None = None,
) -> Path:
    """Create a minimal vault with one atlas feature note."""
    vault = base_dir / "vault"
    atlas_dir = vault / "projects" / project / "atlas"
    atlas_dir.mkdir(parents=True, exist_ok=True)

    if files_read is None:
        files_read = ["weight_stats.py", "weight_ewma.py", "weight_trend_rate.py"]

    files_yaml = "\n".join(f"  - {f}" for f in files_read)
    stale_str = "true" if stale else "false"

    if mermaid_edges is None:
        mermaid_edges = [
            "  weight_stats_py[weight_stats.py] --> weight_ewma_py[weight_ewma.py]",
            "  weight_stats_py[weight_stats.py] --> weight_trend_rate_py[weight_trend_rate.py]",
        ]

    mermaid_block = (
        "```mermaid\nflowchart LR\n" + "\n".join(mermaid_edges) + "\n```"
        if mermaid_edges
        else ""
    )

    note_content = f"""---
feature: {feature_name}
files_read:
{files_yaml}
traced: 2026-08-10
stale: {stale_str}
---

## What

{feature_name} — implementation.

## Flowchart

{mermaid_block}

## Key Files

- `weight_stats.py` — traced during import walk
"""
    (atlas_dir / f"{feature_slug}.md").write_text(note_content)
    return vault


def _make_todo_view(base_dir: Path, todos: list[str]) -> Path:
    """Write a minimal todo-view.md."""
    lines = ["# Todo View", "", "## Notion Todos", ""]
    for t in todos:
        lines.append(f"- [ ] {t}")
    lines.append("")
    content = "\n".join(lines)
    path = base_dir / "todo-view.md"
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# AC1: effort annotation appended for each todo that maps to an atlas feature
# ---------------------------------------------------------------------------

def test_effort_annotation_appended(tmp_path):
    """AC1: effort: S/M/L annotation is present after assessment pass."""
    vault = _make_vault(tmp_path)
    todo_view_path = _make_todo_view(tmp_path, ["Weight tracking"])

    mod = _load_assessment()
    result = mod.annotate_todo_view(todo_view_path.read_text(), vault)

    assert re.search(r"<!--\s*lookout:\s*effort:\s*[SML]\b", result), (
        "Expected a lookout effort annotation (S/M/L) in the output"
    )


# ---------------------------------------------------------------------------
# AC2: blocked-by annotation appended when atlas evidence shows a dependency
# ---------------------------------------------------------------------------

def test_blocked_by_annotation_appended(tmp_path):
    """AC2: blocked-by annotation appears when atlas flowchart has edges."""
    vault = _make_vault(tmp_path)
    todo_view_path = _make_todo_view(tmp_path, ["Weight tracking"])

    mod = _load_assessment()
    result = mod.annotate_todo_view(todo_view_path.read_text(), vault)

    assert re.search(r"<!--\s*lookout:\s*blocked-by:", result), (
        "Expected a lookout blocked-by annotation in the output"
    )


# ---------------------------------------------------------------------------
# AC3: annotations are prefixed with <!-- lookout:
# ---------------------------------------------------------------------------

def test_annotations_use_lookout_prefix(tmp_path):
    """AC3: all annotations are clearly marked as lookout annotations."""
    vault = _make_vault(tmp_path)
    todo_view_path = _make_todo_view(tmp_path, ["Weight tracking"])

    mod = _load_assessment()
    result = mod.annotate_todo_view(todo_view_path.read_text(), vault)

    assert "<!-- lookout:" in result, (
        "Annotations must use the <!-- lookout: prefix"
    )


# ---------------------------------------------------------------------------
# AC4: no Notion write/update/patch endpoints in application code
# ---------------------------------------------------------------------------

def test_no_notion_write_calls():
    """AC4: grep -rE 'notion.*(write|update|patch|post|create|append)' returns zero matches."""
    result = subprocess.run(
        [
            "grep",
            "-rE",
            "--include=*.py",
            "--exclude-dir=tests",
            "--exclude-dir=.git",
            r"notion.*(write|update|patch|post|create|append)",
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 or result.stdout.strip() == "", (
        f"Found Notion write calls in application code:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# AC5: fixture todo mapped to known atlas feature gets both annotations
# ---------------------------------------------------------------------------

def test_fixture_todo_gets_both_annotations(tmp_path):
    """AC5: a todo that maps to a known atlas feature gets both effort and blocked-by."""
    vault = _make_vault(tmp_path)
    todo_view_path = _make_todo_view(tmp_path, ["Weight tracking"])

    mod = _load_assessment()
    result = mod.annotate_todo_view(todo_view_path.read_text(), vault)

    has_effort = bool(re.search(r"<!--\s*lookout:\s*effort:\s*[SML]\b", result))
    has_blocked = bool(re.search(r"<!--\s*lookout:\s*blocked-by:", result))

    assert has_effort, "Expected effort annotation for fixture todo"
    assert has_blocked, "Expected blocked-by annotation for fixture todo"


# ---------------------------------------------------------------------------
# AC6: idempotent — running twice does not duplicate annotations
# ---------------------------------------------------------------------------

def test_idempotent_no_duplicate_annotations(tmp_path):
    """AC6: running the assessment pass twice produces identical output."""
    vault = _make_vault(tmp_path)
    todo_view_path = _make_todo_view(tmp_path, ["Weight tracking"])

    mod = _load_assessment()
    first_run = mod.annotate_todo_view(todo_view_path.read_text(), vault)
    second_run = mod.annotate_todo_view(first_run, vault)

    assert first_run == second_run, (
        "Second run produced different output — annotations were duplicated"
    )


# ---------------------------------------------------------------------------
# AC7: Notion write home is unchanged — collectors/notion.py has no new write logic
# ---------------------------------------------------------------------------

def test_notion_collector_unchanged():
    """AC7: collectors/notion.py does not contain write/update/create logic."""
    notion_py = COLLECTORS_DIR / "notion.py"
    assert notion_py.exists(), f"Expected {notion_py} to exist"
    content = notion_py.read_text()
    write_patterns = re.findall(
        r"notion.*(write|update|patch|create|append)",
        content,
        re.IGNORECASE,
    )
    assert not write_patterns, (
        f"collectors/notion.py contains write logic: {write_patterns}"
    )


# ---------------------------------------------------------------------------
# Bonus: todo with no atlas match has no blocked-by annotation
# ---------------------------------------------------------------------------

def test_no_blocked_by_for_unmatched_todo(tmp_path):
    """AC UAT-6: a todo with no detectable dependency omits the blocked-by line."""
    vault = _make_vault(
        tmp_path,
        feature_slug="simple-feature",
        feature_name="Simple feature",
        files_read=["simple.py"],
        mermaid_edges=[],
    )
    todo_view_path = _make_todo_view(tmp_path, ["Completely unrelated todo item"])

    mod = _load_assessment()
    result = mod.annotate_todo_view(todo_view_path.read_text(), vault)

    assert not re.search(r"<!--\s*lookout:\s*blocked-by:", result), (
        "Unmatched todo should not have a blocked-by annotation"
    )


# ---------------------------------------------------------------------------
# Bonus: effort annotation cites source (evidence reference)
# ---------------------------------------------------------------------------

def test_effort_annotation_cites_source(tmp_path):
    """AC1: effort annotation includes a source citation."""
    vault = _make_vault(tmp_path)
    todo_view_path = _make_todo_view(tmp_path, ["Weight tracking"])

    mod = _load_assessment()
    result = mod.annotate_todo_view(todo_view_path.read_text(), vault)

    assert re.search(r"<!--\s*lookout:\s*effort:\s*[SML].*source:", result), (
        "Effort annotation must cite its evidence source"
    )

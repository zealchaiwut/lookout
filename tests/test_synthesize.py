"""Tests for issue #10: situation.md synthesis contract and situation generator.

Each test maps to a specific AC item from the issue.

All tests use tmp_path so they never touch the real vault.
"""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
SYNTHESIZE = REPO_ROOT / "synthesize.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_synthesize(tmp_path, module_name="synthesize_test"):
    spec = importlib.util.spec_from_file_location(module_name, str(SYNTHESIZE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = tmp_path
    return mod


def _make_snapshot(
    base_dir: Path,
    target: str = "perf-coach",
    timestamp: str = "2099-01-01T00:00:00Z",
    brief_status: str = "ok",
    history_status: str = "ok",
    health: dict | None = None,
    sprints_history: list | None = None,
    brief_data: dict | None = None,
    issues: list | None = None,
    notion_todos: list | None = None,
    changed_files: list | None = None,
    journal_entries: list | None = None,
    include_brief_json: bool = True,
) -> Path:
    """Create a fake snapshot directory and return its path."""
    snap_dir = base_dir / "vault" / "projects" / target / "raw" / timestamp
    snap_dir.mkdir(parents=True, exist_ok=True)

    if health is None:
        health = {"status": "healthy"}
    if sprints_history is None:
        sprints_history = []
    if brief_data is None:
        brief_data = {"name": target, "description": "Test project"}

    manifest = {
        "timestamp": timestamp,
        "target": target,
        "health": health,
        "sources": {
            "brief": {
                "status": brief_status,
                "error": "" if brief_status == "ok" else "Connection refused",
            },
            "sprints_history": {
                "status": history_status,
                "error": "" if history_status == "ok" else "Connection refused",
            },
        },
    }
    (snap_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    if include_brief_json:
        brief_json = {"brief": brief_data, "sprints_history": sprints_history}
        (snap_dir / "brief.json").write_text(json.dumps(brief_json, indent=2))

    if issues is None:
        issues = []
    (snap_dir / "issues.json").write_text(json.dumps({"issues": issues, "prs": []}, indent=2))

    if notion_todos is not None:
        (snap_dir / "notion_todos.json").write_text(json.dumps(notion_todos, indent=2))

    docs_data: dict = {"files": []}
    if changed_files:
        docs_data["changed_files"] = changed_files
    (snap_dir / "docs_manifest.json").write_text(json.dumps(docs_data, indent=2))

    if journal_entries is not None:
        (snap_dir / "journal_delta.json").write_text(
            json.dumps({"entries": journal_entries}, indent=2)
        )

    return snap_dir


def _parse_frontmatter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return {}
    return yaml.safe_load("\n".join(lines[1:end])) or {}


def _section_content(text: str, title: str) -> str:
    """Return the body text of a ## section (empty string if absent)."""
    pattern = rf"## {re.escape(title)}\n(.*?)(?=\n## |\n---|\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# AC: synthesize.py exists
# ---------------------------------------------------------------------------

def test_synthesize_py_exists():
    assert SYNTHESIZE.exists(), "synthesize.py must exist at repo root"


# ---------------------------------------------------------------------------
# AC: frontmatter contains target, run (ISO-8601), sources_ok (boolean)
# ---------------------------------------------------------------------------

def test_frontmatter_target(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    fm = _parse_frontmatter(situation.read_text())
    assert fm.get("target") == "perf-coach", "frontmatter must contain 'target'"


def test_frontmatter_run_is_iso8601(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    fm = _parse_frontmatter(situation.read_text())
    run = fm.get("run", "")
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", str(run)), (
        f"frontmatter 'run' must be ISO-8601: {run!r}"
    )


def test_frontmatter_sources_ok_is_boolean(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    fm = _parse_frontmatter(situation.read_text())
    assert "sources_ok" in fm, "frontmatter must contain 'sources_ok'"
    assert isinstance(fm["sources_ok"], bool), "sources_ok must be a boolean"


# ---------------------------------------------------------------------------
# AC: One-liner section — single sentence
# ---------------------------------------------------------------------------

def test_one_liner_section_exists(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    text = situation.read_text()
    assert "## One-liner" in text, "situation.md must have a ## One-liner section"


def test_one_liner_section_not_empty(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "One-liner")
    assert content, "## One-liner section must not be empty"


def test_one_liner_is_single_sentence(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "One-liner")
    # Strip source annotations and check it is one sentence
    lines = [l.strip() for l in content.splitlines()
             if l.strip() and not l.strip().startswith("_(source")]
    assert len(lines) == 1, f"One-liner must be a single sentence, got: {lines}"


# ---------------------------------------------------------------------------
# AC: Capacity section verdicts
# ---------------------------------------------------------------------------

def test_capacity_section_exists(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    assert "## Capacity" in situation.read_text()


def test_capacity_clear_to_start(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path, health={"status": "healthy"}, sprints_history=[])
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "Capacity")
    assert "Clear to start" in content, f"Expected 'Clear to start' in capacity: {content!r}"


def test_capacity_sprint_running(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(
        tmp_path,
        sprints_history=[{"slug": "perf-coach", "sprint": 3, "state": "active"}],
    )
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "Capacity")
    assert "Sprint running" in content and "wait" in content, (
        f"Expected 'Sprint running — wait' in capacity: {content!r}"
    )


def test_capacity_blocked(tmp_path):
    mod = _load_synthesize(tmp_path)
    blocked_issues = [
        {
            "number": 42,
            "title": "Fix auth",
            "state": "open",
            "labels": [{"name": "blocked"}],
            "assignees": [],
        },
        {
            "number": 43,
            "title": "Fix deploy",
            "state": "open",
            "labels": [{"name": "blocked"}],
            "assignees": [],
        },
    ]
    _make_snapshot(tmp_path, issues=blocked_issues)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "Capacity")
    assert "blocked" in content.lower() and "resolve first" in content.lower(), (
        f"Expected 'N blocked — resolve first' in capacity: {content!r}"
    )


# ---------------------------------------------------------------------------
# AC: Commander absent → exact capacity text
# ---------------------------------------------------------------------------

def test_commander_absent_capacity_text(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path, brief_status="absent", history_status="absent")
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "Capacity")
    assert "commander unreachable" in content and "state unverified" in content, (
        f"Expected 'commander unreachable — state unverified' in capacity: {content!r}"
    )


def test_commander_absent_sources_ok_false(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path, brief_status="absent", history_status="absent")
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    fm = _parse_frontmatter(situation.read_text())
    assert fm.get("sources_ok") is False, "sources_ok must be false when commander is absent"


def test_commander_absent_missing_named_in_note(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path, brief_status="absent", history_status="absent")
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    text = situation.read_text()
    lower = text.lower()
    # Any absent source must be named somewhere in the file
    assert "brief" in lower or "absent" in lower, (
        "situation.md must name absent sources"
    )


# ---------------------------------------------------------------------------
# AC: Since last run — only changed fields
# ---------------------------------------------------------------------------

def test_since_last_run_section_exists(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    assert "## Since last run" in situation.read_text()


def test_since_last_run_lists_changed_fields(tmp_path):
    mod = _load_synthesize(tmp_path)
    # First (older) snapshot: healthy, both sources ok
    _make_snapshot(
        tmp_path,
        timestamp="2099-01-01T00:00:00Z",
        health={"status": "healthy"},
        brief_status="ok",
        history_status="ok",
    )
    # Second (newer) snapshot: degraded health, brief absent
    _make_snapshot(
        tmp_path,
        timestamp="2099-01-01T00:00:01Z",
        health={"status": "degraded"},
        brief_status="absent",
        history_status="ok",
    )
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "Since last run")
    # Both changed fields must appear
    assert "health" in content.lower() or "status" in content.lower(), (
        "Since last run must mention changed health/status fields"
    )
    # The changed status should be visible
    assert "degraded" in content or "absent" in content, (
        "Since last run must show the changed values"
    )


def test_since_last_run_omits_unchanged_fields(tmp_path):
    mod = _load_synthesize(tmp_path)
    # Two identical snapshots (only timestamp differs — which is always ignored)
    _make_snapshot(tmp_path, timestamp="2099-01-01T00:00:00Z", health={"status": "healthy"})
    _make_snapshot(tmp_path, timestamp="2099-01-01T00:00:01Z", health={"status": "healthy"})
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "Since last run")
    # Should indicate no changes (no diff lines, or explicit "no changes")
    lines = [l.strip() for l in content.splitlines()
             if l.strip() and not l.strip().startswith("_(source")]
    diff_lines = [l for l in lines if l.startswith("-")]
    assert len(diff_lines) == 0, (
        f"Since last run must not list unchanged fields; got diff lines: {diff_lines}"
    )


def test_since_last_run_exactly_two_changed_fields(tmp_path):
    """UAT test 6: two fields changed → exactly two listed."""
    mod = _load_synthesize(tmp_path)
    _make_snapshot(
        tmp_path,
        timestamp="2099-01-01T00:00:00Z",
        health={"status": "healthy"},
        brief_status="ok",
        history_status="ok",
    )
    _make_snapshot(
        tmp_path,
        timestamp="2099-01-01T00:00:01Z",
        health={"status": "degraded"},
        brief_status="absent",
        history_status="ok",
    )
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "Since last run")
    diff_lines = [l.strip() for l in content.splitlines()
                  if l.strip().startswith("-") and not l.strip().startswith("_(source")]
    assert len(diff_lines) == 2, (
        f"Expected exactly 2 diff lines (one per changed field), got {len(diff_lines)}: {diff_lines}"
    )


# ---------------------------------------------------------------------------
# AC: What to do next — max 5 items, all wikilinked
# ---------------------------------------------------------------------------

def test_what_to_do_next_section_exists(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    assert "## What to do next" in situation.read_text()


def test_what_to_do_next_max_five_items(tmp_path):
    """UAT test 5: more than 5 items in input → exactly 5 in output."""
    mod = _load_synthesize(tmp_path)
    # 8 distinct Notion todos (non-done)
    todos = [
        {"id": f"t{i}", "title": f"Todo item {i}", "status": "in_progress",
         "project": "perf-coach", "url": "", "last_edited": ""}
        for i in range(8)
    ]
    _make_snapshot(tmp_path, notion_todos=todos)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "What to do next")
    item_lines = [l.strip() for l in content.splitlines()
                  if re.match(r"^\d+\.", l.strip())]
    assert len(item_lines) == 5, (
        f"Expected exactly 5 items in 'What to do next', got {len(item_lines)}: {item_lines}"
    )


def test_what_to_do_next_all_wikilinked(tmp_path):
    mod = _load_synthesize(tmp_path)
    todos = [
        {"id": f"t{i}", "title": f"Action item {i}", "status": "open",
         "project": "perf-coach", "url": "", "last_edited": ""}
        for i in range(3)
    ]
    _make_snapshot(tmp_path, notion_todos=todos)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "What to do next")
    item_lines = [l.strip() for l in content.splitlines()
                  if re.match(r"^\d+\.", l.strip())]
    assert item_lines, "Expected at least one item in 'What to do next'"
    for line in item_lines:
        assert "[[" in line and "]]" in line, (
            f"Item must be wikilinked (contain [[...]]), got: {line!r}"
        )


# ---------------------------------------------------------------------------
# AC: From the journal section
# ---------------------------------------------------------------------------

def test_from_the_journal_section_exists(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    assert "## From the journal" in situation.read_text()


def test_from_the_journal_populated_from_snapshot(tmp_path):
    mod = _load_synthesize(tmp_path)
    entries = [
        {
            "date": "2099-01-01",
            "path": "2099-01-01.md",
            "frontmatter": {},
            "target_lines": ["perf-coach is looking good today"],
            "concerns_lines": [],
        }
    ]
    _make_snapshot(tmp_path, journal_entries=entries)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "From the journal")
    assert "perf-coach" in content.lower() or "2099-01-01" in content, (
        f"Journal section should contain data from journal entries: {content!r}"
    )


# ---------------------------------------------------------------------------
# AC: Open questions section
# ---------------------------------------------------------------------------

def test_open_questions_section_exists(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    assert "## Open questions" in situation.read_text()


def test_open_questions_from_snapshot(tmp_path):
    mod = _load_synthesize(tmp_path)
    question_issues = [
        {
            "number": 99,
            "title": "Should we refactor auth?",
            "state": "open",
            "labels": [{"name": "question"}],
            "assignees": [],
        }
    ]
    _make_snapshot(tmp_path, issues=question_issues)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "Open questions")
    assert "auth" in content.lower() or "99" in content, (
        f"Open questions should include question-labeled issues: {content!r}"
    )


# ---------------------------------------------------------------------------
# AC: Drift section — top 3 drift signals
# ---------------------------------------------------------------------------

def test_drift_section_exists(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    assert "## Drift" in situation.read_text()


def test_drift_section_not_empty(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "Drift")
    assert content, "## Drift section must not be empty"


def test_drift_at_most_three_signals(tmp_path):
    mod = _load_synthesize(tmp_path)
    # Two snapshots with multiple changes to generate many signals
    _make_snapshot(
        tmp_path,
        timestamp="2099-01-01T00:00:00Z",
        health={"status": "healthy"},
        brief_status="ok",
        history_status="ok",
        changed_files=["docs/A.md", "docs/B.md"],
    )
    _make_snapshot(
        tmp_path,
        timestamp="2099-01-01T00:00:01Z",
        health={"status": "degraded"},
        brief_status="absent",
        history_status="absent",
        changed_files=["docs/A.md", "docs/B.md", "docs/C.md"],
    )
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = _section_content(situation.read_text(), "Drift")
    signal_lines = [l.strip() for l in content.splitlines()
                    if l.strip().startswith("-") and not l.strip().startswith("_(source")]
    assert len(signal_lines) <= 3, (
        f"Drift must contain at most 3 signals, got {len(signal_lines)}: {signal_lines}"
    )


# ---------------------------------------------------------------------------
# AC: Every claim traces to a named snapshot file
# ---------------------------------------------------------------------------

def test_sections_have_source_attribution(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    text = situation.read_text()
    # Each section should reference at least one source file
    assert "(source:" in text.lower() or "source:" in text.lower(), (
        "situation.md must have source attributions for its claims"
    )
    # Common source files should be referenced
    assert any(name in text for name in ["manifest.json", "brief.json", "issues.json"]), (
        "situation.md must name the specific snapshot files used"
    )


def test_missing_sources_named_in_note(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path, brief_status="absent")
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    text = situation.read_text()
    # The absent source must be explicitly named
    assert "brief" in text.lower(), (
        "situation.md must name the absent 'brief' source in a note"
    )


# ---------------------------------------------------------------------------
# AC: notes.md byte-identical before and after
# ---------------------------------------------------------------------------

def test_notes_md_not_mutated(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)

    notes_path = tmp_path / "vault" / "projects" / "perf-coach" / "notes.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_content = b"# Notes\n\nSome personal notes here.\n"
    notes_path.write_bytes(notes_content)

    mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")

    assert notes_path.read_bytes() == notes_content, (
        "synthesize() must not modify notes.md"
    )


def test_notes_md_checksum_unchanged_across_runs(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)

    notes_path = tmp_path / "vault" / "projects" / "perf-coach" / "notes.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_bytes(b"# Notes\n\nKeep this unchanged.\n")

    checksum_before = _md5(notes_path)
    mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    checksum_after = _md5(notes_path)

    assert checksum_before == checksum_after, "notes.md checksum must be unchanged after multiple runs"


# ---------------------------------------------------------------------------
# AC: sources_ok is false if any expected source missing; true when all ok
# ---------------------------------------------------------------------------

def test_sources_ok_true_when_all_present(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path, brief_status="ok", history_status="ok")
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    fm = _parse_frontmatter(situation.read_text())
    assert fm.get("sources_ok") is True, "sources_ok must be true when all sources ok"


def test_sources_ok_false_when_source_absent(tmp_path):
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path, brief_status="absent")
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    fm = _parse_frontmatter(situation.read_text())
    assert fm.get("sources_ok") is False, "sources_ok must be false when a source is absent"


def test_sources_ok_false_when_brief_json_missing(tmp_path):
    """UAT test 2: physically remove commander source file → sources_ok: false."""
    mod = _load_synthesize(tmp_path)
    snap = _make_snapshot(tmp_path, include_brief_json=False)
    # Update manifest to reflect absence
    manifest = json.loads((snap / "manifest.json").read_text())
    manifest["sources"]["brief"]["status"] = "absent"
    manifest["sources"]["brief"]["error"] = "file missing"
    (snap / "manifest.json").write_text(json.dumps(manifest, indent=2))

    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    fm = _parse_frontmatter(situation.read_text())
    assert fm.get("sources_ok") is False, (
        "sources_ok must be false when commander source file is missing"
    )


# ---------------------------------------------------------------------------
# AC: two runs on same snapshot → semantically identical (only run differs)
# ---------------------------------------------------------------------------

def test_two_runs_semantically_identical(tmp_path):
    """UAT test 3: same snapshot input → situation.md semantically identical across runs."""
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)

    situation1 = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    text1 = situation1.read_text()

    situation2 = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    text2 = situation2.read_text()

    # Strip the `run:` line (only field expected to differ)
    def strip_run(text):
        return "\n".join(
            line for line in text.splitlines()
            if not line.startswith("run:")
        )

    assert strip_run(text1) == strip_run(text2), (
        "Two runs on identical input must produce semantically identical situation.md "
        "(only 'run' timestamp may differ)"
    )


# ---------------------------------------------------------------------------
# AC: all seven sections present and non-empty (UAT test 1)
# ---------------------------------------------------------------------------

_SEVEN_SECTIONS = [
    "One-liner",
    "Capacity",
    "Since last run",
    "What to do next",
    "From the journal",
    "Open questions",
    "Drift",
]


def test_all_seven_sections_present(tmp_path):
    mod = _load_synthesize(tmp_path)
    todos = [{"id": "t1", "title": "Do something", "status": "open",
              "project": "perf-coach", "url": "", "last_edited": ""}]
    entries = [{"date": "2099-01-01", "path": "x.md", "frontmatter": {},
                "target_lines": ["perf-coach update"], "concerns_lines": []}]
    issues = [{"number": 1, "title": "Open Q?", "state": "open",
               "labels": [{"name": "question"}], "assignees": []}]
    _make_snapshot(tmp_path, notion_todos=todos, journal_entries=entries, issues=issues)
    text = (mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")).read_text()
    for section in _SEVEN_SECTIONS:
        assert f"## {section}" in text, f"Missing section: ## {section}"


def test_all_seven_sections_non_empty(tmp_path):
    mod = _load_synthesize(tmp_path)
    todos = [{"id": "t1", "title": "Action item", "status": "open",
              "project": "perf-coach", "url": "", "last_edited": ""}]
    entries = [{"date": "2099-01-01", "path": "x.md", "frontmatter": {},
                "target_lines": ["perf-coach update"], "concerns_lines": []}]
    issues = [{"number": 1, "title": "Open Q?", "state": "open",
               "labels": [{"name": "question"}], "assignees": []}]
    _make_snapshot(tmp_path, notion_todos=todos, journal_entries=entries, issues=issues)
    text = (mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")).read_text()
    for section in _SEVEN_SECTIONS:
        content = _section_content(text, section)
        assert content, f"Section '## {section}' must not be empty"


# ---------------------------------------------------------------------------
# AC (issue #11): drift.md flags appear in situation.md ## Drift section
# ---------------------------------------------------------------------------

def _write_drift_md(project_dir: Path, flags: list[dict]) -> Path:
    """Write a drift.md in the project dir using the same format as emit_drift_md."""
    lines = ["# Drift Report", ""]
    for i, flag in enumerate(flags, 1):
        lines.append(f"## Flag {i}: {flag['signal_type'].replace('_', ' ').title()}")
        lines.append("")
        lines.append(f"**Claim:** {flag['claim']}")
        lines.append("")
        lines.append(f"**Evidence:** {flag['evidence_path']}")
        lines.append("")
        lines.append(f"**Suggested fix:** {flag['suggested_fix']}")
        lines.append("")
    project_dir.mkdir(parents=True, exist_ok=True)
    drift_path = project_dir / "drift.md"
    drift_path.write_text("\n".join(lines))
    return drift_path


def test_drift_flags_from_drift_md_appear_in_situation(tmp_path):
    """AC3 (issue #11): top 3 drift flags from drift.md are in ## Drift of situation.md."""
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    project_dir = tmp_path / "vault" / "projects" / "perf-coach"
    _write_drift_md(
        project_dir,
        flags=[
            {
                "signal_type": "removed_feature",
                "claim": "`GET /v1/widgets` is available",
                "evidence_path": "docs/api.md (doc) + abc1234 (git)",
                "suggested_fix": "Remove from docs/api.md",
            }
        ],
    )
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    drift_content = _section_content(situation.read_text(), "Drift")
    assert "GET /v1/widgets" in drift_content or "removed_feature" in drift_content.lower(), (
        "## Drift in situation.md must include flags from drift.md"
    )


def test_drift_flags_capped_at_three_even_with_drift_md(tmp_path):
    """AC3 (issue #11): at most 3 drift flags in situation.md even with many in drift.md."""
    mod = _load_synthesize(tmp_path)
    _make_snapshot(tmp_path)
    project_dir = tmp_path / "vault" / "projects" / "perf-coach"
    _write_drift_md(
        project_dir,
        flags=[
            {"signal_type": "removed_feature", "claim": f"claim {i}",
             "evidence_path": f"docs/file{i}.md", "suggested_fix": f"fix {i}"}
            for i in range(5)
        ],
    )
    situation = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    drift_content = _section_content(situation.read_text(), "Drift")
    signal_lines = [l.strip() for l in drift_content.splitlines()
                    if l.strip().startswith("-") and not l.strip().startswith("_(source")]
    # The section may use bullet points or other formatting — just ensure ≤ 3
    assert len(signal_lines) <= 3, (
        f"Drift section must have at most 3 signals, got {len(signal_lines)}"
    )

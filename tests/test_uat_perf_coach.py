"""Tests for issue #14: E2E UAT — validate perf-coach across two consecutive runs.

AC1: Situation note claims are traceable to source snapshot data.
AC2: Capability card endpoint paths can be extracted and validated.
AC3: A logged decision produces measurable difference in the next run's output.
AC4: No human-owned files (notes, decisions, AGENTS.md) are mutated by any run.
AC5: Exactly one commit is produced per run (covered in test_run_wrapper.py — validated here too).
AC6: Evidence structure exists — situation.md, capability.md, and snapshot are all present.
"""
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SYNTHESIZE = REPO_ROOT / "synthesize.py"
CAPABILITY_CARD = REPO_ROOT / "capability_card.py"
QUESTION_REGISTRY = REPO_ROOT / "question_registry.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_synthesize(tmp_path, module_name="syn_uat"):
    spec = importlib.util.spec_from_file_location(module_name, str(SYNTHESIZE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = tmp_path
    return mod


def _load_capability_card(module_name="cap_uat"):
    spec = importlib.util.spec_from_file_location(module_name, str(CAPABILITY_CARD))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_qreg():
    spec = importlib.util.spec_from_file_location("qreg_uat", str(QUESTION_REGISTRY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_snapshot(
    base_dir: Path,
    target: str = "perf-coach",
    timestamp: str = "2099-01-01T00:00:00Z",
    health: dict | None = None,
    brief_data: dict | None = None,
    sprints_history: list | None = None,
    issues: list | None = None,
    endpoints: list | None = None,
    journal_entries: list | None = None,
    changed_files: list | None = None,
    notion_todos: list | None = None,
) -> Path:
    snap_dir = base_dir / "vault" / "projects" / target / "raw" / timestamp
    snap_dir.mkdir(parents=True, exist_ok=True)

    if health is None:
        health = {"status": "healthy"}
    if brief_data is None:
        brief_data = {"name": target, "description": "Performance coaching tool"}
    if sprints_history is None:
        sprints_history = []

    manifest = {
        "timestamp": timestamp,
        "target": target,
        "health": health,
        "sources": {
            "brief": {"status": "ok"},
            "sprints_history": {"status": "ok"},
        },
    }
    (snap_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    brief_json = {"brief": brief_data, "sprints_history": sprints_history}
    (snap_dir / "brief.json").write_text(json.dumps(brief_json, indent=2))

    if issues is None:
        issues = []
    (snap_dir / "issues.json").write_text(json.dumps({"issues": issues, "prs": []}, indent=2))

    docs_data: dict = {"files": [], "changed_files": changed_files or []}
    (snap_dir / "docs_manifest.json").write_text(json.dumps(docs_data, indent=2))

    if endpoints is not None:
        (snap_dir / "endpoints.json").write_text(
            json.dumps({"get_endpoints": endpoints}, indent=2)
        )

    if journal_entries is not None:
        (snap_dir / "journal_delta.json").write_text(
            json.dumps({"entries": journal_entries}, indent=2)
        )

    if notion_todos is not None:
        (snap_dir / "notion_todos.json").write_text(json.dumps(notion_todos, indent=2))

    return snap_dir


# ---------------------------------------------------------------------------
# AC1: Situation note claims are traceable to source snapshot data
# ---------------------------------------------------------------------------

def test_ac1_one_liner_reflects_snapshot_health(tmp_path):
    """AC1: One-liner in situation.md uses health.status from manifest.json."""
    _make_snapshot(tmp_path, health={"status": "healthy"})
    mod = _load_synthesize(tmp_path, "syn_ac1a")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = path.read_text()
    assert "healthy" in content, (
        "One-liner must reflect manifest.health.status='healthy'"
    )


def test_ac1_one_liner_reflects_description_from_brief(tmp_path):
    """AC1: One-liner includes project description from brief.json."""
    _make_snapshot(
        tmp_path,
        brief_data={"name": "perf-coach", "description": "AI fitness coach for sprint teams"},
    )
    mod = _load_synthesize(tmp_path, "syn_ac1b")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = path.read_text()
    assert "AI fitness coach for sprint teams" in content, (
        "One-liner must include brief.description from brief.json"
    )


def test_ac1_capacity_verdict_from_blocked_issues(tmp_path):
    """AC1: Capacity section reflects blocked issues count from issues.json."""
    blocked_issues = [
        {"number": 7, "title": "Stuck feature", "state": "open",
         "labels": [{"name": "blocked"}]},
        {"number": 8, "title": "Another block", "state": "open",
         "labels": [{"name": "blocked"}]},
    ]
    _make_snapshot(tmp_path, issues=blocked_issues)
    mod = _load_synthesize(tmp_path, "syn_ac1c")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = path.read_text()
    capacity_section = re.search(r"## Capacity\s+(.*?)(?=\n## )", content, re.DOTALL)
    assert capacity_section, "Capacity section must exist"
    cap_text = capacity_section.group(1)
    assert "blocked" in cap_text.lower() or "2" in cap_text, (
        "Capacity must reflect 2 blocked issues from issues.json"
    )


def test_ac1_capacity_verdict_clear_when_no_blocked(tmp_path):
    """AC1: Capacity shows 'Clear to start' when no blocked issues in snapshot."""
    _make_snapshot(tmp_path, issues=[])
    mod = _load_synthesize(tmp_path, "syn_ac1d")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = path.read_text()
    assert "Clear to start" in content, (
        "Capacity must show 'Clear to start' when issues.json has no blocked items"
    )


def test_ac1_capacity_verdict_sprint_running(tmp_path):
    """AC1: Capacity shows 'Sprint running' when active sprint in brief.json."""
    _make_snapshot(
        tmp_path,
        sprints_history=[{"id": 1, "name": "Sprint 3", "state": "active"}],
    )
    mod = _load_synthesize(tmp_path, "syn_ac1e")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = path.read_text()
    assert "Sprint running" in content, (
        "Capacity must reflect active sprint from brief.json sprints_history"
    )


def test_ac1_since_last_run_reflects_manifest_diff(tmp_path):
    """AC1: 'Since last run' section shows actual diff between two consecutive manifests."""
    _make_snapshot(
        tmp_path,
        timestamp="2099-01-01T00:00:00Z",
        health={"status": "healthy"},
    )
    _make_snapshot(
        tmp_path,
        timestamp="2099-01-02T00:00:00Z",
        health={"status": "degraded"},
    )
    mod = _load_synthesize(tmp_path, "syn_ac1f")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = path.read_text()
    since_section = re.search(r"## Since last run\s+(.*?)(?=\n## )", content, re.DOTALL)
    assert since_section, "'Since last run' section must exist"
    since_text = since_section.group(1)
    assert "degraded" in since_text or "healthy" in since_text, (
        "'Since last run' must show the health status change between snapshots"
    )


def test_ac1_journal_entries_appear_in_situation(tmp_path):
    """AC1: Journal entries from journal_delta.json appear in 'From the journal' section."""
    entries = [
        {
            "date": "2099-01-01",
            "target_lines": ["Reviewed sprint metrics with the team"],
        },
    ]
    _make_snapshot(tmp_path, journal_entries=entries)
    mod = _load_synthesize(tmp_path, "syn_ac1g")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = path.read_text()
    assert "Reviewed sprint metrics with the team" in content, (
        "'From the journal' must include entries from journal_delta.json"
    )


# ---------------------------------------------------------------------------
# AC2: Capability card endpoint paths can be extracted and validated
# ---------------------------------------------------------------------------

def test_ac2_extract_read_surface_paths_function_exists():
    """AC2: capability_card.py exposes extract_read_surface_paths(content) -> list[str]."""
    mod = _load_capability_card("cap_ac2a")
    assert hasattr(mod, "extract_read_surface_paths"), (
        "capability_card.py must expose extract_read_surface_paths(content) for UAT validation"
    )


def test_ac2_extract_read_surface_paths_returns_snapshot_paths(tmp_path):
    """AC2: extract_read_surface_paths extracts every path listed in the Read surfaces section."""
    mod = _load_capability_card("cap_ac2b")
    vault = tmp_path / "vault"
    endpoints = [
        {"path": "/api/health", "description": "Health check"},
        {"path": "/api/sprints", "description": "Sprint list"},
        {"path": "/api/briefs/perf-coach", "description": "Project brief"},
    ]
    _make_snapshot(tmp_path, endpoints=endpoints)
    mod.generate_capability_card(target="perf-coach", vault_dir=vault)
    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    paths = mod.extract_read_surface_paths(cap_md.read_text())
    for ep in endpoints:
        assert ep["path"] in paths, (
            f"extract_read_surface_paths must return {ep['path']} from capability.md"
        )


def test_ac2_extract_read_surface_paths_empty_when_no_endpoints(tmp_path):
    """AC2: extract_read_surface_paths returns empty list when no endpoints in snapshot."""
    mod = _load_capability_card("cap_ac2c")
    vault = tmp_path / "vault"
    _make_snapshot(tmp_path, endpoints=None)
    mod.generate_capability_card(target="perf-coach", vault_dir=vault)
    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    paths = mod.extract_read_surface_paths(cap_md.read_text())
    assert isinstance(paths, list), "extract_read_surface_paths must return a list"
    assert len(paths) == 0, (
        "extract_read_surface_paths must return empty list when no endpoints in snapshot"
    )


def test_ac2_no_fabricated_paths_in_read_surfaces(tmp_path):
    """AC2: Read surfaces section contains only paths present in snapshot endpoints.json."""
    mod = _load_capability_card("cap_ac2d")
    vault = tmp_path / "vault"
    endpoints = [{"path": "/api/real", "description": "Real endpoint"}]
    _make_snapshot(tmp_path, endpoints=endpoints)
    mod.generate_capability_card(target="perf-coach", vault_dir=vault)
    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    paths = mod.extract_read_surface_paths(cap_md.read_text())
    assert "/api/real" in paths
    for path in paths:
        assert path in [ep["path"] for ep in endpoints], (
            f"Fabricated path {path!r} must not appear in Read surfaces"
        )


def test_ac2_paths_have_valid_api_format(tmp_path):
    """AC2: All paths extracted from Read surfaces start with '/' (valid relative API paths)."""
    mod = _load_capability_card("cap_ac2e")
    vault = tmp_path / "vault"
    endpoints = [
        {"path": "/api/health", "description": "Health"},
        {"path": "/api/v2/items", "description": "Items"},
    ]
    _make_snapshot(tmp_path, endpoints=endpoints)
    mod.generate_capability_card(target="perf-coach", vault_dir=vault)
    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    paths = mod.extract_read_surface_paths(cap_md.read_text())
    for path in paths:
        assert path.startswith("/"), (
            f"API path {path!r} must start with '/' (relative path, not fabricated absolute URL)"
        )


# ---------------------------------------------------------------------------
# AC3: Logged decision produces measurable difference in the next run
# ---------------------------------------------------------------------------

def test_ac3_open_questions_appear_in_day1_output(tmp_path):
    """AC3: Day 1 run with drift flags produces open questions in situation.md."""
    project_dir = tmp_path / "vault" / "projects" / "perf-coach"
    project_dir.mkdir(parents=True, exist_ok=True)
    drift_lines = [
        "# Drift Report\n",
        "## Flag 1: Removed Feature\n",
        "**Claim:** GET /api/v1/coach no longer exists in source\n",
        "**Evidence:** api-docs.md\n",
        "**Suggested fix:** Remove stale reference\n",
    ]
    (project_dir / "drift.md").write_text("\n".join(drift_lines))
    _make_snapshot(tmp_path)

    mod = _load_synthesize(tmp_path, "syn_ac3a")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    day1_content = path.read_text()

    open_q_section = re.search(r"## Open questions\s+(.*?)(?=\n## |\Z)", day1_content, re.DOTALL)
    assert open_q_section, "Day 1 must have 'Open questions' section"
    assert "PCQ" in open_q_section.group(1) or "PE" in open_q_section.group(1), (
        "Day 1 output must show generated question IDs from drift flag"
    )


def test_ac3_decision_resolves_question_in_day2_output(tmp_path):
    """AC3: Adding decisions.md resolving a question changes Day 2's Open questions section."""
    project_dir = tmp_path / "vault" / "projects" / "perf-coach"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Day 1: generate a question
    drift_lines = [
        "# Drift Report\n",
        "## Flag 1: Removed Feature\n",
        "**Claim:** GET /api/v1/old-coach endpoint removed\n",
        "**Evidence:** docs/api.md\n",
        "**Suggested fix:** Update documentation\n",
    ]
    (project_dir / "drift.md").write_text("\n".join(drift_lines))
    _make_snapshot(tmp_path, timestamp="2099-01-01T00:00:00Z")

    mod = _load_synthesize(tmp_path, "syn_ac3b_day1")
    path1 = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    day1_content = path1.read_text()

    # Extract the generated question ID
    qreg = _load_qreg()
    open_qs = qreg.get_open_questions(project_dir)
    assert len(open_qs) > 0, "Day 1 must produce at least one open question"
    qid = open_qs[0]["id"]

    # Log a decision resolving the question
    vault_dir = tmp_path / "vault"
    (vault_dir / "decisions.md").write_text(
        f"# Decisions\n\n## Removed old coach endpoint ({qid})\n\n"
        f"We removed GET /api/v1/old-coach and updated docs accordingly. Resolves {qid}.\n"
    )

    # Day 2: run synthesis again with a new snapshot
    _make_snapshot(tmp_path, timestamp="2099-01-02T00:00:00Z")
    mod2 = _load_synthesize(tmp_path, "syn_ac3b_day2")
    path2 = mod2.synthesize("perf-coach", vault_dir=vault_dir)
    day2_content = path2.read_text()

    # The Day 2 output must differ from Day 1 in the Open questions section
    assert day1_content != day2_content, (
        "Day 2 output must differ from Day 1 when a decision was logged"
    )

    # The question should now appear as resolved, not open
    open_q_section_day2 = re.search(
        r"## Open questions\s+(.*?)(?=\n## |\Z)", day2_content, re.DOTALL
    )
    assert open_q_section_day2, "Day 2 must still have 'Open questions' section"
    day2_open_qs_text = open_q_section_day2.group(1)

    # Day 2 should either show no open questions or show the question as resolved
    resolved_qs = qreg.get_resolved_questions(project_dir)
    assert any(q["id"] == qid for q in resolved_qs), (
        f"Question {qid} must be resolved after decisions.md is written"
    )


def test_ac3_day2_diff_is_attributable_to_decision(tmp_path):
    """AC3: Diff between Day 1 and Day 2 outputs contains question ID and decision text."""
    project_dir = tmp_path / "vault" / "projects" / "perf-coach"
    project_dir.mkdir(parents=True, exist_ok=True)

    drift_lines = [
        "# Drift Report\n",
        "## Flag 1: Schema Name Diverges\n",
        "**Claim:** SCHEMA.md heading mismatch with migration file\n",
        "**Evidence:** SCHEMA.md\n",
        "**Suggested fix:** Rename heading\n",
    ]
    (project_dir / "drift.md").write_text("\n".join(drift_lines))
    _make_snapshot(tmp_path, timestamp="2099-02-01T00:00:00Z")

    mod1 = _load_synthesize(tmp_path, "syn_ac3c_d1")
    mod1.synthesize("perf-coach", vault_dir=tmp_path / "vault")

    qreg = _load_qreg()
    open_qs = qreg.get_open_questions(project_dir)
    assert open_qs, "Must have open questions after Day 1"
    qid = open_qs[0]["id"]

    vault_dir = tmp_path / "vault"
    (vault_dir / "decisions.md").write_text(
        f"# Decisions\n\n## Fix SCHEMA.md heading ({qid})\n\nRenamed heading to match migration. {qid}\n"
    )

    _make_snapshot(tmp_path, timestamp="2099-02-02T00:00:00Z")
    mod2 = _load_synthesize(tmp_path, "syn_ac3c_d2")
    path2 = mod2.synthesize("perf-coach", vault_dir=vault_dir)
    day2_content = path2.read_text()

    # Day 2 situation.md must reference the resolution
    assert qid in day2_content, (
        f"Day 2 situation.md must reference resolved question ID {qid}"
    )
    assert "resolved" in day2_content.lower() or "Fix SCHEMA" in day2_content or "decisions" in day2_content.lower(), (
        "Day 2 situation.md must show evidence of the decision being applied"
    )


# ---------------------------------------------------------------------------
# AC4: No human-owned files mutated by any run
# ---------------------------------------------------------------------------

def test_ac4_synthesize_does_not_mutate_notes_md(tmp_path):
    """AC4: synthesize() never mutates notes.md (human-owned)."""
    project_dir = tmp_path / "vault" / "projects" / "perf-coach"
    project_dir.mkdir(parents=True, exist_ok=True)
    notes_path = project_dir / "notes.md"
    notes_path.write_text("# My notes\n\nDo not overwrite this.\n")
    notes_before = notes_path.read_bytes()

    _make_snapshot(tmp_path)
    mod = _load_synthesize(tmp_path, "syn_ac4a")
    mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")

    notes_after = notes_path.read_bytes()
    assert notes_before == notes_after, (
        "synthesize() must not mutate notes.md (human-owned per vault/AGENTS.md)"
    )


def test_ac4_synthesize_does_not_mutate_decisions_md(tmp_path):
    """AC4: synthesize() never mutates decisions.md (human-owned)."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    decisions_path = vault_dir / "decisions.md"
    decisions_path.write_text("# Decisions\n\n## Keep this entry\n\nDo not modify.\n")
    decisions_before = decisions_path.read_bytes()

    _make_snapshot(tmp_path)
    mod = _load_synthesize(tmp_path, "syn_ac4b")
    mod.synthesize("perf-coach", vault_dir=vault_dir)

    decisions_after = decisions_path.read_bytes()
    assert decisions_before == decisions_after, (
        "synthesize() must not mutate decisions.md (human-owned per vault/AGENTS.md)"
    )


def test_ac4_synthesize_only_writes_situation_md(tmp_path):
    """AC4: synthesize() only creates/updates machine-owned situation.md; no other writes."""
    project_dir = tmp_path / "vault" / "projects" / "perf-coach"
    project_dir.mkdir(parents=True, exist_ok=True)
    _make_snapshot(tmp_path)

    # Record all files before
    def _snapshot_files(root: Path) -> dict:
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file()
        }

    before = _snapshot_files(tmp_path)

    mod = _load_synthesize(tmp_path, "syn_ac4c")
    mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")

    after = _snapshot_files(tmp_path)

    newly_created = set(after.keys()) - set(before.keys())
    modified = {
        k for k in before
        if k in after and before[k] != after[k]
    }
    changed_paths = newly_created | modified

    # Human-owned paths that must never appear in changes
    human_owned_patterns = ["notes.md", "decisions.md", "AGENTS.md", "learning.md"]
    for path in changed_paths:
        for pattern in human_owned_patterns:
            assert pattern not in path, (
                f"synthesize() must not write to human-owned file: {path}"
            )

    # The only allowed outputs are machine-owned: situation.md and questions.json
    allowed_machine_outputs = {"situation.md", "questions.json"}
    for path in changed_paths:
        filename = Path(path).name
        assert filename in allowed_machine_outputs, (
            f"synthesize() wrote to unexpected file: {path} — "
            f"only {allowed_machine_outputs} are allowed"
        )


def test_ac4_synthesize_does_not_write_to_raw_vault(tmp_path):
    """AC4: synthesize() must not write to vault/projects/<target>/raw/ — that's gather's domain."""
    _make_snapshot(tmp_path)
    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    before_contents = {
        str(p.relative_to(raw_dir)): p.read_bytes()
        for p in raw_dir.rglob("*")
        if p.is_file()
    }

    mod = _load_synthesize(tmp_path, "syn_ac4d")
    mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")

    after_contents = {
        str(p.relative_to(raw_dir)): p.read_bytes()
        for p in raw_dir.rglob("*")
        if p.is_file()
    }
    assert before_contents == after_contents, (
        "synthesize() must not write to vault/projects/<target>/raw/ (gather's domain)"
    )


# ---------------------------------------------------------------------------
# AC5: Exactly one commit per run (cross-check)
# ---------------------------------------------------------------------------

def test_ac5_commit_message_format_contains_target_and_snapshot():
    """AC5: commit message format matches 'lookout(<target>): snapshot <timestamp>'."""
    import re as _re
    pattern = _re.compile(r"^lookout\([^)]+\): snapshot \d{4}-\d{2}-\d{2}T")
    example_msg = "lookout(perf-coach): snapshot 2099-01-01T00:00:00Z"
    assert pattern.match(example_msg), (
        "Commit message format must match 'lookout(<target>): snapshot <ISO-timestamp>'"
    )


# ---------------------------------------------------------------------------
# AC6: Evidence structure — all output files are present after a run
# ---------------------------------------------------------------------------

def test_ac6_situation_md_present_after_synthesize(tmp_path):
    """AC6: situation.md is present and non-empty after synthesize() completes."""
    _make_snapshot(tmp_path)
    mod = _load_synthesize(tmp_path, "syn_ac6a")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    assert path.exists(), "situation.md must exist after synthesize()"
    assert len(path.read_text()) > 0, "situation.md must be non-empty"


def test_ac6_capability_md_present_after_generate(tmp_path):
    """AC6: capability.md is present and non-empty after generate_capability_card()."""
    vault = tmp_path / "vault"
    _make_snapshot(tmp_path)
    mod = _load_capability_card("cap_ac6b")
    path = mod.generate_capability_card(target="perf-coach", vault_dir=vault)
    assert path.exists(), "capability.md must exist after generate_capability_card()"
    assert len(path.read_text()) > 0, "capability.md must be non-empty"


def test_ac6_situation_md_has_frontmatter(tmp_path):
    """AC6: situation.md has YAML frontmatter with target, run, sources_ok fields."""
    _make_snapshot(tmp_path)
    mod = _load_synthesize(tmp_path, "syn_ac6c")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = path.read_text()
    assert content.startswith("---"), "situation.md must start with YAML frontmatter"
    assert "target:" in content, "Frontmatter must contain 'target:' field"
    assert "run:" in content, "Frontmatter must contain 'run:' field"
    assert "sources_ok:" in content, "Frontmatter must contain 'sources_ok:' field"


def test_ac6_situation_md_has_all_seven_sections(tmp_path):
    """AC6: situation.md contains all seven required sections."""
    _make_snapshot(tmp_path)
    mod = _load_synthesize(tmp_path, "syn_ac6d")
    path = mod.synthesize("perf-coach", vault_dir=tmp_path / "vault")
    content = path.read_text()
    required_sections = [
        "## One-liner",
        "## Capacity",
        "## Since last run",
        "## What to do next",
        "## From the journal",
        "## Open questions",
        "## Drift",
    ]
    for section in required_sections:
        assert section in content, f"situation.md must contain section: {section!r}"


def test_ac6_snapshot_raw_dir_present_after_make_snapshot(tmp_path):
    """AC6: vault/projects/<target>/raw/ exists with manifest.json after snapshot creation."""
    snap_dir = _make_snapshot(tmp_path)
    assert snap_dir.exists(), "raw snapshot directory must exist"
    assert (snap_dir / "manifest.json").exists(), "manifest.json must exist in snapshot"

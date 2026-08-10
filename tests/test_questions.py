"""
Tests for issue #13: question generation and decision read-back.

AC coverage:
  AC1  — generate question for every drift flag, stalled issue, human-note carry-over
  AC2  — stable IDs never reused
  AC3  — evidence links and 2-3 resolution options per question
  AC4  — read-back removes resolved questions from open list
  AC5  — resolved question's situation note gains cross-link
  AC6  — target doc contradicting logged decision raises drift flag
"""
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SYNTHESIZE = REPO_ROOT / "synthesize.py"
QUESTION_REGISTRY = REPO_ROOT / "question_registry.py"

QUESTION_ID_RE = re.compile(r'\b([A-Z]{2}Q\d+)\b')


def _load_synthesize(tmp_path, module_name="synthesize_test_q"):
    spec = importlib.util.spec_from_file_location(module_name, str(SYNTHESIZE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = tmp_path
    return mod


def _load_registry_mod():
    spec = importlib.util.spec_from_file_location("question_registry_test", str(QUESTION_REGISTRY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_snapshot(
    base_dir: Path,
    target: str = "sk-demo",
    timestamp: str = "2099-01-01T00:00:00Z",
    issues: list | None = None,
    drift_flags: list | None = None,
    notes_content: str | None = None,
    decisions_vault: str | None = None,
    decisions_project: str | None = None,
    doc_files: list | None = None,
) -> Path:
    snap_dir = base_dir / "vault" / "projects" / target / "raw" / timestamp
    snap_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "timestamp": timestamp,
        "target": target,
        "health": {"status": "healthy"},
        "sources": {
            "brief": {"status": "ok"},
            "sprints_history": {"status": "ok"},
        },
    }
    (snap_dir / "manifest.json").write_text(json.dumps(manifest))

    brief_json = {"brief": {"name": target, "description": "test"}, "sprints_history": []}
    (snap_dir / "brief.json").write_text(json.dumps(brief_json))

    if issues is None:
        issues = []
    (snap_dir / "issues.json").write_text(json.dumps({"issues": issues, "prs": []}))

    docs_data: dict = {"files": doc_files or [], "changed_files": []}
    (snap_dir / "docs_manifest.json").write_text(json.dumps(docs_data))

    project_dir = base_dir / "vault" / "projects" / target

    # Write drift.md if flags provided
    if drift_flags is not None:
        drift_lines = ["# Drift Report", ""]
        for i, f in enumerate(drift_flags, 1):
            drift_lines += [
                f"## Flag {i}: {f.get('signal_type', 'drift').replace('_', ' ').title()}",
                "",
                f"**Claim:** {f.get('claim', '')}",
                "",
                f"**Evidence:** {f.get('evidence_path', '')}",
                "",
                f"**Suggested fix:** {f.get('suggested_fix', '')}",
                "",
            ]
        (project_dir / "drift.md").write_text("\n".join(drift_lines))

    if notes_content is not None:
        (project_dir / "notes.md").write_text(notes_content)

    vault_dir = base_dir / "vault"

    if decisions_vault is not None:
        (vault_dir / "decisions.md").write_text(decisions_vault)

    if decisions_project is not None:
        (project_dir / "decisions.md").write_text(decisions_project)

    return snap_dir


def _section_content(text: str, title: str) -> str:
    pattern = rf"## {re.escape(title)}\n(.*?)(?=\n## |\n---|\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# question_registry.py exists
# ---------------------------------------------------------------------------

def test_question_registry_exists():
    assert QUESTION_REGISTRY.exists(), "question_registry.py must exist at repo root"


# ---------------------------------------------------------------------------
# AC2: ID format + prefix + stability
# ---------------------------------------------------------------------------

def test_question_id_format():
    qmod = _load_registry_mod()
    project_dir = Path("/tmp")
    prefix = qmod._get_prefix("sk-demo")
    assert prefix == "SK", f"prefix for 'sk-demo' should be 'SK', got {prefix!r}"


def test_question_id_format_two_letters():
    qmod = _load_registry_mod()
    for name, expected in [("commander", "CO"), ("perf", "PE"), ("ab", "AB")]:
        p = qmod._get_prefix(name)
        assert len(p) == 2 and p.isupper(), f"prefix for {name!r} should be 2 upper letters, got {p!r}"


def test_question_id_never_reused(tmp_path):
    """AC2: IDs issued in run 1 must still appear in run 2 with different IDs for new signals."""
    qmod = _load_registry_mod()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    flag1 = {"signal_type": "removed_feature", "claim": "GET /v1/foo", "evidence_path": "doc1.md", "suggested_fix": "remove it"}
    qmod.generate_questions(project_dir, "sk-demo", [flag1], [], [])

    flag2 = {"signal_type": "removed_feature", "claim": "GET /v1/bar", "evidence_path": "doc2.md", "suggested_fix": "remove it"}
    qmod.generate_questions(project_dir, "sk-demo", [flag2], [], [])

    registry = qmod.load_registry(project_dir)
    ids = list(registry["questions"].keys())
    assert len(ids) == 2, f"Expected 2 unique questions, got {ids}"
    assert ids[0] != ids[1]
    assert all(QUESTION_ID_RE.match(qid) for qid in ids)


def test_same_signal_not_duplicated(tmp_path):
    """AC2: same signal on second run must not produce a new question."""
    qmod = _load_registry_mod()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    flag = {"signal_type": "removed_feature", "claim": "GET /v1/foo", "evidence_path": "d.md", "suggested_fix": "x"}
    qmod.generate_questions(project_dir, "sk-demo", [flag], [], [])
    qmod.generate_questions(project_dir, "sk-demo", [flag], [], [])

    registry = qmod.load_registry(project_dir)
    assert len(registry["questions"]) == 1, "Duplicate signal must not create a second question"


# ---------------------------------------------------------------------------
# AC1 + AC3: question content — drift flag signal
# ---------------------------------------------------------------------------

def test_generates_question_for_drift_flag(tmp_path):
    """AC1: drift flag produces a question entry."""
    qmod = _load_registry_mod()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    flag = {
        "signal_type": "removed_feature",
        "claim": "GET /v1/widgets exists",
        "evidence_path": "api-docs.md (doc) + abc1234 (git)",
        "suggested_fix": "Remove the stale entry",
    }
    new_qs = qmod.generate_questions(project_dir, "sk-demo", [flag], [], [])
    assert len(new_qs) == 1
    q = new_qs[0]
    assert QUESTION_ID_RE.match(q["id"]), f"Bad ID format: {q['id']!r}"
    assert "evidence" in q and q["evidence"], "Question must have evidence"
    assert "options" in q and len(q["options"]) >= 2, "Question must have ≥2 options"


def test_generates_question_for_stalled_issue(tmp_path):
    """AC1: stalled issue produces a question entry."""
    qmod = _load_registry_mod()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    item = {"title": "Migrate to Postgres", "number": 42}
    new_qs = qmod.generate_questions(project_dir, "sk-demo", [], [item], [])
    assert len(new_qs) == 1
    assert "Migrate to Postgres" in new_qs[0]["text"] or "Migrate to Postgres" in new_qs[0]["signal_text"]
    assert "issues.json" in new_qs[0]["evidence"]


def test_generates_question_for_human_note(tmp_path):
    """AC1: human-note carry-over produces a question entry."""
    qmod = _load_registry_mod()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    note = "Should we migrate auth to JWT?"
    new_qs = qmod.generate_questions(project_dir, "sk-demo", [], [], [note])
    assert len(new_qs) == 1
    assert "notes.md" in new_qs[0]["evidence"]
    assert len(new_qs[0].get("options", [])) >= 2, "Human note question needs ≥2 options"


def test_question_has_three_sources_combined(tmp_path):
    """AC1: drift flag + stalled item + human note each produce a question."""
    qmod = _load_registry_mod()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    flag = {"signal_type": "removed_feature", "claim": "GET /foo", "evidence_path": "x.md", "suggested_fix": "fix"}
    item = {"title": "Fix auth", "number": 7}
    note = "Is the DB ready?"

    new_qs = qmod.generate_questions(project_dir, "sk-demo", [flag], [item], [note])
    assert len(new_qs) == 3, f"Expected 3 new questions, got {len(new_qs)}"


# ---------------------------------------------------------------------------
# AC4: read-back removes resolved question from open list
# ---------------------------------------------------------------------------

def test_resolve_from_vault_decisions(tmp_path):
    """AC4: question ID in vault decisions.md → resolved, removed from open list."""
    qmod = _load_registry_mod()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    flag = {"signal_type": "removed_feature", "claim": "GET /old", "evidence_path": "d.md", "suggested_fix": "x"}
    qmod.generate_questions(project_dir, "sk-demo", [flag], [], [])

    registry = qmod.load_registry(project_dir)
    qid = list(registry["questions"].keys())[0]

    # Add decision referencing the question
    (vault_dir / "decisions.md").write_text(
        f"# Decisions\n\n## Decision: Use v2 API (resolves {qid})\n\nWe will migrate to v2.\n"
    )

    resolved = qmod.resolve_questions(project_dir, vault_dir, "sk-demo")
    assert len(resolved) == 1, f"Expected 1 resolved, got {resolved}"
    assert resolved[0]["id"] == qid
    assert resolved[0]["status"] == "resolved"

    open_qs = qmod.get_open_questions(project_dir)
    assert all(q["id"] != qid for q in open_qs), "Resolved question must not appear in open list"


def test_resolve_from_project_decisions(tmp_path):
    """AC4: question ID in project-level decisions.md → resolved."""
    qmod = _load_registry_mod()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    flag = {"signal_type": "todo_still_open", "claim": "- [ ] ship it", "evidence_path": "d.md", "suggested_fix": "x"}
    qmod.generate_questions(project_dir, "sk-demo", [flag], [], [])

    registry = qmod.load_registry(project_dir)
    qid = list(registry["questions"].keys())[0]

    (project_dir / "decisions.md").write_text(
        f"# Decisions\n\n## Choice\n\nThis item is done. Closes {qid}.\n"
    )

    resolved = qmod.resolve_questions(project_dir, vault_dir, "sk-demo")
    assert any(q["id"] == qid for q in resolved)


# ---------------------------------------------------------------------------
# AC5: situation.md shows cross-link for resolved question
# ---------------------------------------------------------------------------

def test_situation_md_cross_link_for_resolved_question(tmp_path):
    """AC5: after resolution, situation.md contains cross-link to the decision entry."""
    snap_dir = _make_snapshot(tmp_path, target="sk-demo")
    qmod = _load_registry_mod()
    project_dir = tmp_path / "vault" / "projects" / "sk-demo"
    vault_dir = tmp_path / "vault"

    # Generate a question then resolve it
    flag = {"signal_type": "removed_feature", "claim": "GET /old/endpoint", "evidence_path": "api.md", "suggested_fix": "remove it"}
    qmod.generate_questions(project_dir, "sk-demo", [flag], [], [])
    registry = qmod.load_registry(project_dir)
    qid = list(registry["questions"].keys())[0]

    decision_heading = "Deprecate old endpoint"
    (vault_dir / "decisions.md").write_text(
        f"# Decisions\n\n## {decision_heading} ({qid})\n\nWe deprecated it.\n"
    )

    mod = _load_synthesize(tmp_path)
    situation_path = mod.synthesize("sk-demo", vault_dir=vault_dir)
    text = situation_path.read_text()

    # Must contain the question ID with a cross-link in the output
    assert qid in text, f"Resolved question ID {qid!r} must appear in situation.md"
    assert "decisions" in text.lower() or "resolved" in text.lower(), \
        "situation.md must reference decisions or show resolved status"


# ---------------------------------------------------------------------------
# AC6: target doc contradicting logged decision → drift flag
# ---------------------------------------------------------------------------

def test_contradiction_raises_drift_flag(tmp_path):
    """AC6: target doc content contradicts a logged decision → drift flag raised."""
    qmod = _load_registry_mod()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    # Decision says GET /v1/old is deprecated
    (vault_dir / "decisions.md").write_text(
        "# Decisions\n\n## Deprecate old endpoint\n\n**Deprecated:** GET /v1/old\n"
    )

    # Doc file still mentions the deprecated endpoint
    docs_manifest = {
        "files": [{"path": "api-docs.md", "content": "The API exposes GET /v1/old for legacy clients."}],
        "changed_files": [],
    }

    flags = qmod.detect_decision_contradictions(project_dir, vault_dir, docs_manifest)
    assert len(flags) >= 1, f"Expected at least 1 contradiction flag, got {flags}"
    assert any("GET /v1/old" in f["claim"] or "GET /v1/old" in f["suggested_fix"] for f in flags)
    assert any("suggested_fix" in f and f["suggested_fix"] for f in flags)


def test_no_contradiction_when_doc_does_not_mention_deprecated(tmp_path):
    """AC6: no drift flag when doc doesn't mention deprecated item."""
    qmod = _load_registry_mod()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    (vault_dir / "decisions.md").write_text(
        "# Decisions\n\n## Deprecate old endpoint\n\n**Deprecated:** GET /v1/old\n"
    )

    docs_manifest = {
        "files": [{"path": "api-docs.md", "content": "The API exposes GET /v2/new for all clients."}],
        "changed_files": [],
    }

    flags = qmod.detect_decision_contradictions(project_dir, vault_dir, docs_manifest)
    assert len(flags) == 0, f"Expected no contradiction flags, got {flags}"


# ---------------------------------------------------------------------------
# Integration: synthesize() includes questions in Open questions section
# ---------------------------------------------------------------------------

def test_synthesize_generates_question_from_drift_flag(tmp_path):
    """AC1 (integration): drift flag in drift.md → question appears in situation.md."""
    flags = [
        {
            "signal_type": "removed_feature",
            "claim": "GET /v1/widgets",
            "evidence_path": "api-docs.md",
            "suggested_fix": "Remove stale reference",
        }
    ]
    _make_snapshot(tmp_path, target="sk-demo", drift_flags=flags)

    mod = _load_synthesize(tmp_path)
    situation_path = mod.synthesize("sk-demo", vault_dir=tmp_path / "vault")
    text = situation_path.read_text()
    open_q_section = _section_content(text, "Open questions")

    assert "SKQ" in open_q_section or "SKQ" in text, \
        "Open questions section must contain a generated question with SK prefix"
    assert "GET /v1/widgets" in open_q_section or "GET /v1/widgets" in text, \
        "Question must reference the drift flag claim"


def test_synthesize_generates_question_from_stalled_issue(tmp_path):
    """AC1 (integration): blocked issue → question in Open questions."""
    issues = [{"number": 5, "title": "Stuck migration", "state": "open",
                "labels": [{"name": "blocked"}]}]
    _make_snapshot(tmp_path, target="sk-demo", issues=issues)

    mod = _load_synthesize(tmp_path)
    situation_path = mod.synthesize("sk-demo", vault_dir=tmp_path / "vault")
    text = situation_path.read_text()
    open_q_section = _section_content(text, "Open questions")

    assert "SKQ" in open_q_section or "SKQ" in text, \
        "Blocked issue must produce a question with SK prefix"
    assert "Stuck migration" in open_q_section or "Stuck migration" in text, \
        "Question must reference the stalled item title"


def test_synthesize_generates_question_from_notes(tmp_path):
    """AC1 (integration): notes.md carry-over line → question in Open questions."""
    _make_snapshot(tmp_path, target="sk-demo", notes_content="Should we switch to async processing?\n")

    mod = _load_synthesize(tmp_path)
    situation_path = mod.synthesize("sk-demo", vault_dir=tmp_path / "vault")
    text = situation_path.read_text()

    assert "SKQ" in text, "Human note carry-over must produce a question"

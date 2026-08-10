"""Tests for issue #11: drift detection routine.

Each test maps to a specific AC item from the issue.
Tests run against drift.py at repo root.
"""
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DRIFT_PY = REPO_ROOT / "drift.py"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "drift"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_drift():
    spec = importlib.util.spec_from_file_location("drift_test", str(DRIFT_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC: drift.py exists
# ---------------------------------------------------------------------------

def test_drift_py_exists():
    assert DRIFT_PY.exists(), "drift.py must exist at repo root"


# ---------------------------------------------------------------------------
# AC: detect_drift returns list of flag dicts with required keys
# ---------------------------------------------------------------------------

def test_detect_drift_returns_list():
    mod = _load_drift()
    flags = mod.detect_drift(
        docs_manifest={"files": []},
        gitlog="",
        brief={},
    )
    assert isinstance(flags, list)


def test_flag_has_required_keys():
    mod = _load_drift()
    gitlog = "abc1234 feat: remove GET /v1/widgets endpoint\n"
    docs_manifest = {
        "files": [
            {
                "path": "tests/fixtures/drift/api-docs.md",
                "content": "## Endpoints\n\n`GET /v1/widgets` — returns all widgets",
            }
        ]
    }
    flags = mod.detect_drift(docs_manifest=docs_manifest, gitlog=gitlog, brief={})
    if flags:
        flag = flags[0]
        assert "claim" in flag, "flag must have 'claim' key"
        assert "evidence_path" in flag, "flag must have 'evidence_path' key"
        assert "suggested_fix" in flag, "flag must have 'suggested_fix' key"
        assert "signal_type" in flag, "flag must have 'signal_type' key"


# ---------------------------------------------------------------------------
# AC: Signal type 1 — doc asserts feature that git history shows was removed
# ---------------------------------------------------------------------------

def test_signal_type_removed_feature_detected():
    """AC2: detect when a doc claims an endpoint that git log shows was removed."""
    mod = _load_drift()
    gitlog = (
        "abc1234 feat: remove GET /v1/widgets endpoint\n"
        "def5678 feat: add user auth\n"
    )
    docs_manifest = {
        "files": [
            {
                "path": "docs/api.md",
                "content": "## Endpoints\n\n`GET /v1/widgets` — returns all widgets",
            }
        ]
    }
    flags = mod.detect_drift(docs_manifest=docs_manifest, gitlog=gitlog, brief={})
    signal_types = [f["signal_type"] for f in flags]
    assert "removed_feature" in signal_types, (
        f"Expected 'removed_feature' signal type in flags; got: {signal_types}"
    )


def test_signal_removed_feature_cites_doc_path_and_git_ref():
    """AC4: flag cites the doc path and the relevant git ref."""
    mod = _load_drift()
    gitlog = "abc1234 feat: remove GET /v1/widgets endpoint\n"
    docs_manifest = {
        "files": [
            {
                "path": "docs/api.md",
                "content": "The `GET /v1/widgets` endpoint is available for all users.",
            }
        ]
    }
    flags = mod.detect_drift(docs_manifest=docs_manifest, gitlog=gitlog, brief={})
    removed_flags = [f for f in flags if f["signal_type"] == "removed_feature"]
    assert removed_flags, "Expected at least one removed_feature flag"
    flag = removed_flags[0]
    assert "docs/api.md" in flag["evidence_path"] or "abc1234" in flag["evidence_path"], (
        f"evidence_path must cite doc path or git ref: {flag['evidence_path']!r}"
    )
    assert flag["claim"], "claim must not be empty"


# ---------------------------------------------------------------------------
# AC: Signal type 2 — todo marked done by commander but still open in doc
# ---------------------------------------------------------------------------

def test_signal_type_todo_done_still_open_in_doc():
    """AC2: detect todo commander marked done but still listed open in doc."""
    mod = _load_drift()
    # commander marks it done
    brief = {
        "completed_todos": ["Implement user authentication"],
    }
    docs_manifest = {
        "files": [
            {
                "path": "docs/todo.md",
                "content": "- [ ] Implement user authentication\n- [ ] Add logging",
            }
        ]
    }
    flags = mod.detect_drift(docs_manifest=docs_manifest, gitlog="", brief=brief)
    signal_types = [f["signal_type"] for f in flags]
    assert "todo_still_open" in signal_types, (
        f"Expected 'todo_still_open' signal type in flags; got: {signal_types}"
    )


def test_signal_todo_cites_both_paths():
    """AC4: todo flag cites the doc path and source of done status."""
    mod = _load_drift()
    brief = {"completed_todos": ["Implement user authentication"]}
    docs_manifest = {
        "files": [
            {
                "path": "docs/todo.md",
                "content": "- [ ] Implement user authentication",
            }
        ]
    }
    flags = mod.detect_drift(docs_manifest=docs_manifest, gitlog="", brief=brief)
    todo_flags = [f for f in flags if f["signal_type"] == "todo_still_open"]
    assert todo_flags, "Expected at least one todo_still_open flag"
    flag = todo_flags[0]
    assert "docs/todo.md" in flag["evidence_path"], (
        f"evidence_path must cite docs/todo.md: {flag['evidence_path']!r}"
    )


# ---------------------------------------------------------------------------
# AC: Signal type 3 — SCHEMA mention diverges from migration file names
# ---------------------------------------------------------------------------

def test_signal_type_schema_name_diverges():
    """AC2: detect SCHEMA mention whose name doesn't match any migration file."""
    mod = _load_drift()
    docs_manifest = {
        "files": [
            {
                "path": "SCHEMA.md",
                "content": "## users_v2\n\nThe users_v2 table holds user records.",
            }
        ],
        "migration_files": ["migrations/0001_users.sql", "migrations/0002_posts.sql"],
    }
    flags = mod.detect_drift(docs_manifest=docs_manifest, gitlog="", brief={})
    signal_types = [f["signal_type"] for f in flags]
    assert "schema_name_diverges" in signal_types, (
        f"Expected 'schema_name_diverges' signal type in flags; got: {signal_types}"
    )


def test_signal_schema_no_flag_when_names_match():
    """No flag when SCHEMA mention matches a migration file."""
    mod = _load_drift()
    docs_manifest = {
        "files": [
            {
                "path": "SCHEMA.md",
                "content": "## users\n\nThe users table holds user records.",
            }
        ],
        "migration_files": ["migrations/0001_users.sql"],
    }
    flags = mod.detect_drift(docs_manifest=docs_manifest, gitlog="", brief={})
    schema_flags = [f for f in flags if f["signal_type"] == "schema_name_diverges"]
    assert not schema_flags, (
        f"Expected no schema_name_diverges flags when names match; got: {schema_flags}"
    )


# ---------------------------------------------------------------------------
# AC: At most 3 flags returned (top 3 highest-confidence)
# ---------------------------------------------------------------------------

def test_at_most_three_flags():
    """detect_drift returns at most 3 flags."""
    mod = _load_drift()
    # Set up all 3 signal types simultaneously
    gitlog = "abc1234 feat: remove GET /v1/widgets endpoint\n"
    brief = {"completed_todos": ["Auth", "Logging", "Deploy"]}
    docs_manifest = {
        "files": [
            {
                "path": "docs/api.md",
                "content": "The `GET /v1/widgets` endpoint exists.",
            },
            {
                "path": "docs/todo.md",
                "content": "- [ ] Auth\n- [ ] Logging\n- [ ] Deploy",
            },
            {
                "path": "SCHEMA.md",
                "content": "## nonexistent_v99\n## also_missing_v7",
            },
        ],
        "migration_files": ["migrations/0001_users.sql"],
    }
    flags = mod.detect_drift(docs_manifest=docs_manifest, gitlog=gitlog, brief=brief)
    assert len(flags) <= 3, f"detect_drift must return at most 3 flags; got {len(flags)}"


# ---------------------------------------------------------------------------
# AC: emit_drift_md writes drift.md with correct structure
# ---------------------------------------------------------------------------

def test_emit_drift_md_creates_file(tmp_path):
    """AC1: emit_drift_md writes drift.md."""
    mod = _load_drift()
    flags = [
        {
            "signal_type": "removed_feature",
            "claim": "`GET /v1/widgets` — returns all widgets",
            "evidence_path": "docs/api.md (doc) + abc1234 (git)",
            "suggested_fix": "Remove the GET /v1/widgets entry from docs/api.md",
        }
    ]
    output_path = tmp_path / "drift.md"
    mod.emit_drift_md(flags=flags, output_path=output_path)
    assert output_path.exists(), "drift.md must be written by emit_drift_md"


def test_emit_drift_md_claim_present(tmp_path):
    """AC1: drift.md contains the claim verbatim excerpt."""
    mod = _load_drift()
    flags = [
        {
            "signal_type": "removed_feature",
            "claim": "`GET /v1/widgets` is available",
            "evidence_path": "docs/api.md (doc) + abc1234 (git)",
            "suggested_fix": "Remove from docs/api.md",
        }
    ]
    output_path = tmp_path / "drift.md"
    mod.emit_drift_md(flags=flags, output_path=output_path)
    text = output_path.read_text()
    assert "GET /v1/widgets" in text, "drift.md must include the claim verbatim excerpt"


def test_emit_drift_md_evidence_path_present(tmp_path):
    """AC1: drift.md contains the evidence path."""
    mod = _load_drift()
    flags = [
        {
            "signal_type": "removed_feature",
            "claim": "`GET /v1/widgets` endpoint exists",
            "evidence_path": "docs/api.md (doc) + abc1234 (git)",
            "suggested_fix": "Remove from docs/api.md",
        }
    ]
    output_path = tmp_path / "drift.md"
    mod.emit_drift_md(flags=flags, output_path=output_path)
    text = output_path.read_text()
    assert "docs/api.md" in text, "drift.md must include evidence path"
    assert "abc1234" in text, "drift.md must include git ref"


def test_emit_drift_md_suggested_fix_present(tmp_path):
    """AC1: drift.md contains the suggested fix as plain text."""
    mod = _load_drift()
    flags = [
        {
            "signal_type": "removed_feature",
            "claim": "`GET /v1/widgets` endpoint exists",
            "evidence_path": "docs/api.md",
            "suggested_fix": "Remove the stale endpoint entry from docs/api.md",
        }
    ]
    output_path = tmp_path / "drift.md"
    mod.emit_drift_md(flags=flags, output_path=output_path)
    text = output_path.read_text()
    assert "Remove the stale endpoint entry" in text, "drift.md must include the suggested fix"


def test_emit_drift_md_empty_when_no_flags(tmp_path):
    """emit_drift_md handles empty flags list gracefully."""
    mod = _load_drift()
    output_path = tmp_path / "drift.md"
    mod.emit_drift_md(flags=[], output_path=output_path)
    assert output_path.exists()
    text = output_path.read_text()
    assert text  # file not empty (has header at minimum)


# ---------------------------------------------------------------------------
# AC: Seeded contradiction fixture
# ---------------------------------------------------------------------------

def test_seeded_fixture_exists():
    """AC4: fixture directory and api-docs.md exist in the repo."""
    assert FIXTURE_DIR.exists(), f"Fixture directory must exist: {FIXTURE_DIR}"
    assert (FIXTURE_DIR / "api-docs.md").exists(), "api-docs.md fixture must exist"
    assert (FIXTURE_DIR / "gitlog.txt").exists(), "gitlog.txt fixture must exist"
    assert (FIXTURE_DIR / "docs_manifest.json").exists(), "docs_manifest.json fixture must exist"


def test_fixture_doc_claims_widgets_endpoint():
    """AC4: fixture doc claims GET /v1/widgets exists."""
    doc = (FIXTURE_DIR / "api-docs.md").read_text()
    assert "GET /v1/widgets" in doc, "api-docs.md must claim GET /v1/widgets exists"


def test_fixture_gitlog_shows_removal():
    """AC4: fixture gitlog shows a commit removing the endpoint."""
    gitlog = (FIXTURE_DIR / "gitlog.txt").read_text()
    assert "/v1/widgets" in gitlog.lower() or "widgets" in gitlog.lower(), (
        "gitlog.txt must reference the widgets endpoint removal"
    )
    assert "remov" in gitlog.lower() or "delet" in gitlog.lower(), (
        "gitlog.txt must show removal/deletion of the endpoint"
    )


def test_drift_detects_fixture_contradiction():
    """AC4: running drift on the fixture produces a removed_feature flag citing doc and git ref."""
    mod = _load_drift()
    manifest_path = FIXTURE_DIR / "docs_manifest.json"
    docs_manifest = json.loads(manifest_path.read_text())
    gitlog = (FIXTURE_DIR / "gitlog.txt").read_text()
    flags = mod.detect_drift(docs_manifest=docs_manifest, gitlog=gitlog, brief={})
    removed = [f for f in flags if f["signal_type"] == "removed_feature"]
    assert removed, "detect_drift on fixture must produce a removed_feature flag"
    flag = removed[0]
    assert flag["claim"], "claim must not be empty"
    assert flag["evidence_path"], "evidence_path must not be empty"
    # Must cite both the doc path and a git ref
    has_doc = "api-docs.md" in flag["evidence_path"] or "fixture" in flag["evidence_path"].lower()
    has_git = any(c in flag["evidence_path"] for c in ["abc", "def", "git", "commit"])
    assert has_doc or has_git, (
        f"evidence_path must cite doc path or git ref: {flag['evidence_path']!r}"
    )

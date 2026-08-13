"""Tests for issue #97: discover atlas entry points from tests and source names.

#89 implemented docs-parsing discovery only. No project in the fleet declares an
entry point in its docs, so it could never fire. These tests cover the signals
that do exist.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import atlas_seed  # noqa: E402
import atlas_trace  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    """A miniature target: an app entry, a feature module, and tests."""
    r = tmp_path / "proj"
    (r / "tests").mkdir(parents=True)
    (r / "services").mkdir()
    (r / "server.py").write_text("import widgets\nimport gadgets\n")
    (r / "widgets.py").write_text("import helpers\n@router.get('/api/widgets')\ndef w(): pass\n")
    (r / "gadgets.py").write_text("pass\n")
    (r / "helpers.py").write_text("__tablename__ = 'widget_rows'\n")
    (r / "services" / "sourcing.py").write_text("pass\n")
    # names the feature AND imports its implementation
    (r / "tests" / "test_widget_flow.py").write_text("import widgets\n")
    # convention suffix: test_<feature>__<criterion>.py
    (r / "tests" / "test_gadget_flow__42.py").write_text("import gadgets\n")
    # drives the app over HTTP — imports nothing local
    (r / "tests" / "test_http_only.py").write_text(
        "from fastapi.testclient import TestClient\nimport json\n"
    )
    return r


# --- discovery order -------------------------------------------------------

def test_test_file_is_found_by_exact_slug(repo):
    got = atlas_trace._find_test_entry_point("widget-flow", "Widget Flow", repo)
    assert got is not None and got.name == "test_widget_flow.py"


def test_test_file_is_found_with_criterion_suffix(repo):
    """`test_<feature>__<issue>.py` is the mandated convention."""
    got = atlas_trace._find_test_entry_point("gadget-flow", "Gadget Flow", repo)
    assert got is not None and got.name == "test_gadget_flow__42.py"


def test_source_file_named_for_the_feature_is_found(repo):
    got = atlas_trace._find_source_by_name("widgets", "Widgets", repo)
    assert got is not None and got.name == "widgets.py"


def test_source_lookup_never_returns_a_test_file(repo):
    got = atlas_trace._find_source_by_name("widget-flow", "Widget Flow", repo)
    assert got is None or not atlas_trace._is_test_path(got, repo)


def test_app_entry_is_probed_not_hardcoded(repo):
    """The old code assumed app.py, which no project in the fleet has."""
    got = atlas_trace._find_app_entry(repo)
    assert got is not None and got.name == "server.py"


def test_app_entry_returns_none_when_no_candidate_exists(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert atlas_trace._find_app_entry(empty) is None


def test_candidates_are_ordered_most_specific_first(repo):
    cands = atlas_trace._candidate_entry_points("widgets", "Widgets", repo)
    names = [c.name for c in cands]
    assert names[0] == "widgets.py"


def test_application_entry_is_never_a_feature_candidate(repo):
    """server.py is not a feature entry point at any size.

    32 commander features fell back to apps/dashboard/server.py and produced
    byte-identical 3-node diagrams. A size limit misses that, because a shallow
    app trace stays small.
    """
    cands = atlas_trace._candidate_entry_points("widget-flow", "Widget Flow", repo)
    assert all(c.name != "server.py" for c in cands)


# --- candidates are evaluated, not trusted ---------------------------------

def test_entry_point_that_imports_nothing_local_yields_no_diagram(repo):
    """A TestClient-driven test resolves but traces to nothing.

    It is the only candidate for this feature, so it is returned in order to
    name what was attempted — but generate_note must emit no diagram for it.
    """
    ep = atlas_trace._find_entry_point_for_feature("http-only", "Http Only", repo)
    note = atlas_trace.generate_note(
        feature_name="Http Only", source_dir=repo, entry_point_file=ep, issues=[],
    )
    body = note.split("```mermaid")[1].split("```")[0]
    assert body.strip() == "flowchart LR"
    assert "OPEN QUESTION" in note


def test_selection_prefers_a_candidate_that_reaches_real_files(repo):
    ep = atlas_trace._find_entry_point_for_feature("widget-flow", "Widget Flow", repo)
    assert ep == "tests/test_widget_flow.py"


# --- output rules ----------------------------------------------------------

def test_test_files_do_not_appear_in_the_diagram_or_key_files(repo):
    note = atlas_trace.generate_note(
        feature_name="Widget Flow", source_dir=repo,
        entry_point_file="tests/test_widget_flow.py", issues=[],
    )
    # The Entry Points section names the test as the tracing origin, which is
    # correct — the reader should know where the walk began. The test must not
    # appear as a *node* or in Key Files, which describe the implementation.
    diagram = note.split("```mermaid")[1].split("```")[0]
    key_files = note.split("## Key Files")[1].split("## Open Questions")[0]
    assert "test_widget_flow" not in diagram
    assert "test_widget_flow" not in key_files
    assert "widgets.py" in key_files


def test_trace_from_a_test_reaches_the_implementation(repo):
    note = atlas_trace.generate_note(
        feature_name="Widget Flow", source_dir=repo,
        entry_point_file="tests/test_widget_flow.py", issues=[],
    )
    body = note.split("```mermaid")[1].split("```")[0]
    assert "widgets.py" in body


def test_missing_entry_point_yields_an_open_question_and_no_diagram(repo):
    note = atlas_trace.generate_note(
        feature_name="Ghost", source_dir=repo, entry_point_file=None, issues=[],
    )
    assert "OPEN QUESTION" in note
    assert "No entry point could be discovered" in note
    body = note.split("```mermaid")[1].split("```")[0]
    assert body.strip() == "flowchart LR"


def test_whole_app_trace_is_refused_rather_than_emitted(repo, monkeypatch):
    """An entry point reaching the whole program describes the app, not a feature."""
    monkeypatch.setattr(atlas_trace, "_MAX_DIAGRAM_FILES", 2)
    note = atlas_trace.generate_note(
        feature_name="Brand Settings", source_dir=repo,
        entry_point_file="server.py", issues=[],
    )
    body = note.split("```mermaid")[1].split("```")[0]
    assert body.strip() == "flowchart LR", "no diagram may be emitted"
    assert "describes the application" in note


def test_rejected_trace_does_not_leave_its_open_questions_behind(repo, monkeypatch):
    monkeypatch.setattr(atlas_trace, "_MAX_DIAGRAM_FILES", 2)
    note = atlas_trace.generate_note(
        feature_name="Brand Settings", source_dir=repo,
        entry_point_file="server.py", issues=[],
    )
    assert note.count("OPEN QUESTION") == 1


def test_empty_diagram_always_accompanies_an_open_question(repo):
    """AC: an empty diagram may only appear alongside an open question."""
    for ep in (None, "nope.py"):
        note = atlas_trace.generate_note(
            feature_name="X", source_dir=repo, entry_point_file=ep, issues=[],
        )
        body = note.split("```mermaid")[1].split("```")[0]
        if body.strip() == "flowchart LR":
            assert "OPEN QUESTION" in note


def test_is_test_path_is_relative_to_source_dir(tmp_path):
    """An absolute check misfires when the source tree sits under `tests/`."""
    src = tmp_path / "tests" / "fixtures" / "trace-src"
    src.mkdir(parents=True)
    f = src / "app.py"
    f.write_text("pass\n")
    assert atlas_trace._is_test_path(f) is True, "absolute check sees the parent dir"
    assert atlas_trace._is_test_path(f, src) is False


# --- atlas_seed preserves the issue number ---------------------------------

README = """# proj

## Features

### Brand Settings (issue #1)
Text.

### Visual Sourcing (issue #4)
Text.

### No Issue Here
Text.

## Install
"""


def test_issue_number_is_captured_from_the_heading():
    feats = {f["slug"]: f for f in atlas_seed.extract_features(README, None)}
    assert feats["brand-settings"]["issue"] == 1
    assert feats["visual-sourcing"]["issue"] == 4
    assert feats["no-issue-here"]["issue"] is None


def test_issue_number_is_not_part_of_the_display_name():
    feats = {f["slug"]: f for f in atlas_seed.extract_features(README, None)}
    assert feats["brand-settings"]["name"] == "Brand Settings"


def test_stub_frontmatter_records_the_issue():
    assert "issue: 7" in atlas_seed._stub_text("Thing", 7)
    assert "issue: null" in atlas_seed._stub_text("Thing", None)

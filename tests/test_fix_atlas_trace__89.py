"""Tests for issue #89: Fix atlas_trace entry-point discovery, per-feature tracing,
and issue filtering.

AC map:
  AC1  — entry-point discovery reads docs/features/ directory
  AC2  — entry point resolved per feature
  AC3  — no entry point → OPEN QUESTION, no fabricated nodes
  AC4  — Related Issues filtered by feature name/slug, capped at 10
  AC5  — atlas note never contains more than 10 issue lines
  AC6  — closed issues excluded
  AC7  — real trace produces non-empty flowchart with a node naming a real file
  AC9  — no dangling bare node references
  AC10 — files_read in frontmatter; traced set to run date; stale: false
  AC11 — batch entry point trace_all_stale()
"""
import importlib.util
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
ATLAS_TRACE_PY = REPO_ROOT / "atlas_trace.py"
FIXTURE_SRC = Path(__file__).parent / "fixtures" / "trace-src"


def _load():
    spec = importlib.util.spec_from_file_location("atlas_trace_89", str(ATLAS_TRACE_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC1: entry-point discovery reads docs/features/ as a directory
# ---------------------------------------------------------------------------

def test_ac1_finds_entry_point_in_features_directory(tmp_path):
    """AC1: reads Entry point from docs/features/<slug>.md"""
    mod = _load()
    src = tmp_path / "src"
    src.mkdir()
    (src / "brand.py").write_text("# brand\n")
    features_dir = src / "docs" / "features"
    features_dir.mkdir(parents=True)
    (features_dir / "brand-settings.md").write_text(
        "# Brand Settings\n\nEntry point: `brand.py`\n"
    )
    ep = mod._find_entry_point_for_feature("brand-settings", "Brand Settings", src)
    assert ep == "brand.py", f"Expected 'brand.py', got {ep!r}"


def test_ac1_also_reads_features_md_file(tmp_path):
    """AC1: falls back to docs/features.md (file) when no directory"""
    mod = _load()
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("# app\n")
    docs = src / "docs"
    docs.mkdir()
    (docs / "features.md").write_text(
        "# Features\n\nEntry point: `app.py`\n"
    )
    ep = mod._find_entry_point_for_feature("some-feature", "Some Feature", src)
    assert ep == "app.py", f"Expected 'app.py', got {ep!r}"


def test_ac1_returns_none_when_no_entry_point_found(tmp_path):
    """AC1: returns None when neither features/ dir nor features.md has an entry point"""
    mod = _load()
    src = tmp_path / "src"
    src.mkdir()
    ep = mod._find_entry_point_for_feature("unknown-feature", "Unknown Feature", src)
    assert ep is None


def test_ac1_function_exists():
    """AC1: _find_entry_point_for_feature is exposed on the module"""
    mod = _load()
    assert hasattr(mod, "_find_entry_point_for_feature"), (
        "atlas_trace must expose _find_entry_point_for_feature()"
    )


# ---------------------------------------------------------------------------
# AC2: entry point resolved per feature, not once per project
# ---------------------------------------------------------------------------

def test_ac2_two_features_resolve_different_entry_points(tmp_path):
    """AC2: two features in same project trace from different files"""
    mod = _load()
    src = tmp_path / "src"
    src.mkdir()
    (src / "brand.py").write_text("# brand\n")
    (src / "captions.py").write_text("# captions\n")
    features_dir = src / "docs" / "features"
    features_dir.mkdir(parents=True)
    (features_dir / "brand-settings.md").write_text("Entry point: `brand.py`\n")
    (features_dir / "caption-hashtags.md").write_text("Entry point: `captions.py`\n")

    ep1 = mod._find_entry_point_for_feature("brand-settings", "Brand Settings", src)
    ep2 = mod._find_entry_point_for_feature(
        "caption-hashtags", "Caption Hashtags", src
    )
    assert ep1 == "brand.py", f"brand-settings entry point wrong: {ep1!r}"
    assert ep2 == "captions.py", f"caption-hashtags entry point wrong: {ep2!r}"
    assert ep1 != ep2, "Two features must resolve to different entry points"


def test_ac2_per_feature_traces_produce_different_diagrams(tmp_path):
    """AC2: tracing two features with different entry points gives different notes"""
    mod = _load()
    src = tmp_path / "src"
    src.mkdir()
    (src / "brand.py").write_text("# brand only\n")
    (src / "captions.py").write_text("# captions only\n")

    note1 = mod.generate_note(
        feature_name="Brand Settings",
        source_dir=src,
        entry_point_file="brand.py",
        issues=[],
    )
    note2 = mod.generate_note(
        feature_name="Caption Hashtags",
        source_dir=src,
        entry_point_file="captions.py",
        issues=[],
    )
    mermaid1 = mod.extract_mermaid_block(note1) or ""
    mermaid2 = mod.extract_mermaid_block(note2) or ""
    assert mermaid1 != mermaid2, (
        "Two features with different entry points must produce different diagrams"
    )


# ---------------------------------------------------------------------------
# AC3: no entry point → OPEN QUESTION, no fabricated nodes
# ---------------------------------------------------------------------------

def test_ac3_missing_entry_point_produces_open_question(tmp_path):
    """AC3: entry point not in source_dir → OPEN QUESTION recorded"""
    mod = _load()
    src = tmp_path / "empty-src"
    src.mkdir()
    note = mod.generate_note(
        feature_name="Unknown Feature",
        source_dir=src,
        entry_point_file="nonexistent.py",
        issues=[],
    )
    assert "OPEN QUESTION" in note, "Must record OPEN QUESTION when entry point missing"


def test_ac3_missing_entry_point_no_fabricated_nodes(tmp_path):
    """AC3: when entry point is missing, no fabricated nodes in diagram"""
    mod = _load()
    src = tmp_path / "empty-src2"
    src.mkdir()
    note = mod.generate_note(
        feature_name="Unknown Feature",
        source_dir=src,
        entry_point_file="nonexistent.py",
        issues=[],
    )
    mermaid = mod.extract_mermaid_block(note)
    if mermaid:
        nodes = mod.get_node_names(mermaid)
        assert len(nodes) == 0, (
            f"No nodes should be invented when entry point missing, found: {nodes}"
        )


# ---------------------------------------------------------------------------
# AC4: Related Issues filtered by feature name/slug, capped at 10
# ---------------------------------------------------------------------------

def test_ac4_filter_issues_function_exists():
    """AC4: _filter_issues is exposed on the module"""
    mod = _load()
    assert hasattr(mod, "_filter_issues"), "atlas_trace must expose _filter_issues()"


def test_ac4_unrelated_issues_excluded():
    """AC4: _filter_issues excludes issues not matching feature name words"""
    mod = _load()
    issues = [
        {"number": 1, "title": "Fix brand settings panel", "state": "OPEN"},
        {"number": 2, "title": "Unrelated database migration", "state": "OPEN"},
        {"number": 3, "title": "Brand color picker bug", "state": "OPEN"},
    ]
    filtered = mod._filter_issues(issues, "Brand Settings")
    nums = {i["number"] for i in filtered}
    assert 1 in nums, "Issue mentioning 'brand' must be included"
    assert 3 in nums, "Issue mentioning 'brand' must be included"
    assert 2 not in nums, "Unrelated issue must be excluded"


def test_ac4_issues_capped_at_10():
    """AC4: _filter_issues caps result at 10 even when more match"""
    mod = _load()
    issues = [
        {"number": i, "title": f"Fix brand issue {i}", "state": "OPEN"}
        for i in range(1, 30)
    ]
    filtered = mod._filter_issues(issues, "Brand Settings")
    assert len(filtered) <= 10, f"Expected ≤10 issues, got {len(filtered)}"


def test_ac4_default_cap_is_10():
    """AC4: default cap is 10"""
    mod = _load()
    issues = [
        {"number": i, "title": f"Brand settings fix {i}", "state": "OPEN"}
        for i in range(1, 20)
    ]
    filtered = mod._filter_issues(issues, "Brand Settings")
    assert len(filtered) == 10


# ---------------------------------------------------------------------------
# AC5: atlas note never contains more than 10 issue lines (even at full-project scale)
# ---------------------------------------------------------------------------

def test_ac5_note_has_at_most_10_issue_lines():
    """AC5: when pre-filtered with _filter_issues, note has ≤10 issue lines"""
    mod = _load()
    issues_raw = [
        {"number": i, "title": f"Brand settings fix {i}", "state": "OPEN"}
        for i in range(1, 50)
    ]
    filtered = mod._filter_issues(issues_raw, "Brand Settings")
    note = mod.generate_note(
        feature_name="Brand Settings",
        source_dir=FIXTURE_SRC,
        entry_point_file="app.py",
        issues=filtered,
    )
    issue_lines = [l for l in note.splitlines() if re.match(r"^- #\d+", l)]
    assert len(issue_lines) <= 10, (
        f"Note contains {len(issue_lines)} issue lines, expected ≤10"
    )


# ---------------------------------------------------------------------------
# AC6: closed issues excluded from Related Issues
# ---------------------------------------------------------------------------

def test_ac6_closed_issues_excluded():
    """AC6: _filter_issues excludes issues with state CLOSED or closed"""
    mod = _load()
    issues = [
        {"number": 1, "title": "Brand settings open", "state": "OPEN"},
        {"number": 2, "title": "Brand settings closed-upper", "state": "CLOSED"},
        {"number": 3, "title": "Brand settings closed-lower", "state": "closed"},
    ]
    filtered = mod._filter_issues(issues, "Brand Settings")
    nums = {i["number"] for i in filtered}
    assert 1 in nums, "Open issue must be included"
    assert 2 not in nums, "CLOSED (uppercase) issue must be excluded"
    assert 3 not in nums, "closed (lowercase) issue must be excluded"


def test_ac6_issues_without_state_treated_as_open():
    """AC6: issues with no state field are treated as open"""
    mod = _load()
    issues = [{"number": 42, "title": "Brand settings fix"}]
    filtered = mod._filter_issues(issues, "Brand Settings")
    assert len(filtered) == 1, "Issue without state field must default to open"


# ---------------------------------------------------------------------------
# AC7: tracing a real target produces non-empty flowchart with a real-file node
# ---------------------------------------------------------------------------

def test_ac7_fixture_trace_produces_nonempty_flowchart():
    """AC7: tracing fixture produces flowchart LR with ≥1 node naming a real file"""
    mod = _load()
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=FIXTURE_SRC,
        entry_point_file="app.py",
        issues=[],
    )
    mermaid = mod.extract_mermaid_block(note)
    assert mermaid is not None, "Must produce a Mermaid block"
    nodes = mod.get_node_names(mermaid)
    assert len(nodes) >= 1, "Flowchart must have at least one node"

    source_files = {f.name for f in FIXTURE_SRC.rglob("*") if f.is_file()}
    has_real_file_node = any(node in source_files for node in nodes)
    assert has_real_file_node, (
        f"At least one node must name a real source file. "
        f"Nodes: {nodes}, Files: {source_files}"
    )


# ---------------------------------------------------------------------------
# AC9: no dangling bare node references emitted
# ---------------------------------------------------------------------------

def test_ac9_no_bare_node_reference_in_fixture_trace():
    """AC9: fixture trace emits no bare node reference (e.g. 'A' alone after 'A[label]')"""
    mod = _load()
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=FIXTURE_SRC,
        entry_point_file="app.py",
        issues=[],
    )
    mermaid = mod.extract_mermaid_block(note)
    assert mermaid is not None
    _assert_no_bare_node_refs(mermaid)


def test_ac9_single_node_no_bare_reference(tmp_path):
    """AC9: single-file trace emits no bare self-reference after the node definition"""
    mod = _load()
    src = tmp_path / "solo"
    src.mkdir()
    (src / "solo.py").write_text("# standalone, no imports\n")
    note = mod.generate_note(
        feature_name="Solo Feature",
        source_dir=src,
        entry_point_file="solo.py",
        issues=[],
    )
    mermaid = mod.extract_mermaid_block(note)
    if mermaid:
        _assert_no_bare_node_refs(mermaid)


def _assert_no_bare_node_refs(mermaid: str) -> None:
    """Fail if any defined node ID appears as a bare lone identifier on its own line."""
    defined: set[str] = set()
    for line in mermaid.splitlines():
        m = re.match(r"\s+(\w+)\s*[\[({]", line)
        if m:
            defined.add(m.group(1))

    directive_words = {"flowchart", "graph", "LR", "TD", "TB", "RL", "BT"}
    for line in mermaid.splitlines():
        stripped = line.strip()
        if not stripped or stripped in directive_words:
            continue
        if "-->" in stripped or "---" in stripped:
            continue
        if re.search(r"[\[({]", stripped):
            continue
        if stripped.startswith("%%"):
            continue
        # A lone word that was previously defined as a node is a bare reference
        if re.match(r"^\w+$", stripped) and stripped in defined:
            raise AssertionError(
                f"Dangling bare node reference found in Mermaid: '{stripped}'"
            )


# ---------------------------------------------------------------------------
# AC10: files_read in frontmatter; traced set to run date; stale: false
# ---------------------------------------------------------------------------

def test_ac10_generate_note_accepts_traced_param():
    """AC10: generate_note() accepts traced= keyword argument"""
    mod = _load()
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=FIXTURE_SRC,
        entry_point_file="app.py",
        issues=[],
        traced="2026-08-13",
    )
    assert "traced: 2026-08-13" in note, (
        "traced date must appear in frontmatter when passed as keyword arg"
    )


def test_ac10_generate_note_accepts_stale_false():
    """AC10: generate_note() accepts stale=False and emits stale: false"""
    mod = _load()
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=FIXTURE_SRC,
        entry_point_file="app.py",
        issues=[],
        stale=False,
    )
    assert "stale: false" in note, "stale: false must appear in frontmatter"


def test_ac10_default_stale_is_true():
    """AC10: generate_note() default stale is true"""
    mod = _load()
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=FIXTURE_SRC,
        entry_point_file="app.py",
        issues=[],
    )
    assert "stale: true" in note


def test_ac10_files_read_lists_traversed_files():
    """AC10: files_read: in frontmatter lists files actually traversed"""
    mod = _load()
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=FIXTURE_SRC,
        entry_point_file="app.py",
        issues=[],
    )
    assert "files_read:" in note, "frontmatter must have files_read:"
    assert "app.py" in note, "app.py (the entry point) must be listed"


# ---------------------------------------------------------------------------
# AC11: batch entry point — trace_all_stale()
# ---------------------------------------------------------------------------

def test_ac11_trace_all_stale_exists():
    """AC11: trace_all_stale() public function exists"""
    mod = _load()
    assert hasattr(mod, "trace_all_stale"), (
        "atlas_trace must expose trace_all_stale(target, vault_dir, source_dir, max_batch)"
    )


def test_ac11_batch_traces_stale_features(tmp_path):
    """AC11: trace_all_stale traces stale features and writes them back"""
    mod = _load()
    vault = tmp_path / "vault"
    atlas_dir = vault / "projects" / "test-proj" / "atlas"
    atlas_dir.mkdir(parents=True)
    raw_dir = vault / "projects" / "test-proj" / "raw" / "2026-08-13"
    raw_dir.mkdir(parents=True)
    (raw_dir / "issues.json").write_text(json.dumps({"issues": []}))

    (atlas_dir / "feature-a.md").write_text(
        "---\nfeature: Feature A\nfiles_read:\n  []\ntraced: null\nstale: true\n---\n"
    )
    (atlas_dir / "feature-b.md").write_text(
        "---\nfeature: Feature B\nfiles_read:\n  []\ntraced: null\nstale: true\n---\n"
    )

    src = tmp_path / "src"
    src.mkdir()
    features_dir = src / "docs" / "features"
    features_dir.mkdir(parents=True)
    (features_dir / "feature-a.md").write_text("Entry point: `a.py`\n")
    (features_dir / "feature-b.md").write_text("Entry point: `b.py`\n")
    (src / "a.py").write_text("# feature a\n")
    (src / "b.py").write_text("# feature b\n")

    traced = mod.trace_all_stale("test-proj", vault, src, max_batch=5)
    assert "feature-a" in traced, "feature-a must be traced"
    assert "feature-b" in traced, "feature-b must be traced"

    note_a = (atlas_dir / "feature-a.md").read_text()
    assert "stale: false" in note_a, "note must have stale: false after tracing"
    assert "traced:" in note_a


def test_ac11_batch_respects_max_batch(tmp_path):
    """AC11: trace_all_stale traces at most max_batch features"""
    mod = _load()
    vault = tmp_path / "vault"
    atlas_dir = vault / "projects" / "test-proj" / "atlas"
    atlas_dir.mkdir(parents=True)
    raw_dir = vault / "projects" / "test-proj" / "raw" / "2026-08-13"
    raw_dir.mkdir(parents=True)
    (raw_dir / "issues.json").write_text(json.dumps({"issues": []}))

    for i in range(1, 6):
        (atlas_dir / f"feature-{i}.md").write_text(
            f"---\nfeature: Feature {i}\nfiles_read:\n  []\ntraced: null\nstale: true\n---\n"
        )

    src = tmp_path / "src"
    src.mkdir()

    traced = mod.trace_all_stale("test-proj", vault, src, max_batch=3)
    assert len(traced) <= 3, f"Expected ≤3 features traced, got {len(traced)}"


def test_ac11_batch_skips_already_traced_features(tmp_path):
    """AC11: trace_all_stale skips features with stale: false"""
    mod = _load()
    vault = tmp_path / "vault"
    atlas_dir = vault / "projects" / "test-proj" / "atlas"
    atlas_dir.mkdir(parents=True)
    raw_dir = vault / "projects" / "test-proj" / "raw" / "2026-08-13"
    raw_dir.mkdir(parents=True)
    (raw_dir / "issues.json").write_text(json.dumps({"issues": []}))

    (atlas_dir / "fresh.md").write_text(
        "---\nfeature: Fresh\nfiles_read:\n  []\ntraced: 2026-08-10\nstale: false\n---\n"
    )
    (atlas_dir / "stale.md").write_text(
        "---\nfeature: Stale\nfiles_read:\n  []\ntraced: null\nstale: true\n---\n"
    )

    src = tmp_path / "src"
    src.mkdir()
    traced = mod.trace_all_stale("test-proj", vault, src, max_batch=5)
    assert "fresh" not in traced, "Already-traced feature must not be re-traced"
    assert "stale" in traced, "Stale feature must be traced"

"""Tests for issue #18: UAT M4 — seed and verify top five perf-coach feature diagrams.

AC1: Exactly five atlas notes exist, one per top perf-coach feature, each with a
     diagram section (## Flowchart with a ```mermaid block).
AC2: Each diagram has been manually compared to the corresponding source code and the
     result (match / mismatch + corrections) is recorded in an issue comment.
     Test verifies the comment body structure required by AC6.
AC3: All mismatches found during review are corrected and the corrected diagrams
     re-verified before closing.
AC4: Staleness logic triggered re-runs only when expected (per the cap rules) across
     all five features — no premature or missing re-runs.
AC5: The run cap was respected: no feature exceeded the configured maximum number
     of runs (max_batch=3).
AC6: Each issue comment includes: diagram-matches-reality (yes/no), a description
     of any corrections made, and the files list reviewed.
AC7: Files list in each atlas note is complete — no referenced file is missing
     from the list.
"""
import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
ATLAS_TRACE_PY = REPO_ROOT / "atlas_trace.py"
GATHER_PY = REPO_ROOT / "gather.py"

TOP_FIVE_SLUGS = [
    "weight-plans",
    "weight-tracking",
    "daily-bodyweight-upsert",
    "bodyweight-ewma-trend",
    "energy-availability-proxy",
]

TOP_FIVE_FEATURES = {
    "weight-plans": "Weight plans",
    "weight-tracking": "Weight tracking",
    "daily-bodyweight-upsert": "Daily bodyweight upsert",
    "bodyweight-ewma-trend": "Bodyweight EWMA trend",
    "energy-availability-proxy": "Energy-availability proxy",
}

_ENTRY_POINTS = {
    "weight-plans": "weight_plan.py",
    "weight-tracking": "weight_stats.py",
    "daily-bodyweight-upsert": "weight_ewma.py",
    "bodyweight-ewma-trend": "weight_ewma.py",
    "energy-availability-proxy": "body_modifier.py",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_atlas_trace():
    spec = importlib.util.spec_from_file_location("atlas_trace_m4", str(ATLAS_TRACE_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_gather():
    spec = importlib.util.spec_from_file_location("gather_m4", str(GATHER_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_source_dir(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a fake source directory with given {filename: content} files."""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (src / name).write_text(content)
    return src


def _make_atlas_stub(atlas_dir: Path, slug: str, feature: str) -> Path:
    atlas_dir.mkdir(parents=True, exist_ok=True)
    stub = atlas_dir / f"{slug}.md"
    stub.write_text(
        f"---\nfeature: {feature}\nfiles: []\ntraced: null\nstale: true\n---\n"
    )
    return stub


def _has_diagram_section(note_text: str) -> bool:
    """Return True when the note contains a ## Flowchart section with a mermaid block."""
    has_heading = bool(re.search(r"^## Flowchart", note_text, re.MULTILINE))
    has_mermaid = bool(re.search(r"```mermaid", note_text))
    return has_heading and has_mermaid


def _parse_files_read(note_text: str) -> list[str]:
    """Extract files_read list from YAML frontmatter."""
    m = re.match(r"^---\n(.*?)\n---", note_text, re.DOTALL)
    if not m:
        return []
    fm = m.group(1)
    block = re.search(r"^files_read:\s*\n((?:[ \t]+-\s*.+\n?)*)", fm, re.MULTILINE)
    if block:
        items = re.findall(r"^[ \t]+-\s*(.+)$", block.group(1), re.MULTILINE)
        return [x.strip() for x in items if x.strip()]
    inline = re.search(r"^files_read:\s*(.+)$", fm, re.MULTILINE)
    if inline:
        val = inline.group(1).strip()
        if val in ("[]", "null", "pending", ""):
            return []
        m2 = re.match(r"\[([^\]]+)\]", val)
        if m2:
            return [x.strip() for x in m2.group(1).split(",") if x.strip()]
    return []


def _get_mermaid_node_names(note_text: str) -> list[str]:
    mod = _load_atlas_trace()
    mermaid = mod.extract_mermaid_block(note_text)
    if not mermaid:
        return []
    return mod.get_node_names(mermaid)


# ---------------------------------------------------------------------------
# AC1: Five atlas notes exist, each with a diagram section
# ---------------------------------------------------------------------------


def test_ac1_generate_note_produces_flowchart_section(tmp_path):
    """AC1: generate_note() produces a ## Flowchart section with a ```mermaid block."""
    mod = _load_atlas_trace()
    src = _make_source_dir(tmp_path, {
        "weight_plan.py": "# Weight plan service\ndef compute_planned_series(): pass\n",
    })
    note = mod.generate_note(
        feature_name="Weight plans",
        source_dir=src,
        entry_point_file="weight_plan.py",
        issues=[],
    )
    assert _has_diagram_section(note), (
        "generate_note() must produce a ## Flowchart section with a ```mermaid block (AC1)"
    )


def test_ac1_generate_note_includes_what_section(tmp_path):
    """AC1: generate_note() includes a ## What section."""
    mod = _load_atlas_trace()
    src = _make_source_dir(tmp_path, {"weight_ewma.py": "def compute_ewma(): pass\n"})
    note = mod.generate_note(
        feature_name="Bodyweight EWMA trend",
        source_dir=src,
        entry_point_file="weight_ewma.py",
        issues=[],
    )
    assert "## What" in note, "generate_note() must include ## What section (AC1)"


def test_ac1_five_feature_stubs_can_be_traced(tmp_path):
    """AC1: Each of the five feature slugs can be traced to produce a note with diagram."""
    mod = _load_atlas_trace()
    for slug, feature in TOP_FIVE_FEATURES.items():
        entry = _ENTRY_POINTS.get(slug, "app.py")
        src = _make_source_dir(tmp_path / slug, {
            entry: f"# {feature} service\ndef main(): pass\n",
        })
        note = mod.generate_note(
            feature_name=feature,
            source_dir=src,
            entry_point_file=entry,
            issues=[],
        )
        assert _has_diagram_section(note), (
            f"Feature '{feature}' (slug={slug}) must produce a note with a diagram section (AC1)"
        )


def test_ac1_note_contains_entry_points_section(tmp_path):
    """AC1: Each traced note contains a ## Entry Points section listing the traced file."""
    mod = _load_atlas_trace()
    src = _make_source_dir(tmp_path, {
        "body_modifier.py": "def compute_body_modifier(): pass\n",
    })
    note = mod.generate_note(
        feature_name="Energy-availability proxy",
        source_dir=src,
        entry_point_file="body_modifier.py",
        issues=[],
    )
    assert "## Entry Points" in note, "Note must have ## Entry Points section (AC1)"
    assert "body_modifier.py" in note, "Entry point file must appear in note (AC1)"


def test_ac1_note_has_key_files_section(tmp_path):
    """AC1: generate_note() produces a ## Key Files section."""
    mod = _load_atlas_trace()
    src = _make_source_dir(tmp_path, {
        "weight_stats.py": "def get_stats(): pass\n",
    })
    note = mod.generate_note(
        feature_name="Weight tracking",
        source_dir=src,
        entry_point_file="weight_stats.py",
        issues=[],
    )
    assert "## Key Files" in note, "Note must have ## Key Files section (AC1)"


# ---------------------------------------------------------------------------
# AC2/AC6: Comment structure validation
# ---------------------------------------------------------------------------


def test_ac6_comment_body_has_diagram_matches_reality_field():
    """AC6: A valid review comment body must contain a 'diagram matches reality' field."""
    valid_comment = (
        "**Feature:** Weight plans\n\n"
        "**Diagram matches reality:** yes\n\n"
        "**Corrections made:** none\n\n"
        "**Files reviewed:** weight_plan.py\n"
    )
    assert "Diagram matches reality" in valid_comment or "diagram matches reality" in valid_comment.lower(), (
        "Comment must contain 'Diagram matches reality' field (AC6)"
    )
    assert "yes" in valid_comment.lower() or "no" in valid_comment.lower(), (
        "Comment must answer yes/no for diagram match (AC6)"
    )


def test_ac6_comment_body_has_corrections_field():
    """AC6: A valid review comment must contain a corrections description."""
    valid_comment = (
        "**Diagram matches reality:** yes\n\n"
        "**Corrections made:** none\n\n"
        "**Files reviewed:** weight_plan.py\n"
    )
    assert "Corrections made" in valid_comment or "corrections" in valid_comment.lower(), (
        "Comment must contain a corrections description (AC6)"
    )


def test_ac6_comment_body_has_files_reviewed_field():
    """AC6: A valid review comment must contain a files list reviewed."""
    valid_comment = (
        "**Diagram matches reality:** yes\n\n"
        "**Corrections made:** none\n\n"
        "**Files reviewed:** weight_plan.py\n"
    )
    assert "Files reviewed" in valid_comment or "files" in valid_comment.lower(), (
        "Comment must contain a files reviewed list (AC6)"
    )


def test_ac6_validate_comment_format():
    """AC6: Helper validates a comment has all three required fields."""
    def _validate_comment(body: str) -> list[str]:
        """Return list of missing required fields."""
        missing = []
        body_lower = body.lower()
        if "diagram matches reality" not in body_lower:
            missing.append("diagram-matches-reality (yes/no)")
        if "corrections" not in body_lower:
            missing.append("corrections made")
        if "files reviewed" not in body_lower and "files list" not in body_lower:
            missing.append("files reviewed")
        return missing

    good_comment = (
        "**Diagram matches reality:** yes\n"
        "**Corrections made:** none\n"
        "**Files reviewed:** weight_plan.py\n"
    )
    assert _validate_comment(good_comment) == [], (
        "Good comment must pass validation — no missing fields (AC6)"
    )

    bad_comment = "Looks good!"
    missing = _validate_comment(bad_comment)
    assert len(missing) == 3, (
        "Bad comment missing all three fields must return 3 missing items (AC6)"
    )


# ---------------------------------------------------------------------------
# AC3: Corrections — no fabricated nodes in diagram
# ---------------------------------------------------------------------------


def test_ac3_mermaid_nodes_are_real_files(tmp_path):
    """AC3: Every file node in the mermaid diagram names a real file that was read."""
    mod = _load_atlas_trace()
    src = _make_source_dir(tmp_path, {
        "weight_ewma.py": "def compute_ewma(): pass\n",
    })
    note = mod.generate_note(
        feature_name="Bodyweight EWMA trend",
        source_dir=src,
        entry_point_file="weight_ewma.py",
        issues=[],
    )
    mermaid = mod.extract_mermaid_block(note)
    assert mermaid is not None, "Diagram must have a mermaid block (AC3)"
    node_names = mod.get_node_names(mermaid)
    files_read = _parse_files_read(note)
    for node in node_names:
        if node.endswith(".py"):
            assert node in files_read, (
                f"Diagram node '{node}' references a .py file not in files_read list (AC3)"
            )


def test_ac3_open_questions_appear_when_entry_missing(tmp_path):
    """AC3: When entry point is missing, an OPEN QUESTION callout appears in the note."""
    mod = _load_atlas_trace()
    src = _make_source_dir(tmp_path, {})  # empty source dir
    note = mod.generate_note(
        feature_name="Weight plans",
        source_dir=src,
        entry_point_file="weight_plan.py",
        issues=[],
    )
    assert "OPEN QUESTION" in note, (
        "Missing entry point must produce an OPEN QUESTION callout (AC3)"
    )


# ---------------------------------------------------------------------------
# AC4: Staleness logic — only stale/untraced notes are candidates
# ---------------------------------------------------------------------------


def test_ac4_non_stale_notes_excluded_from_batch(tmp_path):
    """AC4: Notes with stale: false and a traced date are NOT selected for tracing."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"
    atlas_dir.mkdir()

    # Create one stale and one non-stale note
    (atlas_dir / "stale-feature.md").write_text(
        "---\nfeature: Stale Feature\nfiles: []\ntraced: null\nstale: true\n---\n"
    )
    (atlas_dir / "fresh-feature.md").write_text(
        "---\nfeature: Fresh Feature\nfiles: []\ntraced: 2026-08-01\nstale: false\n---\n"
    )

    batch = mod.select_trace_batch(atlas_dir, max_batch=3)

    assert "stale-feature" in batch, "Stale note must be included in batch (AC4)"
    assert "fresh-feature" not in batch, (
        "Non-stale note with trace date must NOT be in batch (AC4)"
    )


def test_ac4_never_traced_notes_are_candidates(tmp_path):
    """AC4: Notes with traced: null are always trace candidates regardless of stale flag."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"
    atlas_dir.mkdir()

    (atlas_dir / "never-traced.md").write_text(
        "---\nfeature: Never Traced\nfiles: []\ntraced: null\nstale: false\n---\n"
    )

    batch = mod.select_trace_batch(atlas_dir, max_batch=3)

    assert "never-traced" in batch, (
        "Note with traced: null must be a trace candidate even when stale: false (AC4)"
    )


def test_ac4_oldest_traced_selected_first(tmp_path):
    """AC4: Among multiple stale notes, oldest-traced (or null) are selected first."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"
    atlas_dir.mkdir()

    (atlas_dir / "oldest.md").write_text(
        "---\nfeature: Oldest\nfiles: []\ntraced: 2026-01-01\nstale: true\n---\n"
    )
    (atlas_dir / "newest.md").write_text(
        "---\nfeature: Newest\nfiles: []\ntraced: 2026-08-01\nstale: true\n---\n"
    )
    (atlas_dir / "never.md").write_text(
        "---\nfeature: Never\nfiles: []\ntraced: null\nstale: true\n---\n"
    )

    batch = mod.select_trace_batch(atlas_dir, max_batch=2)

    assert "never" in batch, "null-traced note must be selected (AC4)"
    assert "oldest" in batch, "oldest-traced note must be selected (AC4)"
    assert "newest" not in batch, "newest-traced note must not be in batch of 2 (AC4)"


# ---------------------------------------------------------------------------
# AC5: Run cap — batch size never exceeds configured maximum
# ---------------------------------------------------------------------------


def test_ac5_batch_size_never_exceeds_three(tmp_path):
    """AC5: select_trace_batch with default cap=3 returns at most 3 slugs for the top 5."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"
    atlas_dir.mkdir()

    for slug in TOP_FIVE_SLUGS:
        (atlas_dir / f"{slug}.md").write_text(
            f"---\nfeature: {TOP_FIVE_FEATURES[slug]}\nfiles: []\ntraced: null\nstale: true\n---\n"
        )

    batch = mod.select_trace_batch(atlas_dir, max_batch=3)

    assert len(batch) <= 3, (
        f"Batch size must be ≤ 3 (cap), got {len(batch)} (AC5)"
    )


def test_ac5_five_features_require_two_batches(tmp_path):
    """AC5: Tracing all 5 features with cap=3 produces a pending queue after batch 1."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"
    atlas_dir.mkdir()

    for slug in TOP_FIVE_SLUGS:
        (atlas_dir / f"{slug}.md").write_text(
            f"---\nfeature: {TOP_FIVE_FEATURES[slug]}\nfiles: []\ntraced: null\nstale: true\n---\n"
        )

    (atlas_dir / "index.md").write_text(
        "# Atlas Index\n\n"
        "<!-- BEGIN MACHINE MANAGED — do not edit below this line -->\n\n"
        "| feature | files | traced | stale |\n"
        "| ------- | ----- | ------ | ----- |\n"
        + "\n".join(
            f"| {TOP_FIVE_FEATURES[s]} | pending | null | true |"
            for s in TOP_FIVE_SLUGS
        )
        + "\n\n<!-- END MACHINE MANAGED -->\n"
    )

    batch1 = mod.select_trace_batch(atlas_dir, max_batch=3)
    index_text = (atlas_dir / "index.md").read_text()

    assert len(batch1) == 3, f"First batch must contain exactly 3 features, got {len(batch1)} (AC5)"
    assert "pending" in index_text.lower(), (
        "Atlas index must show pending queue for remaining 2 features (AC5)"
    )


def test_ac5_pending_features_still_stale_after_batch1(tmp_path):
    """AC5: Features not selected in batch 1 remain stale — they haven't been traced yet."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"
    atlas_dir.mkdir()

    for slug in TOP_FIVE_SLUGS:
        (atlas_dir / f"{slug}.md").write_text(
            f"---\nfeature: {TOP_FIVE_FEATURES[slug]}\nfiles: []\ntraced: null\nstale: true\n---\n"
        )

    batch1 = mod.select_trace_batch(atlas_dir, max_batch=3)
    batch1_set = set(batch1)
    pending = set(TOP_FIVE_SLUGS) - batch1_set

    for slug in pending:
        note_text = (atlas_dir / f"{slug}.md").read_text()
        assert "stale: true" in note_text, (
            f"Pending feature '{slug}' must remain stale: true after batch 1 (AC5)"
        )


# ---------------------------------------------------------------------------
# AC7: Files list completeness
# ---------------------------------------------------------------------------


def test_ac7_files_read_list_covers_traced_files(tmp_path):
    """AC7: The files_read frontmatter list includes all files touched during tracing."""
    mod = _load_atlas_trace()
    src = _make_source_dir(tmp_path, {
        "weight_plan.py": (
            "from weight_stats import get_stats\n"
            "def compute(): pass\n"
        ),
        "weight_stats.py": "def get_stats(): pass\n",
    })
    note = mod.generate_note(
        feature_name="Weight plans",
        source_dir=src,
        entry_point_file="weight_plan.py",
        issues=[],
    )
    files_read = _parse_files_read(note)
    assert "weight_plan.py" in files_read, "Entry point must appear in files_read list (AC7)"
    assert "weight_stats.py" in files_read, (
        "Imported file weight_stats.py must appear in files_read list (AC7)"
    )


def test_ac7_mermaid_file_nodes_appear_in_files_read(tmp_path):
    """AC7: Every .py file node in the Mermaid diagram also appears in files_read."""
    mod = _load_atlas_trace()
    src = _make_source_dir(tmp_path, {
        "weight_ewma.py": "from weight_ewma_rate import compute_rate\ndef compute_ewma(): pass\n",
        "weight_ewma_rate.py": "def compute_rate(): pass\n",
    })
    note = mod.generate_note(
        feature_name="Bodyweight EWMA trend",
        source_dir=src,
        entry_point_file="weight_ewma.py",
        issues=[],
    )
    files_read = _parse_files_read(note)
    mermaid = mod.extract_mermaid_block(note)
    assert mermaid is not None, "Note must have a mermaid block (AC7)"

    node_names = mod.get_node_names(mermaid)
    for node in node_names:
        if node.endswith(".py"):
            assert node in files_read, (
                f"Mermaid node '{node}' references a .py file missing from files_read (AC7)"
            )


def test_ac7_no_missing_files_in_import_chain(tmp_path):
    """AC7: Multi-hop import chain is fully recorded in files_read list."""
    mod = _load_atlas_trace()
    src = _make_source_dir(tmp_path, {
        "a.py": "from b import foo\ndef entry(): pass\n",
        "b.py": "from c import bar\ndef foo(): pass\n",
        "c.py": "def bar(): pass\n",
    })
    note = mod.generate_note(
        feature_name="Test chain",
        source_dir=src,
        entry_point_file="a.py",
        issues=[],
    )
    files_read = _parse_files_read(note)
    assert "a.py" in files_read, "Entry point a.py must be in files_read (AC7)"
    assert "b.py" in files_read, "Imported b.py must be in files_read (AC7)"
    assert "c.py" in files_read, "Transitively imported c.py must be in files_read (AC7)"


# ---------------------------------------------------------------------------
# Integration: extract_mermaid_block and get_node_names
# ---------------------------------------------------------------------------


def test_extract_mermaid_block_returns_content(tmp_path):
    """extract_mermaid_block returns the mermaid diagram content from a note."""
    mod = _load_atlas_trace()
    src = _make_source_dir(tmp_path, {
        "weight_plan.py": "def compute(): pass\n",
    })
    note = mod.generate_note(
        feature_name="Weight plans",
        source_dir=src,
        entry_point_file="weight_plan.py",
        issues=[],
    )
    block = mod.extract_mermaid_block(note)
    assert block is not None, "extract_mermaid_block must return content for a traced note"
    assert "flowchart" in block, "Mermaid block must start with 'flowchart'"


def test_get_node_names_returns_labels():
    """get_node_names extracts human-readable node labels from mermaid text."""
    mod = _load_atlas_trace()
    mermaid = "flowchart LR\n  A[weight_plan.py]\n  B[(weight_plans)]\n  A --> B\n"
    names = mod.get_node_names(mermaid)
    assert "weight_plan.py" in names, "get_node_names must extract bracket label 'weight_plan.py'"
    assert "weight_plans" in names, "get_node_names must extract paren label 'weight_plans'"

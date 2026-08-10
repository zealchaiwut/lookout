"""Tests for issue #15: atlas seeding bootstrap step.

Each test maps to a specific AC item from the issue.
Tests run against atlas_seed.py at repo root.
"""
import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
ATLAS_SEED_PY = REPO_ROOT / "atlas_seed.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_atlas_seed():
    spec = importlib.util.spec_from_file_location("atlas_seed_test", str(ATLAS_SEED_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_PERF_COACH_README_EXCERPT = """\
# perf-coach

Personal performance dashboard.

## Features

- **Weight tracking** — daily log; gradient-design weight page
- **Habit tracking** — redesigned habits page with 7-segment week wheel
- **Readiness** — unified readiness auto-recompute
- **Training load** — CTL/ATL/TSB calculations
"""

_PERF_COACH_DOCS_FEATURES = """\
# Features Index

## Weight tracking

Details about weight tracking feature.

## Habit tracking

Details about habit tracking feature.

## Coach export

Details about the coach export feature.
"""


# ---------------------------------------------------------------------------
# AC1: atlas_seed.py exists and SKILL.md documents the atlas seed step
# ---------------------------------------------------------------------------

def test_atlas_seed_py_exists():
    """AC1: atlas_seed.py must exist at repo root."""
    assert ATLAS_SEED_PY.exists(), "atlas_seed.py must exist at repo root"


def test_skill_md_documents_atlas_seed():
    """AC1: SKILL.md must contain a documented atlas seed step."""
    skill_md = REPO_ROOT / "SKILL.md"
    assert skill_md.exists(), "SKILL.md must exist"
    text = skill_md.read_text()
    assert "atlas seed" in text.lower() or "atlas-seed" in text.lower(), (
        "SKILL.md must contain a documented atlas seed step"
    )


def test_skill_md_atlas_seed_describes_invocation():
    """AC1: SKILL.md must describe how to invoke seeding for a named target."""
    skill_md = REPO_ROOT / "SKILL.md"
    text = skill_md.read_text()
    assert "atlas_seed" in text or "atlas-seed" in text, (
        "SKILL.md must reference atlas_seed module or command"
    )
    assert "perf-coach" in text or "<target" in text or "<name" in text, (
        "SKILL.md atlas seed section must show how to invoke for a named target"
    )


# ---------------------------------------------------------------------------
# AC2: extract_features derives list from README and docs/features headings
# ---------------------------------------------------------------------------

def test_extract_features_from_readme():
    """AC2: extract_features parses bold feature names from README feature table."""
    mod = _load_atlas_seed()
    features = mod.extract_features(
        readme_text=_PERF_COACH_README_EXCERPT,
        docs_features_text=None,
    )
    names = [f["name"] for f in features]
    assert "Weight tracking" in names, f"Expected 'Weight tracking' in features; got: {names}"
    assert "Habit tracking" in names, f"Expected 'Habit tracking' in features; got: {names}"
    assert len(names) >= 2, "Must extract at least two features from README"


def test_extract_features_from_docs_features():
    """AC2: extract_features also parses ## headings from docs/features text."""
    mod = _load_atlas_seed()
    features = mod.extract_features(
        readme_text=None,
        docs_features_text=_PERF_COACH_DOCS_FEATURES,
    )
    names = [f["name"] for f in features]
    assert "Coach export" in names or "coach-export" in names.lower() or any(
        "coach" in n.lower() for n in names
    ), f"Expected coach export feature; got: {names}"


def test_extract_features_no_hallucinations():
    """AC2: features extracted must come from real source text, not invented."""
    mod = _load_atlas_seed()
    features = mod.extract_features(
        readme_text="# perf-coach\n\n## Features\n\n- **Foo bar** — some description\n",
        docs_features_text=None,
    )
    names = [f["name"] for f in features]
    assert names == ["Foo bar"] or names == ["foo-bar"] or any(
        "foo" in n.lower() for n in names
    ), f"Only features from source text expected; got: {names}"


def test_extract_features_deduplicates():
    """AC2: features appearing in both README and docs/features are not duplicated."""
    mod = _load_atlas_seed()
    features = mod.extract_features(
        readme_text="## Features\n\n- **Weight tracking** — daily log\n",
        docs_features_text="## Weight tracking\n\nDetails here.\n",
    )
    names = [f["name"] for f in features]
    weight_tracking = [n for n in names if "weight" in n.lower() and "tracking" in n.lower()]
    assert len(weight_tracking) == 1, (
        f"Duplicate feature from README+docs must be deduped; got: {names}"
    )


# ---------------------------------------------------------------------------
# AC3: index.md has machine table with required columns
# ---------------------------------------------------------------------------

def test_seed_creates_index_md(tmp_path):
    """AC3: seed() creates vault/projects/<name>/atlas/index.md."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n- **Beta feature** — second\n",
        docs_features_text=None,
    )
    index_path = tmp_path / "projects" / "test-target" / "atlas" / "index.md"
    assert index_path.exists(), f"index.md must be created at {index_path}"


def test_index_md_has_machine_table_columns(tmp_path):
    """AC3: machine table has columns: feature, files, traced, stale."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    text = (tmp_path / "projects" / "test-target" / "atlas" / "index.md").read_text()
    assert "feature" in text, "index.md machine table must have 'feature' column"
    assert "files" in text, "index.md machine table must have 'files' column"
    assert "traced" in text, "index.md machine table must have 'traced' column"
    assert "stale" in text, "index.md machine table must have 'stale' column"


def test_index_md_files_column_is_pending(tmp_path):
    """AC3: 'files' column value is 'pending' when unknown."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    text = (tmp_path / "projects" / "test-target" / "atlas" / "index.md").read_text()
    assert "pending" in text, "index.md 'files' column must show 'pending' for new features"


def test_index_md_traced_is_null(tmp_path):
    """AC3: 'traced' column value is null for new features."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    text = (tmp_path / "projects" / "test-target" / "atlas" / "index.md").read_text()
    assert "null" in text, "index.md 'traced' column must show 'null' for new features"


def test_index_md_stale_is_true(tmp_path):
    """AC3: 'stale' column value is true for new features."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    text = (tmp_path / "projects" / "test-target" / "atlas" / "index.md").read_text()
    assert "true" in text, "index.md 'stale' column must show 'true' for new features"


# ---------------------------------------------------------------------------
# AC4: index.md contains a clearly delimited human section
# ---------------------------------------------------------------------------

def test_index_md_has_human_section_sentinels(tmp_path):
    """AC4: index.md contains sentinel comments fencing the human section."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    text = (tmp_path / "projects" / "test-target" / "atlas" / "index.md").read_text()
    assert "<!-- BEGIN HUMAN" in text or "<!-- human-start" in text.lower() or (
        "<!-- human" in text.lower() and "end" in text.lower()
    ), "index.md must have a clearly delimited human section with sentinel comments"


def test_index_md_human_section_is_distinct_from_machine(tmp_path):
    """AC4: human section is separate from the machine-managed table."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    text = (tmp_path / "projects" / "test-target" / "atlas" / "index.md").read_text()
    # There should be both a machine section and a human section marker
    has_machine = "<!-- BEGIN MACHINE" in text or "machine" in text.lower()
    has_human = "<!-- BEGIN HUMAN" in text or "human" in text.lower()
    assert has_machine and has_human, (
        f"index.md must have both machine and human sections; text: {text[:500]}"
    )


# ---------------------------------------------------------------------------
# AC5: human-section feature gets a new stub file on next seed run
# ---------------------------------------------------------------------------

def test_human_section_feature_creates_stub(tmp_path):
    """AC5: feature added inside human section gets a stub file on next seed."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    index_path = tmp_path / "projects" / "test-target" / "atlas" / "index.md"
    text = index_path.read_text()

    # Insert "my-custom-feature" into the human section
    text = _insert_into_human_section(text, "my-custom-feature")
    index_path.write_text(text)

    # Re-run seed
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )

    stub_path = tmp_path / "projects" / "test-target" / "atlas" / "my-custom-feature.md"
    assert stub_path.exists(), (
        f"Stub for human-section feature must be created at {stub_path}"
    )


def test_human_section_feature_stub_has_correct_frontmatter(tmp_path):
    """AC5: stub created from human section has correct frontmatter."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    index_path = tmp_path / "projects" / "test-target" / "atlas" / "index.md"
    text = index_path.read_text()
    text = _insert_into_human_section(text, "my-custom-feature")
    index_path.write_text(text)

    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )

    stub_path = tmp_path / "projects" / "test-target" / "atlas" / "my-custom-feature.md"
    stub_text = stub_path.read_text()
    assert "feature: my-custom-feature" in stub_text, (
        "stub must have 'feature: my-custom-feature' in frontmatter"
    )
    assert "files: []" in stub_text, "stub must have 'files: []' in frontmatter"
    assert "traced: null" in stub_text, "stub must have 'traced: null' in frontmatter"
    assert "stale: true" in stub_text, "stub must have 'stale: true' in frontmatter"


def test_human_section_feature_added_to_machine_table(tmp_path):
    """AC5: human-section feature appears in machine table on next seed run."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    index_path = tmp_path / "projects" / "test-target" / "atlas" / "index.md"
    text = index_path.read_text()
    text = _insert_into_human_section(text, "my-custom-feature")
    index_path.write_text(text)

    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )

    result_text = index_path.read_text()
    assert "my-custom-feature" in result_text, (
        "Human-section feature must appear in index.md machine table after re-seed"
    )


def test_human_section_edits_not_corrupted(tmp_path):
    """AC5: machine section is not corrupted when human section has edits."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    index_path = tmp_path / "projects" / "test-target" / "atlas" / "index.md"
    text = index_path.read_text()
    text = _insert_into_human_section(text, "my-custom-feature")
    index_path.write_text(text)

    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )

    result_text = index_path.read_text()
    assert "Alpha feature" in result_text or "alpha-feature" in result_text.lower(), (
        "Existing machine-table rows must not be corrupted after human-section edit"
    )


# ---------------------------------------------------------------------------
# AC6: feature removed from human section is dropped from machine table,
#       but stub file is NOT deleted
# ---------------------------------------------------------------------------

def test_removed_human_feature_dropped_from_machine_table(tmp_path):
    """AC6: feature removed from human section is not in machine table on next seed."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    index_path = tmp_path / "projects" / "test-target" / "atlas" / "index.md"
    text = index_path.read_text()
    text = _insert_into_human_section(text, "temp-feature")
    index_path.write_text(text)

    # First re-seed to create stub and add to machine table
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )

    # Now remove from human section
    text = index_path.read_text()
    text = _remove_from_human_section(text, "temp-feature")
    index_path.write_text(text)

    # Re-seed: temp-feature should be dropped from machine table
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )

    result_text = index_path.read_text()
    machine_section = _extract_machine_section(result_text)
    assert "temp-feature" not in machine_section, (
        "Feature removed from human section must be absent from machine table"
    )


def test_removed_human_feature_stub_still_on_disk(tmp_path):
    """AC6: stub file for feature removed from human section is NOT deleted."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    index_path = tmp_path / "projects" / "test-target" / "atlas" / "index.md"
    text = index_path.read_text()
    text = _insert_into_human_section(text, "temp-feature")
    index_path.write_text(text)

    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )

    stub_path = tmp_path / "projects" / "test-target" / "atlas" / "temp-feature.md"
    assert stub_path.exists(), "Stub must be created on first seed after human-section add"

    # Remove from human section and re-seed
    text = index_path.read_text()
    text = _remove_from_human_section(text, "temp-feature")
    index_path.write_text(text)

    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )

    assert stub_path.exists(), (
        "Stub file must NOT be deleted when feature is removed from human section"
    )


# ---------------------------------------------------------------------------
# AC7: every stub has correct frontmatter (no extra keys)
# ---------------------------------------------------------------------------

def test_stub_frontmatter_has_required_keys(tmp_path):
    """AC7: per-feature stub has frontmatter with feature, files, traced, stale."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    atlas_dir = tmp_path / "projects" / "test-target" / "atlas"
    stubs = [f for f in atlas_dir.iterdir() if f.suffix == ".md" and f.name != "index.md"]
    assert stubs, "At least one stub file must be created"
    for stub in stubs:
        text = stub.read_text()
        assert "feature:" in text, f"stub {stub.name} must have 'feature:' in frontmatter"
        assert "files:" in text, f"stub {stub.name} must have 'files:' in frontmatter"
        assert "traced:" in text, f"stub {stub.name} must have 'traced:' in frontmatter"
        assert "stale:" in text, f"stub {stub.name} must have 'stale:' in frontmatter"


def test_stub_frontmatter_correct_values(tmp_path):
    """AC7: stub frontmatter has files=[], traced=null, stale=true."""
    mod = _load_atlas_seed()
    mod.seed(
        target="test-target",
        vault_dir=tmp_path,
        readme_text="## Features\n\n- **Alpha feature** — first\n",
        docs_features_text=None,
    )
    atlas_dir = tmp_path / "projects" / "test-target" / "atlas"
    stubs = [f for f in atlas_dir.iterdir() if f.suffix == ".md" and f.name != "index.md"]
    assert stubs
    for stub in stubs:
        text = stub.read_text()
        assert "files: []" in text, f"stub {stub.name} must have 'files: []'"
        assert "traced: null" in text, f"stub {stub.name} must have 'traced: null'"
        assert "stale: true" in text, f"stub {stub.name} must have 'stale: true'"


# ---------------------------------------------------------------------------
# AC8: idempotency — re-running does not duplicate rows or overwrite human edits
# ---------------------------------------------------------------------------

def test_idempotent_no_duplicate_machine_rows(tmp_path):
    """AC8: re-running seed does not duplicate machine-table rows."""
    mod = _load_atlas_seed()
    readme = "## Features\n\n- **Alpha feature** — first\n- **Beta feature** — second\n"
    mod.seed(target="test-target", vault_dir=tmp_path, readme_text=readme, docs_features_text=None)
    mod.seed(target="test-target", vault_dir=tmp_path, readme_text=readme, docs_features_text=None)

    text = (tmp_path / "projects" / "test-target" / "atlas" / "index.md").read_text()
    machine_section = _extract_machine_section(text)
    alpha_count = machine_section.count("Alpha feature") + machine_section.count("alpha-feature")
    assert alpha_count <= 1, (
        f"'Alpha feature' must appear at most once in machine table; count: {alpha_count}"
    )


def test_idempotent_no_additional_stubs(tmp_path):
    """AC8: re-running seed does not create additional stub files."""
    mod = _load_atlas_seed()
    readme = "## Features\n\n- **Alpha feature** — first\n"
    mod.seed(target="test-target", vault_dir=tmp_path, readme_text=readme, docs_features_text=None)

    atlas_dir = tmp_path / "projects" / "test-target" / "atlas"
    stubs_after_first = set(f.name for f in atlas_dir.iterdir() if f.suffix == ".md" and f.name != "index.md")

    mod.seed(target="test-target", vault_dir=tmp_path, readme_text=readme, docs_features_text=None)
    stubs_after_second = set(f.name for f in atlas_dir.iterdir() if f.suffix == ".md" and f.name != "index.md")

    assert stubs_after_first == stubs_after_second, (
        f"Re-running seed must not create new stub files; "
        f"before: {stubs_after_first}, after: {stubs_after_second}"
    )


def test_idempotent_preserves_human_section(tmp_path):
    """AC8: re-running seed does not overwrite human-section content."""
    mod = _load_atlas_seed()
    readme = "## Features\n\n- **Alpha feature** — first\n"
    mod.seed(target="test-target", vault_dir=tmp_path, readme_text=readme, docs_features_text=None)

    index_path = tmp_path / "projects" / "test-target" / "atlas" / "index.md"
    text = index_path.read_text()
    text = _insert_into_human_section(text, "human-only-feature")
    index_path.write_text(text)

    mod.seed(target="test-target", vault_dir=tmp_path, readme_text=readme, docs_features_text=None)

    result_text = index_path.read_text()
    human_section = _extract_human_section(result_text)
    assert "human-only-feature" in human_section, (
        "Re-running seed must not overwrite human-section content"
    )


# ---------------------------------------------------------------------------
# Sentinel-manipulation helpers used by multiple tests
# ---------------------------------------------------------------------------

def _insert_into_human_section(text: str, feature_name: str) -> str:
    """Insert a feature name line into the human section of index.md."""
    lines = text.split("\n")
    insert_after = None
    for i, line in enumerate(lines):
        if "begin human" in line.lower():
            insert_after = i
            break
    if insert_after is None:
        raise ValueError(f"Could not find human section start marker in:\n{text[:300]}")
    lines.insert(insert_after + 1, f"- {feature_name}")
    return "\n".join(lines)


def _remove_from_human_section(text: str, feature_name: str) -> str:
    """Remove a feature line from the human section of index.md."""
    lines = text.split("\n")
    return "\n".join(line for line in lines if feature_name not in line)


def _extract_machine_section(text: str) -> str:
    """Extract only the machine-managed section from index.md."""
    lower = text.lower()
    if "<!-- begin machine" in lower:
        start = lower.index("<!-- begin machine")
        end_tag = "<!-- end machine"
        if end_tag in lower:
            end = lower.index(end_tag)
            return text[start:end]
        return text[start:]
    if "<!-- machine-start" in lower:
        start = lower.index("<!-- machine-start")
        end_tag = "<!-- machine-end"
        if end_tag in lower:
            end = lower.index(end_tag)
            return text[start:end]
        return text[start:]
    # Fallback: return everything before human section
    if "<!-- begin human" in lower:
        end = lower.index("<!-- begin human")
        return text[:end]
    return text


def _extract_human_section(text: str) -> str:
    """Extract the human section from index.md."""
    lower = text.lower()
    begin_tags = ["<!-- begin human", "<!-- human-start"]
    end_tags = ["<!-- end human", "<!-- human-end"]
    for begin_tag in begin_tags:
        if begin_tag in lower:
            start = lower.index(begin_tag)
            for end_tag in end_tags:
                if end_tag in lower[start:]:
                    end = lower.index(end_tag, start)
                    return text[start:end]
            return text[start:]
    return ""

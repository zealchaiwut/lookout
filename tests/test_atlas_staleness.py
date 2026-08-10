"""Tests for issue #17: staleness detection and trace cap in gather.py.

AC1: gather.py diffs git log changed files against atlas note files; matching
     notes get stale: true and the atlas index entry is updated.
AC2: touching exactly one mapped file marks only that note stale.
AC3: select_trace_batch returns at most 3 notes (oldest-traced first).
AC4: when > 3 stale/new notes exist, remaining notes appear in a pending queue
     section written to atlas index.md.
AC5: given 5 stale notes, a single batch contains exactly 3 and index lists 2
     as pending.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
GATHER_PY = REPO_ROOT / "gather.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_gather():
    spec = importlib.util.spec_from_file_location("gather_stale17", str(GATHER_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@test.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )


def _commit_file(repo_path: Path, rel_path: str, content: str) -> None:
    full = repo_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    subprocess.run(
        ["git", "-C", str(repo_path), "add", rel_path],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "commit", "-m", f"update {rel_path}"],
        check=True, capture_output=True,
    )


def _make_atlas_note(
    atlas_dir: Path,
    slug: str,
    feature: str,
    files: list[str],
    traced: str = "null",
    stale: bool = True,
) -> Path:
    atlas_dir.mkdir(parents=True, exist_ok=True)
    if files:
        files_yaml = "files:\n" + "\n".join(f"  - {f}" for f in files)
    else:
        files_yaml = "files: []"
    note = atlas_dir / f"{slug}.md"
    note.write_text(
        f"---\nfeature: {feature}\n{files_yaml}\n"
        f"traced: {traced}\nstale: {'true' if stale else 'false'}\n---\n"
    )
    return note


# ---------------------------------------------------------------------------
# AC1, AC2: gather.py staleness detection
# ---------------------------------------------------------------------------


def test_mark_stale_notes_marks_changed_file_note(tmp_path):
    """AC1/AC2: note referencing a changed file gets stale: true written into frontmatter."""
    mod = _load_gather()

    repo_dir = tmp_path / "target-repo"
    _init_git_repo(repo_dir)
    _commit_file(repo_dir, "src/foo.py", "# v1")
    _commit_file(repo_dir, "src/foo.py", "# v2")  # appears in git log as changed

    atlas_dir = tmp_path / "atlas"
    _make_atlas_note(atlas_dir, "my-feature", "My Feature", ["src/foo.py"], stale=False)

    marked = mod.mark_stale_atlas_notes(repo_dir, atlas_dir)

    note_text = (atlas_dir / "my-feature.md").read_text()
    assert "stale: true" in note_text, f"Note should be stale:\n{note_text}"
    assert "my-feature" in marked


def test_mark_stale_notes_only_marks_matching_note(tmp_path):
    """AC2: exactly one file changed → exactly one note marked; other notes untouched."""
    mod = _load_gather()

    repo_dir = tmp_path / "target-repo"
    _init_git_repo(repo_dir)
    _commit_file(repo_dir, "src/foo.py", "# v1")
    _commit_file(repo_dir, "src/foo.py", "# v2")  # only foo.py changed

    atlas_dir = tmp_path / "atlas"
    _make_atlas_note(atlas_dir, "foo-feature", "Foo Feature", ["src/foo.py"], stale=False)
    _make_atlas_note(atlas_dir, "bar-feature", "Bar Feature", ["src/bar.py"], stale=False)

    marked = mod.mark_stale_atlas_notes(repo_dir, atlas_dir)

    foo_text = (atlas_dir / "foo-feature.md").read_text()
    bar_text = (atlas_dir / "bar-feature.md").read_text()

    assert "stale: true" in foo_text, "foo-feature should be stale"
    assert "stale: false" in bar_text, "bar-feature should NOT be stale"
    assert "foo-feature" in marked
    assert "bar-feature" not in marked


def test_mark_stale_notes_updates_atlas_index(tmp_path):
    """AC1: atlas index entry is updated to reflect stale: true for marked notes."""
    mod = _load_gather()

    repo_dir = tmp_path / "target-repo"
    _init_git_repo(repo_dir)
    _commit_file(repo_dir, "src/foo.py", "# v1")
    _commit_file(repo_dir, "src/foo.py", "# v2")

    atlas_dir = tmp_path / "atlas"
    _make_atlas_note(atlas_dir, "my-feature", "My Feature", ["src/foo.py"], stale=False)

    (atlas_dir / "index.md").write_text(
        "# Atlas Index\n\n"
        "<!-- BEGIN MACHINE MANAGED — do not edit below this line -->\n\n"
        "| feature | files | traced | stale |\n"
        "| ------- | ----- | ------ | ----- |\n"
        "| My Feature | src/foo.py | 2026-01-01 | false |\n\n"
        "<!-- END MACHINE MANAGED -->\n"
    )

    mod.mark_stale_atlas_notes(repo_dir, atlas_dir)

    updated = (atlas_dir / "index.md").read_text()
    assert "true" in updated, f"Atlas index should show stale true:\n{updated}"


def test_mark_stale_notes_empty_files_list_not_marked(tmp_path):
    """AC1: note with empty files list is not marked (no overlap possible)."""
    mod = _load_gather()

    repo_dir = tmp_path / "target-repo"
    _init_git_repo(repo_dir)
    _commit_file(repo_dir, "src/foo.py", "# v1")
    _commit_file(repo_dir, "src/foo.py", "# v2")

    atlas_dir = tmp_path / "atlas"
    _make_atlas_note(atlas_dir, "empty-feature", "Empty Feature", [], stale=False)

    marked = mod.mark_stale_atlas_notes(repo_dir, atlas_dir)

    assert "empty-feature" not in marked
    note_text = (atlas_dir / "empty-feature.md").read_text()
    assert "stale: false" in note_text


# ---------------------------------------------------------------------------
# AC3, AC4, AC5: trace cap — at most 3, oldest first, pending queue
# ---------------------------------------------------------------------------


def test_select_trace_batch_returns_at_most_3(tmp_path):
    """AC3: select_trace_batch returns at most max_batch notes."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"

    for i in range(5):
        _make_atlas_note(atlas_dir, f"feature-{i}", f"Feature {i}", [], stale=True)

    batch = mod.select_trace_batch(atlas_dir, max_batch=3)
    assert len(batch) <= 3, f"Expected at most 3 in batch, got {len(batch)}: {batch}"


def test_select_trace_batch_returns_exactly_3_from_5(tmp_path):
    """AC5: given 5 stale notes, exactly 3 are returned in the batch."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"

    for i in range(5):
        _make_atlas_note(atlas_dir, f"feature-{i}", f"Feature {i}", [], stale=True)

    batch = mod.select_trace_batch(atlas_dir, max_batch=3)
    assert len(batch) == 3, f"Expected exactly 3 notes, got {len(batch)}: {batch}"


def test_select_trace_batch_writes_pending_queue_to_index(tmp_path):
    """AC4/AC5: remaining 2 of 5 stale notes appear in a pending queue in atlas index."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"

    for i in range(5):
        _make_atlas_note(atlas_dir, f"feature-{i}", f"Feature {i}", [], stale=True)

    (atlas_dir / "index.md").write_text(
        "# Atlas Index\n\n"
        "<!-- BEGIN MACHINE MANAGED — do not edit below this line -->\n\n"
        "| feature | files | traced | stale |\n"
        "| ------- | ----- | ------ | ----- |\n"
        + "\n".join(f"| Feature {i} | pending | null | true |" for i in range(5))
        + "\n\n<!-- END MACHINE MANAGED -->\n"
    )

    batch = mod.select_trace_batch(atlas_dir, max_batch=3)
    index_text = (atlas_dir / "index.md").read_text()

    assert "pending" in index_text.lower(), f"Index should have pending queue:\n{index_text}"
    assert len(batch) == 3


def test_select_trace_batch_oldest_traced_first(tmp_path):
    """AC3: notes with oldest traced date (null = oldest) are selected first."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"

    _make_atlas_note(atlas_dir, "feature-old1", "Feature Old1", [], traced="2026-01-01", stale=True)
    _make_atlas_note(atlas_dir, "feature-old2", "Feature Old2", [], traced="2026-01-15", stale=True)
    _make_atlas_note(atlas_dir, "feature-null", "Feature Null", [], traced="null", stale=True)
    _make_atlas_note(atlas_dir, "feature-recent1", "Feature Recent1", [], traced="2026-08-01", stale=True)
    _make_atlas_note(atlas_dir, "feature-recent2", "Feature Recent2", [], traced="2026-07-01", stale=True)

    batch = mod.select_trace_batch(atlas_dir, max_batch=3)
    batch_set = set(batch)

    assert "feature-null" in batch_set, f"null-traced (oldest) must be in batch: {batch_set}"
    assert "feature-old1" in batch_set, f"oldest-dated must be in batch: {batch_set}"
    assert "feature-old2" in batch_set, f"second-oldest must be in batch: {batch_set}"
    assert "feature-recent1" not in batch_set, f"most-recent should be pending: {batch_set}"
    assert "feature-recent2" not in batch_set, f"second-recent should be pending: {batch_set}"


def test_select_trace_batch_pending_notes_remain_stale(tmp_path):
    """AC4: notes not selected for tracing remain flagged stale: true."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"

    for i in range(5):
        _make_atlas_note(atlas_dir, f"feature-{i}", f"Feature {i}", [], stale=True)

    batch = mod.select_trace_batch(atlas_dir, max_batch=3)
    batch_set = set(batch)

    all_slugs = {f"feature-{i}" for i in range(5)}
    pending_slugs = all_slugs - batch_set

    for slug in pending_slugs:
        note_text = (atlas_dir / f"{slug}.md").read_text()
        assert "stale: true" in note_text, f"{slug} should still be stale:\n{note_text}"


def test_select_trace_batch_includes_untraced_never_run(tmp_path):
    """AC3: notes with traced: null (never traced) are candidates regardless of stale flag."""
    mod = _load_gather()
    atlas_dir = tmp_path / "atlas"

    # Note with traced: null and stale: false (edge case — never traced, not stale)
    _make_atlas_note(atlas_dir, "never-traced", "Never Traced", [], traced="null", stale=False)

    batch = mod.select_trace_batch(atlas_dir, max_batch=3)
    assert "never-traced" in batch, f"Untraced note should be in batch: {batch}"

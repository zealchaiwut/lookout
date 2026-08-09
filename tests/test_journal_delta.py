"""Tests for issue #8: journal delta collector for target mentions.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import json
import time
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
COLLECTOR = REPO_ROOT / "journal_delta.py"
TARGETS_YAML = REPO_ROOT / "targets.yaml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_collector(module_name="journal_delta_test"):
    spec = importlib.util.spec_from_file_location(module_name, str(COLLECTOR))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_targets(tmp_path, journal_entries_path, targets=None):
    if targets is None:
        targets = {"perf-coach": {"commander_slug": "perf-coach", "github": "test/test", "local": str(tmp_path)}}
    data = {
        "sources": {"journal_entries": str(journal_entries_path)},
        "targets": targets,
    }
    p = tmp_path / "targets.yaml"
    p.write_text(yaml.dump(data))
    return p


def _make_fixture_entries(entries_dir):
    """Three .md files; only 2026-02-14.md mentions perf-coach."""
    entries_dir.mkdir(parents=True, exist_ok=True)

    (entries_dir / "2026-01-10.md").write_text(
        "---\ndate: 2026-01-10\ntags: [personal]\n---\n\nNothing special here.\n"
    )

    (entries_dir / "2026-02-14.md").write_text(
        "---\ndate: 2026-02-14\ntags: [work]\n---\n\nWorking on perf-coach today.\n\n## Concerns\n\nperf-coach tests are slow.\n"
    )

    (entries_dir / "2026-03-01.md").write_text(
        "---\ndate: 2026-03-01\ntags: [personal]\n---\n\nJust a quiet day.\n"
    )


# ---------------------------------------------------------------------------
# AC: targets.yaml is authoritative source for journal_entries path
# ---------------------------------------------------------------------------

def test_reads_journal_path_from_targets_yaml(tmp_path):
    """Collector reads journal_entries path from targets.yaml sources."""
    entries_dir = tmp_path / "entries"
    _make_fixture_entries(entries_dir)
    targets_yaml = _write_targets(tmp_path, entries_dir)

    mod = _load_collector("jd_ac1")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    mod.collect(output_path=out, snapshot_path=tmp_path / "snapshot.json")

    assert out.exists(), "journal_delta.json must be written"


# ---------------------------------------------------------------------------
# AC: first run — all entries capped at 30 newest by mtime
# ---------------------------------------------------------------------------

def test_first_run_considers_all_entries(tmp_path):
    """On first run, all .md files are considered (no snapshot filter)."""
    entries_dir = tmp_path / "entries"
    _make_fixture_entries(entries_dir)
    targets_yaml = _write_targets(tmp_path, entries_dir)

    mod = _load_collector("jd_ac2")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    snap = tmp_path / "snapshot.json"
    mod.collect(output_path=out, snapshot_path=snap)

    data = json.loads(out.read_text())
    entries = data.get("entries", [])
    # One file mentions perf-coach so exactly one entry expected
    assert len(entries) == 1, (
        f"Expected 1 entry (2026-02-14.md mentions target), got {len(entries)}"
    )


def test_first_run_capped_at_30(tmp_path):
    """First run processes at most 30 newest entries."""
    import os
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)

    # Create 35 entries using unique filenames (no frontmatter dates to avoid YAML date parsing issues)
    for i in range(35):
        f = entries_dir / f"entry-{i+1:03d}.md"
        f.write_text(f"# Entry {i+1}\n\nperf-coach mention #{i}\n")
        # Stagger mtime by 1s so ordering is deterministic
        mtime = 1_700_000_000 + i
        os.utime(f, (mtime, mtime))

    targets_yaml = _write_targets(tmp_path, entries_dir)
    mod = _load_collector("jd_ac2b")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    snap = tmp_path / "snapshot.json"
    mod.collect(output_path=out, snapshot_path=snap)

    data = json.loads(out.read_text())
    entries = data.get("entries", [])
    assert len(entries) <= 30, f"First run must cap at 30 entries, got {len(entries)}"


# ---------------------------------------------------------------------------
# AC: subsequent run — only entries newer than snapshot timestamp
# ---------------------------------------------------------------------------

def test_subsequent_run_filters_by_snapshot_timestamp(tmp_path):
    """Second run only picks up entries newer than stored snapshot."""
    entries_dir = tmp_path / "entries"
    _make_fixture_entries(entries_dir)
    targets_yaml = _write_targets(tmp_path, entries_dir)

    mod = _load_collector("jd_ac3a")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    snap = tmp_path / "snapshot.json"

    # First run
    mod.collect(output_path=out, snapshot_path=snap)

    # Second run immediately — no new files
    mod2 = _load_collector("jd_ac3b")
    mod2.TARGETS_YAML = targets_yaml
    mod2.REPO_ROOT = tmp_path
    mod2.collect(output_path=out, snapshot_path=snap)

    data = json.loads(out.read_text())
    entries = data.get("entries", [])
    assert entries == [], (
        f"Second run with unchanged files should produce empty entries, got {entries}"
    )


# ---------------------------------------------------------------------------
# AC: qualifying entry shape — date, path, frontmatter, target lines, concerns
# ---------------------------------------------------------------------------

def test_entry_contains_date_and_path(tmp_path):
    """Each delta entry includes entry date and relative file path."""
    entries_dir = tmp_path / "entries"
    _make_fixture_entries(entries_dir)
    targets_yaml = _write_targets(tmp_path, entries_dir)

    mod = _load_collector("jd_ac4a")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    mod.collect(output_path=out, snapshot_path=tmp_path / "snap.json")

    data = json.loads(out.read_text())
    entry = data["entries"][0]
    assert "date" in entry, "Entry must have a 'date' field"
    assert "path" in entry, "Entry must have a 'path' field"


def test_entry_contains_frontmatter(tmp_path):
    """Each delta entry includes all frontmatter fields."""
    entries_dir = tmp_path / "entries"
    _make_fixture_entries(entries_dir)
    targets_yaml = _write_targets(tmp_path, entries_dir)

    mod = _load_collector("jd_ac4b")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    mod.collect(output_path=out, snapshot_path=tmp_path / "snap.json")

    data = json.loads(out.read_text())
    entry = data["entries"][0]
    assert "frontmatter" in entry, "Entry must have a 'frontmatter' field"
    fm = entry["frontmatter"]
    assert "date" in fm, "Frontmatter must include 'date' key from the .md file"


def test_entry_contains_target_mention_lines(tmp_path):
    """Each delta entry includes lines mentioning a registered target (case-insensitive)."""
    entries_dir = tmp_path / "entries"
    _make_fixture_entries(entries_dir)
    targets_yaml = _write_targets(tmp_path, entries_dir)

    mod = _load_collector("jd_ac4c")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    mod.collect(output_path=out, snapshot_path=tmp_path / "snap.json")

    data = json.loads(out.read_text())
    entry = data["entries"][0]
    assert "target_lines" in entry, "Entry must have 'target_lines'"
    assert any("perf-coach" in line.lower() for line in entry["target_lines"]), (
        "target_lines must contain a line mentioning perf-coach"
    )


def test_entry_contains_concerns_lines(tmp_path):
    """Each delta entry includes lines under ## Concerns or ### Concerns headings."""
    entries_dir = tmp_path / "entries"
    _make_fixture_entries(entries_dir)
    targets_yaml = _write_targets(tmp_path, entries_dir)

    mod = _load_collector("jd_ac4d")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    mod.collect(output_path=out, snapshot_path=tmp_path / "snap.json")

    data = json.loads(out.read_text())
    entry = data["entries"][0]
    assert "concerns_lines" in entry, "Entry must have 'concerns_lines'"
    assert len(entry["concerns_lines"]) > 0, (
        "concerns_lines must contain content from ## Concerns section"
    )


def test_case_insensitive_target_match(tmp_path):
    """Target name matching is case-insensitive."""
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / "2026-05-01.md").write_text(
        "---\ndate: 2026-05-01\n---\n\nWorking on PERF-COACH today.\n"
    )
    targets_yaml = _write_targets(tmp_path, entries_dir)

    mod = _load_collector("jd_ac4e")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    mod.collect(output_path=out, snapshot_path=tmp_path / "snap.json")

    data = json.loads(out.read_text())
    assert len(data["entries"]) == 1, (
        "Case-insensitive match should find PERF-COACH as perf-coach"
    )


# ---------------------------------------------------------------------------
# AC: full entry body never written to journal_delta.json
# ---------------------------------------------------------------------------

def test_full_body_never_written(tmp_path):
    """Full entry body text is never written to journal_delta.json."""
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    unique_text = "UNIQUE_BODY_CONTENT_THAT_SHOULD_NOT_APPEAR_IN_DELTA"
    (entries_dir / "2026-06-01.md").write_text(
        f"---\ndate: 2026-06-01\n---\n\nperf-coach mention.\n\n{unique_text}\n"
    )
    targets_yaml = _write_targets(tmp_path, entries_dir)

    mod = _load_collector("jd_ac5")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    mod.collect(output_path=out, snapshot_path=tmp_path / "snap.json")

    raw = out.read_text()
    assert unique_text not in raw, (
        "Full body content must not appear in journal_delta.json"
    )


# ---------------------------------------------------------------------------
# AC: absent source — journal_entries path does not exist
# ---------------------------------------------------------------------------

def test_absent_source_writes_marker(tmp_path):
    """When journal_entries path doesn't exist, output is {\"source\": \"absent\"}."""
    targets_yaml = _write_targets(tmp_path, tmp_path / "no_such_dir")

    mod = _load_collector("jd_ac6")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    mod.collect(output_path=out, snapshot_path=tmp_path / "snap.json")

    data = json.loads(out.read_text())
    assert data == {"source": "absent"}, (
        f"Absent source must produce {{\"source\": \"absent\"}}, got {data}"
    )


def test_absent_source_no_exception(tmp_path):
    """When journal_entries path doesn't exist, no unhandled exception is raised."""
    targets_yaml = _write_targets(tmp_path, tmp_path / "no_such_dir")

    mod = _load_collector("jd_ac6b")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    # Must not raise
    mod.collect(output_path=out, snapshot_path=tmp_path / "snap.json")


# ---------------------------------------------------------------------------
# Fixture test: targeted extract (AC7)
# ---------------------------------------------------------------------------

def test_fixture_targeted_extract(tmp_path):
    """Fixture: 3 .md files, only one mentions perf-coach -> exactly 1 delta entry."""
    entries_dir = tmp_path / "entries"
    _make_fixture_entries(entries_dir)
    targets_yaml = _write_targets(tmp_path, entries_dir)

    mod = _load_collector("jd_fix1")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    mod.collect(output_path=out, snapshot_path=tmp_path / "snap.json")

    data = json.loads(out.read_text())
    entries = data.get("entries", [])
    assert len(entries) == 1, (
        f"Expected exactly 1 entry for fixture, got {len(entries)}"
    )
    assert any("perf-coach" in line.lower() for line in entries[0]["target_lines"]), (
        "Extracted lines must reference perf-coach"
    )


# ---------------------------------------------------------------------------
# Fixture test: absent source (AC8)
# ---------------------------------------------------------------------------

def test_fixture_absent_source(tmp_path):
    """Fixture: non-existent journal_entries path -> {\"source\": \"absent\"}, no stack trace."""
    targets_yaml = _write_targets(tmp_path, tmp_path / "nonexistent_dir")

    mod = _load_collector("jd_fix2")
    mod.TARGETS_YAML = targets_yaml
    mod.REPO_ROOT = tmp_path

    out = tmp_path / "journal_delta.json"
    mod.collect(output_path=out, snapshot_path=tmp_path / "snap.json")

    data = json.loads(out.read_text())
    assert data == {"source": "absent"}, (
        f"Expected {{\"source\": \"absent\"}}, got {data}"
    )


# ---------------------------------------------------------------------------
# Fixture test: empty delta on re-run (AC9)
# ---------------------------------------------------------------------------

def test_fixture_empty_delta_on_rerun(tmp_path):
    """Fixture: second immediate run against unchanged entries -> empty entries array."""
    entries_dir = tmp_path / "entries"
    _make_fixture_entries(entries_dir)
    targets_yaml = _write_targets(tmp_path, entries_dir)

    out = tmp_path / "journal_delta.json"
    snap = tmp_path / "snap.json"

    mod1 = _load_collector("jd_fix3a")
    mod1.TARGETS_YAML = targets_yaml
    mod1.REPO_ROOT = tmp_path
    mod1.collect(output_path=out, snapshot_path=snap)

    mod2 = _load_collector("jd_fix3b")
    mod2.TARGETS_YAML = targets_yaml
    mod2.REPO_ROOT = tmp_path
    mod2.collect(output_path=out, snapshot_path=snap)

    data = json.loads(out.read_text())
    entries = data.get("entries", [])
    assert entries == [], (
        f"Re-run against unchanged entries must produce empty list, got {entries}"
    )

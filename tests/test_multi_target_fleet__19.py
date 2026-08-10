"""Tests for issue #19: register three repos and harden collectors for missing files.

Each test maps to a specific AC item from the issue.
"""
import json
import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"
VAULT_DIR = REPO_ROOT / "vault"

_NEW_TARGETS = ("crux", "viral-radar", "asset-studio")
_ALL_TARGETS = ("commander", "perf-coach", "crux", "viral-radar", "asset-studio")
_DOC_FILENAMES = ("README.md", "PRODUCT.md", "DESIGN.md", "SCHEMA.md")


def _load_gather():
    spec = importlib.util.spec_from_file_location(
        "gather_test", str(REPO_ROOT / "gather.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC1: targets.yaml contains entries for crux, viral-radar, and asset-studio
# ---------------------------------------------------------------------------


def test_ac1_new_targets_registered():
    """AC1: targets.yaml has crux, viral-radar, asset-studio with required fields."""
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    targets = data.get("targets", {})

    for name in _NEW_TARGETS:
        assert name in targets, f"'{name}' missing from targets.yaml"
        t = targets[name]
        assert t.get("local"), f"'{name}' missing 'local' field"
        assert t.get("github"), f"'{name}' missing 'github' field"
        assert t.get("commander_slug"), f"'{name}' missing 'commander_slug' field"


def test_ac1_no_placeholder_values():
    """AC1: No placeholder or TODO strings in new target entries."""
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    targets = data.get("targets", {})
    for name in _NEW_TARGETS:
        if name not in targets:
            pytest.skip(f"{name} not yet registered")
        t = targets[name]
        for field, val in t.items():
            assert "TODO" not in str(val), f"Placeholder in {name}.{field}: {val}"
            assert "<placeholder>" not in str(val).lower(), (
                f"Placeholder in {name}.{field}: {val}"
            )


# ---------------------------------------------------------------------------
# AC2 + AC6: gather completes without exception even when SCHEMA.md or docs/ absent
# ---------------------------------------------------------------------------


def _make_targets_yaml(tmp_path, target_name, target_dir):
    targets_yaml = tmp_path / "targets.yaml"
    with open(targets_yaml, "w") as f:
        yaml.dump(
            {
                "sources": {"commander_api": "http://localhost:9999"},
                "targets": {
                    target_name: {
                        "local": str(target_dir),
                        "github": "test/test",
                        "commander_slug": "test",
                    }
                },
            },
            f,
        )
    return targets_yaml


def test_ac2_gather_no_exception_missing_schema(tmp_path, monkeypatch):
    """AC2/AC6: gather exits cleanly when SCHEMA.md is absent."""
    target_dir = tmp_path / "test-no-schema"
    target_dir.mkdir()
    (target_dir / "README.md").write_text("# test\nA test repo.")
    # No SCHEMA.md, no docs/

    targets_yaml = _make_targets_yaml(tmp_path, "test-no-schema", target_dir)
    gather = _load_gather()
    monkeypatch.setattr(gather, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gather, "TARGETS_YAML", targets_yaml)

    # Must not raise — Commander unreachable is fine
    gather.gather("test-no-schema")


def test_ac2_gather_no_exception_missing_docs(tmp_path, monkeypatch):
    """AC2/AC6: gather exits cleanly when docs/ directory is absent."""
    target_dir = tmp_path / "test-no-docs"
    target_dir.mkdir()
    (target_dir / "README.md").write_text("# test\nA test repo.")
    # No docs/ directory

    targets_yaml = _make_targets_yaml(tmp_path, "test-no-docs", target_dir)
    gather = _load_gather()
    monkeypatch.setattr(gather, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gather, "TARGETS_YAML", targets_yaml)

    gather.gather("test-no-docs")


def test_ac6_gather_no_exception_all_files_absent(tmp_path, monkeypatch):
    """AC6: gather completes when ALL standard doc files and docs/ are absent."""
    target_dir = tmp_path / "test-all-absent"
    target_dir.mkdir()
    # Completely empty target directory

    targets_yaml = _make_targets_yaml(tmp_path, "test-all-absent", target_dir)
    gather = _load_gather()
    monkeypatch.setattr(gather, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gather, "TARGETS_YAML", targets_yaml)

    gather.gather("test-all-absent")


# ---------------------------------------------------------------------------
# AC3: Complete snapshot — absent standard files recorded as null, not omitted
# ---------------------------------------------------------------------------


def _run_gather_and_load_manifest(tmp_path, monkeypatch, target_name, target_dir):
    targets_yaml = _make_targets_yaml(tmp_path, target_name, target_dir)
    gather = _load_gather()
    monkeypatch.setattr(gather, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gather, "TARGETS_YAML", targets_yaml)
    gather.gather(target_name)

    raw_dir = tmp_path / "vault" / "projects" / target_name / "raw"
    snap_dirs = sorted(raw_dir.iterdir())
    assert snap_dirs, "No snapshot written"
    docs_manifest_path = snap_dirs[-1] / "docs_manifest.json"
    assert docs_manifest_path.exists(), "docs_manifest.json not written"
    return json.loads(docs_manifest_path.read_text())


def test_ac3_absent_schema_recorded_as_sentinel(tmp_path, monkeypatch):
    """AC3: SCHEMA.md absent → recorded in docs_manifest.json with null/absent sentinel."""
    target_dir = tmp_path / "no-schema"
    target_dir.mkdir()
    (target_dir / "README.md").write_text("# test\nA test repo.")

    docs_manifest = _run_gather_and_load_manifest(
        tmp_path, monkeypatch, "no-schema", target_dir
    )
    files = docs_manifest.get("files", [])
    paths = [f["path"] for f in files]

    assert "SCHEMA.md" in paths, "SCHEMA.md must appear in docs_manifest.json even when absent"

    schema_entry = next(f for f in files if f["path"] == "SCHEMA.md")
    is_absent_sentinel = (
        schema_entry.get("sha256") is None or schema_entry.get("absent") is True
    )
    assert is_absent_sentinel, (
        f"SCHEMA.md should be recorded with null sha256 or absent=true, got: {schema_entry}"
    )


def test_ac3_all_standard_files_always_in_manifest(tmp_path, monkeypatch):
    """AC3: docs_manifest.json always lists every tracked filename regardless of presence."""
    target_dir = tmp_path / "partial-files"
    target_dir.mkdir()
    (target_dir / "README.md").write_text("# test\nA test repo.")
    # No PRODUCT.md, DESIGN.md, SCHEMA.md, no docs/

    docs_manifest = _run_gather_and_load_manifest(
        tmp_path, monkeypatch, "partial-files", target_dir
    )
    file_paths = {f["path"] for f in docs_manifest.get("files", [])}

    for name in _DOC_FILENAMES:
        assert name in file_paths, (
            f"{name} missing from docs_manifest.json — should be recorded as absent"
        )


def test_ac3_absent_files_have_null_sha256(tmp_path, monkeypatch):
    """AC3: Absent standard files carry null sha256, not omitted."""
    target_dir = tmp_path / "null-sha"
    target_dir.mkdir()
    # No files at all

    docs_manifest = _run_gather_and_load_manifest(
        tmp_path, monkeypatch, "null-sha", target_dir
    )
    for entry in docs_manifest.get("files", []):
        if entry.get("path") in _DOC_FILENAMES:
            if entry.get("absent") or entry.get("sha256") is None:
                # Correct: recorded as absent sentinel
                pass
            else:
                pytest.fail(
                    f"{entry['path']} has sha256={entry['sha256']!r} but file is absent"
                )


# ---------------------------------------------------------------------------
# AC5: Vault index contains exactly five rows with non-empty one-liners
# ---------------------------------------------------------------------------


def _parse_vault_index_data_rows(text):
    """Return table data rows (skip header and separator lines)."""
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # Skip separator lines (only dashes, pipes, spaces)
        if all(c in "-| " for c in stripped):
            continue
        # Skip header row (first column contains "target")
        first_col = stripped.split("|")[1].strip().lower() if "|" in stripped else ""
        if first_col == "target":
            continue
        rows.append(stripped)
    return rows


def test_ac5_vault_index_has_five_rows():
    """AC5: vault/index.md table has exactly five data rows."""
    index_path = VAULT_DIR / "index.md"
    assert index_path.exists(), "vault/index.md does not exist"

    rows = _parse_vault_index_data_rows(index_path.read_text())
    assert len(rows) == 5, (
        f"Expected 5 rows in vault/index.md table, found {len(rows)}: {rows}"
    )


def test_ac5_vault_index_all_targets_present():
    """AC5: All five target names appear in vault/index.md."""
    index_path = VAULT_DIR / "index.md"
    text = index_path.read_text()
    for name in _ALL_TARGETS:
        assert name in text, f"Target '{name}' not found in vault/index.md"


def test_ac5_one_liners_non_empty():
    """AC5: Each row's one-liner column is a non-empty real sentence."""
    index_path = VAULT_DIR / "index.md"
    rows = _parse_vault_index_data_rows(index_path.read_text())
    for row in rows:
        cols = [c.strip() for c in row.split("|") if c.strip()]
        assert len(cols) >= 2, f"Row has too few columns: {row}"
        one_liner = cols[1]
        assert one_liner and one_liner not in ("-", "—", "?", ""), (
            f"Empty or placeholder one-liner in row: {row}"
        )
        # Must be a real sentence (at least a few words)
        assert len(one_liner.split()) >= 3, (
            f"One-liner too short to be real content: '{one_liner}' in row: {row}"
        )


# ---------------------------------------------------------------------------
# AC7: Existing two targets are unaffected
# ---------------------------------------------------------------------------


def test_ac7_existing_targets_still_present():
    """AC7: commander and perf-coach entries remain in targets.yaml."""
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    targets = data.get("targets", {})
    assert "commander" in targets, "commander missing from targets.yaml"
    assert "perf-coach" in targets, "perf-coach missing from targets.yaml"


def test_ac7_existing_targets_fields_intact():
    """AC7: Existing target field values are unchanged."""
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    targets = data.get("targets", {})

    commander = targets.get("commander", {})
    assert commander.get("github") == "zealchaiwut/commander"
    assert commander.get("commander_slug") == "commander"

    perf_coach = targets.get("perf-coach", {})
    assert perf_coach.get("github") == "zealchaiwut/perf-coach"
    assert perf_coach.get("commander_slug") == "perf-coach"


def test_ac7_existing_vault_projects_untouched():
    """AC7: vault/projects/commander and vault/projects/perf-coach still exist."""
    assert (VAULT_DIR / "projects" / "commander").exists()
    assert (VAULT_DIR / "projects" / "perf-coach").exists()

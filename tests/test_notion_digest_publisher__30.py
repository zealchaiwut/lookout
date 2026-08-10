"""Tests for issue #30: Notion weekly digest publisher.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "publish_digest.py"
VAULT_INDEX = REPO_ROOT / "vault" / "index.md"
IDEAS_INDEX = REPO_ROOT / "vault" / "ideas" / "index.md"
TARGETS_YAML = REPO_ROOT / "targets.yaml"
PLIST_PATH = REPO_ROOT / "launchd" / "com.zealchaiwut.lookout-digest.plist"

_PYTHON = sys.executable


def _load_publish_module():
    spec = importlib.util.spec_from_file_location("publish_digest", str(PUBLISH_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC1: Script reads vault/index.md and extracts all index rows + one-liners
# ---------------------------------------------------------------------------


def test_ac1_script_exists():
    """AC1: scripts/publish_digest.py exists."""
    assert PUBLISH_SCRIPT.exists(), f"publish_digest.py not found at {PUBLISH_SCRIPT}"


def test_ac1_parse_index_rows_returns_all_rows():
    """AC1: parse_index_rows extracts every data row from the vault index table."""
    mod = _load_publish_module()
    rows = mod.parse_index_rows(VAULT_INDEX.read_text())
    assert len(rows) >= 5, f"Expected at least 5 index rows, got {len(rows)}"
    targets = [r["target"] for r in rows]
    assert "commander" in targets, "Expected 'commander' in index rows"
    assert "perf-coach" in targets, "Expected 'perf-coach' in index rows"


def test_ac1_parse_one_liners_present_for_every_row():
    """AC1: Every index row has a non-blank one_liner."""
    mod = _load_publish_module()
    rows = mod.parse_index_rows(VAULT_INDEX.read_text())
    for row in rows:
        assert "one_liner" in row, f"Row missing one_liner key: {row}"
        assert row["one_liner"].strip(), f"one_liner is blank for target '{row.get('target')}'"


def test_ac1_parse_ideas_ledger_returns_rows():
    """AC1: parse_ideas_ledger extracts all rows from vault/ideas/index.md."""
    mod = _load_publish_module()
    rows = mod.parse_ideas_ledger(IDEAS_INDEX.read_text())
    assert len(rows) >= 1, "Expected at least one idea row from the ledger"
    assert "idea" in rows[0], f"Row missing 'idea' key: {rows[0]}"


# ---------------------------------------------------------------------------
# AC2: Script writes to exactly one page identified by targets.yaml
# ---------------------------------------------------------------------------


def test_ac2_publish_uses_page_id_from_targets_yaml(tmp_path, monkeypatch):
    """AC2: publish() reads the Notion page ID from targets.yaml sources section."""
    fake_page_id = "abc123-fake-page-id"
    fake_targets = tmp_path / "targets.yaml"
    fake_targets.write_text(yaml.dump({
        "sources": {"notion_digest_page_id": fake_page_id},
        "targets": {},
    }))
    fake_index = tmp_path / "index.md"
    fake_index.write_text(VAULT_INDEX.read_text())
    fake_ideas = tmp_path / "ideas_index.md"
    fake_ideas.write_text(IDEAS_INDEX.read_text())

    write_calls = []
    mod = _load_publish_module()
    monkeypatch.setattr(mod, "_write_page_blocks", lambda pid, blocks, token: write_calls.append(pid))
    monkeypatch.setattr(mod, "_delete_page_blocks", lambda pid, token: None)
    monkeypatch.setenv("NOTION_TOKEN", "fake-token")

    mod.publish(targets_yaml=fake_targets, vault_index=fake_index, ideas_index=fake_ideas)

    assert len(write_calls) == 1, f"Expected exactly 1 Notion write call, got {len(write_calls)}"
    assert write_calls[0] == fake_page_id, (
        f"Expected page ID '{fake_page_id}', got '{write_calls[0]}'"
    )


# ---------------------------------------------------------------------------
# AC3: Idempotent — delete blocks then write on every run
# ---------------------------------------------------------------------------


def test_ac3_delete_before_write_on_every_run(tmp_path, monkeypatch):
    """AC3: publish() always deletes existing blocks before writing new ones."""
    fake_page_id = "test-idempotent-page"
    fake_targets = tmp_path / "targets.yaml"
    fake_targets.write_text(yaml.dump({
        "sources": {"notion_digest_page_id": fake_page_id},
        "targets": {},
    }))
    fake_index = tmp_path / "index.md"
    fake_index.write_text(VAULT_INDEX.read_text())
    fake_ideas = tmp_path / "ideas_index.md"
    fake_ideas.write_text(IDEAS_INDEX.read_text())

    op_log = []
    mod = _load_publish_module()
    monkeypatch.setattr(mod, "_delete_page_blocks", lambda pid, token: op_log.append(("delete", pid)))
    monkeypatch.setattr(mod, "_write_page_blocks", lambda pid, blocks, token: op_log.append(("write", pid)))
    monkeypatch.setenv("NOTION_TOKEN", "fake-token")

    mod.publish(targets_yaml=fake_targets, vault_index=fake_index, ideas_index=fake_ideas)
    mod.publish(targets_yaml=fake_targets, vault_index=fake_index, ideas_index=fake_ideas)

    assert len(op_log) == 4, f"Expected 4 ops (delete+write ×2), got {len(op_log)}: {op_log}"
    assert op_log[0] == ("delete", fake_page_id), f"First op must be delete, got {op_log[0]}"
    assert op_log[1] == ("write", fake_page_id), f"Second op must be write, got {op_log[1]}"
    assert op_log[2] == ("delete", fake_page_id), f"Third op must be delete, got {op_log[2]}"
    assert op_log[3] == ("write", fake_page_id), f"Fourth op must be write, got {op_log[3]}"


# ---------------------------------------------------------------------------
# AC4: Single write endpoint — _write_page_blocks defined only in publish_digest.py
# ---------------------------------------------------------------------------


def _find_write_function_definitions(repo_root: Path) -> list[str]:
    """Return relative paths of files that define Notion write helper functions."""
    hits = []
    write_fn_pattern = re.compile(r"^def (_write_page_blocks|_delete_page_blocks)\s*\(", re.MULTILINE)
    for py_file in sorted(repo_root.rglob("*.py")):
        rel = py_file.relative_to(repo_root)
        rel_str = str(rel)
        if any(skip in rel_str for skip in ["venv/", ".venv/", "__pycache__/"]):
            continue
        content = py_file.read_text(errors="replace")
        if write_fn_pattern.search(content):
            hits.append(rel_str)
    return hits


def test_ac4_write_function_defined_in_exactly_one_file():
    """AC4: _write_page_blocks and _delete_page_blocks are defined in exactly one file."""
    hits = _find_write_function_definitions(REPO_ROOT)
    assert len(hits) == 1, (
        f"Expected exactly 1 file defining Notion write helpers, found {len(hits)}: {hits}"
    )


def test_ac4_write_function_is_in_publish_script():
    """AC4: The single Notion write function lives in scripts/publish_digest.py."""
    hits = _find_write_function_definitions(REPO_ROOT)
    expected = "scripts/publish_digest.py"
    assert hits == [expected], (
        f"Notion write helpers must only be in '{expected}', found: {hits}"
    )


def test_ac4_no_notion_write_calls_outside_publish(tmp_path):
    """AC4: No file outside scripts/publish_digest.py calls Notion write endpoints."""
    # Patterns that indicate a Notion write (not reads/queries)
    write_patterns = [
        re.compile(r"\brequests\.patch\b.*block", re.IGNORECASE | re.DOTALL),
        re.compile(r"\brequests\.delete\b.*block", re.IGNORECASE | re.DOTALL),
        re.compile(r"\.blocks\.children\.append\("),
        re.compile(r"notion.*\.pages\.create\("),
    ]
    allowed = {"scripts/publish_digest.py"}
    violations = []

    for py_file in sorted(REPO_ROOT.rglob("*.py")):
        rel = py_file.relative_to(REPO_ROOT)
        rel_str = str(rel)
        if any(skip in rel_str for skip in ["venv/", ".venv/", "__pycache__/", "tests/"]):
            continue
        if rel_str in allowed:
            continue
        content = py_file.read_text(errors="replace")
        for pat in write_patterns:
            if pat.search(content):
                violations.append(f"{rel_str}: matches pattern '{pat.pattern}'")

    assert not violations, (
        "Notion write calls found outside the allowed publish function:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# AC5: launchd plist schedules the script weekly
# ---------------------------------------------------------------------------


def test_ac5_weekly_plist_exists():
    """AC5: launchd plist for the weekly digest exists."""
    assert PLIST_PATH.exists(), f"Weekly digest plist not found at {PLIST_PATH}"


def test_ac5_plist_uses_weekly_schedule():
    """AC5: Plist uses StartCalendarInterval with a Weekday key for weekly cadence."""
    if not PLIST_PATH.exists():
        pytest.skip("plist not yet created")
    content = PLIST_PATH.read_text()
    assert "StartCalendarInterval" in content, "Plist missing StartCalendarInterval"
    assert "Weekday" in content, (
        "Weekly plist must include a Weekday key in StartCalendarInterval"
    )


def test_ac5_plist_sources_env_for_token():
    """AC5: Plist sources the .env file so NOTION_TOKEN is available at runtime."""
    if not PLIST_PATH.exists():
        pytest.skip("plist not yet created")
    content = PLIST_PATH.read_text()
    assert ".env" in content, "Plist must source the .env file for NOTION_TOKEN access"


def test_ac5_plist_references_publish_script():
    """AC5: Plist ProgramArguments invokes publish_digest.py."""
    if not PLIST_PATH.exists():
        pytest.skip("plist not yet created")
    content = PLIST_PATH.read_text()
    assert "publish_digest" in content, (
        "Plist must invoke publish_digest.py in its ProgramArguments"
    )


# ---------------------------------------------------------------------------
# AC6: Non-zero exit on missing config or unreadable vault
# ---------------------------------------------------------------------------


def test_ac6_exits_nonzero_when_page_id_missing(tmp_path):
    """AC6: Script exits non-zero when targets.yaml lacks notion_digest_page_id."""
    fake_targets = tmp_path / "targets.yaml"
    fake_targets.write_text(yaml.dump({
        "sources": {"commander_api": "http://localhost:8000"},
        "targets": {},
    }))
    fake_index = tmp_path / "index.md"
    fake_index.write_text(VAULT_INDEX.read_text())
    fake_ideas = tmp_path / "ideas_index.md"
    fake_ideas.write_text(IDEAS_INDEX.read_text())

    result = subprocess.run(
        [
            _PYTHON, str(PUBLISH_SCRIPT),
            "--targets-yaml", str(fake_targets),
            "--vault-index", str(fake_index),
            "--ideas-index", str(fake_ideas),
        ],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "NOTION_TOKEN": "tok"},
    )
    assert result.returncode != 0, "Expected non-zero exit when page ID is missing"
    combined = result.stdout + result.stderr
    assert "notion_digest_page_id" in combined or "page" in combined.lower(), (
        f"Expected descriptive error mentioning page ID, got:\n{combined}"
    )


def test_ac6_exits_nonzero_when_vault_index_unreadable(tmp_path):
    """AC6: Script exits non-zero when vault/index.md does not exist."""
    fake_targets = tmp_path / "targets.yaml"
    fake_targets.write_text(yaml.dump({
        "sources": {"notion_digest_page_id": "some-page-id"},
        "targets": {},
    }))
    missing_index = tmp_path / "does_not_exist.md"
    fake_ideas = tmp_path / "ideas_index.md"
    fake_ideas.write_text(IDEAS_INDEX.read_text())

    result = subprocess.run(
        [
            _PYTHON, str(PUBLISH_SCRIPT),
            "--targets-yaml", str(fake_targets),
            "--vault-index", str(missing_index),
            "--ideas-index", str(fake_ideas),
        ],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "NOTION_TOKEN": "tok"},
    )
    assert result.returncode != 0, "Expected non-zero exit when vault/index.md is missing"
    combined = result.stdout + result.stderr
    assert combined.strip(), "Expected some error output when vault/index.md is missing"


def test_ac6_error_message_is_human_readable(tmp_path):
    """AC6: The error message identifies what is missing, not just a traceback."""
    fake_targets = tmp_path / "targets.yaml"
    fake_targets.write_text(yaml.dump({
        "sources": {},
        "targets": {},
    }))
    fake_index = tmp_path / "index.md"
    fake_index.write_text(VAULT_INDEX.read_text())
    fake_ideas = tmp_path / "ideas_index.md"
    fake_ideas.write_text(IDEAS_INDEX.read_text())

    result = subprocess.run(
        [
            _PYTHON, str(PUBLISH_SCRIPT),
            "--targets-yaml", str(fake_targets),
            "--vault-index", str(fake_index),
            "--ideas-index", str(fake_ideas),
        ],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "NOTION_TOKEN": "tok"},
    )
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, (
        f"Got a Python traceback instead of a user-friendly error:\n{combined}"
    )
    assert combined.strip(), "Expected a non-empty error message"


# ---------------------------------------------------------------------------
# AC7: No vault files are written during publish
# ---------------------------------------------------------------------------


def test_ac7_vault_index_unchanged_after_publish(tmp_path, monkeypatch):
    """AC7: publish() does not modify vault/index.md or ideas/index.md."""
    fake_page_id = "test-vault-readonly"
    fake_targets = tmp_path / "targets.yaml"
    fake_targets.write_text(yaml.dump({
        "sources": {"notion_digest_page_id": fake_page_id},
        "targets": {},
    }))
    original_content = VAULT_INDEX.read_text()
    fake_index = tmp_path / "index.md"
    fake_index.write_text(original_content)

    original_ideas = IDEAS_INDEX.read_text()
    fake_ideas = tmp_path / "ideas_index.md"
    fake_ideas.write_text(original_ideas)

    mod = _load_publish_module()
    monkeypatch.setattr(mod, "_delete_page_blocks", lambda pid, token: None)
    monkeypatch.setattr(mod, "_write_page_blocks", lambda pid, blocks, token: None)
    monkeypatch.setenv("NOTION_TOKEN", "fake-token")

    mod.publish(targets_yaml=fake_targets, vault_index=fake_index, ideas_index=fake_ideas)

    assert fake_index.read_text() == original_content, (
        "vault/index.md was modified by publish() — it must be read-only"
    )
    assert fake_ideas.read_text() == original_ideas, (
        "vault/ideas/index.md was modified by publish() — it must be read-only"
    )

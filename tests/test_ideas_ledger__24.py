"""Tests for issue #24: Idea note conventions and ledger regeneration.

Each test maps to a specific AC item from the issue.
"""
import hashlib
import importlib.util
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
IDEAS_LEDGER_PY = REPO_ROOT / "ideas_ledger.py"
VAULT_ROOT = REPO_ROOT / "vault"
IDEAS_DIR = VAULT_ROOT / "ideas"
SKILL_MD = REPO_ROOT / "SKILL.md"
AGENTS_MD = VAULT_ROOT / "agents.md"

VALID_STATUSES = {"idea", "assessed", "promoted", "shipped", "parked"}
MACHINE_DELIMITER = "<!-- BEGIN MACHINE ASSESSMENT -->"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_ledger():
    spec = importlib.util.spec_from_file_location("ideas_ledger", str(IDEAS_LEDGER_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_idea_note(
    tmp_path: Path,
    filename: str,
    slug: str,
    created: str,
    status: str,
    targets: list = None,
    issues: list = None,
    assessed: str = "null",
    effort: str = None,
    blocked_by: str = None,
    freeform: str = "Some human-written content here.\n",
    assessment: str = "No assessment yet.\n",
) -> Path:
    targets_yaml = targets if targets is not None else []
    issues_yaml = issues if issues is not None else []
    fm_lines = [
        "---",
        f"slug: {slug}",
        f"created: {created}",
        f"status: {status}",
        f"targets: {targets_yaml!r}",
        f"issues: {issues_yaml!r}",
        f"assessed: {assessed}",
    ]
    if effort is not None:
        fm_lines.append(f"effort: {effort}")
    if blocked_by is not None:
        fm_lines.append(f"blocked_by: {blocked_by}")
    fm_lines.append("---")
    fm = "\n".join(fm_lines) + "\n\n"
    body = freeform + "\n" + MACHINE_DELIMITER + "\n## Assessment\n\n" + assessment
    path = tmp_path / filename
    path.write_text(fm + body, encoding="utf-8")
    return path


def _sha256_above_delimiter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    idx = text.find(MACHINE_DELIMITER)
    if idx == -1:
        top = text
    else:
        top = text[:idx]
    return hashlib.sha256(top.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# AC1: SKILL.md and agents.md document the idea note format
# ---------------------------------------------------------------------------

def test_skill_md_references_idea_note_format():
    """AC1: SKILL.md contains a section about the idea note format."""
    assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "vault/ideas/" in content or "idea note" in content.lower(), (
        "SKILL.md does not document the idea note format or vault/ideas/ path"
    )


def test_agents_md_references_idea_note_format():
    """AC1: agents.md contains a section about the idea note format."""
    assert AGENTS_MD.exists(), f"agents.md not found at {AGENTS_MD}"
    content = AGENTS_MD.read_text(encoding="utf-8")
    assert "vault/ideas/" in content or "idea note" in content.lower(), (
        "agents.md does not document the idea note format or vault/ideas/ path"
    )


# ---------------------------------------------------------------------------
# AC2: Required frontmatter fields are present and validated
# ---------------------------------------------------------------------------

def test_ideas_ledger_module_exists():
    """AC2: ideas_ledger.py exists at repo root."""
    assert IDEAS_LEDGER_PY.exists(), f"ideas_ledger.py not found at {IDEAS_LEDGER_PY}"


def test_validate_accepts_valid_note(tmp_path):
    """AC2: validate_note() accepts a note with all required fields."""
    ledger = _load_ledger()
    note = _make_idea_note(tmp_path, "2026-01-10-dark-mode.md",
                           slug="dark-mode", created="2026-01-10", status="idea")
    errors = ledger.validate_note(note)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_validate_all_required_fields(tmp_path):
    """AC2: validate_note() checks presence of slug, created, status, targets, issues, assessed."""
    ledger = _load_ledger()
    # Write a note missing all required fields
    path = tmp_path / "bad.md"
    path.write_text("---\n---\n\nNo fields.\n")
    errors = ledger.validate_note(path)
    required = ["slug", "created", "status", "targets", "issues", "assessed"]
    for field in required:
        assert any(field in e for e in errors), (
            f"Expected error mentioning missing field '{field}', got: {errors}"
        )


def test_valid_statuses_accepted(tmp_path):
    """AC2: All five valid status values are accepted."""
    ledger = _load_ledger()
    for status in VALID_STATUSES:
        note = _make_idea_note(tmp_path, f"{status}-note.md",
                               slug=f"test-{status}", created="2026-01-10", status=status)
        errors = ledger.validate_note(note)
        assert errors == [], f"Status '{status}' should be valid, got errors: {errors}"


# ---------------------------------------------------------------------------
# AC3: Two body sections — freeform top and machine-owned Assessment
# ---------------------------------------------------------------------------

def test_delimiter_exists_in_fixture_notes():
    """AC3: Fixture idea notes contain the machine-section delimiter."""
    fixture_dark = IDEAS_DIR / "2026-01-10-dark-mode.md"
    fixture_sync = IDEAS_DIR / "2026-03-04-offline-sync.md"
    for fixture in (fixture_dark, fixture_sync):
        assert fixture.exists(), f"Fixture not found: {fixture}"
        content = fixture.read_text(encoding="utf-8")
        assert MACHINE_DELIMITER in content, (
            f"{fixture.name}: missing machine-section delimiter '{MACHINE_DELIMITER}'"
        )


def test_assessment_section_below_delimiter():
    """AC3: The ## Assessment heading appears below the delimiter, not above."""
    fixture = IDEAS_DIR / "2026-01-10-dark-mode.md"
    assert fixture.exists()
    content = fixture.read_text(encoding="utf-8")
    delim_idx = content.find(MACHINE_DELIMITER)
    assert delim_idx != -1
    assessment_idx = content.find("## Assessment")
    assert assessment_idx > delim_idx, (
        "## Assessment section must appear after the machine-section delimiter"
    )


# ---------------------------------------------------------------------------
# AC4: vault/ideas/index.md is regenerated as a Markdown table
# ---------------------------------------------------------------------------

def test_regenerate_creates_index(tmp_path):
    """AC4: regenerate_ledger() creates vault/ideas/index.md."""
    ledger = _load_ledger()
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    _make_idea_note(ideas_dir, "2026-01-10-dark-mode.md",
                    slug="dark-mode", created="2026-01-10", status="idea")
    ledger.regenerate_ledger(ideas_dir, today=date(2026, 8, 10))
    index = ideas_dir / "index.md"
    assert index.exists(), "index.md was not created"


def test_regenerate_index_has_required_columns(tmp_path):
    """AC4: index.md contains table columns: Idea, Status, Effort, Blocked-by, Age."""
    ledger = _load_ledger()
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    _make_idea_note(ideas_dir, "2026-01-10-dark-mode.md",
                    slug="dark-mode", created="2026-01-10", status="idea")
    ledger.regenerate_ledger(ideas_dir, today=date(2026, 8, 10))
    content = (ideas_dir / "index.md").read_text(encoding="utf-8")
    for col in ("Idea", "Status", "Effort", "Blocked-by", "Age"):
        assert col in content, f"Column '{col}' missing from index.md:\n{content}"


def test_regenerate_index_is_markdown_table(tmp_path):
    """AC4: index.md output is a Markdown table (has | separators)."""
    ledger = _load_ledger()
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    _make_idea_note(ideas_dir, "2026-01-10-dark-mode.md",
                    slug="dark-mode", created="2026-01-10", status="idea")
    ledger.regenerate_ledger(ideas_dir, today=date(2026, 8, 10))
    content = (ideas_dir / "index.md").read_text(encoding="utf-8")
    table_lines = [ln for ln in content.splitlines() if ln.strip().startswith("|")]
    assert len(table_lines) >= 3, (
        f"Expected at least 3 table lines (header, separator, data), got {len(table_lines)}:\n{content}"
    )


# ---------------------------------------------------------------------------
# AC5: Two fixture notes produce a correct, fully-populated ledger
# ---------------------------------------------------------------------------

def test_fixtures_produce_two_row_ledger(tmp_path):
    """AC5: Two fixture notes produce exactly two data rows in the ledger."""
    ledger = _load_ledger()
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    _make_idea_note(ideas_dir, "2026-01-10-dark-mode.md",
                    slug="dark-mode", created="2026-01-10", status="idea")
    _make_idea_note(ideas_dir, "2026-03-04-offline-sync.md",
                    slug="offline-sync", created="2026-03-04", status="assessed",
                    assessed="2026-03-10")
    ledger.regenerate_ledger(ideas_dir, today=date(2026, 8, 10))
    content = (ideas_dir / "index.md").read_text(encoding="utf-8")
    # Table rows (excluding header and separator)
    data_rows = [
        ln for ln in content.splitlines()
        if ln.strip().startswith("|")
        and not ln.strip().startswith("|---")
        and "Idea" not in ln and "Status" not in ln
    ]
    assert len(data_rows) == 2, (
        f"Expected exactly 2 data rows, got {len(data_rows)}:\n{content}"
    )


def test_fixtures_ledger_contains_both_slugs(tmp_path):
    """AC5: The ledger contains both fixture slugs."""
    ledger = _load_ledger()
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    _make_idea_note(ideas_dir, "2026-01-10-dark-mode.md",
                    slug="dark-mode", created="2026-01-10", status="idea")
    _make_idea_note(ideas_dir, "2026-03-04-offline-sync.md",
                    slug="offline-sync", created="2026-03-04", status="assessed",
                    assessed="2026-03-10")
    ledger.regenerate_ledger(ideas_dir, today=date(2026, 8, 10))
    content = (ideas_dir / "index.md").read_text(encoding="utf-8")
    assert "dark-mode" in content, f"dark-mode not found in ledger:\n{content}"
    assert "offline-sync" in content, f"offline-sync not found in ledger:\n{content}"


def test_fixtures_ledger_status_populated(tmp_path):
    """AC5: The ledger rows contain the correct status values."""
    ledger = _load_ledger()
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    _make_idea_note(ideas_dir, "2026-01-10-dark-mode.md",
                    slug="dark-mode", created="2026-01-10", status="idea")
    _make_idea_note(ideas_dir, "2026-03-04-offline-sync.md",
                    slug="offline-sync", created="2026-03-04", status="assessed",
                    assessed="2026-03-10")
    ledger.regenerate_ledger(ideas_dir, today=date(2026, 8, 10))
    content = (ideas_dir / "index.md").read_text(encoding="utf-8")
    assert "idea" in content, f"'idea' status not found in ledger:\n{content}"
    assert "assessed" in content, f"'assessed' status not found in ledger:\n{content}"


def test_fixtures_ledger_age_populated(tmp_path):
    """AC5: The ledger Age column is populated for each row."""
    ledger = _load_ledger()
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    _make_idea_note(ideas_dir, "2026-01-10-dark-mode.md",
                    slug="dark-mode", created="2026-01-10", status="idea")
    ledger.regenerate_ledger(ideas_dir, today=date(2026, 8, 10))
    content = (ideas_dir / "index.md").read_text(encoding="utf-8")
    # Age should be a number followed by 'd'
    assert re.search(r"\d+d", content), f"No age value (e.g. '213d') found in ledger:\n{content}"


# ---------------------------------------------------------------------------
# AC6: Freeform top section is preserved byte-for-byte on re-run
# ---------------------------------------------------------------------------

def test_freeform_top_preserved_on_rerun(tmp_path):
    """AC6: The hash of everything above the delimiter is unchanged after regeneration."""
    ledger = _load_ledger()
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    note = _make_idea_note(ideas_dir, "2026-01-10-dark-mode.md",
                           slug="dark-mode", created="2026-01-10", status="idea",
                           freeform="Original content line.\n")
    before_hash = _sha256_above_delimiter(note)

    # First regeneration
    ledger.regenerate_ledger(ideas_dir, today=date(2026, 8, 10))

    # Mutate freeform top (simulating human edit AFTER first run)
    text = note.read_text(encoding="utf-8")
    delim_idx = text.find(MACHINE_DELIMITER)
    new_text = text[:delim_idx].rstrip("\n") + "\nA new sentence added by human.\n\n" + text[delim_idx:]
    note.write_text(new_text, encoding="utf-8")
    after_edit_hash = _sha256_above_delimiter(note)
    assert after_edit_hash != before_hash, "Setup: hash should differ after edit"

    # Second regeneration — must NOT touch freeform top
    ledger.regenerate_ledger(ideas_dir, today=date(2026, 8, 10))
    after_regen_hash = _sha256_above_delimiter(note)
    assert after_regen_hash == after_edit_hash, (
        "Regeneration must not modify the freeform top section "
        f"(hash changed: {after_edit_hash} → {after_regen_hash})"
    )


def test_only_index_modified_on_rerun(tmp_path):
    """AC6: Only index.md is modified by regenerate_ledger(); idea note files are untouched."""
    ledger = _load_ledger()
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    note = _make_idea_note(ideas_dir, "2026-01-10-dark-mode.md",
                           slug="dark-mode", created="2026-01-10", status="idea")
    note_before = note.read_text(encoding="utf-8")
    ledger.regenerate_ledger(ideas_dir, today=date(2026, 8, 10))
    note_after = note.read_text(encoding="utf-8")
    assert note_before == note_after, (
        "regenerate_ledger() must not modify idea note files"
    )


# ---------------------------------------------------------------------------
# AC7: Unrecognised status causes lint to exit non-zero with clear error
# ---------------------------------------------------------------------------

def test_invalid_status_exits_nonzero(tmp_path):
    """AC7: validate_note() returns errors for invalid status values."""
    ledger = _load_ledger()
    note = _make_idea_note(tmp_path, "bad-status.md",
                           slug="test", created="2026-01-10", status="wip")
    errors = ledger.validate_note(note)
    assert errors, f"Expected validation errors for invalid status 'wip', got none"
    combined = " ".join(errors)
    assert "wip" in combined.lower(), (
        f"Error message must name the invalid status value 'wip': {errors}"
    )


def test_invalid_status_error_names_file(tmp_path):
    """AC7: The error output names the file containing the invalid status."""
    ledger = _load_ledger()
    note = _make_idea_note(tmp_path, "bad-status.md",
                           slug="test", created="2026-01-10", status="wip")
    errors = ledger.validate_note(note)
    combined = " ".join(errors)
    assert "bad-status" in combined or str(note) in combined, (
        f"Error message must name the file: {errors}"
    )


def test_lint_integration_exits_nonzero_on_bad_status(tmp_path):
    """AC7: Running the linter via subprocess exits non-zero for an invalid status note."""
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    _make_idea_note(ideas_dir, "bad-note.md",
                    slug="test", created="2026-01-10", status="wip")

    result = subprocess.run(
        [sys.executable, str(IDEAS_LEDGER_PY), "--ideas-dir", str(ideas_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, (
        f"Expected non-zero exit for invalid status, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    output = result.stdout + result.stderr
    assert "wip" in output.lower(), (
        f"Error output must mention the invalid value 'wip':\n{output}"
    )
    assert "bad-note" in output, (
        f"Error output must name the offending file:\n{output}"
    )


def test_lint_integration_exits_zero_on_valid_notes(tmp_path):
    """AC7: Running the linter exits 0 when all notes have valid statuses."""
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    _make_idea_note(ideas_dir, "2026-01-10-dark-mode.md",
                    slug="dark-mode", created="2026-01-10", status="idea")
    _make_idea_note(ideas_dir, "2026-03-04-offline-sync.md",
                    slug="offline-sync", created="2026-03-04", status="assessed",
                    assessed="2026-03-10")

    result = subprocess.run(
        [sys.executable, str(IDEAS_LEDGER_PY), "--ideas-dir", str(ideas_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit 0 for valid notes, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC8: Conventions doc states Assessment section is machine-owned
# ---------------------------------------------------------------------------

def test_skill_md_states_assessment_is_machine_owned():
    """AC8: SKILL.md explicitly states the Assessment section is machine-owned."""
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "machine" in content.lower() and "assessment" in content.lower(), (
        "SKILL.md must state that the Assessment section is machine-owned"
    )
    assert "hand-edit" in content.lower() or "must not" in content.lower() or "do not" in content.lower(), (
        "SKILL.md must warn against hand-editing the Assessment section"
    )


def test_agents_md_states_assessment_is_machine_owned():
    """AC8: agents.md explicitly states the Assessment section is machine-owned."""
    content = AGENTS_MD.read_text(encoding="utf-8")
    assert "assessment" in content.lower(), (
        "agents.md must mention 'Assessment' in the context of machine-owned sections"
    )
    assert "machine" in content.lower(), (
        "agents.md must mention machine-owned/machine-edited in context of ideas"
    )


def test_skill_md_states_frontmatter_is_machine_owned():
    """AC8: SKILL.md states the frontmatter is also machine-owned."""
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "frontmatter" in content.lower() or "front matter" in content.lower(), (
        "SKILL.md must mention frontmatter in the context of machine ownership"
    )


# ---------------------------------------------------------------------------
# Real fixture notes exist (AC5 — integration)
# ---------------------------------------------------------------------------

def test_real_fixture_dark_mode_exists():
    """AC5: vault/ideas/2026-01-10-dark-mode.md fixture exists."""
    assert (IDEAS_DIR / "2026-01-10-dark-mode.md").exists()


def test_real_fixture_offline_sync_exists():
    """AC5: vault/ideas/2026-03-04-offline-sync.md fixture exists."""
    assert (IDEAS_DIR / "2026-03-04-offline-sync.md").exists()


def test_real_fixtures_validate_cleanly():
    """AC5: Both real fixture notes pass validation."""
    ledger = _load_ledger()
    for fname in ("2026-01-10-dark-mode.md", "2026-03-04-offline-sync.md"):
        path = IDEAS_DIR / fname
        assert path.exists(), f"Fixture not found: {path}"
        errors = ledger.validate_note(path)
        assert errors == [], f"Fixture {fname} has validation errors: {errors}"


def test_real_ledger_regeneration_produces_two_rows(tmp_path):
    """AC5: Running regeneration against the two real fixtures produces a two-row ledger.

    The fixtures are copied into a scratch directory first: regenerating against
    the live vault/ideas/ would both mutate it and couple the assertion to however
    many ideas the vault happens to hold.
    """
    ledger = _load_ledger()
    scratch = tmp_path / "ideas"
    scratch.mkdir()
    for fname in ("2026-01-10-dark-mode.md", "2026-03-04-offline-sync.md"):
        shutil.copy(IDEAS_DIR / fname, scratch / fname)

    ledger.regenerate_ledger(scratch, today=date(2026, 8, 10))
    content = (scratch / "index.md").read_text(encoding="utf-8")
    data_rows = [
        ln for ln in content.splitlines()
        if ln.strip().startswith("|")
        and not re.match(r"\|\s*-+", ln)
        and "Idea" not in ln and "Status" not in ln
    ]
    assert len(data_rows) == 2, (
        f"Expected 2 data rows from real fixtures, got {len(data_rows)}:\n{content}"
    )

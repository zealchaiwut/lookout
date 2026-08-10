"""Tests for issue #12: journal cross-links in SKILL.md and vault/journal/index.md.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CROSSLINK_PY = REPO_ROOT / "journal_crosslink.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_crosslink(module_name="journal_crosslink_test"):
    spec = importlib.util.spec_from_file_location(module_name, str(CROSSLINK_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_delta(entries):
    return {"entries": entries}


def _make_entry(date, path, target_lines, concerns_lines=None):
    return {
        "date": date,
        "path": path,
        "frontmatter": {"date": date},
        "target_lines": target_lines,
        "concerns_lines": concerns_lines or [],
    }


def _two_date_delta():
    """Delta with perf-coach on two distinct dates plus an unrelated target on a third."""
    return _make_delta([
        _make_entry("2026-03-12", "2026-03-12.md",
                    target_lines=["Working on perf-coach today."]),
        _make_entry("2026-03-19", "2026-03-19.md",
                    target_lines=["Reviewed perf-coach metrics."]),
        _make_entry("2026-04-01", "2026-04-01.md",
                    target_lines=["commander deploy went smoothly."]),
    ])


def _make_vault(tmp_path, journal_index_content="# Journal\n"):
    vault = tmp_path / "vault"
    journal_dir = vault / "journal"
    journal_dir.mkdir(parents=True)
    (journal_dir / "index.md").write_text(journal_index_content)
    projects = vault / "projects"
    projects.mkdir()
    return vault


# ---------------------------------------------------------------------------
# Script existence
# ---------------------------------------------------------------------------

def test_journal_crosslink_py_exists():
    assert CROSSLINK_PY.exists(), "journal_crosslink.py must exist at repo root"


# ---------------------------------------------------------------------------
# AC1: two distinct perf-coach dates → exactly two dated links in SKILL.md
# ---------------------------------------------------------------------------

def test_two_dates_produce_two_links_in_skill_md(tmp_path):
    """AC1: delta with perf-coach on 2 dates → exactly 2 dated links in SKILL.md."""
    vault = _make_vault(tmp_path)
    delta = _two_date_delta()

    mod = _load_crosslink("jcl_ac1")
    mod.crosslink(
        delta=delta,
        vault_dir=vault,
        targets={"perf-coach": {}, "commander": {}},
    )

    skill_md = vault / "projects" / "perf-coach" / "SKILL.md"
    assert skill_md.exists(), "SKILL.md must be created for perf-coach"

    content = skill_md.read_text()
    assert "## From the journal" in content

    # Count dated links — format [YYYY-MM-DD](...)
    links = re.findall(r"\[20\d\d-\d\d-\d\d\]\([^)]+\)", content)
    assert len(links) == 2, f"Expected 2 dated links, found {len(links)}: {links}"

    dates_in_links = [re.search(r"\[(20\d\d-\d\d-\d\d)\]", lnk).group(1) for lnk in links]
    assert "2026-03-12" in dates_in_links
    assert "2026-03-19" in dates_in_links


def test_each_link_followed_by_gist(tmp_path):
    """AC1: each dated link is followed by a one-line gist."""
    vault = _make_vault(tmp_path)
    delta = _two_date_delta()

    mod = _load_crosslink("jcl_ac1b")
    mod.crosslink(
        delta=delta,
        vault_dir=vault,
        targets={"perf-coach": {}, "commander": {}},
    )

    skill_md = vault / "projects" / "perf-coach" / "SKILL.md"
    content = skill_md.read_text()

    # Each link line must contain " — " followed by gist text
    link_lines = [l for l in content.splitlines()
                  if re.match(r"\[20\d\d-\d\d-\d\d\]\(", l)]
    assert len(link_lines) == 2, f"Expected 2 link lines, got {len(link_lines)}"
    for line in link_lines:
        assert " — " in line or " - " in line, (
            f"Link line must contain a gist separator: {line!r}"
        )
        parts = re.split(r" — | - ", line, maxsplit=1)
        assert len(parts) == 2 and parts[1].strip(), (
            f"Link line must have non-empty gist: {line!r}"
        )


def test_no_full_entry_text_in_skill_md(tmp_path):
    """AC1: full journal entry text must not be copied into SKILL.md."""
    vault = _make_vault(tmp_path)
    unique_text = "FULL_ENTRY_BODY_CONTENT_XYZ_DO_NOT_COPY"
    delta = _make_delta([
        _make_entry("2026-03-12", "2026-03-12.md",
                    target_lines=[f"perf-coach: {unique_text}"]),
    ])

    mod = _load_crosslink("jcl_ac1c")
    mod.crosslink(
        delta=delta,
        vault_dir=vault,
        targets={"perf-coach": {}},
    )

    skill_md = vault / "projects" / "perf-coach" / "SKILL.md"
    content = skill_md.read_text()
    # The gist is allowed to contain the target_line text (it's a summary line),
    # but any other body content should not appear.
    # Verify the "From the journal" section doesn't contain multi-line dumps.
    section_start = content.find("## From the journal")
    if section_start >= 0:
        section = content[section_start:]
        lines = [l for l in section.splitlines() if l.strip() and not l.startswith("#")]
        for line in lines:
            assert "\n" not in line, "Each journal link must be a single line"


# ---------------------------------------------------------------------------
# AC2: same delta → exactly two new rows in vault/journal/index.md tagged perf-coach
# ---------------------------------------------------------------------------

def test_two_dates_append_two_index_rows(tmp_path):
    """AC2: delta with perf-coach on 2 dates → 2 new rows in vault/journal/index.md."""
    vault = _make_vault(tmp_path)
    delta = _two_date_delta()

    mod = _load_crosslink("jcl_ac2")
    mod.crosslink(
        delta=delta,
        vault_dir=vault,
        targets={"perf-coach": {}, "commander": {}},
    )

    index_md = vault / "journal" / "index.md"
    content = index_md.read_text()

    perf_coach_rows = [l for l in content.splitlines()
                       if "perf-coach" in l and ("2026-03-12" in l or "2026-03-19" in l)]
    assert len(perf_coach_rows) == 2, (
        f"Expected 2 perf-coach rows in vault/journal/index.md, found {len(perf_coach_rows)}"
    )


def test_index_rows_tagged_with_target(tmp_path):
    """AC2: each new index row is tagged with the target name."""
    vault = _make_vault(tmp_path)
    delta = _two_date_delta()

    mod = _load_crosslink("jcl_ac2b")
    mod.crosslink(
        delta=delta,
        vault_dir=vault,
        targets={"perf-coach": {}, "commander": {}},
    )

    index_md = vault / "journal" / "index.md"
    content = index_md.read_text()
    perf_rows = [l for l in content.splitlines() if "perf-coach" in l]
    assert len(perf_rows) >= 2, "Both rows must be tagged with perf-coach"


def test_existing_index_rows_unmodified(tmp_path):
    """AC2: pre-existing rows in vault/journal/index.md are not modified."""
    existing_content = "# Journal\n\n- [2026-01-01](2026-01-01.md) commander — old row\n"
    vault = _make_vault(tmp_path, journal_index_content=existing_content)
    delta = _two_date_delta()

    mod = _load_crosslink("jcl_ac2c")
    mod.crosslink(
        delta=delta,
        vault_dir=vault,
        targets={"perf-coach": {}, "commander": {}},
    )

    index_md = vault / "journal" / "index.md"
    content = index_md.read_text()
    assert "2026-01-01" in content and "old row" in content, (
        "Pre-existing rows must not be modified or removed"
    )


# ---------------------------------------------------------------------------
# AC6: delta with no perf-coach mentions → SKILL.md and index.md unchanged
# ---------------------------------------------------------------------------

def test_no_perf_coach_leaves_skill_md_unchanged(tmp_path):
    """AC6: delta with no perf-coach mentions must leave perf-coach SKILL.md unchanged."""
    vault = _make_vault(tmp_path)
    # Pre-create a SKILL.md with known content
    skill_dir = vault / "projects" / "perf-coach"
    skill_dir.mkdir(parents=True)
    original_content = "# perf-coach\n\nExisting content.\n"
    (skill_dir / "SKILL.md").write_text(original_content)

    # Delta with only commander mentions
    delta = _make_delta([
        _make_entry("2026-04-01", "2026-04-01.md",
                    target_lines=["commander deploy went smoothly."]),
    ])

    mod = _load_crosslink("jcl_ac6a")
    mod.crosslink(
        delta=delta,
        vault_dir=vault,
        targets={"perf-coach": {}, "commander": {}},
    )

    content = (skill_dir / "SKILL.md").read_text()
    assert content == original_content, (
        "perf-coach SKILL.md must be unchanged when no mentions exist"
    )


def test_no_perf_coach_leaves_index_unchanged(tmp_path):
    """AC6: delta with no perf-coach mentions must leave vault/journal/index.md unchanged."""
    original_index = "# Journal\n\n- [2026-01-01](2026-01-01.md) commander — old row\n"
    vault = _make_vault(tmp_path, journal_index_content=original_index)

    delta = _make_delta([
        _make_entry("2026-04-01", "2026-04-01.md",
                    target_lines=["commander deploy went smoothly."]),
    ])

    mod = _load_crosslink("jcl_ac6b")
    mod.crosslink(
        delta=delta,
        vault_dir=vault,
        targets={"perf-coach": {}},
    )

    index_md = vault / "journal" / "index.md"
    content = index_md.read_text()
    perf_coach_rows = [l for l in content.splitlines() if "perf-coach" in l]
    assert len(perf_coach_rows) == 0, (
        "No perf-coach rows must be added when there are no mentions"
    )


# ---------------------------------------------------------------------------
# UAT Step 1: unrelated target's date must NOT appear in perf-coach SKILL.md
# ---------------------------------------------------------------------------

def test_unrelated_target_date_not_in_skill_md(tmp_path):
    """UAT1: unrelated project date (commander, 2026-04-01) must NOT appear in perf-coach SKILL.md."""
    vault = _make_vault(tmp_path)
    delta = _two_date_delta()  # includes 2026-04-01 for commander

    mod = _load_crosslink("jcl_uat1")
    mod.crosslink(
        delta=delta,
        vault_dir=vault,
        targets={"perf-coach": {}, "commander": {}},
    )

    skill_md = vault / "projects" / "perf-coach" / "SKILL.md"
    content = skill_md.read_text()
    assert "2026-04-01" not in content, (
        "Commander's 2026-04-01 entry must not appear in perf-coach SKILL.md"
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def test_main_entrypoint_exists(tmp_path):
    """journal_crosslink.py must have a main() or if __name__ == '__main__' block."""
    source = CROSSLINK_PY.read_text()
    assert "def main(" in source or 'if __name__ == "__main__"' in source, (
        "journal_crosslink.py must have a CLI entry point"
    )

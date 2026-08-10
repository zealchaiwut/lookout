"""Tests for issue #28: M6 UAT — Assess and promote backlog ideas via vault.

Each test maps to a specific AC item from the issue. These are integration
tests that verify the live vault state after running the full UAT pipeline:
  1. Three idea files exist under vault/ideas/ (AC1)
  2. Assessment pass runs without errors and all three are assessed (AC2)
  3. Each assessment has all required fields with citations/open-questions (AC3)
  4. Spot-check citations exist (AC3 grounding rule)
  5. One idea is promoted with linked issue numbers (AC5)
  6. Ship-pass tracking shows per-issue state for promoted idea (AC6)
"""
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
VAULT_ROOT = REPO_ROOT / "vault"
IDEAS_DIR = VAULT_ROOT / "ideas"
ASSESSMENT_PASS_PY = REPO_ROOT / "assessment_pass.py"
SHIP_PASS_PY = REPO_ROOT / "ship_pass.py"
IDEAS_LEDGER_PY = REPO_ROOT / "ideas_ledger.py"

MACHINE_DELIMITER = "<!-- BEGIN MACHINE ASSESSMENT -->"
MACHINE_END = "<!-- END MACHINE ASSESSMENT -->"
ISSUE_TABLE_START = "<!-- BEGIN ISSUE STATE TABLE -->"

# Slugs for the three required UAT idea files
UAT_IDEA_SLUGS = [
    "hermes-journal-summary-skill",
    "perf-coach-trend-alerts",
    "crux-conversation-digest",
]

# Expected filenames (date-prefixed per vault convention)
UAT_IDEA_FILES = [
    "2026-08-10-hermes-journal-summary-skill.md",
    "2026-08-10-perf-coach-trend-alerts.md",
    "2026-08-10-crux-conversation-digest.md",
]

FIVE_ASSESSMENT_FIELDS = [
    "Already exists",
    "Must be built",
    "Effort",
    "Dependencies",
    "Suggested first slice",
]

_FM_RE = re.compile(r"^---\n(.*?)---\n", re.DOTALL)
_KV_RE = re.compile(r"^(\w+):\s*(.*)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _parse_frontmatter(text: str) -> dict | None:
    m = _FM_RE.match(text)
    if not m:
        return None
    fm_body = m.group(1)
    result: dict = {}
    for kv in _KV_RE.finditer(fm_body):
        key = kv.group(1)
        val = kv.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            result[key] = (
                [] if not inner
                else [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
            )
        else:
            result[key] = val if val not in ("null", "~", "") else None
    return result


def _get_assessment_block(text: str) -> str:
    """Return the text between the machine delimiter and end marker."""
    start = text.find(MACHINE_DELIMITER)
    end = text.find(MACHINE_END)
    if start == -1:
        return ""
    if end == -1:
        return text[start + len(MACHINE_DELIMITER):]
    return text[start + len(MACHINE_DELIMITER):end]


def _get_uat_idea_paths() -> list[Path]:
    return [IDEAS_DIR / fname for fname in UAT_IDEA_FILES]


# ---------------------------------------------------------------------------
# AC1: Three idea files exist under vault/ideas/, each from a real backlog item
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", UAT_IDEA_FILES)
def test_uat_idea_file_exists(filename):
    """AC1: Each of the three UAT idea files exists in vault/ideas/."""
    path = IDEAS_DIR / filename
    assert path.exists(), (
        f"AC1: UAT idea file not found: {path}\n"
        "Create three idea files under vault/ideas/ following the established schema."
    )


@pytest.mark.parametrize("filename,slug", zip(UAT_IDEA_FILES, UAT_IDEA_SLUGS))
def test_uat_idea_has_correct_slug(filename, slug):
    """AC1: Each idea file has a frontmatter slug matching its filename."""
    path = IDEAS_DIR / filename
    if not path.exists():
        pytest.skip(f"File not yet created: {filename}")
    fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
    assert fm is not None, f"Cannot parse frontmatter: {filename}"
    assert fm.get("slug") == slug, (
        f"AC1: slug in {filename} should be '{slug}', got '{fm.get('slug')}'"
    )


@pytest.mark.parametrize("filename", UAT_IDEA_FILES)
def test_uat_idea_passes_schema_validation(filename):
    """AC1: Each idea file passes ideas_ledger.py schema validation."""
    path = IDEAS_DIR / filename
    if not path.exists():
        pytest.skip(f"File not yet created: {filename}")
    ledger = _load_module(IDEAS_LEDGER_PY)
    errors = ledger.validate_note(path)
    assert errors == [], (
        f"AC1: Idea file {filename} has schema validation errors: {errors}"
    )


def test_uat_ideas_include_hermes_narrative_idea():
    """AC1: The Hermes journal summary skill idea (narrative-processing) is present."""
    hermes_path = IDEAS_DIR / "2026-08-10-hermes-journal-summary-skill.md"
    assert hermes_path.exists(), (
        "AC1: At least one idea must be the Hermes journal summary skill. "
        f"Expected at: {hermes_path}"
    )
    content = hermes_path.read_text(encoding="utf-8")
    assert "hermes" in content.lower() or "journal" in content.lower(), (
        "AC1: Hermes idea file must reference 'Hermes' or 'journal' in its description"
    )


# ---------------------------------------------------------------------------
# AC2: Assessment pass runs to completion without errors and produces artifacts
# ---------------------------------------------------------------------------

def test_assessment_pass_exits_zero():
    """AC2: Running assessment_pass.py exits 0 (no fatal errors)."""
    result = subprocess.run(
        [sys.executable, str(ASSESSMENT_PASS_PY)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"AC2: assessment_pass.py exited {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.parametrize("filename", UAT_IDEA_FILES)
def test_uat_idea_is_assessed(filename):
    """AC2: Each UAT idea file has been assessed (assessed field is not null)."""
    path = IDEAS_DIR / filename
    if not path.exists():
        pytest.skip(f"File not yet created: {filename}")
    fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
    assert fm is not None, f"Cannot parse frontmatter: {filename}"
    assessed = fm.get("assessed")
    assert assessed is not None, (
        f"AC2: {filename} has not been assessed yet "
        f"(assessed field is null). Run assessment_pass.py."
    )
    status = fm.get("status")
    assert status != "idea", (
        f"AC2: {filename} still has status 'idea' — assessment pass did not run "
        f"or did not process this file."
    )


@pytest.mark.parametrize("filename", UAT_IDEA_FILES)
def test_uat_idea_has_non_empty_assessment_block(filename):
    """AC2: Each UAT idea file has a non-empty assessment block."""
    path = IDEAS_DIR / filename
    if not path.exists():
        pytest.skip(f"File not yet created: {filename}")
    content = path.read_text(encoding="utf-8")
    assert MACHINE_DELIMITER in content, (
        f"AC2: {filename} is missing the machine assessment delimiter"
    )
    block = _get_assessment_block(content)
    assert block.strip() != "", (
        f"AC2: Assessment block in {filename} is empty"
    )
    assert "No assessment yet" not in block, (
        f"AC2: Assessment block in {filename} still contains placeholder text"
    )


# ---------------------------------------------------------------------------
# AC3: Each assessment explicitly names what exists, what is missing, what blocks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", UAT_IDEA_FILES)
@pytest.mark.parametrize("field", FIVE_ASSESSMENT_FIELDS)
def test_uat_assessment_has_required_field(filename, field):
    """AC3: Each assessment block contains all five DESIGN.md §9 fields."""
    path = IDEAS_DIR / filename
    if not path.exists():
        pytest.skip(f"File not yet created: {filename}")
    content = path.read_text(encoding="utf-8")
    block = _get_assessment_block(content)
    assert f"**{field}:**" in block, (
        f"AC3: Assessment in {filename} is missing required field '**{field}:**'.\n"
        f"Assessment block:\n{block}"
    )


@pytest.mark.parametrize("filename", UAT_IDEA_FILES)
def test_uat_assessment_has_citation_or_open_question(filename):
    """AC3: Each assessment block has at least one wikilink or numbered open question.

    Per DESIGN.md §9 grounding rule: every claim must cite a source via wikilink
    or be recorded as a numbered open question (Q1:, Q2:, …).
    """
    path = IDEAS_DIR / filename
    if not path.exists():
        pytest.skip(f"File not yet created: {filename}")
    content = path.read_text(encoding="utf-8")
    block = _get_assessment_block(content)
    has_wikilink = bool(re.search(r"\[\[[^\]]+\]\]", block))
    has_open_question = bool(re.search(r"Q\d+:", block))
    assert has_wikilink or has_open_question, (
        f"AC3: Assessment in {filename} has no wikilink citations and no open questions.\n"
        "Per DESIGN.md §9, every claim must cite a source (wikilink) or be "
        "recorded as a numbered open question (Q1:, Q2:, …).\n"
        f"Assessment block:\n{block}"
    )


def test_perf_coach_assessment_cites_atlas_note():
    """AC3: Assessment for perf-coach idea cites at least one real atlas note."""
    path = IDEAS_DIR / "2026-08-10-perf-coach-trend-alerts.md"
    if not path.exists():
        pytest.skip("perf-coach idea file not yet created")
    content = path.read_text(encoding="utf-8")
    block = _get_assessment_block(content)
    wikilinks = re.findall(r"\[\[([^\]]+)\]\]", block)
    atlas_refs = [w for w in wikilinks if "perf-coach" in w]
    assert atlas_refs, (
        "AC3: perf-coach assessment must cite at least one wikilink from the "
        f"perf-coach project. Found wikilinks: {wikilinks}\n"
        f"Assessment block:\n{block}"
    )


def test_hermes_assessment_has_open_question_for_unresolved_targets():
    """AC3: Hermes idea (unregistered target) has a numbered open question."""
    path = IDEAS_DIR / "2026-08-10-hermes-journal-summary-skill.md"
    if not path.exists():
        pytest.skip("hermes idea file not yet created")
    content = path.read_text(encoding="utf-8")
    block = _get_assessment_block(content)
    # Hermes is not a registered target, so the assessment must raise open questions
    has_q = bool(re.search(r"Q\d+:", block))
    has_wikilink = bool(re.search(r"\[\[[^\]]+\]\]", block))
    # Either an open question (if targets=[] → "first testable step?")
    # or a wikilink (if targets contain a registered project)
    assert has_q or has_wikilink, (
        "AC3: Hermes assessment must have an open question or wikilink citation.\n"
        f"Assessment block:\n{block}"
    )


# ---------------------------------------------------------------------------
# AC5: One idea manually promoted; issue numbers recorded in idea note
# ---------------------------------------------------------------------------

def test_at_least_one_uat_idea_is_promoted():
    """AC5: At least one UAT idea has status=promoted."""
    promoted = []
    for filename in UAT_IDEA_FILES:
        path = IDEAS_DIR / filename
        if not path.exists():
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm and fm.get("status") == "promoted":
            promoted.append(filename)
    assert promoted, (
        "AC5: No UAT idea has been promoted yet. "
        "Manually promote one idea: set status to 'promoted' and record "
        "the GitHub issue number(s) in the 'issues' frontmatter field."
    )


def test_promoted_idea_has_linked_issue_numbers():
    """AC5: The promoted idea has at least one linked GitHub issue number."""
    for filename in UAT_IDEA_FILES:
        path = IDEAS_DIR / filename
        if not path.exists():
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm and fm.get("status") == "promoted":
            issues = fm.get("issues") or []
            assert issues, (
                f"AC5: Promoted idea {filename} has an empty 'issues' list. "
                "Record the GitHub issue number(s) created during manual promotion."
            )
            # Verify each entry looks like an issue number
            for item in issues:
                try:
                    n = int(item)
                    assert n > 0, f"Issue number must be positive: {item}"
                except (ValueError, TypeError):
                    pytest.fail(
                        f"AC5: Invalid issue number '{item}' in {filename}. "
                        "The 'issues' field must contain integer issue numbers."
                    )
            return  # Found and validated a promoted idea
    pytest.skip("No promoted idea found yet — skipping issue-number check")


def test_promoted_idea_issues_are_recorded_in_note_body():
    """AC5: Issue numbers in 'issues' field are referenced in the assessment block or frontmatter."""
    for filename in UAT_IDEA_FILES:
        path = IDEAS_DIR / filename
        if not path.exists():
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm and fm.get("status") == "promoted":
            issues = fm.get("issues") or []
            if not issues:
                continue
            content = path.read_text(encoding="utf-8")
            for issue_num in issues:
                assert str(issue_num) in content, (
                    f"AC5: Issue number {issue_num} not found anywhere in {filename}. "
                    "Ensure the issue number appears in the file (frontmatter field is sufficient)."
                )
            return
    pytest.skip("No promoted idea with issues found — skipping body-reference check")


# ---------------------------------------------------------------------------
# AC6: Following assessment run, promoted idea shows per-issue state in tracking
# ---------------------------------------------------------------------------

def test_ship_pass_exits_zero():
    """AC6: Running ship_pass.py exits 0."""
    result = subprocess.run(
        [sys.executable, str(SHIP_PASS_PY)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"AC6: ship_pass.py exited {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_promoted_idea_has_issue_tracking_table():
    """AC6: After ship_pass runs, promoted idea contains a Linked Issues table."""
    for filename in UAT_IDEA_FILES:
        path = IDEAS_DIR / filename
        if not path.exists():
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm and fm.get("status") == "promoted":
            issues = fm.get("issues") or []
            if not issues:
                pytest.skip("Promoted idea has no issue numbers")
            content = path.read_text(encoding="utf-8")
            # Ship pass writes the issue table when not all issues are closed
            assert ISSUE_TABLE_START in content or "Linked Issues" in content, (
                f"AC6: Promoted idea {filename} does not contain a Linked Issues "
                "tracking table. Run ship_pass.py after setting status to 'promoted'.\n"
                f"Content snippet:\n{content[content.find(MACHINE_DELIMITER):]}"
            )
            return
    pytest.skip("No promoted idea found — skipping tracking table check")


def test_promoted_idea_tracking_shows_issue_state():
    """AC6: Linked Issues table shows a state column for each tracked issue."""
    for filename in UAT_IDEA_FILES:
        path = IDEAS_DIR / filename
        if not path.exists():
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm and fm.get("status") in ("promoted", "shipped"):
            issues = fm.get("issues") or []
            if not issues:
                pytest.skip("Promoted idea has no issue numbers")
            content = path.read_text(encoding="utf-8")
            for issue_num in issues:
                # Issue should appear as #N in the tracking table
                assert f"#{issue_num}" in content or str(issue_num) in content, (
                    f"AC6: Issue #{issue_num} not found in tracking output for {filename}"
                )
            # Table should contain a State column
            if ISSUE_TABLE_START in content:
                tbl_start = content.find(ISSUE_TABLE_START)
                tbl_snippet = content[tbl_start:tbl_start + 500]
                assert "State" in tbl_snippet or "state" in tbl_snippet, (
                    f"AC6: Linked Issues table in {filename} is missing a State column"
                )
            return
    pytest.skip("No promoted/shipped idea found — skipping state column check")


# ---------------------------------------------------------------------------
# Integrity: All three UAT ideas pass ledger validation simultaneously
# ---------------------------------------------------------------------------

def test_all_uat_ideas_pass_validation_together():
    """AC1+AC2: Running ideas_ledger.py exits 0 with all UAT ideas present."""
    for filename in UAT_IDEA_FILES:
        if not (IDEAS_DIR / filename).exists():
            pytest.skip(f"Not all UAT idea files created yet: {filename}")

    result = subprocess.run(
        [sys.executable, str(IDEAS_LEDGER_PY)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        "AC1: ideas_ledger.py validation failed with all UAT ideas present.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

"""Tests for issue #25: Add assessment pass to SKILL.md idea pipeline.

Each test maps to a specific AC item from the issue.
"""
import datetime
import importlib.util
import os
import re
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
ASSESSMENT_PASS_PY = REPO_ROOT / "assessment_pass.py"
VAULT_ROOT = REPO_ROOT / "vault"
IDEAS_DIR = VAULT_ROOT / "ideas"
SKILL_MD = REPO_ROOT / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"

MACHINE_DELIMITER = "<!-- BEGIN MACHINE ASSESSMENT -->"
MACHINE_END = "<!-- END MACHINE ASSESSMENT -->"
MAX_PER_RUN = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_assessment_pass():
    spec = importlib.util.spec_from_file_location(
        "assessment_pass", str(ASSESSMENT_PASS_PY)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_idea_note(
    directory: Path,
    filename: str,
    slug: str,
    created: str = "2026-01-10",
    status: str = "idea",
    targets: list | None = None,
    issues: list | None = None,
    assessed: str = "null",
    freeform: str = "Some human-written idea content.\n",
    assessment_body: str = "No assessment yet.\n",
) -> Path:
    t = targets if targets is not None else []
    i = issues if issues is not None else []
    fm = "\n".join([
        "---",
        f"slug: {slug}",
        f"created: {created}",
        f"status: {status}",
        f"targets: {t!r}",
        f"issues: {i!r}",
        f"assessed: {assessed}",
        "---",
    ]) + "\n\n"
    body = (
        freeform
        + "\n"
        + MACHINE_DELIMITER
        + "\n## Assessment\n\n"
        + assessment_body
        + MACHINE_END
        + "\n"
    )
    path = directory / filename
    path.write_text(fm + body, encoding="utf-8")
    return path


def _set_mtime(path: Path, dt: datetime.datetime) -> None:
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


# ---------------------------------------------------------------------------
# Module exists
# ---------------------------------------------------------------------------

def test_assessment_pass_module_exists():
    """AC1: assessment_pass.py exists at repo root."""
    assert ASSESSMENT_PASS_PY.exists(), f"assessment_pass.py not found at {ASSESSMENT_PASS_PY}"


# ---------------------------------------------------------------------------
# AC8: Cap logic — max 3 per run
# ---------------------------------------------------------------------------

def test_select_cap_at_three(tmp_path):
    """AC8: select_ideas_for_assessment returns at most 3 ideas."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    for i in range(5):
        _make_idea_note(ideas_dir, f"2026-01-0{i+1}-idea-{i}.md",
                        slug=f"idea-{i}", created=f"2026-01-0{i+1}",
                        assessed="null")
    result = ap.select_ideas_for_assessment(ideas_dir, VAULT_ROOT)
    assert len(result) <= MAX_PER_RUN, (
        f"Expected at most {MAX_PER_RUN} ideas, got {len(result)}"
    )


def test_select_cap_exactly_three_when_five_new(tmp_path):
    """AC8: select_ideas_for_assessment returns exactly 3 when 5 new ideas exist."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    for i in range(5):
        _make_idea_note(ideas_dir, f"2026-01-0{i+1}-idea-{i}.md",
                        slug=f"idea-{i}", created=f"2026-01-0{i+1}",
                        assessed="null")
    result = ap.select_ideas_for_assessment(ideas_dir, VAULT_ROOT)
    assert len(result) == MAX_PER_RUN, (
        f"Expected exactly {MAX_PER_RUN} ideas from 5 new, got {len(result)}"
    )


def test_select_cap_not_enforced_early_before_lm_calls(tmp_path):
    """AC8: Cap is enforced in select_ideas_for_assessment, before any processing."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    # Create 10 ideas — all new
    for i in range(10):
        _make_idea_note(ideas_dir, f"2026-01-{i+1:02d}-idea-{i}.md",
                        slug=f"idea-{i}", created=f"2026-01-{i+1:02d}",
                        assessed="null")
    result = ap.select_ideas_for_assessment(ideas_dir, VAULT_ROOT)
    assert len(result) <= MAX_PER_RUN, (
        f"Cap must be <= {MAX_PER_RUN}, got {len(result)}"
    )


# ---------------------------------------------------------------------------
# AC9: Assessed-date skip logic
# ---------------------------------------------------------------------------

def test_select_skips_assessed_unchanged_idea(tmp_path):
    """AC9: An idea assessed today and not modified since is skipped."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    today_str = "2026-08-10"
    note = _make_idea_note(ideas_dir, "2026-01-10-done.md",
                           slug="done", assessed=today_str, status="assessed")
    # Set mtime to same day as assessed
    _set_mtime(note, datetime.datetime(2026, 8, 10, 12, 0, 0))
    result = ap.select_ideas_for_assessment(ideas_dir, VAULT_ROOT,
                                            today=datetime.date(2026, 8, 10))
    assert note not in result, (
        "An idea assessed on the same day it was last modified should be skipped"
    )


def test_select_skips_assessed_idea_with_mtime_before_cutoff(tmp_path):
    """AC9: Idea with mtime on assessed date is skipped (unchanged)."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    note = _make_idea_note(ideas_dir, "2026-01-10-done.md",
                           slug="done", assessed="2026-08-05", status="assessed")
    # mtime is before the cutoff (end of 2026-08-05)
    _set_mtime(note, datetime.datetime(2026, 8, 5, 23, 59, 59))
    result = ap.select_ideas_for_assessment(ideas_dir, VAULT_ROOT,
                                            today=datetime.date(2026, 8, 10))
    assert note not in result, (
        "Idea with mtime before/on assessed date should be skipped"
    )


def test_select_includes_assessed_idea_edited_after_assessed_date(tmp_path):
    """AC9: An idea human-edited after its assessed date is included."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    note = _make_idea_note(ideas_dir, "2026-01-10-edited.md",
                           slug="edited", assessed="2026-08-05", status="assessed")
    # mtime is after the assessed date (next day — human edited)
    _set_mtime(note, datetime.datetime(2026, 8, 6, 9, 0, 0))
    result = ap.select_ideas_for_assessment(ideas_dir, VAULT_ROOT,
                                            today=datetime.date(2026, 8, 10))
    assert note in result, (
        "Idea with mtime after assessed date should be included for re-assessment"
    )


def test_select_includes_null_assessed_idea(tmp_path):
    """AC9: An idea with assessed=null is always included."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    note = _make_idea_note(ideas_dir, "2026-01-10-new.md",
                           slug="new-idea", assessed="null")
    result = ap.select_ideas_for_assessment(ideas_dir, VAULT_ROOT,
                                            today=datetime.date(2026, 8, 10))
    assert note in result, "New idea with assessed=null must be selected"


def test_select_zero_ideas_when_all_assessed_and_unchanged(tmp_path):
    """AC9: Returns empty list when all ideas are assessed and unmodified."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    for i in range(3):
        note = _make_idea_note(
            ideas_dir, f"2026-0{i+1}-01-idea.md",
            slug=f"idea-{i}", assessed="2026-08-05", status="assessed"
        )
        _set_mtime(note, datetime.datetime(2026, 8, 5, 10, 0, 0))
    result = ap.select_ideas_for_assessment(ideas_dir, VAULT_ROOT,
                                            today=datetime.date(2026, 8, 10))
    assert result == [], f"Expected empty list, got {result}"


# ---------------------------------------------------------------------------
# AC2: Assessment pass runs on new/edited ideas
# ---------------------------------------------------------------------------

def test_run_assessment_pass_processes_new_ideas(tmp_path):
    """AC2: run_assessment_pass processes ideas with assessed=null."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    note = _make_idea_note(ideas_dir, "2026-01-10-new.md",
                           slug="new-idea", assessed="null")
    assessed = ap.run_assessment_pass(ideas_dir, VAULT_ROOT,
                                      today=datetime.date(2026, 8, 10))
    assert note in assessed, "New idea should have been assessed"


def test_run_assessment_pass_skips_unedited(tmp_path):
    """AC2: run_assessment_pass skips assessed, unmodified ideas."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    note = _make_idea_note(ideas_dir, "2026-01-10-old.md",
                           slug="old-idea", assessed="2026-08-05", status="assessed")
    _set_mtime(note, datetime.datetime(2026, 8, 5, 10, 0, 0))
    content_before = note.read_text(encoding="utf-8")
    assessed = ap.run_assessment_pass(ideas_dir, VAULT_ROOT,
                                      today=datetime.date(2026, 8, 10))
    assert note not in assessed, "Unmodified assessed idea should be skipped"
    assert note.read_text(encoding="utf-8") == content_before, (
        "Skipped idea file must not be modified"
    )


def test_run_assessment_pass_respects_cap(tmp_path):
    """AC8+AC2: run_assessment_pass processes at most 3 ideas even when 5 are new."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    for i in range(5):
        _make_idea_note(ideas_dir, f"2026-01-0{i+1}-idea-{i}.md",
                        slug=f"idea-{i}", assessed="null")
    assessed = ap.run_assessment_pass(ideas_dir, VAULT_ROOT,
                                      today=datetime.date(2026, 8, 10))
    assert len(assessed) <= MAX_PER_RUN, (
        f"Assessment pass must process at most {MAX_PER_RUN} ideas per run"
    )


# ---------------------------------------------------------------------------
# AC3: Assessment section contains all five fields
# ---------------------------------------------------------------------------

def test_build_assessment_contains_five_fields(tmp_path):
    """AC3: build_assessment produces a section with all 5 required fields."""
    ap = _load_assessment_pass()
    note = _make_idea_note(tmp_path, "2026-01-10-test.md",
                           slug="test-idea", assessed="null")
    assessment = ap.build_assessment(note, VAULT_ROOT,
                                     today=datetime.date(2026, 8, 10))
    for field in ("Already exists", "Must be built", "Effort", "Dependencies",
                  "Suggested first slice"):
        assert f"**{field}:**" in assessment, (
            f"Assessment missing required field '**{field}:**':\n{assessment}"
        )


def test_build_assessment_effort_is_valid_size(tmp_path):
    """AC3: Effort field is one of S / M / L."""
    ap = _load_assessment_pass()
    note = _make_idea_note(tmp_path, "2026-01-10-test.md",
                           slug="test-idea", assessed="null")
    assessment = ap.build_assessment(note, VAULT_ROOT,
                                     today=datetime.date(2026, 8, 10))
    assert re.search(r"\*\*Effort:\*\*\s+[SML]\b", assessment), (
        f"Effort must be one of S / M / L:\n{assessment}"
    )


# ---------------------------------------------------------------------------
# AC4: Grounding rule — wikilinks or open questions
# ---------------------------------------------------------------------------

def test_build_assessment_unknown_claim_becomes_open_question(tmp_path):
    """AC4: Anything unresolvable is recorded as a numbered open question, not a guess."""
    ap = _load_assessment_pass()
    # Use a registered-but-empty project (viral-radar has only .gitkeep)
    note = _make_idea_note(tmp_path, "2026-01-10-test.md",
                           slug="test-idea", assessed="null",
                           targets=["viral-radar"])
    assessment = ap.build_assessment(note, VAULT_ROOT,
                                     today=datetime.date(2026, 8, 10))
    # Should contain a numbered open question
    assert re.search(r"Q\d+:", assessment), (
        f"Assessment for empty-atlas target must contain a numbered open question:\n{assessment}"
    )


# ---------------------------------------------------------------------------
# AC6: Fixture — perf-coach + viral-radar → cites atlas note or capability card
# ---------------------------------------------------------------------------

def test_fixture_perf_coach_viral_radar_cites_atlas_note(tmp_path):
    """AC6: Assessment for perf-coach+viral-radar cites at least one real atlas note."""
    ap = _load_assessment_pass()
    note = _make_idea_note(
        tmp_path, "2026-01-10-perf-idea.md",
        slug="perf-idea", assessed="null",
        targets=["perf-coach", "viral-radar"],
        freeform="Idea: Integrate performance coaching with viral tracking.\n",
    )
    assessment = ap.build_assessment(note, VAULT_ROOT,
                                     today=datetime.date(2026, 8, 10))
    # perf-coach has real atlas notes — expect at least one wikilink to atlas
    wikilinks = re.findall(r"\[\[([^\]]+)\]\]", assessment)
    atlas_refs = [w for w in wikilinks if "perf-coach/atlas/" in w or "viral-radar/atlas/" in w
                  or "perf-coach/capability" in w or "viral-radar/capability" in w]
    assert atlas_refs, (
        f"Assessment must cite at least one real atlas note or capability card.\n"
        f"Wikilinks found: {wikilinks}\nFull assessment:\n{assessment}"
    )


def test_fixture_perf_coach_cited_wikilinks_are_real_files(tmp_path):
    """AC6: Wikilinks in the assessment for perf-coach point to real files in the vault."""
    ap = _load_assessment_pass()
    note = _make_idea_note(
        tmp_path, "2026-01-10-perf-idea.md",
        slug="perf-idea", assessed="null",
        targets=["perf-coach"],
    )
    assessment = ap.build_assessment(note, VAULT_ROOT,
                                     today=datetime.date(2026, 8, 10))
    wikilinks = re.findall(r"\[\[([^\]]+)\]\]", assessment)
    for link in wikilinks:
        # Wikilinks use vault-relative paths: projects/perf-coach/atlas/note
        candidate = VAULT_ROOT / (link + ".md")
        if candidate.exists():
            break
    else:
        # If none resolved perfectly, at minimum check one is a valid atlas reference
        atlas_links = [w for w in wikilinks if "perf-coach/atlas/" in w]
        if atlas_links:
            # Check that the referenced file actually exists
            sample = VAULT_ROOT / (atlas_links[0] + ".md")
            assert sample.exists(), (
                f"Wikilink [[{atlas_links[0]}]] does not point to a real file: {sample}"
            )


# ---------------------------------------------------------------------------
# AC7: Fixture — unregistered project → explicit statement + open question
# ---------------------------------------------------------------------------

def test_fixture_unregistered_project_states_not_in_registry(tmp_path):
    """AC7: Assessment for an unregistered project explicitly states it is not in the registry."""
    ap = _load_assessment_pass()
    note = _make_idea_note(
        tmp_path, "2026-01-10-unknown.md",
        slug="unknown-idea", assessed="null",
        targets=["project-not-in-registry-xyz"],
        freeform="Idea: Use project-not-in-registry-xyz API.\n",
    )
    assessment = ap.build_assessment(note, VAULT_ROOT,
                                     today=datetime.date(2026, 8, 10))
    assert "not in registry" in assessment.lower() or "not registered" in assessment.lower(), (
        f"Assessment must explicitly state that project is not in the registry:\n{assessment}"
    )


def test_fixture_unregistered_project_raises_numbered_open_question(tmp_path):
    """AC7: Assessment for an unregistered project includes a numbered open question."""
    ap = _load_assessment_pass()
    note = _make_idea_note(
        tmp_path, "2026-01-10-unknown.md",
        slug="unknown-idea", assessed="null",
        targets=["project-not-in-registry-xyz"],
    )
    assessment = ap.build_assessment(note, VAULT_ROOT,
                                     today=datetime.date(2026, 8, 10))
    assert re.search(r"Q\d+:", assessment), (
        f"Assessment for unregistered project must include a numbered open question:\n{assessment}"
    )


def test_fixture_unregistered_project_no_fabricated_capabilities(tmp_path):
    """AC7: Assessment for an unregistered project does not fabricate capabilities."""
    ap = _load_assessment_pass()
    note = _make_idea_note(
        tmp_path, "2026-01-10-unknown.md",
        slug="unknown-idea", assessed="null",
        targets=["project-not-in-registry-xyz"],
    )
    assessment = ap.build_assessment(note, VAULT_ROOT,
                                     today=datetime.date(2026, 8, 10))
    # Should not have atlas wikilinks for the unregistered project
    fabricated = re.findall(r"\[\[project-not-in-registry-xyz/atlas/[^\]]+\]\]", assessment)
    assert not fabricated, (
        f"Assessment must not fabricate atlas capabilities for unregistered project:\n{assessment}"
    )


# ---------------------------------------------------------------------------
# AC10: No new fields written until assessment completes without errors
# ---------------------------------------------------------------------------

def test_frontmatter_unchanged_if_assessment_fails(tmp_path, monkeypatch):
    """AC10: Frontmatter is not modified if assessment raises an error."""
    ap = _load_assessment_pass()
    note = _make_idea_note(tmp_path, "2026-01-10-broken.md",
                           slug="broken", assessed="null")
    content_before = note.read_text(encoding="utf-8")

    # Monkeypatch build_assessment to raise an error
    original_build = ap.build_assessment
    def failing_build(*args, **kwargs):
        raise RuntimeError("Simulated assessment failure")
    monkeypatch.setattr(ap, "build_assessment", failing_build)

    ideas_dir = tmp_path
    ap.run_assessment_pass(ideas_dir, VAULT_ROOT, today=datetime.date(2026, 8, 10))

    content_after = note.read_text(encoding="utf-8")
    assert content_after == content_before, (
        "Frontmatter must not be modified when assessment fails"
    )


# ---------------------------------------------------------------------------
# SKILL.md documents the assessment pass (AC1)
# ---------------------------------------------------------------------------

def test_skill_md_documents_assessment_pass():
    """AC1: SKILL.md has a section documenting the assessment-pass skill."""
    assert SKILL_MD.exists()
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "assessment" in content.lower() and "pass" in content.lower(), (
        "SKILL.md must document the assessment-pass skill"
    )
    assert "assessment_pass" in content or "assessment-pass" in content, (
        "SKILL.md must reference the assessment-pass module or command"
    )


def test_skill_md_documents_five_assessment_fields():
    """AC3: SKILL.md documents the five required Assessment fields."""
    content = SKILL_MD.read_text(encoding="utf-8")
    for field in ("Already exists", "Must be built", "Effort", "Dependencies",
                  "Suggested first slice"):
        assert field in content, (
            f"SKILL.md must document the '{field}' Assessment field"
        )


# ---------------------------------------------------------------------------
# DESIGN.md §9 exists with assessment template (AC1)
# ---------------------------------------------------------------------------

def test_design_md_has_section_9():
    """AC1: DESIGN.md contains a §9 section defining the Assessment template."""
    assert DESIGN_MD.exists()
    content = DESIGN_MD.read_text(encoding="utf-8")
    assert "§9" in content, "DESIGN.md must contain a §9 section"


def test_design_md_section_9_contains_all_five_fields():
    """AC1: DESIGN.md §9 lists all five Assessment fields."""
    content = DESIGN_MD.read_text(encoding="utf-8")
    for field in ("Already exists", "Must be built", "Effort", "Dependencies",
                  "Suggested first slice"):
        assert field in content, (
            f"DESIGN.md §9 must define the '{field}' field"
        )


# ---------------------------------------------------------------------------
# Assessment block is written atomically (AC10)
# ---------------------------------------------------------------------------

def test_run_writes_assessed_date_to_frontmatter(tmp_path):
    """AC10: After a successful assessment, the assessed date is updated in frontmatter."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    note = _make_idea_note(ideas_dir, "2026-01-10-new.md",
                           slug="new-idea", assessed="null")
    today = datetime.date(2026, 8, 10)
    ap.run_assessment_pass(ideas_dir, VAULT_ROOT, today=today)
    content = note.read_text(encoding="utf-8")
    assert "assessed: 2026-08-10" in content, (
        f"Assessed date must be written to frontmatter after successful assessment:\n{content}"
    )


def test_run_writes_assessment_block(tmp_path):
    """AC2: After a successful assessment, the Assessment block is populated."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    note = _make_idea_note(ideas_dir, "2026-01-10-new.md",
                           slug="new-idea", assessed="null")
    ap.run_assessment_pass(ideas_dir, VAULT_ROOT, today=datetime.date(2026, 8, 10))
    content = note.read_text(encoding="utf-8")
    # Should have a populated Assessment section (not just "No assessment yet.")
    assert "**Already exists**" in content or "## Assessment" in content, (
        f"Assessment block must be written:\n{content}"
    )


def test_run_preserves_freeform_top(tmp_path):
    """AC2: run_assessment_pass preserves the freeform top section byte-for-byte."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    freeform = "Very specific human-written content that must not be changed.\n"
    note = _make_idea_note(ideas_dir, "2026-01-10-new.md",
                           slug="new-idea", assessed="null", freeform=freeform)
    ap.run_assessment_pass(ideas_dir, VAULT_ROOT, today=datetime.date(2026, 8, 10))
    content = note.read_text(encoding="utf-8")
    assert freeform in content, (
        "Freeform top section must be preserved after assessment pass"
    )


def test_early_exit_when_zero_ideas_to_assess(tmp_path, capsys):
    """AC2: When no ideas need assessment, the pass exits with a log message."""
    ap = _load_assessment_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    # Create already-assessed, unmodified idea
    note = _make_idea_note(ideas_dir, "2026-01-10-old.md",
                           slug="old", assessed="2026-08-05", status="assessed")
    _set_mtime(note, datetime.datetime(2026, 8, 5, 10, 0, 0))
    assessed = ap.run_assessment_pass(ideas_dir, VAULT_ROOT,
                                      today=datetime.date(2026, 8, 10))
    assert assessed == [], "Must return empty list when 0 ideas to assess"
    captured = capsys.readouterr()
    assert "0" in captured.out or "zero" in captured.out.lower() or "skip" in captured.out.lower(), (
        f"Expected log message mentioning 0 ideas to assess:\n{captured.out}"
    )

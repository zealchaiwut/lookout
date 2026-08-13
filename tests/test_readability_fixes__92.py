"""Tests for issue #92: fix three readability issues in the generated site.

Each test is anchored to a specific AC item.

AC1: Card titles render as links; subtitle does not inherit underline/link colour
AC2: Whole card remains clickable and keyboard-focusable, visible focus state
AC3: atlas/index.md appears as first entry inside atlas group, not project notes
AC4: Atlas group count excludes the index entry
AC5: Tables may exceed 72ch prose cap and use available width
AC6: Prose paragraphs remain capped at 72ch
AC7: At 375px nothing overflows horizontally
AC8: Light and dark themes remain legible (regression guard)
AC9: Output remains free of JavaScript (regression guard)
"""
import re
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import render_site as site_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture — a vault with atlas/index.md plus two feature notes
# ---------------------------------------------------------------------------

@pytest.fixture
def atlas_vault(tmp_path):
    v = tmp_path / "vault"
    atlas = v / "projects" / "perf-coach" / "atlas"
    atlas.mkdir(parents=True)
    (v / "projects" / "perf-coach" / "situation.md").write_text("# situation\n\nText.\n")
    (atlas / "index.md").write_text("# Atlas Index\n\nOverview.\n")
    (atlas / "aaaa.md").write_text("# aaaa\n\nText.\n")
    (atlas / "zzzz.md").write_text("# zzzz\n\nText.\n")
    return v


@pytest.fixture
def atlas_built(atlas_vault, tmp_path):
    out = tmp_path / "site"
    site_mod.generate_site(atlas_vault, out)
    return out


# ---------------------------------------------------------------------------
# AC1 — card subtitle does not inherit underline or link colour
# ---------------------------------------------------------------------------

def test_ac1_card_text_decoration_none():
    """The .card rule must suppress the default anchor underline."""
    card_block = re.search(r"\.card\s*\{[^}]+\}", site_mod.CSS)
    assert card_block is not None, ".card rule not found in CSS"
    assert "text-decoration: none" in card_block.group(), (
        ".card must include text-decoration: none to prevent both title and "
        "subtitle from rendering as underlined links"
    )


def test_ac1_card_subtitle_uses_muted_colour():
    """The subtitle <p> inside the card must stay in --text-muted."""
    m = re.search(r"\.card p\s*\{[^}]+\}", site_mod.CSS)
    assert m is not None, ".card p rule not found"
    assert "--text-muted" in m.group(), ".card p must use --text-muted"


def test_ac1_landing_card_structure(tmp_path):
    """Landing cards must be <a class='card'> with <h3> title and <p> subtitle."""
    v = tmp_path / "vault"
    (v / "projects" / "alpha" / "atlas").mkdir(parents=True)
    (v / "projects" / "alpha" / "situation.md").write_text("# alpha\n")
    out = tmp_path / "site"
    site_mod.generate_site(v, out)
    landing = (out / "index.html").read_text()
    assert '<a class="card"' in landing, "card must be an <a> element"
    assert "<h3>alpha</h3>" in landing, "card must contain an <h3> title"
    # Subtitle paragraph exists
    assert re.search(r"<p>\d+ notes", landing), "card must contain a <p> subtitle"


# ---------------------------------------------------------------------------
# AC2 — whole card clickable and keyboard-focusable with visible focus state
# ---------------------------------------------------------------------------

def test_ac2_card_focus_state_in_css():
    """CSS must define a visible focus outline for .card."""
    assert ".card:focus" in site_mod.CSS, (
        "CSS must include a .card:focus or .card:focus-visible rule with an outline"
    )
    focus_block = re.search(r"\.card:focus[^{]*\{[^}]+\}", site_mod.CSS)
    assert focus_block is not None, ".card:focus* rule not found"
    assert "outline" in focus_block.group(), ".card focus rule must set an outline"


def test_ac2_card_is_anchor_not_div(tmp_path):
    """Cards must be <a> elements so they receive keyboard focus natively."""
    v = tmp_path / "vault"
    (v / "projects" / "bravo" / "atlas").mkdir(parents=True)
    (v / "projects" / "bravo" / "situation.md").write_text("# bravo\n")
    out = tmp_path / "site"
    site_mod.generate_site(v, out)
    landing = (out / "index.html").read_text()
    assert '<a class="card"' in landing
    assert '<div class="card"' not in landing


# ---------------------------------------------------------------------------
# AC3 — atlas/index.md inside the atlas group, not among project notes
# ---------------------------------------------------------------------------

def test_ac3_atlas_index_goes_to_atlas_not_notes(atlas_vault):
    """build_tree must route atlas/index.md to proj['atlas'], not proj['notes']."""
    notes = site_mod.collect_notes(atlas_vault)
    tree = site_mod.build_tree(notes)
    proj = tree["projects"]["perf-coach"]
    note_stems = [n.stem for n in proj["notes"]]
    atlas_stems = [n.stem for n in proj["atlas"]]
    assert "index" not in note_stems, "atlas/index.md must not appear in project notes"
    assert "index" in atlas_stems, "atlas/index.md must appear in atlas group"


def test_ac3_atlas_index_is_first_entry(atlas_vault):
    """atlas/index.md must sort before all other atlas entries."""
    notes = site_mod.collect_notes(atlas_vault)
    tree = site_mod.build_tree(notes)
    atlas = tree["projects"]["perf-coach"]["atlas"]
    assert len(atlas) > 0, "atlas must not be empty"
    assert atlas[0].stem == "index", (
        f"First atlas entry is {atlas[0].stem!r}, expected 'index'"
    )


def test_ac3_index_appears_inside_atlas_block_in_sidebar(atlas_built):
    """Rendered sidebar must show 'index' inside the atlas <details> block."""
    page = (
        atlas_built / "notes" / "projects" / "perf-coach" / "situation.html"
    ).read_text()
    atlas_start = page.find("<summary>atlas")
    assert atlas_start != -1, "atlas <summary> not found in sidebar"
    index_link_pos = page.find(">index<", atlas_start)
    assert index_link_pos != -1, "index link not found inside atlas block"


def test_ac3_index_not_in_flat_project_notes(atlas_built):
    """'index' must not appear among situation/capability/etc. in the sidebar."""
    page = (
        atlas_built / "notes" / "projects" / "perf-coach" / "situation.html"
    ).read_text()
    atlas_start = page.find("<summary>atlas")
    # Grab the project block text before the atlas group
    project_block_start = page.find("<summary>perf-coach")
    assert project_block_start != -1
    pre_atlas = page[project_block_start:atlas_start]
    assert ">index<" not in pre_atlas, (
        "index link appeared among project-level notes before the atlas group"
    )


# ---------------------------------------------------------------------------
# AC4 — atlas count excludes the index entry
# ---------------------------------------------------------------------------

def test_ac4_sidebar_count_excludes_index(atlas_built):
    """Sidebar atlas count must be 2 (aaaa + zzzz), not 3 (index counted)."""
    page = (
        atlas_built / "notes" / "projects" / "perf-coach" / "situation.html"
    ).read_text()
    assert '<span class="count">(2)</span>' in page, (
        "Atlas count must be 2 (feature notes only, excluding index)"
    )
    assert '<span class="count">(3)</span>' not in page, (
        "Atlas count must not include the index entry"
    )


def test_ac4_landing_atlas_count_excludes_index(atlas_vault, tmp_path):
    """Landing page subtitle must show 2 atlas (feature notes), not 3."""
    out = tmp_path / "site"
    site_mod.generate_site(atlas_vault, out)
    landing = (out / "index.html").read_text()
    # Should show "2 atlas", not "3 atlas"
    assert "2 atlas" in landing, "Landing card must show 2 atlas (feature notes only)"
    assert "3 atlas" not in landing, "Landing card must not count the index note"


# ---------------------------------------------------------------------------
# AC5 — tables may exceed 72ch prose cap
# ---------------------------------------------------------------------------

def test_ac5_inner_does_not_apply_72ch_unconditionally():
    """The .inner element must not cap all children at 72ch."""
    css = site_mod.CSS
    # Old broken pattern: .inner { max-width: 72ch; }
    # Find any .inner { ... } block and ensure it doesn't set max-width
    inner_rule = re.search(r"\.inner\s*\{([^}]*)\}", css)
    if inner_rule:
        assert "max-width" not in inner_rule.group(1), (
            ".inner must not set max-width — tables would be constrained to 72ch. "
            "Use .inner > *:not(.table-wrap) { max-width: 72ch; } instead."
        )


def test_ac5_prose_constraint_uses_not_table_wrap_selector():
    """The 72ch constraint must use a selector that excludes .table-wrap."""
    assert ".inner > *:not(.table-wrap)" in site_mod.CSS, (
        "CSS must constrain prose with .inner > *:not(.table-wrap) { max-width: 72ch; } "
        "so that .table-wrap can expand beyond 72ch"
    )


# ---------------------------------------------------------------------------
# AC6 — prose paragraphs remain capped at 72ch
# ---------------------------------------------------------------------------

def test_ac6_72ch_constraint_still_present():
    """max-width: 72ch must still appear in the CSS after the table fix."""
    assert "72ch" in site_mod.CSS, "72ch prose cap must remain in CSS"
    assert "max-width: 72ch" in site_mod.CSS


def test_ac6_prose_renders_within_72ch_selector(tmp_path):
    """Rendered pages must include a prose-constraining selector."""
    # The rendered HTML structure means prose is constrained by the new CSS rule
    v = tmp_path / "vault"
    (v / "projects" / "delta" / "atlas").mkdir(parents=True)
    (v / "projects" / "delta" / "situation.md").write_text("# sit\n\nProse paragraph.\n")
    out = tmp_path / "site"
    site_mod.generate_site(v, out)
    page = (out / "notes" / "projects" / "delta" / "situation.html").read_text()
    # The page must have a .inner element wrapping prose
    assert 'class="inner"' in page


# ---------------------------------------------------------------------------
# AC7 — no horizontal overflow at 375px
# ---------------------------------------------------------------------------

def test_ac7_table_wrap_has_overflow_x_auto():
    """Tables wider than their container must scroll within .table-wrap."""
    m = re.search(r"\.table-wrap\s*\{[^}]+\}", site_mod.CSS)
    assert m is not None, ".table-wrap rule not found"
    assert "overflow-x: auto" in m.group(), ".table-wrap must have overflow-x: auto"


def test_ac7_body_has_no_overflow_x_constraint():
    """Body and html must not force horizontal scroll."""
    assert "body { overflow-x" not in site_mod.CSS
    assert "html { overflow-x" not in site_mod.CSS


def test_ac7_narrow_media_query_still_present():
    """@media (max-width: 720px) block must still collapse the sidebar."""
    assert "@media (max-width: 720px)" in site_mod.CSS
    narrow = site_mod.CSS.split("@media (max-width: 720px)")[1]
    assert ".layout { display: block; }" in narrow


# ---------------------------------------------------------------------------
# AC8 — light and dark themes remain legible (regression guard)
# ---------------------------------------------------------------------------

def test_ac8_colour_tokens_unchanged():
    """All design tokens must survive the readability changes."""
    root = site_mod.CSS.split("@media")[0]
    for token in ("--bg", "--surface", "--border", "--text", "--text-muted",
                  "--accent", "--code-bg"):
        assert f"{token}:" in root, f"{token} missing from :root"
    dark = site_mod.CSS.split("@media (prefers-color-scheme: dark)")[1]
    for token in ("--bg", "--text", "--accent"):
        assert f"{token}:" in dark, f"{token} missing from dark override"


# ---------------------------------------------------------------------------
# AC9 — no JavaScript (regression guard)
# ---------------------------------------------------------------------------

def test_ac9_no_script_tags_in_css():
    assert "<script" not in site_mod.CSS.lower()


def test_ac9_no_javascript_in_generated_pages(atlas_built):
    for page in atlas_built.rglob("*.html"):
        text = page.read_text()
        assert "<script" not in text.lower(), f"{page.name} contains a script tag"
        assert "onclick=" not in text.lower()

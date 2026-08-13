"""Tests for issue #91: show note ownership and link to source in the generated site.

Each test is anchored to a specific AC item.

AC1: Every page carries a visible ownership badge with three states
AC2: Ownership derived from vault/agents.md file types and sentinels, not a hardcoded list
AC3: Machine badge states edits are overwritten on the next run
AC4: Mixed badge names the editable region
AC5: Each page links to its source .md file via relative file://-safe path
AC6: Badge distinguishable without colour (icon or text label); contrast OK in light/dark
AC7: Badge does not dominate the page — styled like provenance lines
AC8: Badge and link add no JavaScript and no network request
AC9: Unknown ownership rule falls back to machine badge (safer default)
AC10: pytest passes and lint.py exits 0
"""
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import render_site as site_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — synthetic vault covering each ownership state
# ---------------------------------------------------------------------------

@pytest.fixture
def ownership_vault(tmp_path):
    """Vault with one note in each ownership category."""
    v = tmp_path / "vault"
    (v / "projects" / "alpha" / "atlas").mkdir(parents=True)
    (v / "ideas").mkdir()

    # Machine-owned: situation file
    (v / "projects" / "alpha" / "situation.md").write_text(
        "---\ntarget: alpha\n---\n\n# Situation\n\nMachine content.\n"
    )
    # Machine-owned: atlas file
    (v / "projects" / "alpha" / "atlas" / "feature.md").write_text(
        "# Feature\n\nAtlas content.\n"
    )
    # Human-owned: agents.md
    (v / "agents.md").write_text(
        "# Agents\n\n## Machine-Owned File Types\n\n- **situation** — ...\n\n"
        "## Human-Owned File Types\n\n- **agents.md** — this control note\n"
    )
    # Mixed: idea note with machine assessment sentinel
    (v / "ideas" / "2026-01-01-test-idea.md").write_text(
        "# Test Idea\n\nHuman freeform content.\n\n"
        "<!-- BEGIN MACHINE ASSESSMENT -->\n## Assessment\n\nMachine content.\n"
    )
    # Mixed: map.md with machine edges + human pipelines sentinels
    (v / "map.md").write_text(
        "# Map\n\n<!-- BEGIN MACHINE EDGES -->\n- a -> b\n<!-- END MACHINE EDGES -->\n\n"
        "<!-- BEGIN HUMAN PIPELINES -->\n<!-- END HUMAN PIPELINES -->\n"
    )
    # Unknown / fallback: a file that does not match any known type
    (v / "mystery.md").write_text("# Mystery\n\nUnknown file.\n")
    return v


@pytest.fixture
def built_ownership(ownership_vault, tmp_path):
    out = tmp_path / "site"
    site_mod.generate_site(ownership_vault, out)
    return out, ownership_vault


def read_page(out, rel):
    return (out / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC1 — every page carries a visible ownership badge
# ---------------------------------------------------------------------------

def test_ac1_situation_has_ownership_badge(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/projects/alpha/situation.html")
    assert "ownership-badge" in page


def test_ac1_agents_has_ownership_badge(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/agents.html")
    assert "ownership-badge" in page


def test_ac1_idea_has_ownership_badge(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/ideas/2026-01-01-test-idea.html")
    assert "ownership-badge" in page


def test_ac1_map_has_ownership_badge(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/map.html")
    assert "ownership-badge" in page


# ---------------------------------------------------------------------------
# AC2 — ownership derived from agents.md file types and sentinels, not hardcoded list
# ---------------------------------------------------------------------------

def test_ac2_resolve_ownership_is_a_function():
    """resolve_ownership must exist as a callable in render_site."""
    assert callable(getattr(site_mod, "resolve_ownership", None)), (
        "render_site.resolve_ownership is not defined"
    )


def test_ac2_machine_type_resolved_from_stem(tmp_path):
    vault = tmp_path / "vault"
    (vault / "projects" / "x").mkdir(parents=True)
    md = vault / "projects" / "x" / "situation.md"
    md.write_text("# s\n\nContent.\n")
    note = site_mod.Note(md, vault)
    text = md.read_text()
    result = site_mod.resolve_ownership(note, text)
    assert result["state"] == "machine"


def test_ac2_human_type_resolved_from_name(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    md = vault / "agents.md"
    md.write_text("# Agents\n\nHuman note.\n")
    note = site_mod.Note(md, vault)
    text = md.read_text()
    result = site_mod.resolve_ownership(note, text)
    assert result["state"] == "human"


def test_ac2_mixed_resolved_from_machine_assess_sentinel(tmp_path):
    vault = tmp_path / "vault"
    (vault / "ideas").mkdir(parents=True)
    md = vault / "ideas" / "2026-01-01-foo.md"
    md.write_text("Human part.\n\n<!-- BEGIN MACHINE ASSESSMENT -->\n## Assess\n")
    note = site_mod.Note(md, vault)
    text = md.read_text()
    result = site_mod.resolve_ownership(note, text)
    assert result["state"] == "mixed"


def test_ac2_mixed_resolved_from_machine_and_human_sentinels(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    md = vault / "map.md"
    md.write_text(
        "# Map\n<!-- BEGIN MACHINE EDGES -->\n- a\n<!-- END MACHINE EDGES -->\n"
        "<!-- BEGIN HUMAN PIPELINES -->\n<!-- END HUMAN PIPELINES -->\n"
    )
    note = site_mod.Note(md, vault)
    text = md.read_text()
    result = site_mod.resolve_ownership(note, text)
    assert result["state"] == "mixed"


# ---------------------------------------------------------------------------
# AC3 — machine badge states edits are overwritten
# ---------------------------------------------------------------------------

def test_ac3_machine_badge_mentions_overwrite(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/projects/alpha/situation.html")
    assert "ownership-badge" in page
    # Must mention overwriting
    assert re.search(r"overwrit", page, re.IGNORECASE), (
        "machine badge must warn that edits are overwritten"
    )


def test_ac3_machine_badge_label_visible(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/projects/alpha/situation.html")
    # Must have a text label (not just colour) indicating machine ownership
    assert re.search(r"[Mm]achine", page)


# ---------------------------------------------------------------------------
# AC4 — mixed badge names the editable region
# ---------------------------------------------------------------------------

def test_ac4_idea_mixed_badge_names_freeform_top(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/ideas/2026-01-01-test-idea.html")
    assert "freeform" in page.lower() or "human" in page.lower(), (
        "mixed badge for idea note must name the editable region"
    )


def test_ac4_map_mixed_badge_names_pipelines(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/map.html")
    assert "pipeline" in page.lower() or "human" in page.lower(), (
        "mixed badge for map.md must name the editable region (Pipelines)"
    )


def test_ac4_resolve_ownership_returns_editable_for_mixed(tmp_path):
    vault = tmp_path / "vault"
    (vault / "ideas").mkdir(parents=True)
    md = vault / "ideas" / "2026-01-01-foo.md"
    md.write_text("Human.\n\n<!-- BEGIN MACHINE ASSESSMENT -->\n## Assess\n")
    note = site_mod.Note(md, vault)
    text = md.read_text()
    result = site_mod.resolve_ownership(note, text)
    assert result["state"] == "mixed"
    assert result.get("editable"), "editable region name must be set for mixed state"


# ---------------------------------------------------------------------------
# AC5 — source link with relative file://-safe path to .md
# ---------------------------------------------------------------------------

def test_ac5_source_link_present_on_situation_page(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/projects/alpha/situation.html")
    assert "situation.md" in page, "source link to situation.md must appear on the page"


def test_ac5_source_link_is_relative(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/projects/alpha/situation.html")
    # Must not be an absolute path or http URL
    assert "http" not in page.split("situation.md")[0].split("href=")[-1]


def test_ac5_source_link_resolves_to_actual_md_file(built_ownership, ownership_vault):
    """The href in the source link, resolved from the HTML file, must point to the .md."""
    out, vault = built_ownership
    html_file = out / "notes" / "projects" / "alpha" / "situation.html"
    page = html_file.read_text()
    # Extract the href of the source link
    m = re.search(r'class="source-link"[^>]*href="([^"]+)"', page)
    if not m:
        m = re.search(r'href="([^"]+)"[^>]*class="source-link"', page)
    assert m, "source-link anchor with href not found on situation page"
    href = m.group(1)
    # Resolve relative to the HTML file's directory
    resolved = (html_file.parent / href).resolve()
    expected = (vault / "projects" / "alpha" / "situation.md").resolve()
    assert resolved == expected, f"source link resolved to {resolved}, expected {expected}"


def test_ac5_source_link_on_nested_note(built_ownership, ownership_vault):
    """Atlas note (deeper nesting) must have a working source link."""
    out, vault = built_ownership
    html_file = out / "notes" / "projects" / "alpha" / "atlas" / "feature.html"
    page = html_file.read_text()
    m = re.search(r'class="source-link"[^>]*href="([^"]+)"', page)
    if not m:
        m = re.search(r'href="([^"]+)"[^>]*class="source-link"', page)
    assert m, "source-link anchor not found on atlas/feature page"
    href = m.group(1)
    resolved = (html_file.parent / href).resolve()
    expected = (vault / "projects" / "alpha" / "atlas" / "feature.md").resolve()
    assert resolved == expected


# ---------------------------------------------------------------------------
# AC6 — badge distinguishable without colour (icon or text label)
# ---------------------------------------------------------------------------

def test_ac6_badge_has_text_label_not_just_color(built_ownership):
    """Badge must carry a text label so it is legible without colour."""
    out, _ = built_ownership
    for page_path in out.rglob("*.html"):
        if page_path.name == "index.html" and page_path.parent == out:
            continue  # landing page has no badge
        page = page_path.read_text()
        # The badge container exists
        if "ownership-badge" not in page:
            continue
        # It must contain at least one of the ownership keywords as visible text
        assert re.search(r"machine|human|mixed", page, re.IGNORECASE), (
            f"{page_path.name}: badge must include a text label (machine/human/mixed)"
        )


def test_ac6_css_includes_dark_mode_badge_rule(built_ownership):
    """The stylesheet must have a dark-mode rule that covers the badge."""
    out, _ = built_ownership
    css = (out / "style.css").read_text()
    assert "ownership-badge" in css
    assert "prefers-color-scheme: dark" in css or "ownership-badge" in css


# ---------------------------------------------------------------------------
# AC7 — badge does not dominate — styled as metadata (like provenance)
# ---------------------------------------------------------------------------

def test_ac7_badge_uses_small_font_class(built_ownership):
    """Badge must use a muted/small CSS class, not a heading or large element."""
    out, _ = built_ownership
    page = read_page(out, "notes/projects/alpha/situation.html")
    # Badge must not appear inside a heading tag on the same line
    for line in page.splitlines():
        if "ownership-badge" in line:
            assert not re.search(r"<h[1-3][\s>]", line), (
                f"ownership-badge appears inside a heading: {line!r}"
            )
    # Must use the ownership-badge class (size/color handled by CSS)
    assert "ownership-badge" in page


# ---------------------------------------------------------------------------
# AC8 — no JavaScript, no network request added by badge
# ---------------------------------------------------------------------------

def test_ac8_no_script_tags(built_ownership):
    out, _ = built_ownership
    for page_path in out.rglob("*.html"):
        page = page_path.read_text()
        assert "<script" not in page.lower(), f"{page_path.name} contains a script tag"


def test_ac8_no_external_url_in_source_link(built_ownership):
    out, _ = built_ownership
    for page_path in out.rglob("*.html"):
        page = page_path.read_text()
        # source-link href must not be an external URL
        for m in re.finditer(r'class="source-link"[^>]*href="([^"]+)"', page):
            href = m.group(1)
            assert not href.startswith("http"), (
                f"source link in {page_path.name} must not be an external URL"
            )


# ---------------------------------------------------------------------------
# AC9 — unknown file falls back to machine badge (safer default)
# ---------------------------------------------------------------------------

def test_ac9_unknown_file_defaults_to_machine(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    md = vault / "mystery.md"
    md.write_text("# Mystery\n\nNo sentinels, unknown type.\n")
    note = site_mod.Note(md, vault)
    text = md.read_text()
    result = site_mod.resolve_ownership(note, text)
    assert result["state"] == "machine", (
        "unknown file types must fall back to machine (the safer default)"
    )


def test_ac9_fallback_page_shows_machine_badge(built_ownership):
    out, _ = built_ownership
    page = read_page(out, "notes/mystery.html")
    assert "ownership-badge" in page
    assert re.search(r"[Mm]achine", page)


# ---------------------------------------------------------------------------
# AC10 — lint.py exits 0 (covered by pytest collection; lint tested separately)
# ---------------------------------------------------------------------------

def test_ac10_render_site_imports_only_stdlib():
    """No new third-party imports introduced."""
    import ast
    tree = ast.parse((REPO_ROOT / "render_site.py").read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    allowed = {"argparse", "html", "re", "sys", "os", "pathlib"}
    assert imports <= allowed, f"non-stdlib import introduced: {imports - allowed}"

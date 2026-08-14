"""Tests for issue #88: render the vault to a static HTML site with a tree sidebar.

Each test maps to a specific AC item from the issue.
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import render_site as site_mod  # noqa: E402

VAULT = REPO_ROOT / "vault"


# ---------------------------------------------------------------------------
# Fixtures — a small synthetic vault, so tests do not depend on live content
# ---------------------------------------------------------------------------

@pytest.fixture
def mini_vault(tmp_path):
    v = tmp_path / "vault"
    (v / "projects" / "alpha" / "atlas").mkdir(parents=True)
    (v / "projects" / "beta").mkdir(parents=True)
    (v / "ideas").mkdir()

    (v / "index.md").write_text("# Vault Index\n\n- [[alpha]]\n")
    (v / "map.md").write_text(
        "# Map\n\n<!-- BEGIN MACHINE EDGES -->\n- a -> b\n<!-- END MACHINE EDGES -->\n"
    )
    (v / "projects" / "alpha" / "situation.md").write_text(
        "---\ntarget: alpha\nsources_ok: true\n---\n\n"
        "## One-liner\n\nAlpha is a thing.\n_(source: manifest.json)_\n\n"
        "## Table\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "## Code\n\n```python\nx = 1\n```\n\n"
        "> a quote\n\n1. first\n2. second\n"
    )
    (v / "projects" / "alpha" / "capability.md").write_text("# cap\n\nText.\n")
    (v / "projects" / "alpha" / "drift.md").write_text("# drift\n\nText.\n")
    (v / "projects" / "alpha" / "todo-view.md").write_text("# todo\n\nText.\n")
    (v / "projects" / "alpha" / "atlas" / "zulu.md").write_text("# zulu\n\nZ.\n")
    (v / "projects" / "alpha" / "atlas" / "alfa.md").write_text("# alfa\n\nA.\n")
    (v / "projects" / "beta" / "situation.md").write_text("# beta\n\nB.\n")
    (v / "ideas" / "an-idea.md").write_text("# idea\n\nSee [[alfa]] and [[nope]].\n")
    return v


@pytest.fixture
def built(mini_vault, tmp_path):
    out = tmp_path / "site"
    count = site_mod.generate_site(mini_vault, out)
    return out, count


def read(out, rel):
    return (out / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC1 / AC2 — page per note plus a landing page
# ---------------------------------------------------------------------------

def test_ac1_generates_one_page_per_note_plus_landing(built, mini_vault):
    out, count = built
    notes = len(list(mini_vault.rglob("*.md")))
    assert count == notes + 1
    assert len(list(out.rglob("*.html"))) == notes + 1


def test_ac1_landing_page_exists_and_does_not_collide_with_vault_index(built):
    out, _ = built
    assert (out / "index.html").exists()
    assert (out / "notes" / "index.html").exists()
    assert "Vault Index" in read(out, "notes/index.html")
    assert "Vault Index" not in read(out, "index.html")


def test_ac1_real_vault_page_count_matches_note_count(tmp_path):
    """The live vault renders one page per note, plus the landing page."""
    notes = [
        p for p in VAULT.rglob("*.md")
        if "raw" not in p.relative_to(VAULT).parts
    ]
    out = tmp_path / "site"
    count = site_mod.generate_site(VAULT, out)
    assert count == len(notes) + 1


# ---------------------------------------------------------------------------
# AC3 — no JavaScript, no network
# ---------------------------------------------------------------------------

def test_ac3_output_contains_no_javascript(built):
    out, _ = built
    for page in out.rglob("*.html"):
        text = page.read_text()
        assert "<script" not in text.lower(), f"{page.name} contains a script tag"
        assert "onclick=" not in text.lower()


def test_ac3_output_makes_no_external_requests(built):
    out, _ = built
    for page in out.rglob("*.html"):
        text = page.read_text()
        assert "http://" not in text.replace('href="http', "SAFE")
        for needle in ("https://cdn", "//unpkg", "//cdnjs", "fonts.googleapis"):
            assert needle not in text


def test_ac3_stylesheet_is_local_and_relative(built):
    out, _ = built
    assert (out / "style.css").exists()
    page = read(out, "notes/projects/alpha/situation.html")
    assert 'href="../../../style.css"' in page


# ---------------------------------------------------------------------------
# AC4 — stdlib only
# ---------------------------------------------------------------------------

def test_ac4_site_module_imports_only_stdlib():
    # Parsed rather than pattern-matched: the module docstring contains prose
    # like "from map.md into a project's situation.md", which any regex over the
    # raw text reads as an import.
    tree = ast.parse((REPO_ROOT / "render_site.py").read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    allowed = {"argparse", "html", "re", "sys", "os", "pathlib"}
    assert imports <= allowed, f"non-stdlib import: {imports - allowed}"


# ---------------------------------------------------------------------------
# AC5 / AC6 / AC7 — tree structure, expansion, ordering
# ---------------------------------------------------------------------------

def test_ac5_sidebar_has_the_four_sections(built):
    out, _ = built
    page = read(out, "notes/projects/alpha/situation.html")
    for section in ("Overview", "Projects", "Fleet"):
        assert f"<summary>{section}" in page
    assert "<summary>Ideas" in page


def test_ac5_tree_uses_native_details_not_javascript(built):
    out, _ = built
    page = read(out, "notes/projects/alpha/situation.html")
    assert "<details" in page and "<summary>" in page


def test_ac6_current_page_is_marked(built):
    out, _ = built
    page = read(out, "notes/projects/alpha/situation.html")
    assert 'aria-current="page"' in page
    assert page.count('aria-current="page"') == 1


def test_ac6_only_ancestors_of_current_page_are_open(built):
    out, _ = built
    # An atlas note: its project and the atlas group are open, Ideas is not.
    page = read(out, "notes/projects/alpha/atlas/alfa.html")
    assert "<details open><summary>Projects" in page
    assert "<details open><summary>alpha" in page
    assert re.search(r"<details><summary>Ideas", page)


def test_ac7_project_notes_use_pipeline_order_not_alphabetical(built):
    out, _ = built
    page = read(out, "notes/projects/alpha/situation.html")
    # Scope to alpha's own group — beta also has a `situation` note.
    block = page.split("<summary>alpha</summary>")[1].split("<summary>beta")[0]
    order = [m.group(1) for m in re.finditer(r">([a-z\- ]+)</a></li>", block)]
    keep = [o for o in order if o in ("situation", "capability", "drift", "todo view")]
    assert keep == ["situation", "capability", "drift", "todo view"]


def test_ac7_atlas_notes_sort_alphabetically(built):
    out, _ = built
    page = read(out, "notes/projects/alpha/situation.html")
    assert page.index(">alfa</a>") < page.index(">zulu</a>")


def test_ac7_large_groups_show_a_count(built):
    out, _ = built
    page = read(out, "notes/projects/alpha/situation.html")
    assert '<span class="count">(2)</span>' in page


# ---------------------------------------------------------------------------
# AC8 — markdown constructs
# ---------------------------------------------------------------------------

def test_ac8_headings_render():
    out = site_mod.render_markdown("## Section\n")
    assert "<h2>Section</h2>" in out


def test_ac8_headings_never_skip_a_level_under_the_page_title():
    """The page <h1> is the note title, so note headings start at <h2>."""
    out = site_mod.render_markdown("# Top\n\n## Sub\n\n### Deep\n")
    assert "<h2>Top</h2>" in out and "<h2>Sub</h2>" in out and "<h3>Deep</h3>" in out


def test_ac8_bullet_and_ordered_lists_render():
    assert "<ul><li>a</li><li>b</li></ul>" in site_mod.render_markdown("- a\n- b\n")
    assert "<ol><li>x</li></ol>" in site_mod.render_markdown("1. x\n")


def test_ac8_tables_render_with_header_and_body():
    out = site_mod.render_markdown("| A | B |\n|---|---|\n| 1 | 2 |\n")
    assert "<th>A</th>" in out and "<td>1</td>" in out
    assert "<tr><td>---</td>" not in out, "separator row leaked into the body"


def test_ac8_blockquote_and_fenced_code_render():
    assert "<blockquote>" in site_mod.render_markdown("> hi\n")
    out = site_mod.render_markdown("```python\nx = 1\n```\n")
    assert '<pre class="lang-python"><code>x = 1</code></pre>' in out


def test_ac8_inline_code_bold_italic_and_links_render():
    out = site_mod.render_markdown("`c` **b** *i* _j_ [t](u)\n")
    assert "<code>c</code>" in out
    assert "<strong>b</strong>" in out
    assert out.count("<em>") == 2
    assert '<a href="u">t</a>' in out


def test_ac8_markdown_inside_code_spans_is_not_interpreted():
    out = site_mod.render_markdown("`**not bold**`\n")
    assert "<strong>" not in out
    assert "**not bold**" in out


def test_ac8_provenance_line_is_separated_from_the_paragraph():
    """The source marker follows its content with no blank line between."""
    out = site_mod.render_markdown("Clear to start\n_(source: manifest.json)_\n")
    assert '<p class="provenance">' in out
    assert "Clear to start</p>" in out


def test_ac8_frontmatter_renders_as_metadata_not_prose():
    out = site_mod.render_markdown("---\ntarget: alpha\n---\n\nBody.\n")
    assert '<dl class="frontmatter">' in out
    assert "<dt>target</dt>" in out
    assert "---" not in out


# ---------------------------------------------------------------------------
# AC9 — tables scroll in their own container
# ---------------------------------------------------------------------------

def test_ac9_tables_are_wrapped_in_a_scroll_container():
    out = site_mod.render_markdown("| A |\n|---|\n| 1 |\n")
    assert '<div class="table-wrap">' in out


def test_ac9_scroll_container_has_overflow_x_and_body_does_not():
    assert ".table-wrap { overflow-x: auto;" in site_mod.CSS
    assert "body { overflow-x" not in site_mod.CSS


# ---------------------------------------------------------------------------
# AC10 — wikilinks
# ---------------------------------------------------------------------------

def test_ac10_wikilink_becomes_a_working_relative_link(built):
    out, _ = built
    page = read(out, "notes/ideas/an-idea.html")
    assert '<a href="../projects/alpha/atlas/alfa.html">alfa</a>' in page


def test_ac10_unresolvable_wikilink_is_plain_text_not_a_dead_link(built):
    out, _ = built
    page = read(out, "notes/ideas/an-idea.html")
    assert 'class="wikilink-unresolved"' in page
    assert '<a href="nope' not in page


def test_ac10_directory_wikilink_resolves_to_the_projects_situation(built):
    out, _ = built
    page = read(out, "notes/index.html")
    assert 'href="projects/alpha/situation.html"' in page


def test_ac10_live_vault_has_no_unresolved_wikilinks(tmp_path):
    """lint guarantees resolution; the site must agree with it."""
    out = tmp_path / "site"
    site_mod.generate_site(VAULT, out)
    unresolved = set()
    for page in out.rglob("*.html"):
        unresolved |= set(re.findall(r'title="unresolved: ([^"]+)"', page.read_text()))
    assert unresolved == set(), f"unresolved wikilinks: {sorted(unresolved)}"


# ---------------------------------------------------------------------------
# AC11 / AC12 / AC13 — sentinels, unsupported content, escaping
# ---------------------------------------------------------------------------

def test_ac11_sentinel_comments_are_not_visible(built):
    out, _ = built
    page = read(out, "notes/map.html")
    assert "BEGIN MACHINE" not in page
    assert "<!--" not in page


def test_ac12_unsupported_construct_is_escaped_not_dropped():
    out = site_mod.render_markdown("Text with ~~strike~~ and | pipe.\n")
    assert "~~strike~~" in out, "unsupported syntax must survive as plain text"


def test_ac13_script_tag_in_a_note_is_escaped(built, mini_vault, tmp_path):
    (mini_vault / "projects" / "beta" / "situation.md").write_text(
        "# beta\n\n<script>alert(1)</script>\n"
    )
    out = tmp_path / "site2"
    site_mod.generate_site(mini_vault, out)
    page = read(out, "notes/projects/beta/situation.html")
    assert "&lt;script&gt;" in page
    assert "<script>alert(1)</script>" not in page


def test_ac13_html_in_a_table_cell_does_not_break_the_table():
    out = site_mod.render_markdown("| A |\n|---|\n| <b>x</b> |\n")
    assert "&lt;b&gt;x&lt;/b&gt;" in out


# ---------------------------------------------------------------------------
# AC14 / AC15 — theming and responsive
# ---------------------------------------------------------------------------

def test_ac14_light_palette_defined_on_bare_root():
    root = site_mod.CSS.split("@media")[0]
    for token in ("--bg", "--surface", "--border", "--text", "--accent", "--code-bg"):
        assert f"{token}:" in root, f"{token} not defined on bare :root"


def test_ac14_dark_palette_overrides_under_prefers_color_scheme():
    assert "@media (prefers-color-scheme: dark)" in site_mod.CSS
    dark = site_mod.CSS.split("@media (prefers-color-scheme: dark)")[1]
    for token in ("--bg", "--text", "--accent"):
        assert f"{token}:" in dark


def test_ac15_narrow_viewport_collapses_the_sidebar():
    assert "@media (max-width: 720px)" in site_mod.CSS
    narrow = site_mod.CSS.split("@media (max-width: 720px)")[1]
    assert ".layout { display: block; }" in narrow


def test_ac15_pages_declare_a_responsive_viewport(built):
    out, _ = built
    assert 'name="viewport"' in read(out, "index.html")


# ---------------------------------------------------------------------------
# AC16 — idempotency
# ---------------------------------------------------------------------------

def test_ac16_regeneration_is_byte_identical(mini_vault, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    site_mod.generate_site(mini_vault, a)
    site_mod.generate_site(mini_vault, b)
    for page in sorted(a.rglob("*.html")):
        rel = page.relative_to(a)
        assert page.read_bytes() == (b / rel).read_bytes(), f"{rel} differs between runs"


def test_ac16_rerunning_into_an_existing_dir_is_stable(mini_vault, tmp_path):
    out = tmp_path / "site"
    site_mod.generate_site(mini_vault, out)
    first = {p.relative_to(out): p.read_bytes() for p in sorted(out.rglob("*.html"))}
    site_mod.generate_site(mini_vault, out)
    second = {p.relative_to(out): p.read_bytes() for p in sorted(out.rglob("*.html"))}
    assert first == second


# ---------------------------------------------------------------------------
# AC17 / AC18 — titles, CLI, docs, gitignore
# ---------------------------------------------------------------------------

def test_page_title_names_note_and_project(built):
    out, _ = built
    assert "<title>situation — alpha — lookout</title>" in read(
        out, "notes/projects/alpha/situation.html"
    )


def test_breadcrumb_shows_the_vault_path(built):
    out, _ = built
    page = read(out, "notes/projects/alpha/situation.html")
    assert '<div class="crumb">projects / alpha / situation</div>' in page


def test_cli_runs_and_reports_the_page_count(mini_vault, tmp_path):
    out = tmp_path / "cli-site"
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "render_site.py"),
         "--vault", str(mini_vault), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "wrote" in result.stdout
    assert (out / "index.html").exists()


def test_cli_exits_nonzero_on_a_missing_vault(tmp_path):
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "render_site.py"),
         "--vault", str(tmp_path / "nope"), "--out", str(tmp_path / "o")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1


def test_site_output_is_gitignored():
    assert "site/" in (REPO_ROOT / ".gitignore").read_text().splitlines()


def test_design_md_documents_the_token_set():
    """DESIGN.md previously claimed lookout had no user interface."""
    text = (REPO_ROOT / "DESIGN.md").read_text()
    assert "no user interface" not in text
    for token in ("--bg", "--surface", "--text", "--accent"):
        assert token in text


def test_pipeline_doc_lists_site_as_a_manual_command():
    text = (REPO_ROOT / "docs" / "pipeline.md").read_text()
    assert "render_site.py" in text

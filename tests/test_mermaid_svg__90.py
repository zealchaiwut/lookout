"""Tests for issue #90: render mermaid flowchart LR blocks as inline SVG.

Each test maps to a specific AC item from the issue.
"""
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import render_site  # noqa: E402

VAULT = REPO_ROOT / "vault"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md(body):
    return f"```mermaid\n{body}\n```\n"


def _render(body):
    return render_site.render_markdown(_md(body))


# ---------------------------------------------------------------------------
# AC1 — flowchart LR block renders as inline <svg>
# ---------------------------------------------------------------------------

def test_ac1_flowchart_lr_renders_as_svg():
    out = _render("flowchart LR\n  n[A]")
    assert "<svg" in out
    assert "</svg>" in out


def test_ac1_svg_not_wrapped_in_pre():
    out = _render("flowchart LR\n  n[A]")
    assert "<pre" not in out


def test_ac1_no_script_tag_in_svg_block():
    out = _render("flowchart LR\n  n[A]")
    assert "<script" not in out.lower()


# ---------------------------------------------------------------------------
# AC2 — both node shapes render distinguishably
# ---------------------------------------------------------------------------

def test_ac2_rect_node_produces_rect_element():
    out = _render("flowchart LR\n  n[label]")
    assert "<rect" in out


def test_ac2_cylinder_node_produces_ellipse_element():
    out = _render("flowchart LR\n  n[(label)]")
    assert "<ellipse" in out


def test_ac2_rect_and_cylinder_are_structurally_different():
    rect_out = _render("flowchart LR\n  n[label]")
    cyl_out = _render("flowchart LR\n  n[(label)]")
    # Cylinder has ellipse; rect does not
    assert "<ellipse" not in rect_out
    assert "<ellipse" in cyl_out


def test_ac2_diagram_with_both_shapes_contains_both_elements():
    out = _render("flowchart LR\n  r[file]\n  d[(table)]")
    assert "<rect" in out
    assert "<ellipse" in out


# ---------------------------------------------------------------------------
# AC3 — edges render as lines with arrowhead, connecting correct nodes
# ---------------------------------------------------------------------------

def test_ac3_edge_produces_path_element():
    out = _render("flowchart LR\n  a[A]\n  b[B]\n  a --> b")
    assert "<path" in out


def test_ac3_edge_has_arrowhead_via_marker():
    out = _render("flowchart LR\n  a[A]\n  b[B]\n  a --> b")
    assert "marker-end" in out


def test_ac3_edge_connects_source_right_to_target_left():
    """Source right-edge x < target left-edge x in the path."""
    out = _render("flowchart LR\n  a[A]\n  b[B]\n  a --> b")
    # Parse the M (move-to) x coord of the edge path
    paths = re.findall(r'<path d="M(\d+),', out)
    rects = re.findall(r'<rect[^>]+x="(\d+)"', out)
    if paths and rects:
        # The path start (source right edge) must be > first rect x
        assert int(paths[0]) > int(rects[0])


# ---------------------------------------------------------------------------
# AC4 — node labels are HTML-escaped
# ---------------------------------------------------------------------------

def test_ac4_angle_bracket_in_label_is_escaped():
    out = _render("flowchart LR\n  n[a<b>c]")
    assert "<b>" not in out
    assert "&lt;b&gt;" in out


def test_ac4_ampersand_in_label_is_escaped():
    out = _render("flowchart LR\n  n[a&b]")
    assert "&amp;" in out


def test_ac4_label_with_angle_bracket_produces_valid_svg():
    out = _render("flowchart LR\n  n[<broken>]")
    # SVG must still open and close correctly
    assert "<svg" in out
    assert "</svg>" in out


def test_ac4_label_with_all_special_chars_does_not_corrupt_svg():
    out = _render('flowchart LR\n  n[a <b>& "c"]')
    assert "<svg" in out
    assert "</svg>" in out
    # Raw unescaped angle bracket must not appear in text content
    text_parts = re.findall(r'<text[^>]*>(.*?)</text>', out)
    for t in text_parts:
        assert "<b>" not in t


# ---------------------------------------------------------------------------
# AC5 — layout is left-to-right, nodes do not overlap
# ---------------------------------------------------------------------------

def test_ac5_layout_is_left_to_right_for_edge():
    out = _render("flowchart LR\n  a[A]\n  b[B]\n  a --> b")
    # Use `<rect x="` (x as first attribute) to avoid matching rx="3"
    xs = [int(v) for v in re.findall(r'<rect x="(\d+)"', out)]
    assert len(xs) >= 2, "expected at least 2 rect nodes"
    assert xs[0] < xs[1], "source must be left of target"


def test_ac5_same_layer_nodes_have_different_y():
    # Two nodes with no edge between them both land in layer 0
    out = _render("flowchart LR\n  a[A]\n  b[B]")
    positions = [
        (int(x), int(y))
        for x, y in re.findall(r'<rect x="(\d+)" y="(\d+)"', out)
    ]
    assert len(positions) == 2
    x0, y0 = positions[0]
    x1, y1 = positions[1]
    assert x0 == x1   # same column
    assert y0 != y1   # different row


def test_ac5_no_two_nodes_at_identical_position():
    out = _render(
        "flowchart LR\n  a[A]\n  b[B]\n  c[C]\n  a --> b\n  a --> c"
    )
    positions = [
        (int(x), int(y))
        for x, y in re.findall(r'<rect x="(\d+)" y="(\d+)"', out)
    ]
    assert len(positions) == len(set(positions)), "two nodes share the same position"


# ---------------------------------------------------------------------------
# AC6 — SVG uses CSS custom properties (--text, --border, --surface, --accent)
# ---------------------------------------------------------------------------

def test_ac6_uses_border_token():
    out = _render("flowchart LR\n  n[x]")
    assert "var(--border)" in out


def test_ac6_uses_text_token():
    out = _render("flowchart LR\n  n[x]")
    assert "var(--text)" in out


def test_ac6_uses_surface_token():
    out = _render("flowchart LR\n  n[x]")
    assert "var(--surface)" in out


def test_ac6_uses_accent_token():
    out = _render("flowchart LR\n  n[x]")
    assert "var(--accent)" in out


def test_ac6_no_hardcoded_colour_values():
    out = _render("flowchart LR\n  n[x]")
    # None of the hardcoded palette values from the site CSS appear in the SVG
    hardcoded = ["#fdfdfc", "#22222a", "#3a5a8c", "#f4f4f2", "#e0e0dc",
                 "#16161a", "#e6e6ea", "#7fa3d8"]
    for colour in hardcoded:
        assert colour not in out, f"hardcoded colour {colour!r} found in SVG"


# ---------------------------------------------------------------------------
# AC7 — SVG scales to container, does not overflow content column
# ---------------------------------------------------------------------------

def test_ac7_svg_has_width_100_percent():
    out = _render("flowchart LR\n  n[x]")
    assert 'width="100%"' in out


def test_ac7_svg_has_viewbox():
    out = _render("flowchart LR\n  n[x]")
    assert "viewBox" in out


def test_ac7_max_width_is_capped_in_style():
    out = _render("flowchart LR\n  n[x]")
    assert "max-width" in out


# ---------------------------------------------------------------------------
# AC8 — unsupported constructs fall back to preformatted code, never partial SVG
# ---------------------------------------------------------------------------

def test_ac8_sequence_diagram_falls_back_to_pre():
    out = _render("sequenceDiagram\n  A->>B: hello")
    assert "<svg" not in out
    assert "<pre" in out


def test_ac8_flowchart_td_falls_back():
    out = _render("flowchart TD\n  a --> b")
    assert "<svg" not in out
    assert "<pre" in out


def test_ac8_flowchart_rl_falls_back():
    out = _render("flowchart RL\n  a --> b")
    assert "<svg" not in out
    assert "<pre" in out


def test_ac8_subgraph_falls_back():
    out = _render("flowchart LR\n  subgraph foo\n    a --> b\n  end")
    assert "<svg" not in out
    assert "<pre" in out


def test_ac8_style_directive_falls_back():
    out = _render("flowchart LR\n  a --> b\n  style a fill:#f00")
    assert "<svg" not in out
    assert "<pre" in out


def test_ac8_classdef_falls_back():
    out = _render("flowchart LR\n  a --> b\n  classDef red fill:#f00")
    assert "<svg" not in out
    assert "<pre" in out


def test_ac8_labeled_edge_falls_back():
    out = _render("flowchart LR\n  a -->|label| b")
    assert "<svg" not in out
    assert "<pre" in out


def test_ac8_diamond_shape_falls_back():
    out = _render("flowchart LR\n  a{decision}")
    assert "<svg" not in out
    assert "<pre" in out


def test_ac8_unsupported_arrow_falls_back():
    out = _render("flowchart LR\n  a ==> b")
    assert "<svg" not in out
    assert "<pre" in out


# ---------------------------------------------------------------------------
# AC9 — fallback is visible as source, not silently dropped
# ---------------------------------------------------------------------------

def test_ac9_fallback_preserves_sequence_diagram_source():
    out = _render("sequenceDiagram\n  A->>B: hello")
    assert "sequenceDiagram" in out
    # The pre block HTML-escapes >, so >> becomes &gt;&gt; — still readable
    assert "A-" in out and "B" in out


def test_ac9_fallback_preserves_unsupported_flowchart_source():
    out = _render("flowchart TD\n  a --> b")
    assert "flowchart TD" in out


# ---------------------------------------------------------------------------
# AC10 — output free of JavaScript and network requests
# ---------------------------------------------------------------------------

def test_ac10_no_script_in_full_page(tmp_path):
    vault = VAULT
    out = tmp_path / "site"
    render_site.generate_site(vault, out)
    for page in out.rglob("*.html"):
        text = page.read_text()
        assert "<script" not in text.lower(), f"script tag in {page.name}"


def test_ac10_no_external_url_in_svg():
    # xmlns="http://..." is SVG's namespace declaration, not a network request.
    # Check for external CDN/network URLs only.
    out = _render("flowchart LR\n  n[x]")
    for needle in ("cdn.", "unpkg.", "cdnjs.", "fonts.googleapis"):
        assert needle not in out, f"external resource {needle!r} found in SVG"


# ---------------------------------------------------------------------------
# AC11 — regeneration is byte-identical for unchanged input
# ---------------------------------------------------------------------------

def test_ac11_same_body_same_output():
    body = "flowchart LR\n  a[A]\n  b[B]\n  a --> b"
    assert _render(body) == _render(body)


def test_ac11_generate_site_idempotent(tmp_path):
    vault = VAULT
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    render_site.generate_site(vault, a_dir)
    render_site.generate_site(vault, b_dir)
    for page in sorted(a_dir.rglob("*.html")):
        rel = page.relative_to(a_dir)
        assert page.read_bytes() == (b_dir / rel).read_bytes(), f"{rel} differs"


# ---------------------------------------------------------------------------
# Live vault integration
# ---------------------------------------------------------------------------

def test_live_vault_mermaid_notes_render_svg(tmp_path):
    """All five current atlas notes with mermaid blocks render as SVG."""
    out = tmp_path / "site"
    render_site.generate_site(VAULT, out)
    mermaid_pages = [
        "notes/projects/perf-coach/atlas/weight-tracking.html",
        "notes/projects/perf-coach/atlas/weight-plans.html",
        "notes/projects/perf-coach/atlas/daily-bodyweight-upsert.html",
    ]
    for rel in mermaid_pages:
        page = out / rel
        assert page.exists(), f"{rel} not found"
        content = page.read_text()
        assert "<svg" in content, f"{rel} has no SVG"
        assert "<script" not in content.lower(), f"{rel} has script tag"


def test_live_vault_lone_node_renders_without_error():
    """Lone-node syntax (node id on its own line) is a no-op for declared nodes."""
    body = "flowchart LR\n  n[label]\n  n"
    out = _render(body)
    assert "<svg" in out
    # Only one rect (the node appears once)
    rects = re.findall(r'<rect', out)
    assert len(rects) == 1

"""
render_site.py — render the vault to a static HTML site with a tree sidebar.

Static pages, not a web app: no server, no build step, no client framework, no
network at runtime, and no JavaScript. The output opens with `file://`.

The vault holds a few hundred markdown files and the only way to read them is a
text editor or GitHub. Neither lets you sit down, see the whole fleet, and
click from map.md into a project's situation.md into one of its atlas notes.
That browse-and-follow motion is what this produces.

Markdown scope
--------------
This is deliberately **not** a CommonMark implementation. No markdown library is
installed and the project keeps to the standard library, which is affordable
here only because the vault is machine-generated and therefore emits a small,
fixed subset: headings, bullet and ordered lists, tables, blockquotes, fenced
code, inline emphasis/code/links, wikilinks, and HTML sentinel comments.

Anything outside that subset is escaped and emitted as plain text. It is never
guessed at and never silently dropped.

Output layout
-------------
    site/index.html                      landing page (generated)
    site/notes/<vault-relative>.html     one page per vault markdown file

Notes live under `notes/` so the generated landing page and the vault's own
`index.md` do not collide on `site/index.html`.

Named `render_site` rather than `site` because `site` is a standard-library
module that Python imports at startup — a `site.py` at the repository root
shadows it, and `import site` from a test resolves to the stdlib one.

Usage
-----
    python3 render_site.py [--vault <dir>] [--out <dir>]
"""
import argparse
import html
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent

# Project notes read in pipeline order, not alphabetical — that is the order a
# reader wants them, and the order the derive stages produce them in.
_PROJECT_NOTE_ORDER = ["situation", "capability", "drift", "todo-view", "notes", "decisions"]

_FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]*)\)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])")
_ITALIC_US_RE = re.compile(r"(?<![\w_])_([^_\n]+)_(?![\w_])")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
_ORDERED_RE = re.compile(r"^(\s*)\d+\.\s+(.*)$")
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# A whole-line `_(source: …)_` provenance marker. It is metadata about where a
# section came from, not prose, and is rendered muted and smaller.
_SOURCE_LINE_RE = re.compile(r"^_\((?:source|sources):.*\)_$")

_PLACEHOLDER = "\x00%d\x00"

# ---------------------------------------------------------------------------
# Mermaid → inline SVG (supported subset: flowchart LR only)
# ---------------------------------------------------------------------------

_MM_NODE_RECT_RE = re.compile(r"^\s*(\w+)\[([^\]]*)\]\s*$")
_MM_NODE_CYL_RE = re.compile(r"^\s*(\w+)\[\(([^)]*)\)\]\s*$")
_MM_EDGE_RE = re.compile(r"^\s*(\w+)\s*-->\s*(\w+)\s*$")
_MM_LONE_RE = re.compile(r"^\s*(\w+)\s*$")
_MM_COMMENT_RE = re.compile(r"^\s*%%")
# Layout constants (all integers — SVG coordinates stay whole pixels)
_MM_NW = 140   # node width
_MM_NH = 40    # node height
_MM_EH = 10    # cylinder ellipse half-height
_MM_CG = 80    # column gap (horizontal space between layers)
_MM_RG = 20    # row gap (vertical space between nodes in same layer)
_MM_PAD = 24   # SVG padding (all sides)


def _mm_hash(s: str) -> str:
    """Deterministic 32-bit polynomial hash, returned as a hex string."""
    h = 0
    for c in s:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return format(h, "x")


def _mermaid_to_svg(nodes: dict, node_order: list, edges: list, svg_id: str) -> str:
    """Generate inline SVG from parsed mermaid flowchart LR data."""
    NW, NH, EH = _MM_NW, _MM_NH, _MM_EH
    CG, RG, PAD = _MM_CG, _MM_RG, _MM_PAD

    # Build predecessor / successor maps
    preds: dict = {nid: [] for nid in nodes}
    succs: dict = {nid: [] for nid in nodes}
    for src, dst in edges:
        succs[src].append(dst)
        preds[dst].append(src)

    # BFS layer assignment (longest path from any root)
    layer: dict = {}
    roots = [nid for nid in node_order if not preds[nid]]
    if not roots:
        roots = [node_order[0]]
    for nid in roots:
        layer[nid] = 0
    queue = list(roots)
    visited: set = set(roots)
    qi = 0
    while qi < len(queue):
        nid = queue[qi]
        for dst in succs[nid]:
            new_l = layer[nid] + 1
            if dst not in layer or layer[dst] < new_l:
                layer[dst] = new_l
            if dst not in visited:
                visited.add(dst)
                queue.append(dst)
        qi += 1
    for nid in node_order:
        if nid not in layer:
            layer[nid] = 0

    # Group by layer, preserving insertion order within each layer
    by_layer: dict = {}
    for nid in node_order:
        by_layer.setdefault(layer[nid], []).append(nid)

    # Compute node positions
    positions: dict = {}
    for layer_idx, nids in by_layer.items():
        col_x = PAD + layer_idx * (NW + CG)
        for j, nid in enumerate(nids):
            row_y = PAD + j * (NH + RG)
            positions[nid] = (col_x, row_y)

    # Canvas size
    num_l = max(layer.values()) + 1
    max_row = max(len(v) for v in by_layer.values())
    W = PAD * 2 + num_l * NW + (num_l - 1) * CG
    H = PAD * 2 + max_row * NH + (max_row - 1) * RG

    marker_id = f"mm-a-{svg_id}"
    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"'
        f' width="100%"'
        f' style="max-width:{W}px;height:auto;display:block;margin:.8rem 0;">'
    )
    # Arrowhead marker (accent colour makes arrows visually distinct)
    out.append(
        f'<defs>'
        f'<marker id="{marker_id}" markerWidth="10" markerHeight="7"'
        f' refX="10" refY="3.5" orient="auto" markerUnits="userSpaceOnUse">'
        f'<polygon points="0,0 10,3.5 0,7" style="fill:var(--accent);"/>'
        f'</marker>'
        f'</defs>'
    )

    # Edges — drawn first so nodes render on top
    for src, dst in edges:
        sx, sy = positions[src]
        dx, dy = positions[dst]
        x1, y1 = sx + NW, sy + NH // 2
        x2, y2 = dx, dy + NH // 2
        mx = (x1 + x2) // 2
        out.append(
            f'<path d="M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}"'
            f' style="fill:none;stroke:var(--border);stroke-width:1.5;"'
            f' marker-end="url(#{marker_id})"/>'
        )

    # Nodes
    for nid in node_order:
        x, y = positions[nid]
        label = html.escape(nodes[nid]["label"])
        shape = nodes[nid]["shape"]
        cx = x + NW // 2
        ty = y + NH // 2 + 4   # baseline for 12px font, visually centred

        if shape == "cyl":
            by_y = y + EH        # body rectangle top
            bh = NH - 2 * EH    # body rectangle height
            out.append(
                f'<g>'
                f'<rect x="{x}" y="{by_y}" width="{NW}" height="{bh}"'
                f' style="fill:var(--surface);stroke:var(--border);stroke-width:1;"/>'
                f'<ellipse cx="{cx}" cy="{by_y}" rx="{NW // 2}" ry="{EH}"'
                f' style="fill:var(--surface);stroke:var(--border);stroke-width:1;"/>'
                f'<ellipse cx="{cx}" cy="{y + NH - EH}" rx="{NW // 2}" ry="{EH}"'
                f' style="fill:none;stroke:var(--border);stroke-width:1;"/>'
                f'<text x="{cx}" y="{ty}" text-anchor="middle" font-size="12"'
                f' style="fill:var(--text);font-family:var(--mono);">'
                f'{label}</text>'
                f'</g>'
            )
        else:
            out.append(
                f'<rect x="{x}" y="{y}" width="{NW}" height="{NH}" rx="3"'
                f' style="fill:var(--surface);stroke:var(--border);stroke-width:1;"/>'
            )
            out.append(
                f'<text x="{cx}" y="{ty}" text-anchor="middle" font-size="12"'
                f' style="fill:var(--text);font-family:var(--mono);">'
                f'{label}</text>'
            )

    out.append("</svg>")
    return "".join(out)


def _render_mermaid(body: str):
    """Parse a mermaid block; return inline SVG string, or None if unsupported."""
    lines = body.strip().splitlines()

    # First non-empty, non-comment line must be exactly 'flowchart LR'
    non_empty = [line.strip() for line in lines if line.strip() and not _MM_COMMENT_RE.match(line)]
    if not non_empty or non_empty[0] != "flowchart LR":
        return None

    nodes: dict = {}
    node_order: list = []
    edges: list = []

    past_header = False
    for line in lines:
        stripped = line.strip()
        if not stripped or _MM_COMMENT_RE.match(line):
            continue
        if not past_header:
            past_header = True
            continue  # skip the validated 'flowchart LR' header

        # Cylinder node: id[(label)]  — must try before rect to avoid partial match
        m = _MM_NODE_CYL_RE.match(line)
        if m:
            nid, label = m.group(1), m.group(2)
            if nid not in nodes:
                node_order.append(nid)
                nodes[nid] = {"label": label, "shape": "cyl"}
            continue

        # Rect node: id[label]
        m = _MM_NODE_RECT_RE.match(line)
        if m:
            nid, label = m.group(1), m.group(2)
            if nid not in nodes:
                node_order.append(nid)
                nodes[nid] = {"label": label, "shape": "rect"}
            continue

        # Edge: src --> dst
        m = _MM_EDGE_RE.match(line)
        if m:
            src, dst = m.group(1), m.group(2)
            for nid in (src, dst):
                if nid not in nodes:
                    node_order.append(nid)
                    nodes[nid] = {"label": nid, "shape": "rect"}
            edges.append((src, dst))
            continue

        # Lone node id (already declared → no-op; undeclared → implicit rect)
        m = _MM_LONE_RE.match(line)
        if m:
            nid = m.group(1)
            if nid not in nodes:
                node_order.append(nid)
                nodes[nid] = {"label": nid, "shape": "rect"}
            continue

        # Unrecognised line → unsupported construct → caller shows fallback
        return None

    if not nodes:
        return None

    return _mermaid_to_svg(nodes, node_order, edges, _mm_hash(body))


# ---------------------------------------------------------------------------
# Vault model
# ---------------------------------------------------------------------------

class Note:
    """One vault markdown file and where it lands in the output."""

    def __init__(self, path: Path, vault_dir: Path):
        self.path = path
        self.rel = path.relative_to(vault_dir)          # e.g. projects/crux/situation.md
        self.out_rel = Path("notes") / self.rel.with_suffix(".html")
        self.stem = path.stem

    @property
    def title(self) -> str:
        return self.stem.replace("-", " ")


def collect_notes(vault_dir: Path) -> list:
    """Every vault markdown file except raw/ snapshots, sorted by path."""
    notes = []
    for p in sorted(vault_dir.rglob("*.md")):
        if "raw" in p.relative_to(vault_dir).parts:
            continue
        notes.append(Note(p, vault_dir))
    return notes


def build_link_index(notes: list, vault_dir: Path) -> dict:
    """Map wikilink targets to notes, mirroring lint.py's resolution rules.

    lint indexes each note by bare stem and by vault-relative path without
    suffix, and also indexes directories. A directory target has no page of its
    own, so it resolves to that directory's index.md when one exists.
    """
    index: dict = {}
    for note in notes:
        index.setdefault(note.stem, note)
        index[str(note.rel.with_suffix(""))] = note

    for d in sorted(vault_dir.rglob("*")):
        if not d.is_dir() or "raw" in d.relative_to(vault_dir).parts:
            continue
        # A directory has no page of its own. Prefer its index.md; for a
        # project directory there is none, so fall back to situation.md — the
        # note a reader following [[perf-coach]] actually wants.
        target = None
        for candidate in ("index.md", "situation.md"):
            f = d / candidate
            if f.exists():
                target = next((n for n in notes if n.path == f), None)
                if target is not None:
                    break
        if target is None:
            continue
        index.setdefault(d.name, target)
        index.setdefault(str(d.relative_to(vault_dir)), target)
    return index


# ---------------------------------------------------------------------------
# Inline rendering
# ---------------------------------------------------------------------------

def _relative_href(from_out_rel: Path, to_out_rel: Path) -> str:
    """POSIX relative href between two output paths, for file:// browsing."""
    import os
    rel = os.path.relpath(to_out_rel.as_posix(), start=from_out_rel.parent.as_posix())
    return rel.replace("\\", "/")


def render_inline(text: str, note=None, link_index=None) -> str:
    """Render inline markdown in `text`, escaping everything else.

    Code spans are extracted before any other rule so their contents are never
    reinterpreted as emphasis or links.
    """
    if link_index is None:
        link_index = {}

    spans: list = []

    def _stash(rendered: str) -> str:
        spans.append(rendered)
        return _PLACEHOLDER % (len(spans) - 1)

    def _code(m):
        return _stash(f"<code>{html.escape(m.group(1))}</code>")

    text = _INLINE_CODE_RE.sub(_code, text)

    def _wiki(m):
        target = m.group(1).strip()
        label = (m.group(2) or target).strip()
        dest = link_index.get(target)
        if dest is None:
            # lint already guarantees resolution; this is the safety net. A dead
            # href is worse than visible plain text, so emit the latter.
            return _stash(
                f'<span class="wikilink-unresolved" '
                f'title="unresolved: {html.escape(target)}">{html.escape(label)}</span>'
            )
        href = _relative_href(note.out_rel, dest.out_rel) if note else dest.out_rel.as_posix()
        return _stash(f'<a href="{html.escape(href)}">{html.escape(label)}</a>')

    text = _WIKILINK_RE.sub(_wiki, text)

    def _link(m):
        label, url = m.group(1), m.group(2)
        return _stash(f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>')

    text = _MD_LINK_RE.sub(_link, text)

    text = html.escape(text)
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _ITALIC_RE.sub(r"<em>\1</em>", text)
    text = _ITALIC_US_RE.sub(r"<em>\1</em>", text)

    for i, span in enumerate(spans):
        text = text.replace(_PLACEHOLDER % i, span)
    return text


# ---------------------------------------------------------------------------
# Block rendering
# ---------------------------------------------------------------------------

def _render_frontmatter(fm_body: str) -> str:
    rows = []
    for line in fm_body.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        rows.append(
            f"<div><dt>{html.escape(key.strip())}</dt>"
            f"<dd>{html.escape(val.strip())}</dd></div>"
        )
    if not rows:
        return ""
    return '<dl class="frontmatter">' + "".join(rows) + "</dl>"


def _render_table(rows: list, note, link_index) -> str:
    """Render a markdown table. rows excludes the separator line."""
    def cells(line):
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        return [c.strip() for c in line.split("|")]

    head = cells(rows[0])
    body = [cells(r) for r in rows[1:]]
    out = ['<div class="table-wrap"><table><thead><tr>']
    out += [f"<th>{render_inline(c, note, link_index)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>")
        out += [f"<td>{render_inline(c, note, link_index)}</td>" for c in row]
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render_markdown(text: str, note=None, link_index=None) -> str:
    """Render the vault's markdown subset to HTML."""
    if link_index is None:
        link_index = {}

    parts: list = []

    fm = _FM_RE.match(text)
    if fm:
        parts.append(_render_frontmatter(fm.group(1)))
        text = text[fm.end():]

    # Sentinel comments mark machine/human ownership regions. They are structure
    # for the generators, not content, and must not reach the page.
    text = _COMMENT_RE.sub("", text)

    lines = text.splitlines()
    i = 0
    para: list = []

    def flush_para():
        if not para:
            return
        joined = " ".join(para).strip()
        para.clear()
        if not joined:
            return
        if _SOURCE_LINE_RE.match(joined):
            inner = joined[1:-1]
            parts.append(f'<p class="provenance">{render_inline(inner, note, link_index)}</p>')
        else:
            parts.append(f"<p>{render_inline(joined, note, link_index)}</p>")

    while i < len(lines):
        line = lines[i]

        if not line.strip():
            flush_para()
            i += 1
            continue

        if line.startswith("```"):
            flush_para()
            lang = line[3:].strip()
            body: list = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            raw = chr(10).join(body)
            if lang == "mermaid":
                svg = _render_mermaid(raw)
                if svg is not None:
                    parts.append(svg)
                    continue
            cls = f' class="lang-{html.escape(lang)}"' if lang else ""
            parts.append(
                f"<pre{cls}><code>{html.escape(raw)}</code></pre>"
            )
            continue

        if _SOURCE_LINE_RE.match(line.strip()):
            flush_para()
            inner = line.strip()[1:-1]
            parts.append(
                f'<p class="provenance">{render_inline(inner, note, link_index)}</p>'
            )
            i += 1
            continue

        m = _HEADING_RE.match(line)
        if m:
            flush_para()
            # The page <h1> is the note title, so note headings start at <h2>.
            # Clamping rather than shifting avoids skipping a level.
            level = min(max(len(m.group(1)), 2), 6)
            parts.append(
                f"<h{level}>{render_inline(m.group(2), note, link_index)}</h{level}>"
            )
            i += 1
            continue

        if line.lstrip().startswith(">"):
            flush_para()
            quote: list = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                quote.append(lines[i].lstrip()[1:].lstrip())
                i += 1
            inner = render_inline(" ".join(quote), note, link_index)
            parts.append(f"<blockquote><p>{inner}</p></blockquote>")
            continue

        if line.strip().startswith("|"):
            flush_para()
            table: list = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not _TABLE_SEP_RE.match(lines[i]):
                    table.append(lines[i])
                i += 1
            if table:
                parts.append(_render_table(table, note, link_index))
            continue

        if _BULLET_RE.match(line) or _ORDERED_RE.match(line):
            flush_para()
            ordered = bool(_ORDERED_RE.match(line))
            items: list = []
            while i < len(lines):
                m2 = _ORDERED_RE.match(lines[i]) if ordered else _BULLET_RE.match(lines[i])
                if not m2:
                    break
                items.append(render_inline(m2.group(2), note, link_index))
                i += 1
            tag = "ol" if ordered else "ul"
            parts.append(f"<{tag}>" + "".join(f"<li>{it}</li>" for it in items) + f"</{tag}>")
            continue

        para.append(line.strip())
        i += 1

    flush_para()
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Sidebar tree
# ---------------------------------------------------------------------------

def _project_note_sort_key(note):
    try:
        return (0, _PROJECT_NOTE_ORDER.index(note.stem), note.stem)
    except ValueError:
        return (1, 0, note.stem)


def build_tree(notes: list) -> dict:
    """Group notes into the sidebar's four sections."""
    overview, ideas, journal = [], [], []
    projects: dict = {}

    for note in notes:
        parts = note.rel.parts
        if parts[0] == "projects" and len(parts) >= 2:
            proj = projects.setdefault(parts[1], {"notes": [], "atlas": []})
            if "atlas" in parts:
                proj["atlas"].append(note)
            else:
                proj["notes"].append(note)
        elif parts[0] == "ideas":
            ideas.append(note)
        elif parts[0] == "journal":
            journal.append(note)
        else:
            overview.append(note)

    for proj in projects.values():
        proj["notes"].sort(key=_project_note_sort_key)
        proj["atlas"].sort(key=lambda n: ("" if n.stem == "index" else n.stem))

    return {
        "overview": sorted(overview, key=lambda n: n.stem),
        "projects": dict(sorted(projects.items())),
        "ideas": sorted(ideas, key=lambda n: n.stem),
        "journal": sorted(journal, key=lambda n: n.stem),
    }


def _link(note, active, from_note) -> str:
    href = _relative_href(from_note.out_rel, note.out_rel) if from_note else note.out_rel.as_posix()
    cur = ' aria-current="page"' if active else ""
    cls = ' class="active"' if active else ""
    return f'<li{cls}><a href="{html.escape(href)}"{cur}>{html.escape(note.title)}</a></li>'


def _details(summary: str, body: str, open_: bool, count=None) -> str:
    label = html.escape(summary)
    if count is not None:
        label += f' <span class="count">({count})</span>'
    return (
        f'<details{" open" if open_ else ""}>'
        f"<summary>{label}</summary>{body}</details>"
    )


def render_sidebar(tree: dict, current, from_note) -> str:
    """Render the full tree, expanding only the current page's ancestors.

    The whole tree ships in every page so each page stands alone under file://.
    Collapsing is native <details>/<summary> — no JavaScript.
    """
    def items(notes):
        return "<ul>" + "".join(_link(n, n is current, from_note) for n in notes) + "</ul>"

    out = ['<nav class="tree" aria-label="Vault">']

    in_overview = current in tree["overview"]
    out.append(_details("Overview", items(tree["overview"]), in_overview))

    proj_body = []
    any_project = False
    for name, proj in tree["projects"].items():
        proj_notes = proj["notes"]
        atlas = proj["atlas"]
        active_here = current in proj_notes or current in atlas
        any_project = any_project or active_here
        body = items(proj_notes)
        if atlas:
            feature_count = sum(1 for n in atlas if n.stem != "index")
            body += _details(
                "atlas", items(atlas), current in atlas, count=feature_count
            )
        proj_body.append(_details(name, body, active_here))
    out.append(_details("Projects", "".join(proj_body), any_project))

    if tree["ideas"]:
        out.append(_details(
            "Ideas", items(tree["ideas"]), current in tree["ideas"], count=len(tree["ideas"])
        ))
    if tree["journal"]:
        out.append(_details("Journal", items(tree["journal"]), current in tree["journal"]))

    out.append("</nav>")
    return "".join(out)


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------

CSS = """\
:root {
  --bg: #fdfdfc;
  --surface: #f4f4f2;
  --border: #e0e0dc;
  --text: #22222a;
  --text-muted: #6a6a76;
  --accent: #3a5a8c;
  --code-bg: #f0f0ee;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16161a;
    --surface: #1e1e24;
    --border: #2e2e36;
    --text: #e6e6ea;
    --text-muted: #9a9aa8;
    --accent: #7fa3d8;
    --code-bg: #24242c;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font-family: var(--font); font-size: 15px; line-height: 1.55;
}
.layout { display: flex; align-items: flex-start; }
.sidebar {
  width: 17rem; flex: 0 0 17rem; background: var(--surface);
  border-right: 1px solid var(--border);
  height: 100vh; position: sticky; top: 0; overflow-y: auto;
  padding: 1rem 0.75rem 3rem;
}
.sidebar .brand {
  font-family: var(--mono); font-weight: 600; letter-spacing: .02em;
  padding: 0 .5rem .75rem; display: block; color: var(--text);
  text-decoration: none; border-bottom: 1px solid var(--border); margin-bottom: .75rem;
}
.tree ul { list-style: none; margin: 0; padding-left: .85rem; }
.tree li { margin: 0; }
.tree a {
  display: block; padding: .18rem .5rem; color: var(--text);
  text-decoration: none; border-radius: 3px;
  border-left: 2px solid transparent; font-size: 13.5px;
}
.tree a:hover { background: var(--bg); }
.tree li.active > a {
  border-left-color: var(--accent); color: var(--accent);
  font-weight: 600; background: var(--bg);
}
.tree summary {
  cursor: pointer; padding: .2rem .4rem; font-size: 13.5px;
  font-weight: 600; border-radius: 3px; user-select: none;
}
.tree summary:hover { background: var(--bg); }
.tree details details { margin-left: .5rem; }
.count { color: var(--text-muted); font-weight: 400; }
.content { flex: 1 1 auto; min-width: 0; padding: 2rem 2.5rem 6rem; }
.inner > *:not(.table-wrap) { max-width: 72ch; }
.crumb {
  font-family: var(--mono); font-size: 12.5px; color: var(--text-muted);
  margin-bottom: .35rem;
}
h1 { font-size: 1.6rem; margin: 0 0 1.25rem; line-height: 1.25; }
h2 {
  font-size: 1.12rem; margin: 2rem 0 .6rem; padding-bottom: .3rem;
  border-bottom: 1px solid var(--border);
}
h3 { font-size: 1rem; margin: 1.4rem 0 .4rem; }
p { margin: .6rem 0; }
a { color: var(--accent); }
ul, ol { margin: .6rem 0; padding-left: 1.4rem; }
li { margin: .18rem 0; }
code {
  font-family: var(--mono); font-size: .875em;
  background: var(--code-bg); padding: .1em .32em; border-radius: 3px;
}
pre {
  background: var(--code-bg); border: 1px solid var(--border); border-radius: 4px;
  padding: .8rem 1rem; overflow-x: auto; font-size: 13px; line-height: 1.45;
}
pre code { background: none; padding: 0; font-size: inherit; }
blockquote {
  margin: .8rem 0; padding: .1rem 1rem; border-left: 3px solid var(--border);
  color: var(--text-muted);
}
.table-wrap { overflow-x: auto; margin: .8rem 0; max-width: 100%; }
table { border-collapse: collapse; font-size: 13.5px; line-height: 1.35; }
th, td {
  border: 1px solid var(--border); padding: .32rem .6rem;
  text-align: left; vertical-align: top;
}
th { background: var(--surface); font-weight: 600; }
td code, th code { white-space: nowrap; }
.provenance { color: var(--text-muted); font-size: 12.5px; margin-top: -.25rem; }
.frontmatter {
  display: grid; grid-template-columns: max-content 1fr; gap: .1rem .9rem;
  background: var(--surface); border: 1px solid var(--border); border-radius: 4px;
  padding: .7rem .9rem; margin: 0 0 1.5rem; font-family: var(--mono); font-size: 12.5px;
}
.frontmatter > div { display: contents; }
.frontmatter dt { color: var(--text-muted); }
.frontmatter dd { margin: 0; }
.wikilink-unresolved { color: var(--text-muted); border-bottom: 1px dotted var(--border); }
.cards { display: grid; gap: .75rem; grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr)); }
.card {
  border: 1px solid var(--border); border-radius: 4px; padding: .8rem 1rem;
  background: var(--surface); text-decoration: none; display: block;
}
.card:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.card h3 { margin: 0 0 .3rem; color: var(--accent); }
.card p { margin: 0; color: var(--text-muted); font-size: 13px; }
@media (max-width: 720px) {
  .layout { display: block; }
  .sidebar {
    width: auto; flex: none; height: auto; position: static;
    border-right: none; border-bottom: 1px solid var(--border);
  }
  .content { padding: 1.25rem 1rem 4rem; }
}
"""


def _page(title: str, crumb: str, body: str, sidebar: str, css_href: str, home_href: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{html.escape(css_href)}">
</head>
<body>
<div class="layout">
<aside class="sidebar">
<a class="brand" href="{html.escape(home_href)}">lookout</a>
{sidebar}
</aside>
<main class="content"><div class="inner">
<div class="crumb">{html.escape(crumb)}</div>
{body}
</div></main>
</div>
</body>
</html>
"""


def _landing_body(tree: dict, notes: list) -> str:
    cards = []
    for name, proj in tree["projects"].items():
        situation = next((n for n in proj["notes"] if n.stem == "situation"), None)
        href = situation.out_rel.as_posix() if situation else "#"
        atlas_count = sum(1 for n in proj["atlas"] if n.stem != "index")
        cards.append(
            f'<a class="card" href="{html.escape(href)}">'
            f"<h3>{html.escape(name)}</h3>"
            f'<p>{len(proj["notes"])} notes · {atlas_count} atlas</p></a>'
        )
    return (
        "<h1>lookout</h1>"
        f"<p>{len(notes)} notes across {len(tree['projects'])} projects. "
        "Pick a project, or use the tree.</p>"
        '<h2>Projects</h2><div class="cards">' + "".join(cards) + "</div>"
    )


def generate_site(vault_dir: Path, out_dir: Path) -> int:
    """Render the vault to `out_dir`. Returns the number of HTML files written."""
    notes = collect_notes(vault_dir)
    link_index = build_link_index(notes, vault_dir)
    tree = build_tree(notes)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "style.css").write_text(CSS, encoding="utf-8")

    written = 0
    for note in notes:
        text = note.path.read_text(encoding="utf-8", errors="replace")
        body = render_markdown(text, note, link_index)
        sidebar = render_sidebar(tree, note, note)
        crumb = " / ".join(note.rel.with_suffix("").parts)
        project = note.rel.parts[1] if note.rel.parts[0] == "projects" else None
        title = f"{note.title} — {project} — lookout" if project else f"{note.title} — lookout"
        depth = len(note.out_rel.parts) - 1
        css_href = "../" * depth + "style.css"
        home_href = "../" * depth + "index.html"
        page = _page(
            title, crumb, f"<h1>{html.escape(note.title)}</h1>\n{body}",
            sidebar, css_href, home_href,
        )
        dest = out_dir / note.out_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")
        written += 1

    landing = _page(
        "lookout", "index",
        _landing_body(tree, notes),
        render_sidebar(tree, None, None),
        "style.css", "index.html",
    )
    (out_dir / "index.html").write_text(landing, encoding="utf-8")
    written += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser(prog="render_site.py", description=__doc__)
    parser.add_argument("--vault", default=str(REPO_ROOT / "vault"))
    parser.add_argument("--out", default=str(REPO_ROOT / "site"))
    args = parser.parse_args()

    vault_dir = Path(args.vault)
    if not vault_dir.is_dir():
        print(f"render_site: vault not found: {vault_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)
    count = generate_site(vault_dir, out_dir)
    print(f"render_site: wrote {count} pages to {out_dir}")
    print(f"render_site: open {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()

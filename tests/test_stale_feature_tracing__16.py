"""UAT tests for issue #16: Add tracing step to SKILL.md for stale features.

Tests verify that:
1. SKILL.md contains a tracing step for stale features
2. The tracing step discovers entry points from docs and traverses imports
3. Generated atlas notes have all six required sections
4. Mermaid flowcharts are syntactically valid
5. Every Mermaid node is verifiable in source
6. Unresolved handlers produce open questions, not speculative edges
"""
import importlib.util
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
SKILL_MD = REPO_ROOT / "SKILL.md"
ATLAS_TRACE_PY = REPO_ROOT / "atlas_trace.py"


def _load_atlas_trace():
    """Dynamically load atlas_trace.py module."""
    spec = importlib.util.spec_from_file_location("atlas_trace_mod", str(ATLAS_TRACE_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# UAT Step 1: SKILL.md contains tracing step
# ---------------------------------------------------------------------------

def test_uat_1_skill_md_has_tracing_step():
    """UAT Step 1: SKILL.md contains a tracing step for stale features."""
    assert SKILL_MD.exists(), "SKILL.md must exist at repo root"
    text = SKILL_MD.read_text()

    # Verify atlas-trace section exists
    assert "atlas-trace" in text.lower() or "atlas_trace" in text, (
        "SKILL.md must contain an 'atlas-trace' section"
    )

    # Verify it describes the tracing step
    assert "trace" in text.lower() and "stale" in text.lower(), (
        "Tracing step must mention 'trace' and 'stale'"
    )


def test_uat_1_skill_md_describes_entry_point_discovery():
    """UAT Step 1: Tracing step must describe discovering entry points from docs."""
    text = SKILL_MD.read_text()

    # Find the atlas-trace section
    lines = text.split("\n")
    in_atlas_section = False
    section_text = []

    for line in lines:
        if "atlas-trace" in line.lower():
            in_atlas_section = True
        elif in_atlas_section and line.startswith("## ") and "atlas-trace" not in line.lower():
            break
        elif in_atlas_section:
            section_text.append(line)

    section = "\n".join(section_text).lower()
    assert "entry point" in section or "discover" in section, (
        "Tracing step must describe discovering entry points from docs"
    )


def test_uat_1_skill_md_describes_import_traversal():
    """UAT Step 1: Tracing step must describe traversing imports."""
    text = SKILL_MD.read_text()

    lines = text.split("\n")
    in_atlas_section = False
    section_text = []

    for line in lines:
        if "atlas-trace" in line.lower():
            in_atlas_section = True
        elif in_atlas_section and line.startswith("## ") and "atlas-trace" not in line.lower():
            break
        elif in_atlas_section:
            section_text.append(line)

    section = "\n".join(section_text).lower()
    assert "import" in section, (
        "Tracing step must describe traversing imports in source"
    )


# ---------------------------------------------------------------------------
# UAT Step 2: Skill runs against perf-coach feature
# ---------------------------------------------------------------------------

def test_uat_2_atlas_trace_module_exists():
    """UAT Step 2: atlas_trace.py module exists and is loadable."""
    assert ATLAS_TRACE_PY.exists(), f"atlas_trace.py must exist at {ATLAS_TRACE_PY}"
    mod = _load_atlas_trace()
    assert hasattr(mod, "generate_note"), "Module must expose generate_note function"


def test_uat_2_generate_note_processes_perf_coach_source(tmp_path):
    """UAT Step 2: Skill can run against perf-coach-like source without prompting."""
    mod = _load_atlas_trace()

    # Create a perf-coach-like source tree
    src = tmp_path / "perf-coach-src"
    src.mkdir()

    # Entry point with documented entry
    (src / "app.py").write_text(
        "from recommendation_engine import RecommendationEngine\n"
    )
    (src / "recommendation_engine.py").write_text(
        "class RecommendationEngine:\n"
        "    def generate(self):\n"
        "        return {}\n"
    )

    # Docs describing entry point
    docs = src / "docs"
    docs.mkdir()
    (docs / "features.md").write_text(
        "# Today Recommendation\n\n"
        "Entry point: `app.py`\n"
    )

    # Generate note (should not prompt, should not error)
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    assert isinstance(note, str), "generate_note must return a string"
    assert len(note) > 0, "Generated note must not be empty"


# ---------------------------------------------------------------------------
# UAT Step 3: Generated atlas note has all six required sections
# ---------------------------------------------------------------------------

def test_uat_3_atlas_note_has_frontmatter():
    """UAT Step 3: Generated note has YAML frontmatter with files_read list."""
    mod = _load_atlas_trace()
    src = Path(__file__).parent / "fixtures" / "trace-src"

    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    assert note.startswith("---"), "Note must start with YAML frontmatter"
    assert "files_read:" in note, "Frontmatter must have files_read: key"

    # Parse frontmatter
    end_idx = note.index("---", 3)
    frontmatter = note[3:end_idx]
    assert "feature:" in frontmatter, "Frontmatter must have feature: key"
    assert "stale:" in frontmatter, "Frontmatter must have stale: key"


def test_uat_3_atlas_note_has_what_section():
    """UAT Step 3: Generated note has '## What' section describing the feature."""
    mod = _load_atlas_trace()
    src = Path(__file__).parent / "fixtures" / "trace-src"

    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    assert re.search(r"##\s+What\b", note, re.IGNORECASE), (
        "Note must have a '## What' section"
    )


def test_uat_3_atlas_note_has_entry_points_section():
    """UAT Step 3: Generated note has '## Entry Points' section."""
    mod = _load_atlas_trace()
    src = Path(__file__).parent / "fixtures" / "trace-src"

    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    assert re.search(r"##\s+Entry\s+Points?", note, re.IGNORECASE), (
        "Note must have '## Entry Points' section"
    )


def test_uat_3_atlas_note_has_related_issues_section():
    """UAT Step 3: Generated note has '## Related Issues' section."""
    mod = _load_atlas_trace()
    src = Path(__file__).parent / "fixtures" / "trace-src"

    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    assert re.search(r"##\s+Related\s+Issues?", note, re.IGNORECASE), (
        "Note must have '## Related Issues' section"
    )


def test_uat_3_atlas_note_has_flowchart_section():
    """UAT Step 3: Generated note has '## Flowchart' section with Mermaid block."""
    mod = _load_atlas_trace()
    src = Path(__file__).parent / "fixtures" / "trace-src"

    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    assert re.search(r"##\s+Flowchart", note, re.IGNORECASE), (
        "Note must have '## Flowchart' section"
    )
    assert "```mermaid" in note, "Flowchart section must contain mermaid block"


def test_uat_3_atlas_note_has_key_files_section():
    """UAT Step 3: Generated note has '## Key Files' section."""
    mod = _load_atlas_trace()
    src = Path(__file__).parent / "fixtures" / "trace-src"

    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    assert re.search(r"##\s+Key\s+Files?", note, re.IGNORECASE), (
        "Note must have '## Key Files' section"
    )


# ---------------------------------------------------------------------------
# UAT Step 4: Mermaid syntax is valid
# ---------------------------------------------------------------------------

def test_uat_4_mermaid_block_is_valid(tmp_path):
    """UAT Step 4: Mermaid block exits 0 with no errors (or structural check passes)."""
    mod = _load_atlas_trace()
    src = Path(__file__).parent / "fixtures" / "trace-src"

    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    # Structural validity check: must have flowchart directive and at least one edge
    m = re.search(r"```mermaid\n(.*?)```", note, re.DOTALL)
    assert m, "Must have mermaid block"

    mermaid = m.group(1).strip()
    assert re.match(r"(flowchart|graph)\s+", mermaid), (
        "Mermaid must start with flowchart or graph directive"
    )
    assert re.search(r"\w+\s*(-->|---|\[)", mermaid), (
        "Mermaid must have at least one node or edge"
    )

    # If mmdc is available, run it for syntax check
    mmdc_path = _which("mmdc")
    if mmdc_path:
        note_file = tmp_path / "test_note.md"
        note_file.write_text(note)
        result = subprocess.run(
            [mmdc_path, "-i", str(note_file), "-o", str(tmp_path / "out.svg")],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0, f"mmdc syntax check failed: {result.stderr}"


# ---------------------------------------------------------------------------
# UAT Step 5: Every Mermaid node is verifiable via grep
# ---------------------------------------------------------------------------

def test_uat_5_mermaid_nodes_are_grep_verifiable():
    """UAT Step 5: Every node in Mermaid can be grep'd or found in the fixture."""
    mod = _load_atlas_trace()
    src = Path(__file__).parent / "fixtures" / "trace-src"

    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    mermaid = mod.extract_mermaid_block(note)
    assert mermaid, "Must have mermaid block"

    nodes = mod.get_node_names(mermaid)
    assert len(nodes) > 0, "Mermaid must have at least one node"

    # Collect all source file contents and file names
    source_text = ""
    source_files = set()
    source_stems = set()

    for py_file in src.rglob("*.py"):
        source_files.add(py_file.name)
        source_stems.add(py_file.stem)
        source_text += py_file.read_text() + "\n"

    # Every node must be grep-able (appear in source or be a route/table)
    for node in nodes:
        node_lower = node.lower()

        # Check if it's a file reference
        is_file = any(
            node_lower in fname.lower() or fname.lower() in node_lower
            for fname in (source_files | source_stems)
        )

        # Check if it's a route (starts with /)
        is_route = node.startswith("/")

        # Check if it's a table (underscore-separated, lowercase alphanumerics)
        is_table = "_" in node and re.match(r"^[a-z_]+$", node_lower)

        # Check if it appears in source text
        appears_in_source = node in source_text or node_lower in source_text.lower()

        assert (is_file or is_route or is_table or appears_in_source), (
            f"Node '{node}' must be grep-able in source. "
            f"(Files: {source_files}, Stems: {source_stems})"
        )


# ---------------------------------------------------------------------------
# UAT Step 6: Ambiguous flow produces open question, not speculative edge
# ---------------------------------------------------------------------------

def test_uat_6_missing_handler_produces_open_question(tmp_path):
    """UAT Step 6: When handler is missing, note has open question, not speculative edge."""
    mod = _load_atlas_trace()

    # Create source with missing intermediate handler
    src = tmp_path / "ambiguous-src"
    src.mkdir()

    (src / "app.py").write_text(
        "from missing_processor import process\n"
        "from db import DataStore\n"
        "\n"
        "@app.get('/api/coaching')\n"
        "def get_coaching():\n"
        "    return process()\n"
    )

    (src / "db.py").write_text(
        "class DataStore:\n"
        "    table = 'coaching_data'\n"
    )

    # missing_processor.py is intentionally absent

    note = mod.generate_note(
        feature_name="Coaching",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    # Must have an open question callout
    has_open_question = (
        "<!-- OPEN QUESTION" in note or
        re.search(r"##\s+Open\s+Questions?", note) is not None
    )
    assert has_open_question, (
        "Note must contain explicit open question when handler is missing"
    )

    # The missing module should not be a regular node in the diagram
    mermaid = mod.extract_mermaid_block(note)
    if mermaid and "missing_processor" in mermaid:
        # If it appears, it must be marked as uncertain (?, OPEN, etc)
        has_uncertainty = "?" in mermaid or "OPEN" in note
        assert has_uncertainty, (
            "missing_processor must not appear as a regular node without uncertainty marker"
        )


def test_uat_6_ambiguous_flow_note_is_clearly_labeled(tmp_path):
    """UAT Step 6: Open question callout must use recognized format."""
    mod = _load_atlas_trace()

    src = tmp_path / "ambig2-src"
    src.mkdir()

    (src / "app.py").write_text(
        "from unknown_handler import handle\n"
    )

    note = mod.generate_note(
        feature_name="Feature",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    # Must use HTML comment or section format for open questions
    has_html_comment = "<!-- OPEN QUESTION" in note
    has_section = re.search(r"##\s+Open\s+Questions?", note) is not None

    assert (has_html_comment or has_section), (
        "Open question must use HTML comment (<!-- OPEN QUESTION: ... -->) "
        "or '## Open Questions' section"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _which(cmd: str) -> str | None:
    """Find a command in PATH, returning the full path or None."""
    import shutil
    return shutil.which(cmd)

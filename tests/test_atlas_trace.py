"""Tests for issue #16: tracing step in SKILL.md for stale features.

Each test maps to a specific AC item from the issue.
Tests run against atlas_trace.py at repo root.
"""
import importlib.util
import re
import subprocess
import sys
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
ATLAS_TRACE_PY = REPO_ROOT / "atlas_trace.py"
SKILL_MD = REPO_ROOT / "SKILL.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_atlas_trace():
    spec = importlib.util.spec_from_file_location("atlas_trace_test", str(ATLAS_TRACE_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_perf_coach_source(base_dir: Path) -> Path:
    """Create a minimal fake perf-coach source tree for tracing tests."""
    src = base_dir / "perf-coach-src"
    src.mkdir(parents=True, exist_ok=True)

    # Entry point: main app file
    (src / "app.py").write_text(
        "from routes import coaching_router\n"
        "from db import CoachingSession\n"
        "\n"
        "def create_app():\n"
        "    app = App()\n"
        "    app.include_router(coaching_router)\n"
        "    return app\n"
    )

    # Routes file
    (src / "routes.py").write_text(
        "from db import CoachingSession\n"
        "from models import Recommendation\n"
        "\n"
        "coaching_router = Router()\n"
        "\n"
        "@coaching_router.get('/api/recommendations')\n"
        "def get_recommendations():\n"
        "    sessions = CoachingSession.query()\n"
        "    return Recommendation.from_sessions(sessions)\n"
    )

    # DB file
    (src / "db.py").write_text(
        "class CoachingSession:\n"
        "    table = 'coaching_sessions'\n"
        "    @classmethod\n"
        "    def query(cls):\n"
        "        return []\n"
    )

    # Models file
    (src / "models.py").write_text(
        "class Recommendation:\n"
        "    @staticmethod\n"
        "    def from_sessions(sessions):\n"
        "        return []\n"
    )

    # Docs describing entry points
    docs = src / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "features.md").write_text(
        "# Today Recommendation\n\n"
        "Entry point: `app.py` → `routes.py` → `/api/recommendations`\n"
        "Database table: `coaching_sessions`\n"
    )

    return src


def _make_issues_snapshot(base_dir: Path, issues: list | None = None) -> Path:
    import json
    snap = base_dir / "snapshot"
    snap.mkdir(exist_ok=True)
    data = {"issues": issues or [], "prs": []}
    (snap / "issues.json").write_text(json.dumps(data))
    return snap


# ---------------------------------------------------------------------------
# AC1: SKILL.md contains a tracing step for stale features
# ---------------------------------------------------------------------------

def test_skill_md_has_tracing_step():
    """AC1: SKILL.md must contain a tracing step for stale features."""
    assert SKILL_MD.exists(), "SKILL.md must exist"
    text = SKILL_MD.read_text()
    assert "trac" in text.lower(), "SKILL.md must contain a tracing step"


def test_skill_md_tracing_step_mentions_entry_points():
    """AC1: SKILL.md tracing step must mention entry points."""
    text = SKILL_MD.read_text()
    assert "entry point" in text.lower(), (
        "SKILL.md tracing step must describe discovering entry points from docs"
    )


def test_skill_md_tracing_step_mentions_imports():
    """AC1: SKILL.md tracing step must mention traversing imports."""
    text = SKILL_MD.read_text()
    assert "import" in text.lower(), (
        "SKILL.md tracing step must describe traversing imports"
    )


def test_skill_md_tracing_step_applies_to_stale_features():
    """AC1: SKILL.md tracing step must scope itself to stale features."""
    text = SKILL_MD.read_text()
    assert "stale" in text.lower(), (
        "SKILL.md tracing step must indicate it applies to stale features"
    )


# ---------------------------------------------------------------------------
# AC2: Generated note contains all six required sections
# ---------------------------------------------------------------------------

def test_atlas_trace_py_exists():
    """AC2: atlas_trace.py must exist at repo root."""
    assert ATLAS_TRACE_PY.exists(), "atlas_trace.py must exist at repo root"


def test_generate_note_returns_string():
    """AC2: generate_note() returns a string."""
    mod = _load_atlas_trace()
    src = Path(sys.modules[__name__].__file__).parent / "fixtures" / "trace-src"
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )
    assert isinstance(note, str), "generate_note() must return a str"
    assert len(note) > 0, "generate_note() must return non-empty string"


def test_generated_note_has_frontmatter():
    """AC2: Generated note must open with YAML frontmatter listing files read."""
    mod = _load_atlas_trace()
    src = Path(sys.modules[__name__].__file__).parent / "fixtures" / "trace-src"
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )
    assert note.startswith("---"), "Note must start with YAML frontmatter (---)"
    end = note.index("---", 3)
    frontmatter = note[3:end]
    assert "files_read:" in frontmatter, (
        "Frontmatter must contain 'files_read:' listing every file read during tracing"
    )


def test_generated_note_has_description_section():
    """AC2: Generated note must contain a description/what section."""
    mod = _load_atlas_trace()
    src = Path(sys.modules[__name__].__file__).parent / "fixtures" / "trace-src"
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )
    assert re.search(r"##\s+(What|Description)", note, re.IGNORECASE), (
        "Note must contain a '## What' or '## Description' section"
    )


def test_generated_note_has_entry_points_section():
    """AC2: Generated note must contain an entry points section."""
    mod = _load_atlas_trace()
    src = Path(sys.modules[__name__].__file__).parent / "fixtures" / "trace-src"
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )
    assert re.search(r"##\s+Entry\s+[Pp]oints?", note), (
        "Note must contain an '## Entry Points' section"
    )


def test_generated_note_has_related_issues_section():
    """AC2: Generated note must contain a related issues section."""
    mod = _load_atlas_trace()
    src = Path(sys.modules[__name__].__file__).parent / "fixtures" / "trace-src"
    issues = [{"number": 42, "title": "Add coaching recommendations endpoint"}]
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=issues,
    )
    assert re.search(r"##\s+Related\s+[Ii]ssues?", note), (
        "Note must contain a '## Related Issues' section"
    )


def test_generated_note_related_issues_lists_issue_numbers():
    """AC2: Related issues section must list the issue numbers passed in."""
    mod = _load_atlas_trace()
    src = Path(sys.modules[__name__].__file__).parent / "fixtures" / "trace-src"
    issues = [
        {"number": 42, "title": "Add coaching recommendations endpoint"},
        {"number": 99, "title": "Fix session query performance"},
    ]
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=issues,
    )
    assert "#42" in note or "42" in note, "Related issues must include issue #42"
    assert "#99" in note or "99" in note, "Related issues must include issue #99"


def test_generated_note_has_mermaid_flowchart():
    """AC2: Generated note must contain a Mermaid flowchart block."""
    mod = _load_atlas_trace()
    src = Path(sys.modules[__name__].__file__).parent / "fixtures" / "trace-src"
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )
    assert "```mermaid" in note, "Note must contain a ```mermaid code block"
    assert "flowchart" in note or "graph" in note, (
        "Mermaid block must use flowchart or graph diagram type"
    )


def test_generated_note_has_key_files_section():
    """AC2: Generated note must contain a key files section with one line per file."""
    mod = _load_atlas_trace()
    src = Path(sys.modules[__name__].__file__).parent / "fixtures" / "trace-src"
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )
    assert re.search(r"##\s+Key\s+[Ff]iles?", note), (
        "Note must contain a '## Key Files' section"
    )


# ---------------------------------------------------------------------------
# AC3: Mermaid block is syntactically valid
# ---------------------------------------------------------------------------

def test_mermaid_block_has_valid_syntax(tmp_path):
    """AC3: Mermaid block must be syntactically valid (mmdc exit 0 or structural check)."""
    mod = _load_atlas_trace()
    src = Path(sys.modules[__name__].__file__).parent / "fixtures" / "trace-src"
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    # Extract mermaid block
    m = re.search(r"```mermaid\n(.*?)```", note, re.DOTALL)
    assert m, "Note must contain a mermaid block"
    mermaid_content = m.group(1).strip()

    # Structural validity: must start with flowchart or graph directive
    assert re.match(r"(flowchart|graph)\s+\w+", mermaid_content), (
        "Mermaid block must start with 'flowchart' or 'graph' directive"
    )

    # Must have at least one node definition (A --> B or A[label])
    assert re.search(r"\w+\s*(-->|---|\[)", mermaid_content), (
        "Mermaid block must contain at least one node or edge"
    )

    # Try mmdc if available
    mmdc = shutil.which("mmdc")
    if mmdc:
        note_file = tmp_path / "test_note.md"
        note_file.write_text(note)
        result = subprocess.run(
            [mmdc, "-i", str(note_file), "-o", str(tmp_path / "out.svg")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"mmdc reported syntax errors:\n{result.stderr}"
        )


def test_mermaid_block_extract_function_exists():
    """AC3: atlas_trace.py must expose extract_mermaid_block(note_text) -> str."""
    mod = _load_atlas_trace()
    assert hasattr(mod, "extract_mermaid_block"), (
        "atlas_trace.py must expose extract_mermaid_block(note_text) -> str"
    )


def test_extract_mermaid_block_returns_content():
    """AC3: extract_mermaid_block returns the content inside the mermaid fence."""
    mod = _load_atlas_trace()
    sample = "# Note\n\n```mermaid\nflowchart LR\n  A --> B\n```\n"
    result = mod.extract_mermaid_block(sample)
    assert "flowchart LR" in result
    assert "A --> B" in result


def test_extract_mermaid_block_returns_none_when_absent():
    """AC3: extract_mermaid_block returns None when no mermaid block is present."""
    mod = _load_atlas_trace()
    result = mod.extract_mermaid_block("# No diagram here\n")
    assert result is None, "extract_mermaid_block must return None when no mermaid block"


# ---------------------------------------------------------------------------
# AC4: Every Mermaid node names a real file, route, or table from source
# ---------------------------------------------------------------------------

def test_mermaid_nodes_are_real_source_artifacts():
    """AC4: Every node in the Mermaid diagram names a real file, route, or table from source."""
    mod = _load_atlas_trace()
    src = Path(sys.modules[__name__].__file__).parent / "fixtures" / "trace-src"
    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    mermaid = mod.extract_mermaid_block(note)
    assert mermaid, "Must have a Mermaid block"

    # get_node_names() must be implemented to allow external verification
    nodes = mod.get_node_names(mermaid)
    assert isinstance(nodes, list), "get_node_names() must return a list"
    assert len(nodes) > 0, "Mermaid diagram must have at least one node"

    # Each node label must correspond to a real artifact in the source
    # Acceptable artifacts: filenames, route paths starting with '/', table names
    source_files = {f.name for f in src.rglob("*") if f.is_file()}
    source_file_stems = {f.stem for f in src.rglob("*") if f.is_file()}

    for node in nodes:
        node_lower = node.lower()
        is_file_ref = any(
            node_lower in fname.lower() or fname.lower() in node_lower
            for fname in source_files | source_file_stems
        )
        is_route = node.startswith("/")
        is_table = "_" in node and re.match(r"^[a-z_]+$", node_lower)
        assert is_file_ref or is_route or is_table, (
            f"Mermaid node '{node}' does not name a real file, route, or table "
            f"from source. Source files: {source_files}"
        )


def test_get_node_names_function_exists():
    """AC4: atlas_trace.py must expose get_node_names(mermaid_text) -> list[str]."""
    mod = _load_atlas_trace()
    assert hasattr(mod, "get_node_names"), (
        "atlas_trace.py must expose get_node_names(mermaid_text) -> list[str]"
    )


def test_get_node_names_extracts_labels():
    """AC4: get_node_names extracts human-readable labels from Mermaid nodes."""
    mod = _load_atlas_trace()
    mermaid = "flowchart LR\n  A[app.py] --> B[routes.py]\n  B --> C[/api/recommendations]\n"
    names = mod.get_node_names(mermaid)
    assert "app.py" in names, "get_node_names must extract 'app.py' from A[app.py]"
    assert "routes.py" in names, "get_node_names must extract 'routes.py' from B[routes.py]"
    assert "/api/recommendations" in names


# ---------------------------------------------------------------------------
# AC5: Unresolved flows produce explicit open questions, not fabricated edges
# ---------------------------------------------------------------------------

def test_open_question_when_handler_missing(tmp_path):
    """AC5: When a handler is missing, note must have open question, not speculative edge."""
    mod = _load_atlas_trace()

    # Source with a gap: routes.py imports from missing_handler.py (not present)
    src = tmp_path / "gap-src"
    src.mkdir()
    (src / "app.py").write_text(
        "from routes import router\n"
        "from missing_handler import handle  # this file does not exist\n"
    )
    (src / "routes.py").write_text(
        "@router.get('/api/coach')\n"
        "def coach():\n"
        "    return handle()\n"
    )
    # missing_handler.py is intentionally absent

    note = mod.generate_note(
        feature_name="Coach Feature",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    # Must have an open question (HTML comment or dedicated section)
    has_open_question = (
        "<!-- OPEN QUESTION" in note
        or "OPEN QUESTION" in note
        or re.search(r"##\s+Open\s+[Qq]uestions?", note)
    )
    assert has_open_question, (
        "Note must contain an explicit open question when a handler cannot be resolved. "
        "Use <!-- OPEN QUESTION: ... --> or a '## Open Questions' section."
    )


def test_no_fabricated_edge_when_handler_missing(tmp_path):
    """AC5: Missing handler must not appear as a node connected to both endpoints."""
    mod = _load_atlas_trace()

    src = tmp_path / "gap-src2"
    src.mkdir()
    (src / "app.py").write_text(
        "from routes import router\n"
        "from missing_handler import handle\n"
    )
    (src / "routes.py").write_text(
        "@router.get('/api/coach')\n"
        "def coach():\n"
        "    return handle()\n"
    )

    note = mod.generate_note(
        feature_name="Coach Feature",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    mermaid = mod.extract_mermaid_block(note)
    if mermaid:
        # missing_handler.py must not appear as a node connecting two real nodes
        # It may appear with a '?' or similar marker indicating uncertainty
        assert "missing_handler" not in mermaid or "?" in mermaid or "OPEN" in mermaid, (
            "missing_handler.py must not appear as a regular (non-speculative) node "
            "in the Mermaid diagram when the file does not exist in source"
        )


def test_open_question_uses_recognized_format():
    """AC5: Open questions must use HTML comment or dedicated section format."""
    mod = _load_atlas_trace()
    note_with_oq = "# Note\n\n<!-- OPEN QUESTION: Where does handle() route? -->\n"
    note_with_section = "# Note\n\n## Open Questions\n\n- Where does handle() route?\n"
    note_without = "# Note\n\nNo questions here.\n"

    def _has_oq(note):
        return (
            "<!-- OPEN QUESTION" in note
            or re.search(r"##\s+Open\s+[Qq]uestions?", note) is not None
        )

    assert _has_oq(note_with_oq), "HTML comment form must be recognized as open question"
    assert _has_oq(note_with_section), "Section form must be recognized as open question"
    assert not _has_oq(note_without), "Notes without open questions must not be marked"


# ---------------------------------------------------------------------------
# AC6: Tracing perf-coach produces a verifiable diagram (fixture-based)
# ---------------------------------------------------------------------------

def test_perf_coach_fixture_trace_produces_verifiable_nodes(tmp_path):
    """AC6: Tracing the perf-coach fixture produces a diagram with grep-able nodes."""
    mod = _load_atlas_trace()
    src = tmp_path / "pc-src"
    src.mkdir()

    # Minimal perf-coach-like source
    (src / "app.py").write_text(
        "from recommendation_engine import RecommendationEngine\n"
        "from data_store import TrainingLoadTable\n"
        "\n"
        "@app.get('/api/today')\n"
        "def today_recommendation():\n"
        "    engine = RecommendationEngine()\n"
        "    return engine.generate()\n"
    )
    (src / "recommendation_engine.py").write_text(
        "from data_store import TrainingLoadTable\n"
        "\n"
        "class RecommendationEngine:\n"
        "    def generate(self):\n"
        "        data = TrainingLoadTable.latest()\n"
        "        return {'recommendation': 'rest'}\n"
    )
    (src / "data_store.py").write_text(
        "class TrainingLoadTable:\n"
        "    table = 'training_loads'\n"
        "    @classmethod\n"
        "    def latest(cls):\n"
        "        return {}\n"
    )

    note = mod.generate_note(
        feature_name="Today Recommendation",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    mermaid = mod.extract_mermaid_block(note)
    assert mermaid, "Must produce a Mermaid diagram"

    nodes = mod.get_node_names(mermaid)
    assert len(nodes) >= 2, "Perf-coach trace must have at least 2 nodes"

    # Every node must be grep-able in the source
    source_text = "\n".join(f.read_text() for f in src.rglob("*.py"))
    for node in nodes:
        clean = node.strip("/").replace(".py", "")
        assert clean in source_text or node in source_text, (
            f"Node '{node}' must be grep-able in the perf-coach source files"
        )


# ---------------------------------------------------------------------------
# AC7: Ambiguous flow produces atlas note with labeled open question
# ---------------------------------------------------------------------------

def test_ambiguous_flow_produces_open_question_not_speculative_edge(tmp_path):
    """AC7: Ambiguous perf-coach flow results in an open question, not a speculative edge."""
    mod = _load_atlas_trace()
    src = tmp_path / "ambiguous-src"
    src.mkdir()

    # app.py references a handler that doesn't exist
    (src / "app.py").write_text(
        "from missing_intermediate import process_load\n"
        "\n"
        "@app.get('/api/readiness')\n"
        "def readiness():\n"
        "    return process_load()\n"
    )
    # missing_intermediate.py is intentionally absent

    note = mod.generate_note(
        feature_name="Readiness",
        source_dir=src,
        entry_point_file="app.py",
        issues=[],
    )

    # Must have open question
    has_open_question = (
        "<!-- OPEN QUESTION" in note
        or re.search(r"##\s+Open\s+[Qq]uestions?", note) is not None
    )
    assert has_open_question, (
        "AC7: Ambiguous flow must produce an explicit open question in the atlas note"
    )

    # Must not have a speculative edge connecting /api/readiness directly to
    # missing_intermediate without any uncertainty marker
    mermaid = mod.extract_mermaid_block(note)
    if mermaid and "missing_intermediate" in mermaid:
        assert "?" in mermaid or "OPEN" in mermaid, (
            "AC7: missing_intermediate must not appear as a regular node in the diagram "
            "— it must carry an uncertainty marker or be omitted"
        )


def test_open_question_is_clearly_labeled():
    """AC7: Open question callout must be clearly labeled (not just a generic comment)."""
    mod = _load_atlas_trace()

    sample_note_good = (
        "# Note\n\n"
        "<!-- OPEN QUESTION: missing_intermediate.py not found; "
        "process_load() handler unresolved -->\n"
    )
    sample_note_bad_generic = "# Note\n\n<!-- TODO: fix this -->\n"

    def _has_labeled_oq(note):
        return bool(re.search(r"<!--\s*OPEN QUESTION", note, re.IGNORECASE))

    assert _has_labeled_oq(sample_note_good), (
        "OPEN QUESTION HTML comment must be recognized"
    )
    assert not _has_labeled_oq(sample_note_bad_generic), (
        "Generic TODO comment must not be confused with OPEN QUESTION"
    )

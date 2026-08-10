"""Tests for issue #20: Generate cross-project capability map in SKILL.md.

Each test maps to a specific AC item from the issue.
Tests run against capability_map.py at repo root.
"""
import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
CAPABILITY_MAP_PY = REPO_ROOT / "capability_map.py"
VAULT_DIR = REPO_ROOT / "vault"
SKILL_MD = REPO_ROOT / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"

BEGIN_EDGES = "<!-- BEGIN MACHINE EDGES -->"
END_EDGES = "<!-- END MACHINE EDGES -->"
BEGIN_PIPELINES = "<!-- BEGIN HUMAN PIPELINES -->"
END_PIPELINES = "<!-- END HUMAN PIPELINES -->"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_capability_map():
    spec = importlib.util.spec_from_file_location(
        "capability_map_test", str(CAPABILITY_MAP_PY)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_vault_with_cards(tmp_path: Path, cards: dict[str, str]) -> Path:
    """Create a temp vault with capability.md files from the given dict."""
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    for name, content in cards.items():
        project_dir = vault / "projects" / name
        project_dir.mkdir(parents=True)
        (project_dir / "capability.md").write_text(content)
    (vault / "map.md").write_text("# Map\n")
    return vault


def _producer_card(name: str, surfaces: list[str]) -> str:
    """Build a minimal capability card that exposes the given GET paths."""
    surface_lines = "\n".join(
        f"- `GET {p}` — endpoint on {name}\n  - Example: `curl http://localhost:8000{p}`"
        for p in surfaces
    )
    return (
        f"# {name} — Capability Card\n\n"
        f"## What it is\n\n`{name}` is a tracked project.\n\n"
        f"## Data it owns\n\n- vault/projects/{name}/\n\n"
        f"## Read surfaces\n\n{surface_lines}\n\n"
        f"## How to make it do things\n\n- Commander slug: `{name}`\n\n"
        f"## Constraints\n\n- Read-only access.\n\n"
        f"## Notes for AI\n\n_None._\n"
    )


def _consumer_card(name: str, referenced_surfaces: list[str]) -> str:
    """Build a minimal capability card that references other projects' surfaces."""
    notes = "This project uses the following surfaces from other projects:\n"
    for s in referenced_surfaces:
        notes += f"- `GET {s}`\n"
    return (
        f"# {name} — Capability Card\n\n"
        f"## What it is\n\n`{name}` is a tracked project.\n\n"
        f"## Data it owns\n\n- vault/projects/{name}/\n\n"
        f"## Read surfaces\n\n_No read surfaces discovered in snapshot evidence._\n\n"
        f"## How to make it do things\n\n- Commander slug: `{name}`\n\n"
        f"## Constraints\n\n- Read-only access.\n\n"
        f"## Notes for AI\n\n{notes}\n"
    )


# ---------------------------------------------------------------------------
# AC1: map.md has both sentinel sections
# ---------------------------------------------------------------------------

def test_ac1_map_has_both_sentinel_sections(tmp_path):
    """AC1: map.md exists with both BEGIN/END MACHINE EDGES and HUMAN PIPELINES sections."""
    vault = _make_vault_with_cards(tmp_path, {})
    mod = _load_capability_map()
    mod.generate_map(vault_dir=vault)

    content = (vault / "map.md").read_text()
    assert BEGIN_EDGES in content, "Missing BEGIN MACHINE EDGES sentinel"
    assert END_EDGES in content, "Missing END MACHINE EDGES sentinel"
    assert BEGIN_PIPELINES in content, "Missing BEGIN HUMAN PIPELINES sentinel"
    assert END_PIPELINES in content, "Missing END HUMAN PIPELINES sentinel"

    # Sentinels appear in correct order
    edges_start = content.index(BEGIN_EDGES)
    edges_end = content.index(END_EDGES)
    pipelines_start = content.index(BEGIN_PIPELINES)
    pipelines_end = content.index(END_PIPELINES)
    assert edges_start < edges_end < pipelines_start < pipelines_end, (
        "Sentinel sections appear out of order"
    )


# ---------------------------------------------------------------------------
# AC2: Pipelines section is byte-for-byte identical after re-run
# ---------------------------------------------------------------------------

def test_ac2_pipelines_preserved_across_runs(tmp_path):
    """AC2: Re-running generation leaves the Pipelines section unchanged."""
    vault = _make_vault_with_cards(tmp_path, {})
    mod = _load_capability_map()

    # First run — establishes the file
    mod.generate_map(vault_dir=vault)

    # Add something to the pipelines section
    content = (vault / "map.md").read_text()
    pipelines_block = f"{BEGIN_PIPELINES}\n- test-flow: A → B → C\n{END_PIPELINES}"
    content = re.sub(
        rf"{re.escape(BEGIN_PIPELINES)}.*?{re.escape(END_PIPELINES)}",
        pipelines_block,
        content,
        flags=re.DOTALL,
    )
    (vault / "map.md").write_text(content)

    snapshot_pipelines = (
        (vault / "map.md").read_text()
        .split(BEGIN_PIPELINES)[1]
        .split(END_PIPELINES)[0]
    )

    # Second run — should preserve the pipelines section
    mod.generate_map(vault_dir=vault)
    after_content = (vault / "map.md").read_text()
    after_pipelines = (
        after_content.split(BEGIN_PIPELINES)[1].split(END_PIPELINES)[0]
    )

    assert after_pipelines == snapshot_pipelines, (
        "Pipelines section was modified by a re-run"
    )


# ---------------------------------------------------------------------------
# AC3: Edges only reference existing capability cards
# ---------------------------------------------------------------------------

def test_ac3_edges_reference_existing_cards(tmp_path):
    """AC3: Every generated edge names a producer and consumer that both have capability cards."""
    cards = {
        "producer-a": _producer_card("producer-a", ["/api/data"]),
        "consumer-b": _consumer_card("consumer-b", ["/api/data"]),
    }
    vault = _make_vault_with_cards(tmp_path, cards)
    mod = _load_capability_map()
    mod.generate_map(vault_dir=vault)

    content = (vault / "map.md").read_text()
    edges_text = content.split(BEGIN_EDGES)[1].split(END_EDGES)[0]

    known_names = set(cards.keys())
    for line in edges_text.strip().splitlines():
        if not line.strip() or not line.startswith("-"):
            continue
        # Edge format: "- <producer> → <consumer> via GET <path>"
        m = re.match(r"^- (\S+) → (\S+) via GET ", line)
        assert m, f"Edge line has unexpected format: {line!r}"
        producer, consumer = m.group(1), m.group(2)
        assert producer in known_names, (
            f"Edge producer '{producer}' has no capability card"
        )
        assert consumer in known_names, (
            f"Edge consumer '{consumer}' has no capability card"
        )


# ---------------------------------------------------------------------------
# AC4: Edge lines name the concrete surface documented in a capability card
# ---------------------------------------------------------------------------

def test_ac4_edge_names_concrete_surface(tmp_path):
    """AC4: Each edge line names the surface exactly as it appears in the producer's card."""
    cards = {
        "viral-radar": _producer_card("viral-radar", ["/training-data"]),
        "perf-coach": _consumer_card("perf-coach", ["/training-data"]),
    }
    vault = _make_vault_with_cards(tmp_path, cards)
    mod = _load_capability_map()
    mod.generate_map(vault_dir=vault)

    content = (vault / "map.md").read_text()
    edges_text = content.split(BEGIN_EDGES)[1].split(END_EDGES)[0]

    assert "viral-radar → perf-coach via GET /training-data" in edges_text, (
        f"Expected edge not found. Edges section:\n{edges_text}"
    )


# ---------------------------------------------------------------------------
# AC5: No edge for surfaces not in any capability card
# ---------------------------------------------------------------------------

def test_ac5_no_edge_for_undocumented_surface(tmp_path):
    """AC5: Surfaces mentioned in non-Read-surfaces text but not in any card's
    Read surfaces section do not produce an edge."""
    cards = {
        "producer-a": _producer_card("producer-a", ["/api/real-endpoint"]),
        # consumer-b mentions a fictional path that no card exposes
        "consumer-b": _consumer_card("consumer-b", ["/api/fictional-endpoint"]),
    }
    vault = _make_vault_with_cards(tmp_path, cards)
    mod = _load_capability_map()
    mod.generate_map(vault_dir=vault)

    content = (vault / "map.md").read_text()
    edges_text = content.split(BEGIN_EDGES)[1].split(END_EDGES)[0]

    assert "/api/fictional-endpoint" not in edges_text, (
        "Edge emitted for surface not in any capability card"
    )


def test_ac5_no_edge_when_no_cards(tmp_path):
    """AC5: No edges emitted when no capability cards exist."""
    vault = _make_vault_with_cards(tmp_path, {})
    mod = _load_capability_map()
    mod.generate_map(vault_dir=vault)

    content = (vault / "map.md").read_text()
    edges_text = content.split(BEGIN_EDGES)[1].split(END_EDGES)[0].strip()
    assert edges_text == "", f"Expected empty Edges section, got: {edges_text!r}"


# ---------------------------------------------------------------------------
# AC6: Sentinel pipeline entry persists through three runs
# ---------------------------------------------------------------------------

def test_ac6_sentinel_pipeline_survives_three_runs(tmp_path):
    """AC6: A sentinel entry in the Human Pipelines section is unchanged after 3 runs."""
    cards = {
        "producer-a": _producer_card("producer-a", ["/api/data"]),
        "consumer-b": _consumer_card("consumer-b", ["/api/data"]),
    }
    vault = _make_vault_with_cards(tmp_path, cards)
    mod = _load_capability_map()

    # First run to establish the file
    mod.generate_map(vault_dir=vault)

    # Add sentinel to pipelines section
    content = (vault / "map.md").read_text()
    sentinel = "- sentinel-pipeline: do-not-delete"
    pipelines_with_sentinel = f"{BEGIN_PIPELINES}\n{sentinel}\n{END_PIPELINES}"
    content = re.sub(
        rf"{re.escape(BEGIN_PIPELINES)}.*?{re.escape(END_PIPELINES)}",
        pipelines_with_sentinel,
        content,
        flags=re.DOTALL,
    )
    (vault / "map.md").write_text(content)

    # Runs 1, 2, 3
    for run in range(3):
        mod.generate_map(vault_dir=vault)
        current = (vault / "map.md").read_text()
        assert sentinel in current, (
            f"Sentinel entry missing after run {run + 1}"
        )
        # Verify it's inside the human pipelines section
        pipelines_section = current.split(BEGIN_PIPELINES)[1].split(END_PIPELINES)[0]
        assert sentinel in pipelines_section, (
            f"Sentinel not inside Human Pipelines section after run {run + 1}"
        )


# ---------------------------------------------------------------------------
# AC6 (additional): Machine content must not appear inside human section
# ---------------------------------------------------------------------------

def test_ac6_machine_content_not_in_human_section(tmp_path):
    """AC6: No machine-written edge content appears inside the Human Pipelines section."""
    cards = {
        "producer-a": _producer_card("producer-a", ["/api/data"]),
        "consumer-b": _consumer_card("consumer-b", ["/api/data"]),
    }
    vault = _make_vault_with_cards(tmp_path, cards)
    mod = _load_capability_map()
    mod.generate_map(vault_dir=vault)

    content = (vault / "map.md").read_text()
    pipelines_section = content.split(BEGIN_PIPELINES)[1].split(END_PIPELINES)[0]

    # Machine edges contain "→" and "via GET"
    assert "→" not in pipelines_section or "via GET" not in pipelines_section, (
        "Machine-generated edge content found inside Human Pipelines section"
    )


# ---------------------------------------------------------------------------
# AC7: vault/index.md contains link to map.md
# ---------------------------------------------------------------------------

def test_ac7_vault_index_links_to_map():
    """AC7: The project index (vault/index.md) contains a link to map.md."""
    index_path = VAULT_DIR / "index.md"
    assert index_path.exists(), "vault/index.md does not exist"
    content = index_path.read_text()
    assert "map.md" in content, "vault/index.md does not link to map.md"


# ---------------------------------------------------------------------------
# AC8: SKILL.md references map generation and points to DESIGN.md §7
# ---------------------------------------------------------------------------

def test_ac8_skill_md_references_map_generation():
    """AC8: SKILL.md contains a section describing the map generation step."""
    assert SKILL_MD.exists(), "SKILL.md does not exist"
    content = SKILL_MD.read_text()
    # Should mention capability map or map generation
    assert "capability-map" in content.lower() or "capability map" in content.lower(), (
        "SKILL.md does not reference the capability map module"
    )


def test_ac8_skill_md_points_to_design_section():
    """AC8: SKILL.md references DESIGN.md §7 for rationale."""
    assert SKILL_MD.exists(), "SKILL.md does not exist"
    content = SKILL_MD.read_text()
    assert "DESIGN.md" in content and "§7" in content, (
        "SKILL.md does not point to DESIGN.md §7"
    )

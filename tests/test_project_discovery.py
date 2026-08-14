"""Tests for project_discovery.py — docs-first Discovery page."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import project_discovery  # noqa: E402
import project_flow  # noqa: E402
import render_site as site_mod  # noqa: E402


def _write_targets(tmp_path: Path, target: str, local: Path) -> Path:
    yaml_path = tmp_path / "targets.yaml"
    yaml_path.write_text(f"targets:\n  {target}:\n    local: {local}\n")
    return yaml_path


def _with_targets(yaml_path: Path):
    """Patch both modules that resolve local clones."""
    originals = (project_flow.TARGETS_YAML, project_discovery.TARGETS_YAML)
    project_flow.TARGETS_YAML = yaml_path
    project_discovery.TARGETS_YAML = yaml_path
    return originals


def _restore_targets(originals):
    project_flow.TARGETS_YAML, project_discovery.TARGETS_YAML = originals


def test_discovery_shows_product_steps_not_commander_template(tmp_path):
    local = tmp_path / "src"
    (local / "docs").mkdir(parents=True)
    (local / "docs" / "workflow.md").write_text(
        "# Workflow\n\ndriven by Commander.\n\n"
        "## Stage 1 — Bulk Create\n\nBA.\n\n"
        "## Stage 2 — Run Sprint\n\nCoder.\n"
    )
    (local / "PRODUCT.md").write_text(
        "# Product\n\n"
        "## Core User Flows\n\n"
        "1. **Pick account** — select the brand.\n"
        "2. **Build carousel** — compose slides.\n"
    )
    (local / "server.py").write_text("from routers import health\n")
    (local / "routers").mkdir()
    (local / "routers" / "health.py").write_text("x = 1\n")

    vault = tmp_path / "vault"
    project = vault / "projects" / "alpha"
    (project / "atlas").mkdir(parents=True)
    (project / "atlas" / "index.md").write_text("# Atlas\n")
    (project / "capability.md").write_text(
        "# Capability\n\n## What it is\n\nA carousel studio.\n"
    )
    snap = project / "raw" / "t"
    snap.mkdir(parents=True)
    (snap / "manifest.json").write_text("{}")
    (snap / "endpoints.json").write_text(json.dumps({"get_endpoints": []}))

    yaml_path = _write_targets(tmp_path, "alpha", local)
    originals = _with_targets(yaml_path)
    try:
        text = project_discovery.generate_discovery("alpha", vault).read_text()
    finally:
        _restore_targets(originals)

    assert "## Product flow" in text
    assert "Pick account" in text
    assert "Build carousel" in text
    assert "Bulk Create" not in text
    assert "Run Sprint" not in text
    assert "A carousel studio." in text
    assert "[[projects/alpha/flow]]" in text


def test_commander_template_alone_is_not_sold_as_product_flow(tmp_path):
    local = tmp_path / "src"
    (local / "docs").mkdir(parents=True)
    (local / "docs" / "workflow.md").write_text(
        "# Workflow\n\ndriven by Commander.\n\n"
        "## Stage 1 — Bulk Create\n\nBA.\n\n"
        "## Stage 2 — Run Sprint\n\nCoder.\n"
    )
    (local / "PRODUCT.md").write_text("# Product\n\nNo numbered flows here.\n")
    vault = tmp_path / "vault"
    (vault / "projects" / "alpha").mkdir(parents=True)
    yaml_path = _write_targets(tmp_path, "alpha", local)
    originals = _with_targets(yaml_path)
    try:
        text = project_discovery.generate_discovery("alpha", vault).read_text()
    finally:
        _restore_targets(originals)

    flow_section = text.split("## API map")[0]
    assert "Bulk Create" not in flow_section
    assert "How work ships" in flow_section or "Commander sprint template" in flow_section


def test_api_map_joins_atlas_when_path_cited(tmp_path):
    local = tmp_path / "src"
    local.mkdir()
    vault = tmp_path / "vault"
    project = vault / "projects" / "alpha"
    atlas = project / "atlas"
    snap = project / "raw" / "t"
    atlas.mkdir(parents=True)
    snap.mkdir(parents=True)
    (atlas / "index.md").write_text("# Atlas\n")
    (atlas / "health.md").write_text(
        "# Health\n\n"
        "- Route: `/api/health`\n"
        "- Key Files:\n"
        "  - `routers/health.py`\n"
    )
    (snap / "manifest.json").write_text("{}")
    (snap / "endpoints.json").write_text(json.dumps({
        "get_endpoints": [
            {
                "path": "/api/health",
                "description": "Health check",
                "example_response": "200 JSON — ok",
            },
            {
                "path": "/api/orphan",
                "description": "Orphan",
                "example_response": "200 JSON — none",
            },
        ]
    }))

    yaml_path = _write_targets(tmp_path, "alpha", local)
    originals = _with_targets(yaml_path)
    try:
        text = project_discovery.generate_discovery("alpha", vault).read_text()
    finally:
        _restore_targets(originals)

    assert "## API map" in text
    assert "`GET /api/health`" in text
    assert "[[projects/alpha/atlas/health]]" in text
    assert "`routers/health.py`" in text
    assert "`GET /api/orphan`" in text
    # Orphan row should show em dashes for atlas/handler
    orphan_line = [ln for ln in text.splitlines() if "/api/orphan" in ln][0]
    assert orphan_line.count("—") >= 2


def test_module_map_is_lr_mermaid_and_respects_node_cap(tmp_path):
    local = tmp_path / "src"
    local.mkdir()
    (local / "server.py").write_text(
        "from routers import a\nfrom services import b\n"
    )
    (local / "routers").mkdir()
    (local / "services").mkdir()
    (local / "apps").mkdir()
    for i in range(20):
        (local / "apps" / f"pkg{i}").mkdir()
        (local / f"extra{i}.py").write_text("x = 1\n")

    vault = tmp_path / "vault"
    (vault / "projects" / "alpha").mkdir(parents=True)
    yaml_path = _write_targets(tmp_path, "alpha", local)
    originals = _with_targets(yaml_path)
    try:
        text = project_discovery.generate_discovery("alpha", vault).read_text()
    finally:
        _restore_targets(originals)

    assert "## Module map" in text
    assert "```mermaid" in text
    assert "flowchart LR" in text
    block = text.split("```mermaid")[1].split("```")[0]
    node_lines = [
        ln for ln in block.splitlines()
        if "[" in ln and "-->" not in ln and "flowchart" not in ln
    ]
    assert 1 <= len(node_lines) <= project_discovery._MODULE_NODE_CAP
    assert "omitted for readability" in text
    assert "-->" in block
    assert "server.py" in block


def test_missing_local_has_honest_empty_sections(tmp_path):
    vault = tmp_path / "vault"
    project = vault / "projects" / "ghost"
    project.mkdir(parents=True)
    yaml_path = tmp_path / "targets.yaml"
    yaml_path.write_text("targets:\n  ghost: {}\n")
    originals = _with_targets(yaml_path)
    try:
        text = project_discovery.generate_discovery("ghost", vault).read_text()
    finally:
        _restore_targets(originals)

    assert "## Product flow" in text
    assert "## API map" in text
    assert "## Module map" in text
    assert "No local clone" in text or "No entry files" in text or "No product flow" in text
    assert "No GET endpoints" in text
    assert "[[projects/ghost/situation|Situation]]" in text


def test_sidebar_puts_discovery_before_situation(tmp_path):
    v = tmp_path / "vault"
    (v / "projects" / "alpha").mkdir(parents=True)
    (v / "index.md").write_text("# Index\n")
    (v / "projects" / "alpha" / "discovery.md").write_text("# Discovery\n")
    (v / "projects" / "alpha" / "situation.md").write_text("# Situation\n")
    out = tmp_path / "site"
    site_mod.generate_site(v, out)
    page = (out / "notes" / "projects" / "alpha" / "discovery.html").read_text()
    # In the project group, discovery link should appear before situation
    block = page.split("<summary>alpha</summary>")[1].split("</details>")[0]
    assert block.index("discovery.html") < block.index("situation.html")
    landing = (out / "index.html").read_text()
    assert 'href="notes/projects/alpha/discovery.html"' in landing

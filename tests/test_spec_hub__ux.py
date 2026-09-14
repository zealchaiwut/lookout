"""Tests for Spec Hub (spec.md) — Product / Requirements / Design / API / Plan."""
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import project_spec_view  # noqa: E402
import render_site  # noqa: E402

PRODUCT = """# PRODUCT

## The problem (diagnosis, not guess)

Content-mix problem driven by supply.

## What this tool must do — three jobs

1. **Find the wave.** Surface topics with audience.
2. **Prove the recipe.** Replace hunches with data.

Explicit non-goal: **volume.** Fewer, better posts.

## Core concepts

- **Watchlist** — admired accounts.
- **Tiers** — gold / silver / bronze.

## Milestones and exit tests

| # | Batch | Exit test |
|---|-------|-----------|
| 1 | Core engine | Paste posts → tiers |

## Hard constraints

- **Language:** Thai + English.
- **Scale:** 5–15 accounts, SQLite.
"""

DESIGN = """# DESIGN

## Direction: race telemetry

The subject's world is road racing.

## Signature element

**The podium rail.** Medal dots everywhere tiers appear.

## Palette

| Token | Hex | Use |
|---|---|---|
| `--track` | `#F2F3F1` | App background |
| `--signal` | `#E8590C` | Accent |

## Typography

- **Body:** IBM Plex Sans Thai.
- **Data:** IBM Plex Mono.

## Layout

```
┌───┬────┐
│ A │ B  │
└───┴────┘
```
"""


def _setup(tmp_path, monkeypatch, *, in_vault=False):
    local = tmp_path / "clone"
    local.mkdir()
    vault = tmp_path / "vault"
    targets = tmp_path / "targets.yaml"
    targets.write_text(yaml.dump({
        "targets": {"demo": {"local": str(local), "github": "a/b", "commander_slug": "demo"}}
    }))
    monkeypatch.setattr(project_spec_view, "TARGETS_YAML", targets)
    if in_vault:
        spec = vault / "projects" / "demo" / "spec"
        spec.mkdir(parents=True)
        (spec / "PRODUCT.md").write_text(PRODUCT)
        (spec / "DESIGN.md").write_text(DESIGN)
        (spec / "api.yaml").write_text(
            "openapi: '3.0.3'\ninfo: {title: demo, version: '0'}\n"
            "paths: {'/x': {get: {responses: {'200': {description: ok}}}}}\n"
        )
        (spec / "plan.md").write_text("# Spec plan — demo\n\n- [ ] Review\n")
        (spec / "status.yaml").write_text(
            "status: draft\nupdated: '2026-09-14T00:00:00Z'\n"
            "history:\n- status: draft\n  at: '2026-09-14T00:00:00Z'\n"
            "  note: workspace created\nfiles: {}\nnotes: ''\n"
        )
    else:
        (local / "PRODUCT.md").write_text(PRODUCT)
        (local / "DESIGN.md").write_text(DESIGN)
    return vault


def test_spec_hub_panes_from_clone(tmp_path, monkeypatch):
    vault = _setup(tmp_path, monkeypatch, in_vault=False)
    out = project_spec_view.generate_spec("demo", vault)
    assert out.name == "spec.md"
    text = out.read_text()
    assert "## Product" in text
    assert "### The problem" in text
    assert "Find the wave" in text
    assert "## Requirements" in text
    assert "Hard constraints" in text
    assert "Thai" in text
    assert "Milestones" in text
    assert "Core engine" in text
    assert "## Design" in text
    assert "podium rail" in text
    assert "```palette" in text
    assert "--track" in text
    assert "IBM Plex" in text
    assert "┌───┬────┐" in text
    assert "## API" in text
    assert "## Plan" in text
    stub = (vault / "projects" / "demo" / "spec-view.md").read_text()
    assert "Spec Hub" in stub or "projects/demo/spec" in stub


def test_spec_hub_prefers_vault_and_shows_status(tmp_path, monkeypatch):
    vault = _setup(tmp_path, monkeypatch, in_vault=True)
    # Clone has different (should be ignored) product
    local = tmp_path / "clone"
    (local / "PRODUCT.md").write_text("# PRODUCT\n\n## Core concepts\n\n- **CloneOnly**\n")
    text = project_spec_view.generate_spec("demo", vault).read_text()
    assert "Watchlist" in text
    assert "CloneOnly" not in text
    assert "**Status:** `draft`" in text
    assert "documented path" in text
    assert "workspace created" in text


def test_heading_slug_and_palette_render():
    assert render_site._slugify_heading("Product") == "product"
    assert render_site._slugify_heading("Hard constraints") == "hard-constraints"
    html = render_site.render_markdown(
        "# Title\n\n## Design\n\n```palette\n--signal|#E8590C|Accent\n```\n"
    )
    assert 'id="design"' in html
    assert "palette-strip" in html
    assert "#E8590C" in html

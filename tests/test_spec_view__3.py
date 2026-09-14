"""Tests for human-readable Spec Hub (replaces thin spec-view)."""
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import project_spec_view  # noqa: E402

PRODUCT = """# PRODUCT

## The problem

Supply problem.

## What this tool must do — three jobs

1. **Find the wave.** Surface topics with audience.
2. **Prove the recipe.** Replace hunches with data.

## Core concepts

- **Watchlist** — admired accounts.
- **Tiers** — gold / silver / bronze.

## Hard constraints

- **Language:** Thai + English.
"""

DESIGN = """# DESIGN

## Direction: race telemetry

The subject's world is road racing.

## Signature element

Podium rail.

## Palette

| Token | Hex | Use |
|---|---|---|
| `--track` | `#F2F3F1` | App background |
| `--signal` | `#E8590C` | Accent |

## Typography

- **Body:** IBM Plex Sans.

## Layout

```
┌───┬────┐
│ A │ B  │
└───┴────┘
```
"""


def test_generate_spec_view_extracts_product_and_design(tmp_path, monkeypatch):
    local = tmp_path / "clone"
    local.mkdir()
    (local / "PRODUCT.md").write_text(PRODUCT)
    (local / "DESIGN.md").write_text(DESIGN)
    vault = tmp_path / "vault"
    targets = tmp_path / "targets.yaml"
    targets.write_text(yaml.dump({
        "targets": {"demo": {"local": str(local), "github": "a/b", "commander_slug": "demo"}}
    }))
    monkeypatch.setattr(project_spec_view, "TARGETS_YAML", targets)
    out = project_spec_view.generate_spec_view("demo", vault)
    assert out.name == "spec.md"
    text = out.read_text()
    assert "## Product" in text
    assert "## Requirements" in text
    assert "Find the wave" in text
    assert "Watchlist" in text
    assert "## Design" in text
    assert "--track" in text
    assert "┌───┬────┐" in text

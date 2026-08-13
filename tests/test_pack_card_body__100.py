"""Tests for issue #100: packs carry the capability card body and open questions.

A pack holding only a one-liner is decorative — the read surfaces are what a
reader or an agent needs to work against a target.
"""
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pack  # noqa: E402

SITUATION = """---
target: alpha
---

## One-liner

`alpha` — Alpha does things.
_(source: manifest.json)_

## Capacity

Clear to start
_(source: manifest.json)_

## Open questions

- AQ1: Should the widget cache expire?
_(source: questions.json)_
"""

SITUATION_NO_Q = SITUATION.replace(
    "- AQ1: Should the widget cache expire?", "_No open questions._"
)

CARD = """# alpha — Capability Card

## What it is

Alpha ingests widgets and ranks them.

## Data it owns

- Snapshots under raw/

## Read surfaces

- `GET /api/widgets` — list widgets
  - Example: `curl http://localhost:8000/api/widgets`
- `GET /api/health` — health
  - Example: `curl http://localhost:8000/api/health`

## How to make it do things

- **Commander slug:** `alpha`

## Constraints

- Read-only.

## Notes for AI

SENTINEL-SCRATCHPAD
"""


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    (v / "projects" / "alpha").mkdir(parents=True)
    (v / "packs").mkdir()
    (v / "projects" / "alpha" / "situation.md").write_text(SITUATION)
    (v / "projects" / "alpha" / "capability.md").write_text(CARD)
    (v / "map.md").write_text("# Capability Map\n\n- a → b\n")
    (v / "agents.md").write_text(
        "# Agents\n\n## Read-Only Invariant\n\nNo writes to targets.\n"
    )
    ty = tmp_path / "targets.yaml"
    ty.write_text(yaml.dump({"targets": {"alpha": {"local": "/tmp/alpha"}}}))
    return v, ty


def _pack_text(vault, ty):
    return pack.generate_pack(targets=["alpha"], vault_dir=vault, targets_yaml=ty).read_text()


def test_pack_includes_every_read_surface(vault):
    v, ty = vault
    text = _pack_text(v, ty)
    assert "`GET /api/widgets`" in text
    assert "`GET /api/health`" in text


def test_pack_includes_the_card_description(vault):
    v, ty = vault
    assert "Alpha ingests widgets and ranks them." in _pack_text(v, ty)


def test_pack_includes_data_owned_and_constraints(vault):
    v, ty = vault
    text = _pack_text(v, ty)
    assert "## Data it owns" in text
    assert "## Constraints" in text


def test_pack_excludes_the_notes_for_ai_scratchpad(vault):
    """Preserved notes are a scratchpad, not a description of the target."""
    v, ty = vault
    assert "SENTINEL-SCRATCHPAD" not in _pack_text(v, ty)


def test_pack_includes_open_questions(vault):
    v, ty = vault
    text = _pack_text(v, ty)
    assert "### Open questions" in text
    assert "AQ1: Should the widget cache expire?" in text


def test_pack_omits_the_heading_when_there_are_no_open_questions(vault):
    """A heading that says nothing is worse than its absence."""
    v, ty = vault
    (v / "projects" / "alpha" / "situation.md").write_text(SITUATION_NO_Q)
    text = _pack_text(v, ty)
    assert "### Open questions" not in text


def test_pack_still_carries_the_one_liner_and_capacity(vault):
    v, ty = vault
    text = _pack_text(v, ty)
    assert "Alpha does things." in text
    assert "Clear to start" in text


def test_provenance_lines_are_stripped(vault):
    v, ty = vault
    assert "_(source:" not in _pack_text(v, ty)


def test_pack_still_carries_map_and_ground_rules(vault):
    v, ty = vault
    text = _pack_text(v, ty)
    assert "Capability Map" in text
    assert "Read-Only Invariant" in text


def test_missing_capability_card_does_not_break_the_pack(vault):
    v, ty = vault
    (v / "projects" / "alpha" / "capability.md").unlink()
    text = _pack_text(v, ty)
    assert "Alpha does things." in text
    assert "Read-Only Invariant" in text


def test_card_body_is_what_makes_the_pack_substantial(vault):
    """Regression guard: the pack once carried none of the card at all.

    Measured against the same pack with the card removed, rather than an
    arbitrary byte threshold that would drift with fixture size.
    """
    v, ty = vault
    with_card = len(_pack_text(v, ty))
    (v / "projects" / "alpha" / "capability.md").unlink()
    without_card = len(_pack_text(v, ty))
    assert with_card > without_card * 2, (
        f"card body added only {with_card - without_card} bytes"
    )

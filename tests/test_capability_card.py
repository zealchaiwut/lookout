"""Tests for issue #12: capability card generator.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CAPABILITY_CARD_PY = REPO_ROOT / "capability_card.py"

FIVE_REQUIRED_SECTIONS = [
    "## What it is",
    "## Data it owns",
    "## Read surfaces",
    "## How to make it do things",
    "## Constraints",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_capability_card(module_name="capability_card_test"):
    spec = importlib.util.spec_from_file_location(module_name, str(CAPABILITY_CARD_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_snapshot(tmp_path, target="perf-coach", endpoints=None, timestamp="2026-03-12T00:00:00Z"):
    """Create a minimal snapshot directory for a target."""
    snap_dir = tmp_path / "vault" / "projects" / target / "raw" / timestamp
    snap_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "timestamp": timestamp,
        "target": target,
        "health": {"status": "healthy"},
        "sources": {},
    }
    (snap_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    if endpoints is not None:
        (snap_dir / "endpoints.json").write_text(
            json.dumps({"get_endpoints": endpoints}, indent=2)
        )

    return snap_dir


def _make_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    return vault


def _count_tokens(text):
    """Simple whitespace tokenizer matching the project's standard."""
    return len(text.split())


# ---------------------------------------------------------------------------
# Script existence
# ---------------------------------------------------------------------------

def test_capability_card_py_exists():
    assert CAPABILITY_CARD_PY.exists(), "capability_card.py must exist at repo root"


# ---------------------------------------------------------------------------
# AC3: only real GET endpoints from snapshot evidence; no fabricated ones
# ---------------------------------------------------------------------------

def test_only_real_endpoints_listed(tmp_path):
    """AC3: capability.md lists every real GET endpoint from snapshot evidence."""
    vault = _make_vault(tmp_path)
    endpoints = [
        {"path": "/api/health", "description": "Health check"},
        {"path": "/api/briefs/perf-coach", "description": "Get project brief"},
    ]
    _make_snapshot(tmp_path, endpoints=endpoints)

    mod = _load_capability_card("cap_ac3a")
    mod.generate_capability_card(
        target="perf-coach",
        vault_dir=vault,
    )

    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    assert cap_md.exists(), "capability.md must be generated"
    content = cap_md.read_text()

    for ep in endpoints:
        assert ep["path"] in content, (
            f"Real endpoint {ep['path']} must appear in capability.md"
        )


def test_no_fabricated_endpoints_when_none_in_snapshot(tmp_path):
    """AC3: when snapshot has no endpoints.json, no fabricated endpoints appear."""
    vault = _make_vault(tmp_path)
    _make_snapshot(tmp_path, endpoints=None)

    mod = _load_capability_card("cap_ac3b")
    mod.generate_capability_card(
        target="perf-coach",
        vault_dir=vault,
    )

    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    content = cap_md.read_text()

    # Common fabricated/placeholder patterns must not appear
    for placeholder in ["/api/example", "/api/placeholder", "/api/foo", "GET /example"]:
        assert placeholder not in content, (
            f"Placeholder endpoint {placeholder!r} must not appear in capability.md"
        )


def test_snapshot_endpoints_all_present(tmp_path):
    """AC3: every endpoint in snapshot evidence is listed; none are omitted."""
    vault = _make_vault(tmp_path)
    endpoints = [
        {"path": "/api/health", "description": "Health check"},
        {"path": "/api/sprints", "description": "Sprint list"},
        {"path": "/api/todos", "description": "Todo list"},
    ]
    _make_snapshot(tmp_path, endpoints=endpoints)

    mod = _load_capability_card("cap_ac3c")
    mod.generate_capability_card(
        target="perf-coach",
        vault_dir=vault,
    )

    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    content = cap_md.read_text()
    for ep in endpoints:
        assert ep["path"] in content, f"Endpoint {ep['path']} omitted from capability.md"


# ---------------------------------------------------------------------------
# AC4: capability.md ≤1500 tokens and contains all five required sections
# ---------------------------------------------------------------------------

def test_capability_card_has_five_sections(tmp_path):
    """AC4: capability.md contains all five required sections."""
    vault = _make_vault(tmp_path)
    _make_snapshot(tmp_path)

    mod = _load_capability_card("cap_ac4a")
    mod.generate_capability_card(
        target="perf-coach",
        vault_dir=vault,
    )

    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    content = cap_md.read_text()
    for section in FIVE_REQUIRED_SECTIONS:
        assert section in content, f"Required section missing: {section!r}"


def test_capability_card_within_token_limit(tmp_path):
    """AC4: capability.md is within 1500 tokens."""
    vault = _make_vault(tmp_path)
    endpoints = [{"path": f"/api/endpoint-{i}", "description": f"Endpoint {i}"}
                 for i in range(20)]
    _make_snapshot(tmp_path, endpoints=endpoints)

    mod = _load_capability_card("cap_ac4b")
    mod.generate_capability_card(
        target="perf-coach",
        vault_dir=vault,
    )

    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    content = cap_md.read_text()
    token_count = mod.count_tokens(content)
    assert token_count <= 1500, (
        f"capability.md must be ≤1500 tokens, got {token_count}"
    )


def test_what_it_is_at_most_two_sentences(tmp_path):
    """AC4: 'What it is' section contains ≤2 sentences."""
    vault = _make_vault(tmp_path)
    _make_snapshot(tmp_path)

    mod = _load_capability_card("cap_ac4c")
    mod.generate_capability_card(
        target="perf-coach",
        vault_dir=vault,
    )

    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    content = cap_md.read_text()

    # Extract content of "What it is" section
    m = re.search(r"## What it is\s+(.*?)(?=\n## |\Z)", content, re.DOTALL)
    assert m, "Could not find 'What it is' section content"
    section_text = m.group(1).strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", section_text) if s.strip()]
    assert len(sentences) <= 2, (
        f"'What it is' must be ≤2 sentences, found {len(sentences)}: {sentences}"
    )


# ---------------------------------------------------------------------------
# AC5: SENTINEL in Notes for AI preserved across 3 regenerations
# ---------------------------------------------------------------------------

def test_sentinel_preserved_across_three_regenerations(tmp_path):
    """AC5: SENTINEL-XYZ-001 in 'Notes for AI' section survives 3 regenerations."""
    vault = _make_vault(tmp_path)
    _make_snapshot(tmp_path)

    mod = _load_capability_card("cap_ac5")

    # Initial generation
    mod.generate_capability_card(target="perf-coach", vault_dir=vault)
    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    content = cap_md.read_text()

    # Inject SENTINEL into Notes for AI section
    sentinel = "SENTINEL-XYZ-001"
    assert "## Notes for AI" in content, "capability.md must have 'Notes for AI' section"
    content_with_sentinel = content.replace(
        "## Notes for AI",
        f"## Notes for AI\n\n{sentinel}",
        1,
    )
    cap_md.write_text(content_with_sentinel)

    # Verify sentinel is there before the 3 runs
    assert sentinel in cap_md.read_text()

    # Run regeneration three times
    for i in range(3):
        mod2 = _load_capability_card(f"cap_ac5_run{i}")
        mod2.generate_capability_card(target="perf-coach", vault_dir=vault)
        result = cap_md.read_text()
        assert sentinel in result, (
            f"SENTINEL-XYZ-001 must be preserved after regeneration run {i + 1}"
        )


def test_sentinel_section_content_not_altered(tmp_path):
    """AC5: No other content in Notes for AI is altered during regeneration."""
    vault = _make_vault(tmp_path)
    _make_snapshot(tmp_path)

    mod = _load_capability_card("cap_ac5b")
    mod.generate_capability_card(target="perf-coach", vault_dir=vault)
    cap_md = vault / "projects" / "perf-coach" / "capability.md"

    # Add multiple notes including sentinel
    original_notes = "SENTINEL-XYZ-001\n\nThis is a custom note that must survive.\n"
    content = cap_md.read_text().replace(
        "## Notes for AI",
        f"## Notes for AI\n\n{original_notes}",
        1,
    )
    cap_md.write_text(content)

    mod2 = _load_capability_card("cap_ac5b_regen")
    mod2.generate_capability_card(target="perf-coach", vault_dir=vault)

    result = cap_md.read_text()
    assert "SENTINEL-XYZ-001" in result
    assert "This is a custom note that must survive." in result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def test_count_tokens_function_exists():
    """capability_card.py must expose a count_tokens(text) function."""
    mod = _load_capability_card("cap_api")
    assert hasattr(mod, "count_tokens"), "count_tokens(text) must be defined"
    result = mod.count_tokens("hello world foo")
    assert isinstance(result, int) and result > 0


def test_generate_capability_card_function_exists():
    """capability_card.py must expose generate_capability_card(target, vault_dir)."""
    mod = _load_capability_card("cap_api2")
    assert hasattr(mod, "generate_capability_card"), (
        "generate_capability_card(target, vault_dir) must be defined"
    )


def test_cli_entry_point_exists():
    """capability_card.py must have a CLI entry point."""
    source = CAPABILITY_CARD_PY.read_text()
    assert "def main(" in source or 'if __name__ == "__main__"' in source


# ---------------------------------------------------------------------------
# AC7: generated output passes lint (no broken wikilinks)
# ---------------------------------------------------------------------------

def test_no_wikilinks_in_generated_capability_md(tmp_path):
    """AC7: capability.md must not contain broken [[wikilinks]]."""
    vault = _make_vault(tmp_path)
    _make_snapshot(tmp_path)

    mod = _load_capability_card("cap_ac7")
    mod.generate_capability_card(target="perf-coach", vault_dir=vault)

    cap_md = vault / "projects" / "perf-coach" / "capability.md"
    content = cap_md.read_text()
    # No [[wikilinks]] to avoid lint failures (lint checks wikilinks resolve)
    wikilinks = re.findall(r"\[\[([^\]]+)\]\]", content)
    assert len(wikilinks) == 0, (
        f"capability.md must not contain wikilinks (lint-unsafe): {wikilinks}"
    )

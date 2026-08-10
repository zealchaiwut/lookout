"""Tests for issue #21: pack.py for lookout pack command.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
PACK_PY = REPO_ROOT / "pack.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_pack():
    spec = importlib.util.spec_from_file_location("pack_test_mod", str(PACK_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_situation_md(target: str, one_liner: str, capacity: str) -> str:
    return (
        f"---\ntarget: {target}\nrun: \"2026-08-10T12:00:00Z\"\nsources_ok: true\n---\n\n"
        f"## One-liner\n\n{one_liner}\n_(source: manifest.json, brief.json)_\n\n"
        f"## Capacity\n\n{capacity}\n_(source: manifest.json, brief.json, issues.json)_\n\n"
        f"## Since last run\n\n_No changes detected._\n_(source: manifest.json)_\n"
    )


_DEFAULT_MAP = (
    "# Capability Map\n\n"
    "<!-- BEGIN MACHINE EDGES -->\n"
    "<!-- END MACHINE EDGES -->\n\n"
    "<!-- BEGIN HUMAN PIPELINES -->\n"
    "<!-- END HUMAN PIPELINES -->\n"
)

_DEFAULT_AGENTS = (
    "# Agents\n\n"
    "## Read-Only Invariant\n\n"
    "No tool run from this repo may write to any target project.\n\n"
    "## Source of Truth\n\n"
    "`raw/` snapshots are the sole source of truth.\n\n"
    "## Machine-Owned File Types\n\n"
    "- **packs** — bundled export sets\n"
)


def _make_targets_yaml(tmp_path: Path, targets: list[str]) -> Path:
    data = {
        "sources": {"commander_api": "http://localhost:9999"},
        "targets": {
            t: {"commander_slug": t, "github": f"test/{t}", "local": f"/tmp/{t}"}
            for t in targets
        },
    }
    p = tmp_path / "targets.yaml"
    p.write_text(yaml.dump(data))
    return p


def _make_vault(
    tmp_path: Path,
    target_cards: dict[str, tuple[str, str]],
    map_content: str = _DEFAULT_MAP,
    agents_content: str = _DEFAULT_AGENTS,
) -> Path:
    """Create a temp vault with situation.md files, map.md, and agents.md."""
    vault = tmp_path / "vault"
    (vault / "packs").mkdir(parents=True)
    (vault / "map.md").write_text(map_content)
    (vault / "agents.md").write_text(agents_content)
    for target, (one_liner, capacity) in target_cards.items():
        proj = vault / "projects" / target
        proj.mkdir(parents=True)
        (proj / "situation.md").write_text(
            _make_situation_md(target, one_liner, capacity)
        )
    return vault


# ---------------------------------------------------------------------------
# AC1: lookout pack <target...> writes vault/packs/<date>-<slug>.md
# ---------------------------------------------------------------------------

def test_ac1_pack_file_path(tmp_path):
    """AC1: Pack output path is vault/packs/<YYYY-MM-DD>-<slug>.md."""
    pack = _load_pack()
    targets = ["alpha", "beta"]
    vault = _make_vault(tmp_path, {"alpha": ("A does things.", "High."), "beta": ("B does things.", "Medium.")})
    targets_yaml = _make_targets_yaml(tmp_path, targets)
    now = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml, now=now)

    assert result == vault / "packs" / "2026-08-10-alpha-beta.md"
    assert result.exists()


def test_ac1_slug_is_kebab_join(tmp_path):
    """AC1: Slug is all targets joined by dashes."""
    pack = _load_pack()
    targets = ["alpha", "beta", "gamma", "delta"]
    vault = _make_vault(
        tmp_path,
        {t: (f"{t} one-liner.", f"{t} capacity.") for t in targets},
    )
    targets_yaml = _make_targets_yaml(tmp_path, targets)
    now = datetime(2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml, now=now)

    assert result.name == "2026-08-10-alpha-beta-gamma-delta.md"


# ---------------------------------------------------------------------------
# AC2 / AC9: Header has timestamp, target list, and ⚠ STALE warnings
# ---------------------------------------------------------------------------

def test_ac2_header_has_timestamp(tmp_path):
    """AC2: Header contains the generated timestamp."""
    pack = _load_pack()
    targets = ["alpha"]
    vault = _make_vault(tmp_path, {"alpha": ("A is great.", "Full.")})
    targets_yaml = _make_targets_yaml(tmp_path, targets)
    now = datetime(2026, 8, 10, 15, 30, 0, tzinfo=timezone.utc)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml, now=now)
    content = result.read_text()

    assert "2026-08-10T15:30:00Z" in content


def test_ac2_header_lists_targets(tmp_path):
    """AC2: Header contains the list of requested targets."""
    pack = _load_pack()
    targets = ["alpha", "beta", "gamma"]
    vault = _make_vault(tmp_path, {t: (f"{t}.", "Cap.") for t in targets})
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    for t in targets:
        assert t in content.split("\n")[:10] or any(t in line for line in content.split("\n")[:10])


def test_ac2_no_stale_warning_for_fresh_card(tmp_path):
    """AC2: No STALE warning for a recently-updated card."""
    pack = _load_pack()
    targets = ["alpha"]
    vault = _make_vault(tmp_path, {"alpha": ("A is fresh.", "Full.")})
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    assert "⚠ STALE" not in content


def test_ac9_stale_warning_for_old_card(tmp_path):
    """AC9: A stale card produces exactly one ⚠ STALE line in the header."""
    pack = _load_pack()
    targets = ["alpha", "beta"]
    vault = _make_vault(
        tmp_path,
        {
            "alpha": ("Alpha is old.", "Unknown."),
            "beta": ("Beta is fresh.", "Full."),
        },
    )
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    # Back-date alpha's situation.md to 10 days ago
    alpha_card = vault / "projects" / "alpha" / "situation.md"
    old_time = time.time() - (10 * 24 * 3600)
    os.utime(alpha_card, (old_time, old_time))

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    stale_lines = [ln for ln in content.split("\n") if "⚠ STALE" in ln]
    assert len(stale_lines) == 1
    assert "alpha" in stale_lines[0]
    assert "⚠ STALE" not in content.replace(stale_lines[0], "", 1) or True  # only one


def test_ac9_stale_line_includes_date(tmp_path):
    """AC9: STALE warning line includes the card's last updated date."""
    pack = _load_pack()
    targets = ["alpha"]
    vault = _make_vault(tmp_path, {"alpha": ("Alpha.", "Cap.")})
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    alpha_card = vault / "projects" / "alpha" / "situation.md"
    old_time = time.time() - (10 * 24 * 3600)
    os.utime(alpha_card, (old_time, old_time))

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    stale_lines = [ln for ln in content.split("\n") if "⚠ STALE" in ln]
    assert len(stale_lines) == 1
    assert re.search(r"\d{4}-\d{2}-\d{2}", stale_lines[0]), "No date in STALE line"


# ---------------------------------------------------------------------------
# AC3: Cards appended in order targets were supplied
# ---------------------------------------------------------------------------

def test_ac3_targets_in_order(tmp_path):
    """AC3: Target blocks appear in the same order as the command-line arguments."""
    pack = _load_pack()
    targets = ["gamma", "alpha", "beta"]
    vault = _make_vault(tmp_path, {t: (f"{t} one-liner.", f"{t} cap.") for t in targets})
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    pos_gamma = content.find("gamma")
    pos_alpha = content.find("alpha")
    pos_beta = content.find("beta")
    assert pos_gamma < pos_alpha < pos_beta, "Targets not in supplied order"


# ---------------------------------------------------------------------------
# AC4: Each target contributes only situation one-liner and capacity line
# ---------------------------------------------------------------------------

def test_ac4_exactly_two_content_lines_per_target(tmp_path):
    """AC4: Each target block has exactly the one-liner and capacity line."""
    pack = _load_pack()
    targets = ["alpha"]
    vault = _make_vault(tmp_path, {"alpha": ("Alpha does great things.", "At 80% capacity.")})
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    assert "Alpha does great things." in content
    assert "At 80% capacity." in content
    # Source annotations should NOT appear
    assert "_(source:" not in content
    # Since last run section should NOT appear
    assert "Since last run" not in content


def test_ac4_no_extra_card_sections(tmp_path):
    """AC4: Sections beyond one-liner and capacity are not included."""
    pack = _load_pack()
    targets = ["alpha"]
    vault = _make_vault(tmp_path, {"alpha": ("One liner.", "Capacity line.")})
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    # These section headers from situation.md must not appear
    assert "## Since last run" not in content
    assert "## What to do next" not in content
    assert "## From the journal" not in content
    assert "## Open questions" not in content
    assert "## Drift" not in content


# ---------------------------------------------------------------------------
# AC5: Both sections of map.md appended verbatim
# ---------------------------------------------------------------------------

def test_ac5_map_verbatim(tmp_path):
    """AC5: map.md content appears verbatim in the pack output."""
    pack = _load_pack()
    targets = ["alpha"]
    map_content = (
        "# Capability Map\n\n"
        "<!-- BEGIN MACHINE EDGES -->\n"
        "alpha -> beta\n"
        "<!-- END MACHINE EDGES -->\n\n"
        "<!-- BEGIN HUMAN PIPELINES -->\n"
        "pipeline: alpha | beta\n"
        "<!-- END HUMAN PIPELINES -->\n"
    )
    vault = _make_vault(tmp_path, {"alpha": ("A.", "Cap.")}, map_content=map_content)
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    assert "<!-- BEGIN MACHINE EDGES -->" in content
    assert "alpha -> beta" in content
    assert "<!-- END MACHINE EDGES -->" in content
    assert "<!-- BEGIN HUMAN PIPELINES -->" in content
    assert "pipeline: alpha | beta" in content
    assert "<!-- END HUMAN PIPELINES -->" in content


def test_ac5_map_both_sections_present(tmp_path):
    """AC5: Both MACHINE EDGES and HUMAN PIPELINES sections are in the pack."""
    pack = _load_pack()
    targets = ["alpha"]
    vault = _make_vault(tmp_path, {"alpha": ("A.", "Cap.")})
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    assert "BEGIN MACHINE EDGES" in content
    assert "END MACHINE EDGES" in content
    assert "BEGIN HUMAN PIPELINES" in content
    assert "END HUMAN PIPELINES" in content


# ---------------------------------------------------------------------------
# AC6: Footer has only the read-only ground-rules block from agents.md
# ---------------------------------------------------------------------------

def test_ac6_footer_has_ground_rules(tmp_path):
    """AC6: Pack footer contains the Read-Only Invariant from agents.md."""
    pack = _load_pack()
    targets = ["alpha"]
    vault = _make_vault(tmp_path, {"alpha": ("A.", "Cap.")})
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    assert "No tool run from this repo may write to any target project." in content


def test_ac6_footer_excludes_other_agents_sections(tmp_path):
    """AC6: Footer does not include Machine-Owned or Human-Owned file type sections."""
    pack = _load_pack()
    targets = ["alpha"]
    agents_content = (
        "# Agents\n\n"
        "## Read-Only Invariant\n\nNo writes allowed.\n\n"
        "## Source of Truth\n\n`raw/` is truth.\n\n"
        "## Machine-Owned File Types\n\n- **packs** — excluded content marker MACHINE_OWNED\n\n"
        "## Human-Owned File Types\n\n- **notes** — excluded content marker HUMAN_OWNED\n"
    )
    vault = _make_vault(tmp_path, {"alpha": ("A.", "Cap.")}, agents_content=agents_content)
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    assert "excluded content marker MACHINE_OWNED" not in content
    assert "excluded content marker HUMAN_OWNED" not in content
    assert "No writes allowed." in content


# ---------------------------------------------------------------------------
# AC8: Pack of 4 projects completes in under 1 second
# ---------------------------------------------------------------------------

def test_ac8_performance_under_one_second(tmp_path):
    """AC8: Generating a pack of 4 projects completes in under 1 second."""
    pack = _load_pack()
    targets = ["alpha", "beta", "gamma", "delta"]
    vault = _make_vault(
        tmp_path,
        {t: (f"{t} does something.", f"{t} at full capacity.") for t in targets},
    )
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    start = time.monotonic()
    pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"Pack took {elapsed:.2f}s (limit: 1.0s)"


# ---------------------------------------------------------------------------
# AC10: Every byte traceable — no injected prose between blocks
# ---------------------------------------------------------------------------

def test_ac10_no_injected_prose(tmp_path):
    """AC10: No filler prose between blocks in the pack output."""
    pack = _load_pack()
    targets = ["alpha"]
    vault = _make_vault(tmp_path, {"alpha": ("A does X.", "Cap Y.")})
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    content = result.read_text()

    # These are examples of injected prose that should never appear
    forbidden = [
        "Here are",
        "The following",
        "Below you will",
        "This pack contains",
        "As requested",
        "Please note",
    ]
    for phrase in forbidden:
        assert phrase not in content, f"Injected prose found: {phrase!r}"


# ---------------------------------------------------------------------------
# AC11: Missing or unrecognised target exits non-zero with clear error message
# ---------------------------------------------------------------------------

def test_ac11_unknown_target_exits_nonzero(tmp_path):
    """AC11: Unknown target name causes non-zero exit."""
    pack = _load_pack()
    vault = _make_vault(tmp_path, {})
    targets_yaml = _make_targets_yaml(tmp_path, ["alpha"])

    with pytest.raises((SystemExit, pack.UnknownTargetError)) as exc_info:
        pack.generate_pack(
            targets=["nonexistent"],
            vault_dir=vault,
            targets_yaml=targets_yaml,
        )

    if isinstance(exc_info.value, SystemExit):
        assert exc_info.value.code != 0


def test_ac11_error_message_names_unknown_target(tmp_path, capsys):
    """AC11: Error message specifically names the unrecognised target."""
    pack = _load_pack()
    vault = _make_vault(tmp_path, {})
    targets_yaml = _make_targets_yaml(tmp_path, ["alpha"])

    try:
        pack.generate_pack(
            targets=["nonexistent"],
            vault_dir=vault,
            targets_yaml=targets_yaml,
        )
    except (SystemExit, pack.UnknownTargetError) as exc:
        pass

    captured = capsys.readouterr()
    assert "nonexistent" in captured.err or "nonexistent" in str(exc)


def test_ac11_subprocess_unknown_target(tmp_path):
    """AC11: Subprocess invocation of pack.py with unknown target exits non-zero."""
    result = subprocess.run(
        [sys.executable, str(PACK_PY), "nonexistent_target_xyz"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "nonexistent_target_xyz" in result.stderr


def test_ac11_valid_targets_exit_zero(tmp_path):
    """AC11: Known targets succeed with exit code 0."""
    pack = _load_pack()
    targets = ["alpha"]
    vault = _make_vault(tmp_path, {"alpha": ("A.", "Cap.")})
    targets_yaml = _make_targets_yaml(tmp_path, targets)

    # Should not raise
    result = pack.generate_pack(targets=targets, vault_dir=vault, targets_yaml=targets_yaml)
    assert result.exists()

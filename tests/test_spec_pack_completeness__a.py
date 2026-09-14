"""Tests for Spec pack completeness (Step A)."""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from collectors import spec as spec_mod  # noqa: E402
import project_discovery  # noqa: E402
import synthesize  # noqa: E402


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_collect_spec_scores_present_and_absent(tmp_path):
    root = tmp_path / "proj"
    _write(root / "PRODUCT.md", "# Product\n")
    _write(root / "DESIGN.md", "# Design\n")
    _write(root / "SCHEMA.md", "# Schema\n")
    (root / "docs").mkdir()
    _write(root / "docs" / "a.md")
    out = tmp_path / "snap"
    out.mkdir()
    result = spec_mod.collect_spec(root, out)
    assert result["status"] == "ok"
    assert result["score"] == "4/5"
    data = json.loads((out / "spec.json").read_text())
    assert data["files"]["PRODUCT.md"]["present"] is True
    assert data["files"]["api.yaml"]["present"] is False
    assert data["completeness"]["absent"] == ["api.yaml"]
    assert "API ✗" in data["completeness"]["badge"]
    assert "PRODUCT ✓" in data["completeness"]["badge"]


def test_api_yaml_alias_openapi(tmp_path):
    root = tmp_path / "proj"
    _write(root / "PRODUCT.md")
    _write(root / "openapi.yaml", "openapi: 3.0.0\n")
    out = tmp_path / "snap"
    out.mkdir()
    spec_mod.collect_spec(root, out)
    data = json.loads((out / "spec.json").read_text())
    assert data["files"]["api.yaml"]["present"] is True
    assert data["files"]["api.yaml"]["path"] == "openapi.yaml"


def test_format_badge_line():
    badge = spec_mod.format_badge_line({
        "completeness": {
            "badge": "PRODUCT ✓ · DESIGN ✗ · SCHEMA ✗ · API ✗ · docs ✗",
            "score": "1/5",
        }
    })
    assert badge.endswith("(1/5)")
    assert "PRODUCT ✓" in badge


def test_situation_includes_spec_pack_section():
    body = synthesize._render_situation(
        target="t",
        run="2026-09-14T00:00:00Z",
        sources_ok=True,
        one_liner="t — thing",
        capacity="Clear to start",
        since_last_run=[],
        what_to_do_next=[],
        journal=[],
        open_questions=[],
        drift=[],
        missing_sources=[],
        snapshot_name="",
        spec_badge="PRODUCT ✓ · DESIGN ✓ · SCHEMA ✓ · API ✗ · docs ✓  (4/5)",
    )
    assert "## Spec pack" in body
    assert "API ✗" in body
    assert "_(source: spec.json)_" in body


def test_discovery_spec_section(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    project = vault / "projects" / "demo"
    snap = project / "raw" / "2026-09-14T00:00:00Z"
    snap.mkdir(parents=True)
    (project / "capability.md").write_text("# demo\n\n## What it is\n\nDemo.\n")
    (snap / "spec.json").write_text(json.dumps({
        "files": {},
        "completeness": {
            "present": ["PRODUCT.md"],
            "absent": ["DESIGN.md", "SCHEMA.md", "api.yaml", "docs/"],
            "score": "1/5",
            "badge": "PRODUCT ✓ · DESIGN ✗ · SCHEMA ✗ · API ✗ · docs ✗",
        },
    }))
    (snap / "manifest.json").write_text("{}")
    monkeypatch.setattr(project_discovery, "_load_target_local", lambda *a, **k: None)
    out = project_discovery.generate_discovery("demo", vault)
    text = out.read_text()
    assert "## Spec pack" in text
    assert "PRODUCT ✓" in text
    assert "Missing (recommended for SDD)" in text

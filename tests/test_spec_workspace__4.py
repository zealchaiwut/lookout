"""Tests for Spec workspace + status machine (Step 4)."""
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import spec_workspace as sw  # noqa: E402


def _targets_yaml(tmp_path: Path, local: Path) -> Path:
    path = tmp_path / "targets.yaml"
    path.write_text(yaml.dump({
        "targets": {
            "demo": {
                "local": str(local),
                "github": "a/b",
                "commander_slug": "demo",
            }
        }
    }))
    return path


def test_ensure_workspace_creates_status_and_mirrors(tmp_path, monkeypatch):
    local = tmp_path / "clone"
    local.mkdir()
    (local / "PRODUCT.md").write_text("# PRODUCT\n")
    (local / "DESIGN.md").write_text("# DESIGN\n")
    vault = tmp_path / "vault"
    monkeypatch.setattr(sw, "TARGETS_YAML", _targets_yaml(tmp_path, local))

    out = sw.ensure_workspace("demo", vault)
    assert out == vault / "projects" / "demo" / "spec"
    assert (out / "status.yaml").is_file()
    assert (out / "mock").is_dir()
    assert (out / "PRODUCT.md").read_text().startswith("# PRODUCT")
    assert (out / "DESIGN.md").is_file()

    status = sw.read_status(out)
    assert status["status"] == "draft"
    assert status["files"]["PRODUCT.md"] == "present"
    assert status["files"]["api.yaml"] == "absent"
    assert "plan.md" not in status["files"]


def test_ensure_workspace_does_not_overwrite_vault_copy(tmp_path, monkeypatch):
    local = tmp_path / "clone"
    local.mkdir()
    (local / "PRODUCT.md").write_text("from-clone\n")
    vault = tmp_path / "vault"
    spec = vault / "projects" / "demo" / "spec"
    spec.mkdir(parents=True)
    (spec / "PRODUCT.md").write_text("from-vault\n")
    monkeypatch.setattr(sw, "TARGETS_YAML", _targets_yaml(tmp_path, local))

    sw.ensure_workspace("demo", vault)
    assert (spec / "PRODUCT.md").read_text() == "from-vault\n"


def test_status_transitions(tmp_path, monkeypatch):
    local = tmp_path / "clone"
    local.mkdir()
    vault = tmp_path / "vault"
    monkeypatch.setattr(sw, "TARGETS_YAML", _targets_yaml(tmp_path, local))
    sw.ensure_workspace("demo", vault)

    sw.set_status("demo", "in-review", vault, note="ready for review")
    assert sw.read_status(sw.spec_dir("demo", vault))["status"] == "in-review"

    sw.set_status("demo", "approved", vault)
    sw.set_status("demo", "promoted", vault)
    assert sw.read_status(sw.spec_dir("demo", vault))["status"] == "promoted"

    with pytest.raises(sw.SpecWorkspaceError):
        sw.set_status("demo", "approved", vault)  # promoted → approved illegal

    sw.set_status("demo", "draft", vault, note="next cycle")
    assert sw.read_status(sw.spec_dir("demo", vault))["status"] == "draft"


def test_illegal_skip_raises(tmp_path, monkeypatch):
    local = tmp_path / "clone"
    local.mkdir()
    vault = tmp_path / "vault"
    monkeypatch.setattr(sw, "TARGETS_YAML", _targets_yaml(tmp_path, local))
    sw.ensure_workspace("demo", vault)
    with pytest.raises(sw.SpecWorkspaceError, match="Cannot transition"):
        sw.set_status("demo", "approved", vault)

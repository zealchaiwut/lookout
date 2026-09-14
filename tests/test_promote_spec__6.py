"""Tests for lookout promote-spec (Step 6)."""
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import promote_spec as ps  # noqa: E402
import spec_workspace as sw  # noqa: E402


def _setup(tmp_path, monkeypatch):
    local = tmp_path / "clone"
    local.mkdir()
    (local / "PRODUCT.md").write_text("old product\n")
    vault = tmp_path / "vault"
    targets = tmp_path / "targets.yaml"
    targets.write_text(yaml.dump({
        "targets": {
            "demo": {
                "local": str(local),
                "github": "a/b",
                "commander_slug": "demo",
            }
        }
    }))
    monkeypatch.setattr(sw, "TARGETS_YAML", targets)
    monkeypatch.setattr(ps, "TARGETS_YAML", targets)
    directory = sw.ensure_workspace("demo", vault)
    (directory / "api.yaml").write_text("openapi: '3.0.3'\npaths: {}\n")
    (directory / "PRODUCT.md").write_text("new product\n")
    # Advance to approved without going through validate (unit-level).
    sw.set_status("demo", "in-review", vault)
    sw.set_status("demo", "approved", vault)
    return vault, local, directory


def test_promote_spec_copies_and_flips_status(tmp_path, monkeypatch):
    vault, local, _ = _setup(tmp_path, monkeypatch)
    result = ps.promote_spec("demo", vault)
    assert result["status"] == "promoted"
    assert "PRODUCT.md" in result["copied"]
    assert "api.yaml" in result["copied"]
    assert (local / "PRODUCT.md").read_text() == "new product\n"
    assert (local / "api.yaml").is_file()
    assert sw.read_status(sw.spec_dir("demo", vault))["status"] == "promoted"


def test_promote_spec_requires_approved(tmp_path, monkeypatch):
    vault, local, _ = _setup(tmp_path, monkeypatch)
    sw.set_status("demo", "in-review", vault)  # approved → in-review (rework)
    with pytest.raises(ps.PromoteSpecError, match="approved"):
        ps.promote_spec("demo", vault)
    assert (local / "PRODUCT.md").read_text() == "old product\n"
    assert not (local / "api.yaml").exists()



def test_promote_spec_dry_run_no_write(tmp_path, monkeypatch):
    vault, local, _ = _setup(tmp_path, monkeypatch)
    result = ps.promote_spec("demo", vault, dry_run=True)
    assert result["dry_run"] is True
    assert result["status"] == "approved"
    assert (local / "PRODUCT.md").read_text() == "old product\n"
    assert not (local / "api.yaml").exists()
    assert sw.read_status(sw.spec_dir("demo", vault))["status"] == "approved"

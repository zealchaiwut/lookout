"""Tests for Spec mock validate + approve CLI (Step 5)."""
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import spec_validate as sv  # noqa: E402
import spec_workspace as sw  # noqa: E402

_MIN_API = """
openapi: 3.0.3
info:
  title: demo
  version: 0.0.1
paths:
  /api/health:
    get:
      summary: health
      responses:
        '200':
          description: ok
"""


def _setup(tmp_path, monkeypatch, api_text=_MIN_API):
    local = tmp_path / "clone"
    local.mkdir()
    vault = tmp_path / "vault"
    targets = tmp_path / "targets.yaml"
    targets.write_text(yaml.dump({
        "targets": {
            "demo": {"local": str(local), "github": "a/b", "commander_slug": "demo"}
        }
    }))
    monkeypatch.setattr(sw, "TARGETS_YAML", targets)
    directory = sw.ensure_workspace("demo", vault)
    (directory / "api.yaml").write_text(api_text)
    sw.ensure_workspace("demo", vault)  # refresh inventory
    return vault, directory


def test_validate_ok(tmp_path, monkeypatch):
    vault, _ = _setup(tmp_path, monkeypatch)
    summary = sv.validate_target("demo", vault)
    assert summary["paths"] == 1
    assert summary["operations"] == 1
    raw = yaml.safe_load((sw.spec_dir("demo", vault) / "status.yaml").read_text())
    assert raw.get("last_validated")


def test_validate_rejects_missing_responses(tmp_path, monkeypatch):
    bad = """
openapi: 3.0.3
paths:
  /x:
    get:
      summary: no responses
"""
    vault, _ = _setup(tmp_path, monkeypatch, api_text=bad)
    with pytest.raises(sv.SpecValidateError, match="responses"):
        sv.validate_target("demo", vault)


def test_submit_and_approve_flow(tmp_path, monkeypatch):
    vault, _ = _setup(tmp_path, monkeypatch)
    with pytest.raises(sv.SpecValidateError, match="in-review"):
        sv.approve_spec("demo", vault)

    submitted = sv.submit_for_review("demo", vault, note="ready")
    assert submitted["status"] == "in-review"

    approved = sv.approve_spec("demo", vault, note="lgtm")
    assert approved["status"] == "approved"


def test_mock_json_must_parse(tmp_path, monkeypatch):
    vault, directory = _setup(tmp_path, monkeypatch)
    (directory / "mock" / "broken.json").write_text("{not json")
    with pytest.raises(sv.SpecValidateError, match="invalid JSON"):
        sv.validate_target("demo", vault)


def test_cli_validate_exit_zero(tmp_path, monkeypatch, capsys):
    vault, _ = _setup(tmp_path, monkeypatch)
    code = sv.main(["--vault", str(vault), "validate", "demo"])
    assert code == 0
    assert "OK:" in capsys.readouterr().out

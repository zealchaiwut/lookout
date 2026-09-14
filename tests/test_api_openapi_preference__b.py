"""Tests for OpenAPI-preferred endpoint collection (Step B)."""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import gather  # noqa: E402
from collectors import api as api_mod  # noqa: E402


OPENAPI = """
openapi: 3.0.3
info:
  title: demo
  version: 0.1.0
paths:
  /api/health:
    get:
      summary: Health check
      responses:
        "200":
          description: ok
  /accounts:
    get:
      summary: List accounts
      responses:
        "200":
          description: list
    post:
      summary: Create account
      responses:
        "201":
          description: created
"""


README = """# demo

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/from-readme` | Should be ignored when OpenAPI exists |
| `GET` | `/api/health` | Duplicate from readme |
"""


def test_openapi_preferred_over_readme_tables(tmp_path):
    local = tmp_path / "proj"
    local.mkdir()
    (local / "api.yaml").write_text(OPENAPI)
    (local / "README.md").write_text(README)
    out = tmp_path / "snap"
    out.mkdir()
    result = gather._collect_endpoints(local, out, target="demo")
    assert result["status"] == "ok"
    assert result["from_openapi"] is True
    data = json.loads((out / "endpoints.json").read_text())
    paths = {e["path"] for e in data["get_endpoints"]}
    assert paths == {"/api/health", "/accounts"}
    assert "/from-readme" not in paths
    assert data["source_files"] == ["api.yaml"]


def test_falls_back_to_readme_when_no_openapi(tmp_path):
    local = tmp_path / "proj"
    local.mkdir()
    (local / "README.md").write_text(README)
    out = tmp_path / "snap"
    out.mkdir()
    result = gather._collect_endpoints(local, out, target="demo")
    assert result["from_openapi"] is False
    data = json.loads((out / "endpoints.json").read_text())
    paths = {e["path"] for e in data["get_endpoints"]}
    assert "/from-readme" in paths


def test_endpoints_to_openapi_round_trip():
    eps = [{"path": "/x", "description": "X", "response": "200 JSON — X"}]
    doc = api_mod.endpoints_to_openapi(eps, title="t")
    assert doc["openapi"].startswith("3.")
    assert "/x" in doc["paths"]
    parsed = api_mod.parse_openapi_yaml(__import__("yaml").dump(doc))
    assert parsed[0]["path"] == "/x"

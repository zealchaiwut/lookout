"""Tests for issue #5: gather.py snapshot core with commander collectors.

Each test maps to a specific AC item from the issue.

All tests that invoke gather() use a tmp_path fixture so they never write to
the real vault, keeping the scaffolded vault clean for the lint checks.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml

REPO_ROOT = Path(__file__).parent.parent
GATHER = REPO_ROOT / "gather.py"
TARGETS_YAML = REPO_ROOT / "targets.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_target():
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    return next(iter(data["targets"]))


def _valid_target_slug():
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    name = next(iter(data["targets"]))
    return data["targets"][name].get("commander_slug", name)


def _load_gather_module(tmp_path, module_name="gather_test"):
    """Load gather.py as an isolated module pointing its vault at tmp_path."""
    shutil.copy(str(TARGETS_YAML), str(tmp_path / "targets.yaml"))
    spec = importlib.util.spec_from_file_location(module_name, str(GATHER))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = tmp_path
    mod.TARGETS_YAML = tmp_path / "targets.yaml"
    return mod


def _ok_http(slug):
    """Return a mock_get function that returns valid 200 responses."""
    health_resp = MagicMock()
    health_resp.ok = True
    health_resp.json.return_value = {"status": "healthy"}

    brief_resp = MagicMock()
    brief_resp.ok = True
    brief_resp.json.return_value = {"name": slug, "description": "test project"}

    history_resp = MagicMock()
    history_resp.ok = True
    history_resp.json.return_value = [{"slug": slug, "sprint": 1}, {"slug": "other", "sprint": 1}]

    def mock_get(url, timeout=10):
        if "/api/health" in url:
            return health_resp
        if "/api/projects/" in url and "/brief" in url:
            return brief_resp
        if "/api/sprints/history" in url:
            return history_resp
        raise ValueError(f"Unexpected URL: {url}")

    return mock_get


# ---------------------------------------------------------------------------
# AC: gather.py exists
# ---------------------------------------------------------------------------

def test_gather_py_exists():
    assert GATHER.exists(), "gather.py must exist at repo root"


# ---------------------------------------------------------------------------
# AC: unknown target exits non-zero with clear message referencing targets.yaml
# ---------------------------------------------------------------------------

def test_unknown_target_exits_nonzero():
    result = subprocess.run(
        [sys.executable, str(GATHER), "totally-unknown-target-xyz"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode != 0, "Unknown target must exit non-zero"


def test_unknown_target_message_references_targets_yaml():
    result = subprocess.run(
        [sys.executable, str(GATHER), "totally-unknown-target-xyz"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    combined = result.stdout + result.stderr
    assert "targets.yaml" in combined, "Error message must reference targets.yaml"


def test_unknown_target_no_vault_dir_created():
    result = subprocess.run(
        [sys.executable, str(GATHER), "totally-unknown-target-xyz"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode != 0
    assert not (REPO_ROOT / "vault" / "projects" / "totally-unknown-target-xyz").exists()


# ---------------------------------------------------------------------------
# AC: no HTTP methods other than GET
# ---------------------------------------------------------------------------

def test_no_non_get_http_methods():
    source = GATHER.read_text()
    forbidden = [
        "requests.post", "requests.put", "requests.patch", "requests.delete",
        "method='POST'", 'method="POST"',
        "method='PUT'", 'method="PUT"',
        "method='PATCH'", 'method="PATCH"',
        "method='DELETE'", 'method="DELETE"',
    ]
    for pattern in forbidden:
        assert pattern not in source, f"gather.py must not use {pattern!r}"


# ---------------------------------------------------------------------------
# AC: module docstring documents manifest JSON shape
# ---------------------------------------------------------------------------

def test_module_docstring_documents_manifest_shape():
    source = GATHER.read_text()
    assert '"""' in source or "'''" in source, "Module must have a docstring"
    # Docstring is at the top — check first 2000 chars
    header = source[:2000]
    assert "status" in header, "Docstring must document 'status' field"
    assert "error" in header, "Docstring must document 'error' field"
    assert "health" in header, "Docstring must document 'health' field"
    assert "sources" in header, "Docstring must document 'sources' field"


# ---------------------------------------------------------------------------
# AC: ok path — mocked HTTP 200 responses produce correct files
# ---------------------------------------------------------------------------

def test_ok_path_creates_vault_directory(tmp_path):
    """On ok path, vault/projects/<name>/raw/<timestamp>/ is created."""
    target = _valid_target()
    slug = _valid_target_slug()
    mod = _load_gather_module(tmp_path, "gather_vault_dir")

    with patch("requests.get", side_effect=_ok_http(slug)):
        mod.gather(target)

    expected_base = tmp_path / "vault" / "projects" / target / "raw"
    children = list(expected_base.iterdir()) if expected_base.exists() else []
    assert len(children) >= 1, f"Expected at least one timestamped dir under {expected_base}"
    latest = sorted(children)[-1]
    assert (latest / "manifest.json").exists(), "manifest.json must be written"
    assert (latest / "brief.json").exists(), "brief.json must be written"


def test_ok_path_manifest_has_ok_status(tmp_path):
    """On ok path, manifest.json lists all sources with status: ok."""
    target = _valid_target()
    slug = _valid_target_slug()
    mod = _load_gather_module(tmp_path, "gather_ok_manifest")

    with patch("requests.get", side_effect=_ok_http(slug)):
        mod.gather(target)

    latest = sorted((tmp_path / "vault" / "projects" / target / "raw").iterdir())[-1]
    manifest = json.loads((latest / "manifest.json").read_text())

    sources = manifest["sources"]
    assert len(sources) > 0, "manifest must list at least one source"
    for name, entry in sources.items():
        assert entry["status"] == "ok", f"source '{name}' should be ok, got: {entry}"
        assert entry["error"] == "", f"source '{name}' error should be empty string"


def test_ok_path_manifest_has_health_fields(tmp_path):
    """manifest.json header includes Commander /api/health summary fields."""
    target = _valid_target()
    slug = _valid_target_slug()

    health_resp = MagicMock()
    health_resp.ok = True
    health_resp.json.return_value = {"status": "healthy", "uptime": 999}

    brief_resp = MagicMock()
    brief_resp.ok = True
    brief_resp.json.return_value = {"name": slug}

    history_resp = MagicMock()
    history_resp.ok = True
    history_resp.json.return_value = []

    def mock_get(url, timeout=10):
        if "/api/health" in url:
            return health_resp
        if "/api/projects/" in url and "/brief" in url:
            return brief_resp
        if "/api/sprints/history" in url:
            return history_resp
        raise ValueError(f"Unexpected URL: {url}")

    mod = _load_gather_module(tmp_path, "gather_ok_health")
    with patch("requests.get", side_effect=mock_get):
        mod.gather(target)

    latest = sorted((tmp_path / "vault" / "projects" / target / "raw").iterdir())[-1]
    manifest = json.loads((latest / "manifest.json").read_text())

    assert "health" in manifest, "manifest.json must have a 'health' header key"
    assert manifest["health"].get("status") == "healthy"
    assert manifest["health"].get("uptime") == 999


def test_ok_path_brief_json_has_brief_and_sprints(tmp_path):
    """brief.json contains brief response and filtered sprints history."""
    target = _valid_target()
    slug = _valid_target_slug()

    brief_data = {"name": slug, "description": "a project"}
    history_data = [
        {"slug": slug, "sprint": 1},
        {"slug": "other-proj", "sprint": 1},
        {"slug": slug, "sprint": 2},
    ]

    health_resp = MagicMock()
    health_resp.ok = True
    health_resp.json.return_value = {"status": "healthy"}

    brief_resp = MagicMock()
    brief_resp.ok = True
    brief_resp.json.return_value = brief_data

    history_resp = MagicMock()
    history_resp.ok = True
    history_resp.json.return_value = history_data

    def mock_get(url, timeout=10):
        if "/api/health" in url:
            return health_resp
        if "/api/projects/" in url and "/brief" in url:
            return brief_resp
        if "/api/sprints/history" in url:
            return history_resp
        raise ValueError(f"Unexpected URL: {url}")

    mod = _load_gather_module(tmp_path, "gather_ok_brief")
    with patch("requests.get", side_effect=mock_get):
        mod.gather(target)

    latest = sorted((tmp_path / "vault" / "projects" / target / "raw").iterdir())[-1]
    brief = json.loads((latest / "brief.json").read_text())

    assert "brief" in brief, "brief.json must have 'brief' key"
    assert brief["brief"] == brief_data, "brief.json brief data must match API response"
    assert "sprints_history" in brief, "brief.json must have 'sprints_history' key"
    for entry in brief["sprints_history"]:
        assert entry.get("slug") == slug, f"Unexpected slug in sprints_history: {entry}"
    assert len(brief["sprints_history"]) == 2, "Should have 2 filtered sprint entries"


# ---------------------------------------------------------------------------
# AC: absent path — mocked connection error → status: absent, exit code 0
# ---------------------------------------------------------------------------

def test_absent_path_exit_code_zero(tmp_path):
    """When Commander is unreachable, gather() must not raise and exit code is 0."""
    target = _valid_target()
    mod = _load_gather_module(tmp_path, "gather_absent_exit")

    def mock_get_error(url, timeout=10):
        raise requests.exceptions.ConnectionError("Connection refused")

    with patch("requests.get", side_effect=mock_get_error):
        try:
            mod.gather(target)
        except SystemExit as exc:
            assert exc.code == 0, f"Expected exit 0 on absent path, got {exc.code}"
        except Exception as exc:
            pytest.fail(f"gather() raised an unexpected exception on absent path: {exc}")


def test_absent_path_manifest_has_absent_status(tmp_path):
    """On absent path, manifest.json has status: absent for all Commander sources."""
    target = _valid_target()
    mod = _load_gather_module(tmp_path, "gather_absent_manifest")

    def mock_get_error(url, timeout=10):
        raise requests.exceptions.ConnectionError("Connection refused")

    with patch("requests.get", side_effect=mock_get_error):
        mod.gather(target)

    expected_base = tmp_path / "vault" / "projects" / target / "raw"
    assert expected_base.exists(), "vault directory must be created even on absent path"
    latest = sorted(expected_base.iterdir())[-1]
    manifest = json.loads((latest / "manifest.json").read_text())

    sources = manifest["sources"]
    assert len(sources) > 0, "manifest must list at least one source"
    for name, entry in sources.items():
        assert entry["status"] == "absent", f"source '{name}' must be absent on connection error"
        assert entry["error"] != "", f"source '{name}' must have a non-empty error string"


def test_absent_path_no_traceback(tmp_path):
    """On connection error, no Python traceback is printed."""
    target = _valid_target()
    mod = _load_gather_module(tmp_path, "gather_absent_traceback")

    output_lines = []

    def mock_get_error(url, timeout=10):
        raise requests.exceptions.ConnectionError("Connection refused")

    import io
    from contextlib import redirect_stdout, redirect_stderr

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    with patch("requests.get", side_effect=mock_get_error), \
         redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        try:
            mod.gather(target)
        except SystemExit:
            pass

    combined = stdout_buf.getvalue() + stderr_buf.getvalue()
    assert "Traceback" not in combined, f"No traceback should appear:\n{combined}"


# ---------------------------------------------------------------------------
# AC: 10-second timeout used on all HTTP calls
# ---------------------------------------------------------------------------

def test_timeout_is_10_seconds(tmp_path):
    """All HTTP calls use a 10-second timeout."""
    calls = []

    def mock_get(url, timeout=None):
        calls.append({"url": url, "timeout": timeout})
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {}
        return resp

    target = _valid_target()
    mod = _load_gather_module(tmp_path, "gather_timeout")

    with patch("requests.get", side_effect=mock_get):
        mod.gather(target)

    assert len(calls) > 0, "Expected at least one HTTP call"
    for call in calls:
        assert call["timeout"] == 10, f"Expected timeout=10 for {call['url']}, got {call['timeout']}"


# ---------------------------------------------------------------------------
# AC: creates vault directory on every run
# ---------------------------------------------------------------------------

def test_creates_new_directory_each_run(tmp_path):
    """Each run creates a new timestamped directory under vault/projects/<name>/raw/."""
    target = _valid_target()

    def mock_get_ok(url, timeout=10):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {}
        return resp

    timestamps = ["2099-01-01T00:00:00Z", "2099-01-01T00:00:01Z"]
    ts_iter = iter(timestamps)

    class _FakeDatetime:
        @staticmethod
        def now(tz=None):
            class _Fake:
                def strftime(self, fmt):
                    return next(ts_iter)
            return _Fake()

    mod = _load_gather_module(tmp_path, "gather_newdir")

    with patch("requests.get", side_effect=mock_get_ok):
        mod.datetime = _FakeDatetime
        mod.gather(target)
        mod.gather(target)

    expected_base = tmp_path / "vault" / "projects" / target / "raw"
    children = list(expected_base.iterdir()) if expected_base.exists() else []
    assert len(children) == 2, (
        f"Expected 2 distinct timestamped dirs (one per run), got {[c.name for c in children]}"
    )

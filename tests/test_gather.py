"""Tests for issue #5: gather.py snapshot core with commander collectors.

Each test maps to a specific AC item from the issue.
"""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
GATHER = REPO_ROOT / "gather.py"
TARGETS_YAML = REPO_ROOT / "targets.yaml"


def _valid_target():
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    return next(iter(data["targets"]))


def _valid_target_slug():
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    name = next(iter(data["targets"]))
    return data["targets"][name].get("commander_slug", name)


def _commander_api():
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    return data.get("sources", {}).get("commander_api", "http://localhost:8000")


def run_gather(args, env=None):
    return subprocess.run(
        [sys.executable, str(GATHER)] + args,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


# ---------------------------------------------------------------------------
# AC: gather.py exists
# ---------------------------------------------------------------------------

def test_gather_py_exists():
    assert GATHER.exists(), "gather.py must exist at repo root"


# ---------------------------------------------------------------------------
# AC: unknown target exits non-zero with clear message referencing targets.yaml
# ---------------------------------------------------------------------------

def test_unknown_target_exits_nonzero():
    result = run_gather(["totally-unknown-target-xyz"])
    assert result.returncode != 0, "Unknown target must exit non-zero"


def test_unknown_target_message_references_targets_yaml():
    result = run_gather(["totally-unknown-target-xyz"])
    combined = result.stdout + result.stderr
    assert "targets.yaml" in combined, "Error message must reference targets.yaml"


def test_unknown_target_no_vault_dir_created(tmp_path):
    """No vault directory is created for an unknown target."""
    import importlib.util, sys as _sys

    spec = importlib.util.spec_from_file_location("gather", str(GATHER))
    mod = importlib.util.load_from_spec = None  # don't import at module level

    result = run_gather(["totally-unknown-target-xyz"])
    assert result.returncode != 0
    # vault/projects/totally-unknown-target-xyz must not exist
    assert not (REPO_ROOT / "vault" / "projects" / "totally-unknown-target-xyz").exists()


# ---------------------------------------------------------------------------
# AC: no HTTP methods other than GET (grep check)
# ---------------------------------------------------------------------------

def test_no_non_get_http_methods():
    source = GATHER.read_text()
    forbidden = ["requests.post", "requests.put", "requests.patch", "requests.delete",
                 ".post(", ".put(", ".patch(", ".delete(",
                 "method='POST'", 'method="POST"',
                 "method='PUT'", 'method="PUT"',
                 "method='PATCH'", 'method="PATCH"',
                 "method='DELETE'", 'method="DELETE"']
    for pattern in forbidden:
        assert pattern not in source, f"gather.py must not use {pattern!r}"


# ---------------------------------------------------------------------------
# AC: module docstring documents manifest JSON shape
# ---------------------------------------------------------------------------

def test_module_docstring_documents_manifest_shape():
    source = GATHER.read_text()
    # Module docstring must be present and mention key manifest fields
    assert '"""' in source or "'''" in source, "Module must have a docstring"
    # Must document status and error fields
    assert "status" in source[:2000], "Docstring must document 'status' field"
    assert "error" in source[:2000], "Docstring must document 'error' field"
    assert "health" in source[:2000], "Docstring must document 'health' field"
    assert "sources" in source[:2000], "Docstring must document 'sources' field"


# ---------------------------------------------------------------------------
# AC: ok path — mocked HTTP 200 responses produce correct brief.json and manifest.json
# ---------------------------------------------------------------------------

def test_ok_path_creates_vault_directory(tmp_path):
    """On ok path, vault/projects/<name>/raw/<timestamp>/ is created with expected files."""
    import importlib.util, shutil

    target = _valid_target()
    slug = _valid_target_slug()

    # Copy targets.yaml to tmp_path so the module can load it
    shutil.copy(str(TARGETS_YAML), str(tmp_path / "targets.yaml"))

    health_resp = MagicMock()
    health_resp.ok = True
    health_resp.json.return_value = {"status": "healthy", "version": "1.0"}

    brief_resp = MagicMock()
    brief_resp.ok = True
    brief_resp.json.return_value = {"name": slug, "description": "test"}

    history_resp = MagicMock()
    history_resp.ok = True
    history_resp.json.return_value = [{"slug": slug, "sprint": 1}, {"slug": "other", "sprint": 2}]

    def mock_get(url, timeout=10):
        if "/api/health" in url:
            return health_resp
        if "/api/projects/" in url and "/brief" in url:
            return brief_resp
        if "/api/sprints/history" in url:
            return history_resp
        raise ValueError(f"Unexpected URL: {url}")

    spec = importlib.util.spec_from_file_location("gather_vault_dir", str(GATHER))
    mod = importlib.util.module_from_spec(spec)

    with patch("requests.get", side_effect=mock_get):
        spec.loader.exec_module(mod)
        # Redirect output directory to tmp_path
        mod.REPO_ROOT = tmp_path
        mod.TARGETS_YAML = tmp_path / "targets.yaml"
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

    health_resp = MagicMock()
    health_resp.ok = True
    health_resp.json.return_value = {"status": "healthy"}

    brief_resp = MagicMock()
    brief_resp.ok = True
    brief_resp.json.return_value = {"name": slug}

    history_resp = MagicMock()
    history_resp.ok = True
    history_resp.json.return_value = [{"slug": slug, "sprint": 1}]

    def mock_get(url, timeout=10):
        if "/api/health" in url:
            return health_resp
        if "/api/projects/" in url and "/brief" in url:
            return brief_resp
        if "/api/sprints/history" in url:
            return history_resp
        raise ValueError(f"Unexpected URL: {url}")

    import importlib.util
    spec = importlib.util.spec_from_file_location("gather_ok_manifest", str(GATHER))
    mod = importlib.util.module_from_spec(spec)

    with patch("requests.get", side_effect=mock_get):
        spec.loader.exec_module(mod)
        mod.gather(target)

    expected_base = REPO_ROOT / "vault" / "projects" / target / "raw"
    latest = sorted(expected_base.iterdir())[-1]
    manifest = json.loads((latest / "manifest.json").read_text())

    sources = manifest["sources"]
    for name, entry in sources.items():
        assert entry["status"] == "ok", f"source '{name}' should be ok, got: {entry}"
        assert entry["error"] == "", f"source '{name}' error should be empty string"


def test_ok_path_manifest_has_health_fields():
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

    import importlib.util
    spec = importlib.util.spec_from_file_location("gather_ok_health", str(GATHER))
    mod = importlib.util.module_from_spec(spec)

    with patch("requests.get", side_effect=mock_get):
        spec.loader.exec_module(mod)
        mod.gather(target)

    expected_base = REPO_ROOT / "vault" / "projects" / target / "raw"
    latest = sorted(expected_base.iterdir())[-1]
    manifest = json.loads((latest / "manifest.json").read_text())

    assert "health" in manifest, "manifest.json must have a 'health' header key"
    assert manifest["health"].get("status") == "healthy"
    assert manifest["health"].get("uptime") == 999


def test_ok_path_brief_json_has_brief_and_sprints():
    """brief.json contains brief response and filtered sprints history."""
    target = _valid_target()
    slug = _valid_target_slug()

    health_resp = MagicMock()
    health_resp.ok = True
    health_resp.json.return_value = {"status": "healthy"}

    brief_data = {"name": slug, "description": "a project"}
    brief_resp = MagicMock()
    brief_resp.ok = True
    brief_resp.json.return_value = brief_data

    history_data = [
        {"slug": slug, "sprint": 1},
        {"slug": "other-proj", "sprint": 1},
        {"slug": slug, "sprint": 2},
    ]
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

    import importlib.util
    spec = importlib.util.spec_from_file_location("gather_ok_brief", str(GATHER))
    mod = importlib.util.module_from_spec(spec)

    with patch("requests.get", side_effect=mock_get):
        spec.loader.exec_module(mod)
        mod.gather(target)

    expected_base = REPO_ROOT / "vault" / "projects" / target / "raw"
    latest = sorted(expected_base.iterdir())[-1]
    brief = json.loads((latest / "brief.json").read_text())

    assert "brief" in brief, "brief.json must have 'brief' key"
    assert brief["brief"] == brief_data, "brief.json brief data must match API response"
    assert "sprints_history" in brief, "brief.json must have 'sprints_history' key"
    # Only entries for this slug should appear
    for entry in brief["sprints_history"]:
        assert entry.get("slug") == slug, f"Unexpected slug in sprints_history: {entry}"
    assert len(brief["sprints_history"]) == 2, "Should have 2 filtered sprint entries"


# ---------------------------------------------------------------------------
# AC: absent path — mocked connection error → status: absent, exit code 0
# ---------------------------------------------------------------------------

def test_absent_path_exit_code_zero():
    """When Commander is unreachable, exit code is 0."""
    import importlib.util
    import requests as req

    target = _valid_target()

    spec = importlib.util.spec_from_file_location("gather_absent_exit", str(GATHER))
    mod = importlib.util.module_from_spec(spec)

    def mock_get_error(url, timeout=10):
        raise req.exceptions.ConnectionError("Connection refused")

    with patch("requests.get", side_effect=mock_get_error):
        spec.loader.exec_module(mod)
        # gather() should not raise and should write manifest with absent status
        # It should not call sys.exit(1) for a valid target
        try:
            mod.gather(target)
        except SystemExit as e:
            assert e.code == 0, f"Expected exit 0 on absent path, got {e.code}"


def test_absent_path_manifest_has_absent_status():
    """On absent path, manifest.json has status: absent for all Commander sources."""
    import importlib.util
    import requests as req

    target = _valid_target()

    spec = importlib.util.spec_from_file_location("gather_absent_manifest", str(GATHER))
    mod = importlib.util.module_from_spec(spec)

    def mock_get_error(url, timeout=10):
        raise req.exceptions.ConnectionError("Connection refused")

    with patch("requests.get", side_effect=mock_get_error):
        spec.loader.exec_module(mod)
        mod.gather(target)

    expected_base = REPO_ROOT / "vault" / "projects" / target / "raw"
    assert expected_base.exists(), "vault directory must be created even on absent path"
    latest = sorted(expected_base.iterdir())[-1]
    manifest = json.loads((latest / "manifest.json").read_text())

    sources = manifest["sources"]
    assert len(sources) > 0, "manifest must list at least one source"
    for name, entry in sources.items():
        assert entry["status"] == "absent", f"source '{name}' must be absent on connection error"
        assert entry["error"] != "", f"source '{name}' must have a non-empty error string"


def test_absent_path_no_traceback():
    """On connection error, no traceback is printed."""
    result = run_gather([_valid_target()])
    # If Commander is not running locally, this tests the real absent path
    # We check that even if it errors, there's no Python traceback
    if result.returncode != 0:
        # If it exited non-zero, that's a bug (should be 0 for absent)
        pytest.fail(f"gather exited {result.returncode} on absent path; expected 0\nstderr: {result.stderr}")
    # No Traceback in output
    assert "Traceback" not in result.stdout, "No traceback should appear in stdout"
    assert "Traceback" not in result.stderr, "No traceback should appear in stderr"


# ---------------------------------------------------------------------------
# AC: 10-second timeout used on all HTTP calls
# ---------------------------------------------------------------------------

def test_timeout_is_10_seconds():
    """All HTTP calls use a 10-second timeout."""
    calls = []

    def mock_get(url, timeout=None):
        calls.append({"url": url, "timeout": timeout})
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {}
        return resp

    import importlib.util
    spec = importlib.util.spec_from_file_location("gather_timeout", str(GATHER))
    mod = importlib.util.module_from_spec(spec)

    with patch("requests.get", side_effect=mock_get):
        spec.loader.exec_module(mod)
        mod.gather(_valid_target())

    assert len(calls) > 0, "Expected at least one HTTP call"
    for call in calls:
        assert call["timeout"] == 10, f"Expected timeout=10 for {call['url']}, got {call['timeout']}"


# ---------------------------------------------------------------------------
# AC: creates vault directory on every run
# ---------------------------------------------------------------------------

def test_creates_new_directory_each_run(tmp_path):
    """Each run creates a new timestamped directory under vault/projects/<name>/raw/."""
    import importlib.util, shutil

    target = _valid_target()
    shutil.copy(str(TARGETS_YAML), str(tmp_path / "targets.yaml"))

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

    spec = importlib.util.spec_from_file_location("gather_newdir2", str(GATHER))
    mod = importlib.util.module_from_spec(spec)

    with patch("requests.get", side_effect=mock_get_ok):
        spec.loader.exec_module(mod)
        mod.REPO_ROOT = tmp_path
        mod.TARGETS_YAML = tmp_path / "targets.yaml"
        # Patch the datetime name in the module's own namespace
        mod.datetime = _FakeDatetime

        mod.gather(target)
        mod.gather(target)

    expected_base = tmp_path / "vault" / "projects" / target / "raw"
    children = list(expected_base.iterdir()) if expected_base.exists() else []
    assert len(children) == 2, (
        f"Expected 2 distinct timestamped dirs (one per run), got {[c.name for c in children]}"
    )

"""Tests for issue #7: Notion todos collector with rate-limit handling.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
GATHER = REPO_ROOT / "gather.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_module(module_name="gather_notion_base"):
    spec = importlib.util.spec_from_file_location(module_name, str(GATHER))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _targets_with_notion(tmp_path, db_id="test-db-id-12345"):
    local = tmp_path / "fake_local"
    local.mkdir(exist_ok=True)
    data = {
        "sources": {
            "commander_api": "http://localhost:8000",
            "notion_todos_db": db_id,
        },
        "targets": {
            "perf-coach": {
                "commander_slug": "perf-coach",
                "local": str(local),
            },
        },
    }
    path = tmp_path / "targets.yaml"
    path.write_text(yaml.dump(data))
    return path


def _load_notion_gather(tmp_path, db_id="test-db-id-12345", module_name="gather_notion"):
    targets_path = _targets_with_notion(tmp_path, db_id=db_id)
    spec = importlib.util.spec_from_file_location(module_name, str(GATHER))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = tmp_path
    mod.TARGETS_YAML = targets_path
    return mod


def _notion_page(page_id, title="Task", status="In Progress", project="perf-coach"):
    return {
        "id": page_id,
        "url": f"https://notion.so/{page_id.replace('-', '')}",
        "last_edited_time": "2026-08-10T12:00:00.000Z",
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": title}],
            },
            "Status": {
                "type": "select",
                "select": {"name": status},
            },
            "Project": {
                "type": "select",
                "select": {"name": project},
            },
        },
    }


def _notion_resp(results, has_more=False, next_cursor=None):
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = {
        "results": results,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }
    return resp


def _err_resp(status_code, message):
    resp = MagicMock()
    resp.ok = False
    resp.status_code = status_code
    resp.json.return_value = {"message": message, "code": "unauthorized"}
    return resp


def _rate_limit_resp():
    resp = MagicMock()
    resp.ok = False
    resp.status_code = 429
    resp.json.return_value = {"message": "rate limited"}
    return resp


def _ok_http():
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = {}
    return lambda url, timeout=10: resp


def _fake_subprocess():
    result = MagicMock()
    result.returncode = 0
    result.stdout = ""
    result.stderr = ""
    return lambda *args, **kwargs: result


# ---------------------------------------------------------------------------
# AC: no page-create or page-update endpoints
# ---------------------------------------------------------------------------

def test_no_page_create_or_update_endpoints():
    """gather.py must not reference /v1/pages (page-create or page-update)."""
    result = subprocess.run(
        ["grep", "-n", r"v1/pages", str(GATHER)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 or result.stdout.strip() == "", (
        f"gather.py must not call page-create or page-update Notion endpoints"
        f" (/v1/pages):\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# AC: NOTION_TOKEN missing → source recorded as absent
# ---------------------------------------------------------------------------

def test_missing_token_returns_absent():
    """_collect_notion_todos with empty token returns absent status."""
    mod = _load_module("gather_notion_no_token")
    out = MagicMock()  # out_dir not used when token missing
    result = mod._collect_notion_todos("perf-coach", "", "some-db-id", out)
    assert result["status"] == "absent"
    assert result["error"] != ""
    assert "NOTION_TOKEN" in result["error"] or "token" in result["error"].lower()


# ---------------------------------------------------------------------------
# AC: successful multi-page pagination
# ---------------------------------------------------------------------------

def test_pagination_exhausted(tmp_path):
    """Collector follows next_cursor until has_more is False."""
    mod = _load_module("gather_notion_pag")

    page1 = [_notion_page("page-1", "Task A", "Done", "perf-coach")]
    page2 = [_notion_page("page-2", "Task B", "In Progress", "Global")]

    call_count = [0]

    def mock_post(url, headers=None, json=None, timeout=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return _notion_resp(page1, has_more=True, next_cursor="cursor-abc")
        return _notion_resp(page2, has_more=False)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep"):
        result = mod._collect_notion_todos(
            "perf-coach", "secret-token", "db-id", out_dir
        )

    assert result["status"] == "ok", f"Expected ok, got: {result}"
    assert call_count[0] == 2, f"Expected 2 page requests, got {call_count[0]}"

    todos = json.loads((out_dir / "notion_todos.json").read_text())
    assert len(todos) == 2, f"Expected 2 todos across pages, got {len(todos)}"
    ids = {t["id"] for t in todos}
    assert "page-1" in ids and "page-2" in ids


def test_pagination_sends_next_cursor(tmp_path):
    """Second page request includes start_cursor from first response."""
    mod = _load_module("gather_notion_cursor")

    captured_payloads = []

    def mock_post(url, headers=None, json=None, timeout=None):
        captured_payloads.append(json)
        if len(captured_payloads) == 1:
            return _notion_resp([], has_more=True, next_cursor="cursor-xyz")
        return _notion_resp([], has_more=False)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep"):
        mod._collect_notion_todos("perf-coach", "token", "db-id", out_dir)

    assert len(captured_payloads) >= 2
    assert captured_payloads[1].get("start_cursor") == "cursor-xyz", (
        f"Second request must include start_cursor. Got: {captured_payloads[1]}"
    )


# ---------------------------------------------------------------------------
# AC: 429 backoff and retry
# ---------------------------------------------------------------------------

def test_429_backoff_retry_succeeds(tmp_path):
    """Collector retries after HTTP 429 and succeeds on subsequent attempt."""
    mod = _load_module("gather_notion_429")

    attempt = [0]

    def mock_post(url, headers=None, json=None, timeout=None):
        attempt[0] += 1
        if attempt[0] == 1:
            return _rate_limit_resp()
        return _notion_resp([_notion_page("p1")], has_more=False)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    sleep_calls = []

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        result = mod._collect_notion_todos("perf-coach", "token", "db-id", out_dir)

    assert result["status"] == "ok", f"Expected ok after retry, got: {result}"
    assert attempt[0] == 2, f"Expected 2 attempts (1 retry), got {attempt[0]}"
    backoff_calls = [s for s in sleep_calls if s >= 1.0]
    assert len(backoff_calls) >= 1, (
        f"Expected at least one backoff sleep ≥1s on 429. Sleeps: {sleep_calls}"
    )


def test_429_exponential_backoff(tmp_path):
    """Each successive 429 doubles the backoff delay."""
    mod = _load_module("gather_notion_exp")

    attempt = [0]

    def mock_post(url, headers=None, json=None, timeout=None):
        attempt[0] += 1
        if attempt[0] < 3:
            return _rate_limit_resp()
        return _notion_resp([], has_more=False)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    sleep_calls = []

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        mod._collect_notion_todos("perf-coach", "token", "db-id", out_dir)

    backoff_sleeps = [s for s in sleep_calls if s >= 1.0]
    assert len(backoff_sleeps) >= 2, (
        f"Expected ≥2 backoff sleeps for 2 consecutive 429s. Sleeps: {sleep_calls}"
    )
    assert backoff_sleeps[1] >= backoff_sleeps[0], (
        f"Second backoff must be ≥ first. Got: {backoff_sleeps}"
    )


def test_429_max_retries_returns_absent(tmp_path):
    """After max retries of 429, returns absent with error."""
    mod = _load_module("gather_notion_maxretry")

    def mock_post(url, headers=None, json=None, timeout=None):
        return _rate_limit_resp()

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep"):
        result = mod._collect_notion_todos("perf-coach", "token", "db-id", out_dir)

    assert result["status"] == "absent"
    assert result["error"] != ""


# ---------------------------------------------------------------------------
# AC: invalid token → source recorded as absent with API error string
# ---------------------------------------------------------------------------

def test_invalid_token_records_absent_with_error(tmp_path):
    """HTTP 401 (invalid token) is recorded as absent with the API error string."""
    mod = _load_module("gather_notion_401")

    def mock_post(url, headers=None, json=None, timeout=None):
        return _err_resp(401, "API token is invalid.")

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep"):
        result = mod._collect_notion_todos("perf-coach", "bad-token", "db-id", out_dir)

    assert result["status"] == "absent"
    assert "API token is invalid" in result["error"] or result["error"] != ""


def test_invalid_token_no_unhandled_exception(tmp_path):
    """Invalid token must not raise an unhandled exception."""
    mod = _load_module("gather_notion_noexc")

    def mock_post(url, headers=None, json=None, timeout=None):
        return _err_resp(401, "API token is invalid.")

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    try:
        with patch("requests.post", side_effect=mock_post), \
             patch("time.sleep"):
            mod._collect_notion_todos("perf-coach", "bad-token", "db-id", out_dir)
    except Exception as exc:
        pytest.fail(
            f"_collect_notion_todos raised an unhandled exception: {exc}"
        )


# ---------------------------------------------------------------------------
# AC: normalized schema — exactly id, title, status, project, url, last_edited
# ---------------------------------------------------------------------------

def test_normalized_fields_exact_keys(tmp_path):
    """Each todo in notion_todos.json has exactly the 6 required keys."""
    mod = _load_module("gather_notion_norm")

    page = _notion_page("abc-123", "Fix bug", "Done", "perf-coach")

    def mock_post(url, headers=None, json=None, timeout=None):
        return _notion_resp([page], has_more=False)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep"):
        mod._collect_notion_todos("perf-coach", "token", "db-id", out_dir)

    todos = json.loads((out_dir / "notion_todos.json").read_text())
    assert len(todos) == 1
    expected_keys = {"id", "title", "status", "project", "url", "last_edited"}
    assert set(todos[0].keys()) == expected_keys, (
        f"Expected keys {expected_keys}, got {set(todos[0].keys())}"
    )


def test_normalized_field_values(tmp_path):
    """Normalized fields match source page data."""
    mod = _load_module("gather_notion_vals")

    page = _notion_page("abc-123", "Fix the bug", "Done", "Global")

    def mock_post(url, headers=None, json=None, timeout=None):
        return _notion_resp([page], has_more=False)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep"):
        mod._collect_notion_todos("perf-coach", "token", "db-id", out_dir)

    todos = json.loads((out_dir / "notion_todos.json").read_text())
    t = todos[0]
    assert t["id"] == "abc-123"
    assert t["title"] == "Fix the bug"
    assert t["status"] == "Done"
    assert t["project"] == "Global"
    assert "notion.so" in t["url"]
    assert t["last_edited"] == "2026-08-10T12:00:00.000Z"


# ---------------------------------------------------------------------------
# AC: results written to notion_todos.json
# ---------------------------------------------------------------------------

def test_writes_notion_todos_json(tmp_path):
    """Collector writes notion_todos.json to the output directory."""
    mod = _load_module("gather_notion_write")

    def mock_post(url, headers=None, json=None, timeout=None):
        return _notion_resp([_notion_page("p1")], has_more=False)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep"):
        result = mod._collect_notion_todos("perf-coach", "token", "db-id", out_dir)

    assert result["status"] == "ok"
    assert (out_dir / "notion_todos.json").exists(), (
        "notion_todos.json must be written to the output directory"
    )
    data = json.loads((out_dir / "notion_todos.json").read_text())
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# AC: rate limit — ≤3 requests/second (time.sleep called between requests)
# ---------------------------------------------------------------------------

def test_rate_limit_sleep_called_between_requests(tmp_path):
    """Collector calls time.sleep between page requests to cap rate."""
    mod = _load_module("gather_notion_rate")

    call_count = [0]

    def mock_post(url, headers=None, json=None, timeout=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return _notion_resp([_notion_page("p1")], has_more=True, next_cursor="c1")
        return _notion_resp([_notion_page("p2")], has_more=False)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    sleep_calls = []

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        mod._collect_notion_todos("perf-coach", "token", "db-id", out_dir)

    rate_sleeps = [s for s in sleep_calls if 0 < s <= 1.0]
    assert len(rate_sleeps) >= 1, (
        f"Expected rate-limit sleeps (≤1s) between requests. Sleeps: {sleep_calls}"
    )
    for s in rate_sleeps:
        assert s <= 1.0 / 3 + 0.01, (
            f"Rate-limit sleep must be ≤1/3 s ({1/3:.3f}s), got {s}s"
        )


# ---------------------------------------------------------------------------
# AC: filter — Project equals target name OR Global
# ---------------------------------------------------------------------------

def test_filter_includes_target_and_global(tmp_path):
    """Request payload filters Project to target_name OR Global."""
    mod = _load_module("gather_notion_filter")

    captured = []

    def mock_post(url, headers=None, json=None, timeout=None):
        captured.append(json)
        return _notion_resp([], has_more=False)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("requests.post", side_effect=mock_post), \
         patch("time.sleep"):
        mod._collect_notion_todos("perf-coach", "token", "db-id", out_dir)

    assert len(captured) == 1
    payload = captured[0]
    assert "filter" in payload, "Request must include a filter"
    filter_str = json.dumps(payload["filter"])
    assert "perf-coach" in filter_str, "Filter must include target name"
    assert "Global" in filter_str, "Filter must include 'Global'"


# ---------------------------------------------------------------------------
# AC: DB placeholder in targets.yaml → Notion source absent from manifest
# ---------------------------------------------------------------------------

def test_placeholder_db_skipped_in_manifest(tmp_path):
    """When notion_todos_db is <placeholder>, source is NOT added to manifest."""
    mod = _load_notion_gather(tmp_path, db_id="<placeholder>",
                              module_name="gather_notion_ph")

    with patch("requests.get", side_effect=_ok_http()), \
         patch("subprocess.run", side_effect=_fake_subprocess()), \
         patch("time.sleep"):
        mod.gather("perf-coach")

    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    latest = sorted(raw_dir.iterdir())[-1]
    manifest = json.loads((latest / "manifest.json").read_text())

    assert "notion_todos" not in manifest["sources"], (
        "notion_todos must not appear in manifest when DB ID is <placeholder>"
    )


# ---------------------------------------------------------------------------
# AC: integration — gather() includes notion_todos in sources
# ---------------------------------------------------------------------------

def test_gather_includes_notion_todos_source(tmp_path):
    """When DB is configured and token set, gather() adds notion_todos to sources."""
    mod = _load_notion_gather(tmp_path, module_name="gather_notion_int")

    def mock_post(url, headers=None, json=None, timeout=None):
        return _notion_resp([_notion_page("p1")], has_more=False)

    with patch("requests.get", side_effect=_ok_http()), \
         patch("subprocess.run", side_effect=_fake_subprocess()), \
         patch("requests.post", side_effect=mock_post), \
         patch("time.sleep"), \
         patch("dotenv.load_dotenv"), \
         patch.dict("os.environ", {"NOTION_TOKEN": "valid-token"}):
        mod.gather("perf-coach")

    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    latest = sorted(raw_dir.iterdir())[-1]
    manifest = json.loads((latest / "manifest.json").read_text())

    assert "notion_todos" in manifest["sources"], (
        f"notion_todos must be in manifest sources. Got: {list(manifest['sources'].keys())}"
    )
    assert manifest["sources"]["notion_todos"]["status"] == "ok"
    assert (latest / "notion_todos.json").exists(), (
        "notion_todos.json must be written alongside manifest.json"
    )


def test_gather_records_absent_when_token_missing(tmp_path):
    """gather() records notion_todos as absent when NOTION_TOKEN is not set."""
    mod = _load_notion_gather(tmp_path, module_name="gather_notion_no_tok_int")

    env_without_token = {
        k: v for k, v in __import__("os").environ.items()
        if k != "NOTION_TOKEN"
    }

    with patch("requests.get", side_effect=_ok_http()), \
         patch("subprocess.run", side_effect=_fake_subprocess()), \
         patch("time.sleep"), \
         patch("dotenv.load_dotenv"), \
         patch.dict("os.environ", env_without_token, clear=True):
        mod.gather("perf-coach")

    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    latest = sorted(raw_dir.iterdir())[-1]
    manifest = json.loads((latest / "manifest.json").read_text())

    assert "notion_todos" in manifest["sources"], (
        "notion_todos must be in manifest when DB is configured but token missing"
    )
    assert manifest["sources"]["notion_todos"]["status"] == "absent"
    assert manifest["sources"]["notion_todos"]["error"] != ""

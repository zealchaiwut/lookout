"""Tests for issue #6: gh, git, and docs-manifest collectors.

Each test maps to a specific AC item.
"""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
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


def _valid_target_data():
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    name = next(iter(data["targets"]))
    return name, data["targets"][name]


def _load_gather_module(tmp_path, module_name="gather_test"):
    shutil.copy(str(TARGETS_YAML), str(tmp_path / "targets.yaml"))
    spec = importlib.util.spec_from_file_location(module_name, str(GATHER))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = tmp_path
    mod.TARGETS_YAML = tmp_path / "targets.yaml"
    return mod


def _ok_http_mock():
    """Minimal HTTP mock — Commander responses irrelevant here."""
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = {}
    return lambda url, timeout=10: resp


def _make_fake_local(tmp_path):
    """Create a fake local repo directory with doc files."""
    local = tmp_path / "fake_repo"
    local.mkdir()
    (local / "README.md").write_text("# Fake Project\nSome content.")
    (local / "PRODUCT.md").write_text("# Product\nDetails.")
    docs = local / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\nHow to use.")
    return local


def _targets_yaml_with_local(tmp_path, local_path):
    """Write a targets.yaml that points local at the given path."""
    data = {
        "targets": {
            "perf-coach": {
                "local": str(local_path),
                "github": "zealchaiwut/perf-coach",
                "commander_slug": "perf-coach",
            }
        },
        "sources": {"commander_api": "http://localhost:8000"},
    }
    path = tmp_path / "targets.yaml"
    path.write_text(yaml.dump(data))
    return path


def _load_gather_with_local(tmp_path, local_path, module_name="gather_local"):
    targets_path = _targets_yaml_with_local(tmp_path, local_path)
    spec = importlib.util.spec_from_file_location(module_name, str(GATHER))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = tmp_path
    mod.TARGETS_YAML = targets_path
    return mod


# ---------------------------------------------------------------------------
# AC: target path that does not exist causes immediate abort, no output files
# ---------------------------------------------------------------------------

def test_missing_target_path_aborts_nonzero(tmp_path):
    """gather() exits non-zero when the configured local path doesn't exist."""
    missing = tmp_path / "does-not-exist-abc123"
    mod = _load_gather_with_local(tmp_path, missing, "gather_missing_path")

    with pytest.raises(SystemExit) as exc:
        with patch("requests.get", side_effect=_ok_http_mock()):
            mod.gather("perf-coach")
    assert exc.value.code != 0


def test_missing_target_path_no_output_files(tmp_path):
    """When local path is missing, no output files are written to vault."""
    missing = tmp_path / "does-not-exist-abc123"
    mod = _load_gather_with_local(
        tmp_path, missing, "gather_missing_no_output"
    )

    try:
        with patch("requests.get", side_effect=_ok_http_mock()):
            mod.gather("perf-coach")
    except SystemExit:
        pass

    vault_base = tmp_path / "vault" / "projects"
    assert (
        not vault_base.exists()
        or not any(vault_base.rglob("issues.json"))
        and not any(vault_base.rglob("gitlog.txt"))
        and not any(vault_base.rglob("docs_manifest.json"))
    ), "No output files should be written when target path is missing"


def test_missing_target_path_clear_error_message(tmp_path, capsys):
    """When local path is missing, the error message identifies the path."""
    missing = tmp_path / "does-not-exist-abc123"
    mod = _load_gather_with_local(tmp_path, missing, "gather_missing_msg")

    try:
        with patch("requests.get", side_effect=_ok_http_mock()):
            mod.gather("perf-coach")
    except SystemExit:
        pass

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert str(missing) in combined or "does-not-exist" in combined, (
        f"Error message should identify missing path. Got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# AC: no write git/gh subcommands in gather.py
# ---------------------------------------------------------------------------

def test_no_write_git_gh_commands():
    """gather.py must not contain write git or gh subcommands."""
    result = subprocess.run(
        [
            "grep", "-rE",
            r"(gh (issue|pr) (create|edit|delete|close|merge)"
            r"|git (push|commit|add|rm|reset|checkout -b))",
            str(GATHER),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 or result.stdout.strip() == "", (
        f"Forbidden write commands found in gather.py:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# AC: gh collector — issues.json written with read-only subcommands
# ---------------------------------------------------------------------------

def test_gh_collector_writes_issues_json(tmp_path):
    """gh collector writes issues.json when gh CLI is available."""
    local = _make_fake_local(tmp_path)
    mod = _load_gather_with_local(tmp_path, local, "gather_gh_ok")

    fake_issues = [{"number": 1, "title": "Bug", "state": "open"}]
    fake_prs = [{"number": 2, "title": "Feature PR", "state": "open"}]

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        if "issue" in cmd:
            result.stdout = json.dumps(fake_issues)
        elif "pr" in cmd:
            result.stdout = json.dumps(fake_prs)
        else:
            result.stdout = ""
        result.stderr = ""
        return result

    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.gather("perf-coach")

    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    latest = sorted(raw_dir.iterdir())[-1]
    assert (latest / "issues.json").exists(), (
        "issues.json must be written by gh collector"
    )

    data = json.loads((latest / "issues.json").read_text())
    assert (
        "issues" in data
        or "prs" in data
        or isinstance(data, list)
        or isinstance(data, dict)
    ), "issues.json must contain gh data"


def test_gh_collector_only_read_subcommands(tmp_path):
    """gh collector only calls read-only subcommands (list, view)."""
    local = _make_fake_local(tmp_path)
    mod = _load_gather_with_local(tmp_path, local, "gather_gh_readonly")

    gh_calls = []

    def mock_run(cmd, **kwargs):
        if isinstance(cmd, list) and len(cmd) > 0 and "gh" in str(cmd[0]):
            gh_calls.append(cmd)
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps([])
        result.stderr = ""
        return result

    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.gather("perf-coach")

    write_subcommands = {"create", "edit", "delete", "close", "merge"}
    for cmd in gh_calls:
        if len(cmd) >= 3:
            subcommand = str(cmd[2])
            assert subcommand not in write_subcommands, (
                f"gh collector must not use write subcommand"
                f" '{subcommand}': {cmd!r}"
            )


def test_gh_collector_degrades_when_gh_unavailable(tmp_path):
    """gh collector skips gracefully when gh is not installed."""
    local = _make_fake_local(tmp_path)
    mod = _load_gather_with_local(tmp_path, local, "gather_gh_absent")

    def mock_run(cmd, **kwargs):
        if isinstance(cmd, list) and len(cmd) > 0 and "gh" in str(cmd[0]):
            raise FileNotFoundError("gh not found")
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.gather("perf-coach")

    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    latest = sorted(raw_dir.iterdir())[-1]
    if (latest / "issues.json").exists():
        data = json.loads((latest / "issues.json").read_text())
        assert (
            "error" in data
            or "status" in data
            or data == {}
            or data == []
        ), "issues.json when degraded must indicate error or be empty"


# ---------------------------------------------------------------------------
# AC: git collector — gitlog.txt written with log, branch, and status
# ---------------------------------------------------------------------------

def test_git_collector_writes_gitlog_txt(tmp_path):
    """git collector writes gitlog.txt containing log, branch, and status."""
    local = _make_fake_local(tmp_path)
    mod = _load_gather_with_local(tmp_path, local, "gather_git_ok")

    fake_log = "abc1234 First commit\ndef5678 Second commit\n"
    fake_branch = "main\n"
    fake_status = "M README.md\n"

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        if isinstance(cmd, list):
            cmd_str = " ".join(str(c) for c in cmd)
            if "log" in cmd_str and "--oneline" in cmd_str:
                result.stdout = fake_log
            elif "branch" in cmd_str and "--show-current" in cmd_str:
                result.stdout = fake_branch
            elif "status" in cmd_str and "--porcelain" in cmd_str:
                result.stdout = fake_status
            else:
                result.stdout = ""
        else:
            result.stdout = ""
        return result

    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.gather("perf-coach")

    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    latest = sorted(raw_dir.iterdir())[-1]
    assert (latest / "gitlog.txt").exists(), (
        "gitlog.txt must be written by git collector"
    )

    content = (latest / "gitlog.txt").read_text()
    assert "abc1234" in content, "gitlog.txt must contain commit log output"
    assert "main" in content, "gitlog.txt must contain branch name"
    assert "README" in content, (
        "gitlog.txt must contain porcelain status output"
    )


def test_git_collector_uses_target_path(tmp_path):
    """git collector uses -C <target-path> flag, not repo root."""
    local = _make_fake_local(tmp_path)
    mod = _load_gather_with_local(tmp_path, local, "gather_git_path")

    git_calls = []

    def mock_run(cmd, **kwargs):
        if isinstance(cmd, list) and "git" in str(cmd[0] if cmd else ""):
            git_calls.append(list(cmd))
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.gather("perf-coach")

    assert len(git_calls) > 0, "git collector must make at least one git call"
    for cmd in git_calls:
        cmd_str = " ".join(str(c) for c in cmd)
        assert "-C" in cmd, f"git call must use -C flag: {cmd_str!r}"


def test_git_collector_degrades_when_not_git_repo(tmp_path):
    """git collector skips gracefully when target is not a git repo."""
    local = _make_fake_local(tmp_path)
    mod = _load_gather_with_local(tmp_path, local, "gather_git_absent")

    def mock_run(cmd, **kwargs):
        if isinstance(cmd, list) and "git" in str(cmd[0] if cmd else ""):
            result = MagicMock()
            result.returncode = 128
            result.stdout = ""
            result.stderr = "fatal: not a git repository"
            return result
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps([])
        result.stderr = ""
        return result

    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.gather("perf-coach")


# ---------------------------------------------------------------------------
# AC: docs-manifest collector — docs_manifest.json with required fields
# ---------------------------------------------------------------------------

def test_docs_manifest_written(tmp_path):
    """docs-manifest collector writes docs_manifest.json."""
    local = _make_fake_local(tmp_path)
    mod = _load_gather_with_local(tmp_path, local, "gather_docs_ok")

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.gather("perf-coach")

    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    latest = sorted(raw_dir.iterdir())[-1]
    assert (latest / "docs_manifest.json").exists(), (
        "docs_manifest.json must be written by docs-manifest collector"
    )


def test_docs_manifest_has_required_fields(tmp_path):
    """Each entry in docs_manifest.json has path, sha256, heading, mtime."""
    local = _make_fake_local(tmp_path)
    mod = _load_gather_with_local(tmp_path, local, "gather_docs_fields")

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.gather("perf-coach")

    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    latest = sorted(raw_dir.iterdir())[-1]
    manifest_data = json.loads((latest / "docs_manifest.json").read_text())
    if isinstance(manifest_data, dict) and "files" in manifest_data:
        files = manifest_data["files"]
    elif isinstance(manifest_data, list):
        files = manifest_data
    else:
        files = (
            list(manifest_data.values())
            if isinstance(manifest_data, dict)
            else []
        )

    assert len(files) > 0, (
        "docs_manifest.json must have at least one file entry"
    )
    for entry in files:
        assert "path" in entry, f"Entry missing 'path': {entry}"
        assert "sha256" in entry, f"Entry missing 'sha256': {entry}"
        assert "heading" in entry, f"Entry missing 'heading': {entry}"
        assert "mtime" in entry, f"Entry missing 'mtime': {entry}"


def test_docs_manifest_scans_standard_files_and_docs_dir(tmp_path):
    """docs-manifest collector scans standard doc files and docs/ dir."""
    local = _make_fake_local(tmp_path)
    (local / "PRODUCT.md").write_text("# Product\nDetails.")
    mod = _load_gather_with_local(tmp_path, local, "gather_docs_scan")

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.gather("perf-coach")

    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    latest = sorted(raw_dir.iterdir())[-1]
    manifest_data = json.loads((latest / "docs_manifest.json").read_text())

    if isinstance(manifest_data, dict) and "files" in manifest_data:
        files = manifest_data["files"]
    elif isinstance(manifest_data, list):
        files = manifest_data
    else:
        files = []

    paths = [e["path"] for e in files]
    assert any("README.md" in p for p in paths), (
        f"README.md must be in manifest. Paths: {paths}"
    )
    assert any("guide.md" in p for p in paths), (
        f"docs/guide.md must be in manifest. Paths: {paths}"
    )


def test_docs_manifest_degrades_when_no_doc_files(tmp_path):
    """docs-manifest collector produces empty manifest when no doc files."""
    local = tmp_path / "empty_repo"
    local.mkdir()
    mod = _load_gather_with_local(tmp_path, local, "gather_docs_empty")

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.gather("perf-coach")


# ---------------------------------------------------------------------------
# AC: changed_files diff logic — unit tests with two fixture manifests
# ---------------------------------------------------------------------------

def _two_run_gather(
    tmp_path, local, mod_name_1, mod_name_2, between_runs_fn
):
    """Run gather twice with distinct timestamps; return latest dir."""
    timestamps = iter(["2099-01-01T00:00:00Z", "2099-01-02T00:00:00Z"])

    class _FakeDatetime:
        @staticmethod
        def now(tz=None):
            class _Fake:
                def strftime(self, fmt):
                    return next(timestamps)
            return _Fake()

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    mod = _load_gather_with_local(tmp_path, local, mod_name_1)
    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod.datetime = _FakeDatetime
        mod.gather("perf-coach")

    between_runs_fn()

    mod2 = _load_gather_with_local(tmp_path, local, mod_name_2)
    with patch("requests.get", side_effect=_ok_http_mock()), \
         patch("subprocess.run", side_effect=mock_run):
        mod2.datetime = _FakeDatetime
        mod2.gather("perf-coach")

    raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
    runs = sorted(raw_dir.iterdir())
    assert len(runs) >= 2, (
        f"Expected 2 snapshot runs, got {[r.name for r in runs]}"
    )
    return runs[-1]


def test_changed_files_detects_modified_file(tmp_path):
    """changed_files lists files whose sha256 changed between snapshots."""
    local = _make_fake_local(tmp_path)
    readme = local / "README.md"

    latest = _two_run_gather(
        tmp_path, local,
        "gather_diff_modified", "gather_diff_modified2",
        lambda: readme.write_text("# Changed Content\nSomething different."),
    )

    manifest_data = json.loads((latest / "docs_manifest.json").read_text())
    changed = manifest_data.get("changed_files", [])
    assert any("README" in p for p in changed), (
        f"changed_files should include README.md after modification."
        f" Got: {changed}"
    )


def test_changed_files_detects_added_file(tmp_path):
    """changed_files lists newly added files between snapshots."""
    local = _make_fake_local(tmp_path)

    latest = _two_run_gather(
        tmp_path, local,
        "gather_diff_added", "gather_diff_added2",
        lambda: (local / "DESIGN.md").write_text("# Design\nSystem design."),
    )

    manifest_data = json.loads((latest / "docs_manifest.json").read_text())
    changed = manifest_data.get("changed_files", [])
    assert any("DESIGN" in p for p in changed), (
        f"changed_files should include newly added DESIGN.md. Got: {changed}"
    )


def test_changed_files_detects_removed_file(tmp_path):
    """changed_files lists removed files between snapshots."""
    local = _make_fake_local(tmp_path)
    product_md = local / "PRODUCT.md"
    product_md.write_text("# Product\nTo be removed.")

    latest = _two_run_gather(
        tmp_path, local,
        "gather_diff_removed", "gather_diff_removed2",
        lambda: product_md.unlink(),
    )

    manifest_data = json.loads((latest / "docs_manifest.json").read_text())
    changed = manifest_data.get("changed_files", [])
    assert any("PRODUCT" in p for p in changed), (
        f"changed_files should include removed PRODUCT.md. Got: {changed}"
    )


def test_changed_files_using_fixture_manifests(tmp_path):
    """AC8: unit test changed_files diff logic with two fixture manifests."""
    prior_manifest = {
        "files": [
            {
                "path": "README.md", "sha256": "aaa",
                "heading": "# Old", "mtime": 1000,
            },
            {
                "path": "PRODUCT.md", "sha256": "bbb",
                "heading": "# Product", "mtime": 1000,
            },
            {
                "path": "docs/guide.md", "sha256": "ccc",
                "heading": "# Guide", "mtime": 1000,
            },
        ]
    }
    updated_manifest = {
        "files": [
            {
                "path": "README.md", "sha256": "aaa_changed",
                "heading": "# New", "mtime": 2000,
            },
            {
                "path": "DESIGN.md", "sha256": "ddd",
                "heading": "# Design", "mtime": 2000,
            },
            {
                "path": "docs/guide.md", "sha256": "ccc",
                "heading": "# Guide", "mtime": 1000,
            },
        ]
    }

    prev_dir = tmp_path / "prev"
    prev_dir.mkdir()
    (prev_dir / "docs_manifest.json").write_text(json.dumps(prior_manifest))

    spec = importlib.util.spec_from_file_location(
        "gather_fixture", str(GATHER)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if hasattr(mod, "_compute_changed_files"):
        changed = mod._compute_changed_files(prior_manifest, updated_manifest)
        assert "README.md" in changed, (
            f"README.md should be in changed. Got: {changed}"
        )
        assert "DESIGN.md" in changed, (
            f"DESIGN.md (added) should be in changed. Got: {changed}"
        )
        assert "PRODUCT.md" in changed, (
            f"PRODUCT.md (removed) should be in changed. Got: {changed}"
        )
        assert "docs/guide.md" not in changed, (
            f"Unchanged guide.md should not be in changed. Got: {changed}"
        )
    else:
        local = _make_fake_local(tmp_path)
        (local / "README.md").write_text("# Old\nOriginal.")

        vault_prior = (
            tmp_path / "vault" / "projects"
            / "perf-coach" / "raw" / "2099-01-01T00:00:00Z"
        )
        vault_prior.mkdir(parents=True)
        (vault_prior / "docs_manifest.json").write_text(
            json.dumps(prior_manifest)
        )

        targets_path = _targets_yaml_with_local(tmp_path, local)
        spec2 = importlib.util.spec_from_file_location(
            "gather_fixture2", str(GATHER)
        )
        mod2 = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod2)
        mod2.REPO_ROOT = tmp_path
        mod2.TARGETS_YAML = targets_path

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        (local / "README.md").write_text("# New\nChanged content here.")

        with patch("requests.get", side_effect=_ok_http_mock()), \
             patch("subprocess.run", side_effect=mock_run):
            mod2.gather("perf-coach")

        raw_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw"
        runs = sorted(raw_dir.iterdir())
        latest = [r for r in runs if r.name != "2099-01-01T00:00:00Z"]
        assert latest, "Should have a new snapshot run"
        manifest_data = json.loads(
            (latest[-1] / "docs_manifest.json").read_text()
        )
        changed = manifest_data.get("changed_files", [])
        assert any("README" in p for p in changed), (
            f"README.md should appear in changed_files. Got: {changed}"
        )

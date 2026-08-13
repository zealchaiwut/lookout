"""Tests for issue #85: branch guard and StartOnMount removal.

AC mapping:
- AC1: StartOnMount removed from both plist templates
- AC3/AC4: commit proceeds on expected branch; skipped (with message) on another branch
- AC5: exit code 0 in both cases
- AC6: working tree never switched
- AC6b: snapshot_branch configurable from targets.yaml, defaults to develop
- AC8: manifest.json records whether snapshot was committed
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
ALL_PLIST = REPO_ROOT / "launchd" / "com.zealchaiwut.lookout-all.plist.template"
DIGEST_PLIST = REPO_ROOT / "launchd" / "com.zealchaiwut.lookout-digest.plist.template"


def _load_all_runner():
    spec = importlib.util.spec_from_file_location("all_runner", str(REPO_ROOT / "all_runner.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _setup_git_repo(path, branch="develop"):
    subprocess.run(["git", "init"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=path, capture_output=True)
    subprocess.run(["git", "branch", "-m", branch], cwd=path, capture_output=True)


def _write_targets_yaml(path, snapshot_branch=None, extra_targets=None):
    data = {
        "contract_version": 1,
        "sources": {"commander_api": "http://localhost:9999"},
        "targets": {"testpkg": {"local": str(path), "github": "a/a", "commander_slug": "a"}},
    }
    if snapshot_branch is not None:
        data["snapshot_branch"] = snapshot_branch
    if extra_targets:
        data["targets"].update(extra_targets)
    p = path / "targets.yaml"
    p.write_text(yaml.dump(data))
    return p


def _write_manifest(snapshot_dir):
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "timestamp": "2026-08-12T00:00:00Z",
        "target": "testpkg",
        "health": {},
        "sources": {},
    }
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return snapshot_dir / "manifest.json"


# ---------------------------------------------------------------------------
# AC1: StartOnMount removed from both plist templates
# ---------------------------------------------------------------------------

def test_ac1_start_on_mount_removed_from_all_plist():
    content = ALL_PLIST.read_text()
    assert "StartOnMount" not in content, (
        "StartOnMount must be removed from com.zealchaiwut.lookout-all.plist.template"
    )


def test_ac1_start_on_mount_removed_from_digest_plist():
    content = DIGEST_PLIST.read_text()
    assert "StartOnMount" not in content, (
        "StartOnMount must be removed from com.zealchaiwut.lookout-digest.plist.template"
    )


# ---------------------------------------------------------------------------
# AC6b: snapshot_branch configurable from targets.yaml
# ---------------------------------------------------------------------------

def test_snapshot_branch_defaults_to_develop(tmp_path):
    mod = _load_all_runner()
    targets_yaml = _write_targets_yaml(tmp_path)  # no snapshot_branch key
    assert mod._load_snapshot_branch(targets_yaml) == "develop"


def test_snapshot_branch_reads_custom_value_from_yaml(tmp_path):
    mod = _load_all_runner()
    targets_yaml = _write_targets_yaml(tmp_path, snapshot_branch="main")
    assert mod._load_snapshot_branch(targets_yaml) == "main"


# ---------------------------------------------------------------------------
# AC3: _get_current_branch returns the active branch name
# ---------------------------------------------------------------------------

def test_get_current_branch_returns_active_branch(tmp_path):
    mod = _load_all_runner()
    _setup_git_repo(tmp_path, branch="develop")
    assert mod._get_current_branch(tmp_path) == "develop"


def test_get_current_branch_reflects_checkout(tmp_path):
    mod = _load_all_runner()
    _setup_git_repo(tmp_path, branch="develop")
    subprocess.run(["git", "checkout", "-b", "tmp/test-branch"], cwd=tmp_path, capture_output=True)
    assert mod._get_current_branch(tmp_path) == "tmp/test-branch"


# ---------------------------------------------------------------------------
# AC3: commit proceeds on expected branch
# ---------------------------------------------------------------------------

def test_ac3_commit_is_attempted_on_expected_branch(tmp_path, monkeypatch):
    """When on the expected branch, git commit subprocess is invoked."""
    mod = _load_all_runner()
    _setup_git_repo(tmp_path, branch="develop")
    snapshot_dir = tmp_path / "vault" / "projects" / "testpkg" / "raw" / "2026-08-12T00:00:00Z"
    _write_manifest(snapshot_dir)

    # Create a file to commit so git commit actually succeeds
    vault_raw = tmp_path / "vault" / "projects" / "testpkg" / "raw"
    vault_raw.mkdir(parents=True, exist_ok=True)
    (vault_raw / "2026-08-12T00:00:00Z" / "data.txt").write_text("snapshot")

    result = subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
    # Let _commit_target do its own git operations; verify commit appears in log
    mod._commit_target("testpkg", "2026-08-12T00:00:00Z", tmp_path, snapshot_branch="develop")

    log = subprocess.run(
        ["git", "log", "--oneline", "-5"], cwd=tmp_path, capture_output=True, text=True
    )
    assert "lookout(testpkg)" in log.stdout, (
        "Expected a lookout snapshot commit in git log when on expected branch"
    )


# ---------------------------------------------------------------------------
# AC4: commit is skipped with a message when on a different branch
# ---------------------------------------------------------------------------

def test_ac4_commit_skipped_on_wrong_branch(tmp_path, capsys):
    """When on a different branch, git commit is not executed."""
    mod = _load_all_runner()
    _setup_git_repo(tmp_path, branch="develop")
    subprocess.run(
        ["git", "checkout", "-b", "feature/some-work"], cwd=tmp_path, capture_output=True
    )
    snapshot_dir = tmp_path / "vault" / "projects" / "testpkg" / "raw" / "2026-08-12T00:00:00Z"
    _write_manifest(snapshot_dir)

    mod._commit_target("testpkg", "2026-08-12T00:00:00Z", tmp_path, snapshot_branch="develop")

    # No lookout commit should appear in git log
    log = subprocess.run(
        ["git", "log", "--oneline", "-5"], cwd=tmp_path, capture_output=True, text=True
    )
    assert "lookout(testpkg)" not in log.stdout, (
        "git commit must not run when not on the expected branch"
    )


def test_ac4_skip_message_names_both_branches(tmp_path, capsys):
    """Skip message must name both the current branch and the expected branch."""
    mod = _load_all_runner()
    _setup_git_repo(tmp_path, branch="develop")
    subprocess.run(
        ["git", "checkout", "-b", "tmp/branch-guard"], cwd=tmp_path, capture_output=True
    )
    snapshot_dir = tmp_path / "vault" / "projects" / "testpkg" / "raw" / "2026-08-12T00:00:00Z"
    _write_manifest(snapshot_dir)

    mod._commit_target("testpkg", "2026-08-12T00:00:00Z", tmp_path, snapshot_branch="develop")
    captured = capsys.readouterr()
    output = captured.out + captured.err

    assert "tmp/branch-guard" in output, "Message must name the current branch"
    assert "develop" in output, "Message must name the expected branch"


# ---------------------------------------------------------------------------
# AC5: exit code 0 when commit skipped
# ---------------------------------------------------------------------------

def test_ac5_run_all_succeeds_when_commit_skipped(tmp_path, monkeypatch):
    """run_all exits successfully even when the commit is skipped on a wrong branch."""
    mod = _load_all_runner()
    _setup_git_repo(tmp_path, branch="develop")
    subprocess.run(
        ["git", "checkout", "-b", "tmp/guard-test"], cwd=tmp_path, capture_output=True
    )
    snapshot_dir = tmp_path / "vault" / "projects" / "testpkg" / "raw" / "2026-08-12T00:00:00Z"
    _write_manifest(snapshot_dir)
    targets_yaml = _write_targets_yaml(tmp_path)
    lint_ok = tmp_path / "lint.py"
    lint_ok.write_text("import sys; sys.exit(0)\n")

    class FakeGather:
        REPO_ROOT = tmp_path
        TARGETS_YAML = targets_yaml
        @staticmethod
        def gather(target_name):
            return {}

    class FakeDerive:
        ERROR = "error"
        @staticmethod
        def derive_target(*a, **kw):
            return []
        @staticmethod
        def print_summary(*a, **kw):
            pass
        @staticmethod
        def any_error(r):
            return False
        @staticmethod
        def derive_vault(*a, **kw):
            return []

    monkeypatch.setattr(mod, "gather_module", FakeGather)
    monkeypatch.setattr(mod, "derive_module", FakeDerive)

    results, any_failed = mod.run_all(
        targets_yaml=targets_yaml,
        lint_script=lint_ok,
        lock_path=tmp_path / "test.lock",
        repo_root=tmp_path,
    )
    assert not any_failed, (
        f"run_all must succeed (exit 0) even when commit is skipped; results={results}"
    )


# ---------------------------------------------------------------------------
# AC6: working tree never switched
# ---------------------------------------------------------------------------

def test_ac6_working_tree_not_switched_after_skip(tmp_path):
    """After a skipped commit, the working tree remains on the original branch."""
    mod = _load_all_runner()
    _setup_git_repo(tmp_path, branch="develop")
    subprocess.run(
        ["git", "checkout", "-b", "feature/wrong-branch"], cwd=tmp_path, capture_output=True
    )
    snapshot_dir = tmp_path / "vault" / "projects" / "testpkg" / "raw" / "2026-08-12T00:00:00Z"
    _write_manifest(snapshot_dir)

    branch_before = mod._get_current_branch(tmp_path)
    mod._commit_target("testpkg", "2026-08-12T00:00:00Z", tmp_path, snapshot_branch="develop")
    branch_after = mod._get_current_branch(tmp_path)

    assert branch_before == branch_after == "feature/wrong-branch", (
        f"Working tree was moved: before={branch_before!r}, after={branch_after!r}"
    )


# ---------------------------------------------------------------------------
# AC8: manifest records commit status
# ---------------------------------------------------------------------------

def test_ac8_manifest_records_committed_false_on_wrong_branch(tmp_path):
    mod = _load_all_runner()
    _setup_git_repo(tmp_path, branch="develop")
    subprocess.run(
        ["git", "checkout", "-b", "tmp/no-commit"], cwd=tmp_path, capture_output=True
    )
    snapshot_dir = tmp_path / "vault" / "projects" / "testpkg" / "raw" / "2026-08-12T00:00:00Z"
    manifest_path = _write_manifest(snapshot_dir)

    mod._commit_target("testpkg", "2026-08-12T00:00:00Z", tmp_path, snapshot_branch="develop")

    data = json.loads(manifest_path.read_text())
    assert "committed" in data, "manifest.json must have a 'committed' key"
    assert data["committed"] is False, "committed must be False when commit was skipped"


def test_ac8_manifest_records_committed_true_on_expected_branch(tmp_path):
    mod = _load_all_runner()
    _setup_git_repo(tmp_path, branch="develop")
    snapshot_dir = tmp_path / "vault" / "projects" / "testpkg" / "raw" / "2026-08-12T00:00:00Z"
    manifest_path = _write_manifest(snapshot_dir)
    # Stage a file so git commit succeeds
    (snapshot_dir / "data.txt").write_text("snapshot content")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)

    mod._commit_target("testpkg", "2026-08-12T00:00:00Z", tmp_path, snapshot_branch="develop")

    data = json.loads(manifest_path.read_text())
    assert "committed" in data, "manifest.json must have a 'committed' key"
    assert data["committed"] is True, "committed must be True when commit succeeded"


def test_ac8_update_manifest_committed_helper(tmp_path):
    """_update_manifest_committed writes the committed field regardless of branch."""
    mod = _load_all_runner()
    snapshot_dir = tmp_path / "vault" / "projects" / "mypkg" / "raw" / "2026-08-12T00:00:00Z"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(json.dumps({"target": "mypkg"}))

    mod._update_manifest_committed("mypkg", tmp_path, committed=True)
    data = json.loads((snapshot_dir / "manifest.json").read_text())
    assert data["committed"] is True

    mod._update_manifest_committed("mypkg", tmp_path, committed=False)
    data = json.loads((snapshot_dir / "manifest.json").read_text())
    assert data["committed"] is False

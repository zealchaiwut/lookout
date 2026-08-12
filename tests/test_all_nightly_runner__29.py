"""Tests for issue #29: lookout --all nightly runner with launchd scheduling.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
BIN_LOOKOUT = REPO_ROOT / "bin" / "lookout"
TARGETS_YAML = REPO_ROOT / "targets.yaml"
PLIST_PATH = REPO_ROOT / "launchd" / "com.zealchaiwut.lookout-all.plist.template"
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.sh"
README_PATH = REPO_ROOT / "README.md"

_PYTHON = sys.executable


def _load_all_runner():
    """Load all_runner module (created by this issue's implementation)."""
    path = REPO_ROOT / "all_runner.py"
    spec = importlib.util.spec_from_file_location("all_runner", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_targets_yaml(tmp_path, targets_dict):
    """Write a minimal targets.yaml with given targets."""
    p = tmp_path / "targets.yaml"
    p.write_text(yaml.dump({
        "sources": {"commander_api": "http://localhost:9999"},
        "targets": targets_dict,
    }))
    return p


def _setup_git_repo(path):
    """Create a minimal git repo at path."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=path, capture_output=True)


# ---------------------------------------------------------------------------
# AC1: --all flag is accepted and discovers all registered targets
# ---------------------------------------------------------------------------


def test_ac1_all_flag_accepted_with_empty_registry(tmp_path):
    """AC1: lookout --all exits without 'unrecognized argument' error."""
    targets_yaml = _make_targets_yaml(tmp_path, {})  # no targets → run completes instantly
    env = os.environ.copy()
    env["LOOKOUT_TARGETS_YAML"] = str(targets_yaml)
    env["LOOKOUT_LOCK_PATH"] = str(tmp_path / "test.lock")

    result = subprocess.run(
        [_PYTHON, str(BIN_LOOKOUT), "--all"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    combined = (result.stdout + result.stderr).lower()
    assert "unrecognized" not in combined, f"--all flag not recognised:\n{combined}"
    assert "unknown argument" not in combined, f"--all flag not recognised:\n{combined}"


def test_ac1_all_runner_module_exists():
    """AC1: all_runner.py exists and has run_all function."""
    runner_path = REPO_ROOT / "all_runner.py"
    assert runner_path.exists(), "all_runner.py not found in repo root"
    mod = _load_all_runner()
    assert hasattr(mod, "run_all"), "all_runner.py missing run_all function"


def test_ac1_load_targets_returns_all_from_yaml(tmp_path):
    """AC1: all_runner discovers every target registered in targets.yaml."""
    targets_dict = {
        "alpha": {"local": str(tmp_path), "github": "a/a", "commander_slug": "a"},
        "beta":  {"local": str(tmp_path), "github": "b/b", "commander_slug": "b"},
        "gamma": {"local": str(tmp_path), "github": "c/c", "commander_slug": "c"},
    }
    targets_yaml = _make_targets_yaml(tmp_path, targets_dict)
    mod = _load_all_runner()
    discovered = mod.load_targets_from_yaml(targets_yaml)
    assert set(discovered) == {"alpha", "beta", "gamma"}, (
        f"load_targets_from_yaml returned {discovered}"
    )


# ---------------------------------------------------------------------------
# AC3 + AC4: Failure isolation and summary output
# ---------------------------------------------------------------------------


def test_ac3_failure_does_not_abort_remaining(tmp_path, monkeypatch):
    """AC3: When one target fails, remaining targets are still processed."""
    _setup_git_repo(tmp_path)
    targets_dict = {}
    for i in range(3):
        d = tmp_path / f"good-{i}"
        d.mkdir()
        targets_dict[f"good-{i}"] = {
            "local": str(d), "github": "t/t", "commander_slug": "t"
        }
    targets_dict["broken"] = {
        "local": str(tmp_path / "no-such-path-xyz"),
        "github": "t/t", "commander_slug": "t",
    }
    targets_yaml = _make_targets_yaml(tmp_path, targets_dict)
    lint_ok = tmp_path / "lint_ok.py"
    lint_ok.write_text("import sys; sys.exit(0)\n")

    mod = _load_all_runner()
    # Monkeypatch commit to no-op (avoid git operations in real repo)
    monkeypatch.setattr(mod, "_commit_target", lambda *a, **kw: None)

    processed = []

    def mock_gather(target_name):
        processed.append(target_name)
        if target_name == "broken":
            raise SystemExit(1)
        return {"commander": {"status": "absent", "count": 0},
                "notion": {"status": "absent", "count": 0},
                "journal": {"status": "absent", "count": 0}}

    monkeypatch.setattr(mod.gather_module, "gather", mock_gather)

    results, any_failed = mod.run_all(
        targets_yaml=targets_yaml,
        lint_script=lint_ok,
        lock_path=tmp_path / "test.lock",
        repo_root=tmp_path,
    )

    assert "broken" in processed, "broken target was never attempted"
    for i in range(3):
        assert f"good-{i}" in processed, f"good-{i} was not processed"
    assert any_failed, "Expected any_failed=True"

    success_targets = {r[0] for r in results if r[1]}
    failed_targets = {r[0] for r in results if not r[1]}
    assert "broken" in failed_targets
    assert len(success_targets) == 3


def test_ac4_summary_names_each_target_with_status(tmp_path, monkeypatch, capsys):
    """AC4: Summary output contains each target's name and status."""
    _setup_git_repo(tmp_path)
    targets_dict = {
        "alpha": {"local": str(tmp_path), "github": "t/t", "commander_slug": "t"},
        "broken": {"local": str(tmp_path / "no-exist"), "github": "t/t", "commander_slug": "t"},
    }
    targets_yaml = _make_targets_yaml(tmp_path, targets_dict)
    lint_ok = tmp_path / "lint_ok.py"
    lint_ok.write_text("import sys; sys.exit(0)\n")

    mod = _load_all_runner()
    monkeypatch.setattr(mod, "_commit_target", lambda *a, **kw: None)

    def mock_gather(target_name):
        if target_name == "broken":
            raise SystemExit(1)
        return {}

    monkeypatch.setattr(mod.gather_module, "gather", mock_gather)

    results, any_failed = mod.run_all(
        targets_yaml=targets_yaml,
        lint_script=lint_ok,
        lock_path=tmp_path / "test.lock",
        repo_root=tmp_path,
    )

    captured = capsys.readouterr()
    output = captured.out + captured.err

    assert "alpha" in output, f"'alpha' not in summary output:\n{output}"
    assert "broken" in output, f"'broken' not in summary output:\n{output}"
    lower = output.lower()
    has_summary = "summary" in lower or "result" in lower or "status" in lower
    assert has_summary, f"No summary section in output:\n{output}"
    assert "success" in lower or "ok" in lower, "No success indicator in summary"
    assert "fail" in lower or "error" in lower, "No failure indicator in summary"


# ---------------------------------------------------------------------------
# AC5: Five targets, one broken — exactly one failure reported
# ---------------------------------------------------------------------------


def test_ac5_five_targets_one_broken_one_failure(tmp_path, monkeypatch):
    """AC5: Five targets, one broken; run completes reporting exactly one failure."""
    _setup_git_repo(tmp_path)
    targets_dict = {}
    for i in range(4):
        targets_dict[f"good-{i}"] = {
            "local": str(tmp_path), "github": "t/t", "commander_slug": "t"
        }
    targets_dict["broken"] = {
        "local": str(tmp_path / "no-such-abc"), "github": "t/t", "commander_slug": "t"
    }
    targets_yaml = _make_targets_yaml(tmp_path, targets_dict)
    lint_ok = tmp_path / "lint_ok.py"
    lint_ok.write_text("import sys; sys.exit(0)\n")

    mod = _load_all_runner()
    monkeypatch.setattr(mod, "_commit_target", lambda *a, **kw: None)

    def mock_gather(target_name):
        if target_name == "broken":
            raise SystemExit(1)
        return {}

    monkeypatch.setattr(mod.gather_module, "gather", mock_gather)

    results, any_failed = mod.run_all(
        targets_yaml=targets_yaml,
        lint_script=lint_ok,
        lock_path=tmp_path / "test.lock",
        repo_root=tmp_path,
    )

    assert any_failed, "Expected any_failed=True"

    succeeded = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]

    assert len(succeeded) == 4, f"Expected 4 successes, got {len(succeeded)}: {succeeded}"
    assert len(failed) == 1, f"Expected 1 failure, got {len(failed)}: {failed}"
    assert failed[0][0] == "broken", f"Expected 'broken' to fail, got {failed[0][0]}"


# ---------------------------------------------------------------------------
# AC8: Lock directory prevents concurrent invocation
# ---------------------------------------------------------------------------


def test_ac8_lock_held_exits_nonzero(tmp_path):
    """AC8: When lock dir exists, --all exits non-zero with human-readable message."""
    lock_dir = tmp_path / "lookout-all.lock"
    lock_dir.mkdir()

    env = os.environ.copy()
    env["LOOKOUT_LOCK_PATH"] = str(lock_dir)
    env["LOOKOUT_TARGETS_YAML"] = str(TARGETS_YAML)

    result = subprocess.run(
        [_PYTHON, str(BIN_LOOKOUT), "--all"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    assert result.returncode != 0, "Expected non-zero exit when lock is held"
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, "Got a traceback instead of a user message"
    lock_mentioned = str(lock_dir) in combined or "lock" in combined.lower()
    assert lock_mentioned, f"Lock path not mentioned in output:\n{combined}"


def test_ac8_lock_message_is_readable(tmp_path):
    """AC8: The blocked-run message identifies the lock path clearly."""
    lock_dir = tmp_path / "lookout-all.lock"
    lock_dir.mkdir()

    env = os.environ.copy()
    env["LOOKOUT_LOCK_PATH"] = str(lock_dir)
    env["LOOKOUT_TARGETS_YAML"] = str(TARGETS_YAML)

    result = subprocess.run(
        [_PYTHON, str(BIN_LOOKOUT), "--all"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    combined = result.stdout + result.stderr
    # Must contain lock path (or at least the lock filename) and a path separator
    assert ("/" in combined or "\\" in combined), "No path separator in message"
    assert "lock" in combined.lower(), "Word 'lock' missing from message"


def test_ac8_lock_released_after_successful_run(tmp_path, monkeypatch):
    """AC8: Lock directory is removed after the run completes."""
    lock_path = tmp_path / "test-run.lock"
    targets_yaml = _make_targets_yaml(tmp_path, {})  # no targets → quick exit
    lint_ok = tmp_path / "lint.py"
    lint_ok.write_text("import sys; sys.exit(0)\n")

    mod = _load_all_runner()
    monkeypatch.setattr(mod, "_commit_target", lambda *a, **kw: None)
    monkeypatch.setattr(mod.gather_module, "gather", lambda t: {})

    mod.run_all(
        targets_yaml=targets_yaml,
        lint_script=lint_ok,
        lock_path=lock_path,
        repo_root=tmp_path,
    )
    assert not lock_path.exists(), "Lock directory was not cleaned up after run"


# ---------------------------------------------------------------------------
# AC6: launchd plist exists at expected location
# ---------------------------------------------------------------------------


def test_ac6_plist_file_exists():
    """AC6: launchd plist exists in the repo under launchd/."""
    assert PLIST_PATH.exists(), f"Plist not found at {PLIST_PATH}"


# ---------------------------------------------------------------------------
# AC7: plist follows journal conventions
# ---------------------------------------------------------------------------


def test_ac7_plist_has_start_calendar_interval():
    """AC7: Plist uses StartCalendarInterval for scheduling."""
    if not PLIST_PATH.exists():
        pytest.skip("plist not yet created")
    content = PLIST_PATH.read_text()
    assert "StartCalendarInterval" in content, "Plist missing StartCalendarInterval"


def test_ac7_plist_scheduled_at_0615():
    """AC7: Plist is scheduled for Hour=6, Minute=15."""
    if not PLIST_PATH.exists():
        pytest.skip("plist not yet created")
    content = PLIST_PATH.read_text()
    assert "<integer>6</integer>" in content, "Hour not set to 6"
    assert "<integer>15</integer>" in content, "Minute not set to 15"


def test_ac7_plist_has_wake_catchup():
    """AC7: Plist has StartOnMount or RunAtLoad for wake catch-up."""
    if not PLIST_PATH.exists():
        pytest.skip("plist not yet created")
    content = PLIST_PATH.read_text()
    catchup_keys = ["StartOnMount", "RunAtLoad", "AbandonProcessGroup"]
    assert any(k in content for k in catchup_keys), (
        f"Plist missing wake catch-up key (one of {catchup_keys})"
    )


def test_ac7_plist_or_install_references_env():
    """AC7: Plist or install script sources environment tokens from .env."""
    plist_ok = PLIST_PATH.exists() and ".env" in PLIST_PATH.read_text()
    install_ok = (
        INSTALL_SCRIPT.exists()
        and ".env" in INSTALL_SCRIPT.read_text()
    )
    assert plist_ok or install_ok, (
        "Neither plist nor install.sh references the .env file"
    )


# ---------------------------------------------------------------------------
# AC9: install script exists and is idempotent
# ---------------------------------------------------------------------------


def test_ac9_install_script_exists():
    """AC9: scripts/install.sh exists."""
    assert INSTALL_SCRIPT.exists(), f"Install script not found at {INSTALL_SCRIPT}"


def test_ac9_install_uses_launchctl():
    """AC9: install.sh uses launchctl to load the plist."""
    if not INSTALL_SCRIPT.exists():
        pytest.skip("install.sh not yet created")
    content = INSTALL_SCRIPT.read_text()
    assert "launchctl" in content, "install.sh must use launchctl"


def test_ac9_install_is_idempotent():
    """AC9: install.sh handles an already-loaded job gracefully."""
    if not INSTALL_SCRIPT.exists():
        pytest.skip("install.sh not yet created")
    content = INSTALL_SCRIPT.read_text()
    has_guard = (
        "bootout" in content
        or "unload" in content
        or "2>/dev/null" in content
        or "|| true" in content
        or "if " in content
    )
    assert has_guard, (
        "install.sh appears to lack idempotency guard "
        "(bootout/unload/2>/dev/null/|| true)"
    )


# ---------------------------------------------------------------------------
# AC10: README documents the nightly runner
# ---------------------------------------------------------------------------


def test_ac10_readme_has_nightly_section():
    """AC10: README.md documents the nightly runner."""
    content = README_PATH.read_text()
    lower = content.lower()
    assert "nightly" in lower or "lookout --all" in content, (
        "README.md missing nightly runner section"
    )


def test_ac10_readme_covers_install():
    """AC10: README explains how to install the launchd plist."""
    content = README_PATH.read_text()
    lower = content.lower()
    assert "install" in lower and ("launchctl" in lower or "plist" in lower), (
        "README missing install steps for the launchd plist"
    )


def test_ac10_readme_covers_manual_run():
    """AC10: README shows how to run manually."""
    content = README_PATH.read_text()
    assert "lookout --all" in content or "bin/lookout --all" in content, (
        "README missing manual run instructions"
    )


def test_ac10_readme_covers_lock_release():
    """AC10: README explains how to release a stuck lock."""
    content = README_PATH.read_text()
    lower = content.lower()
    assert "lock" in lower and ("rmdir" in content or "rm -r" in content or "rm -rf" in content), (
        "README missing lock release instructions"
    )

"""all_runner.py — lookout --all pipeline: run every registered target.

Exported entry points:
  load_targets_from_yaml(path) → list[str]
  run_one(target, targets_yaml, lint_script, repo_root) → (bool, str)
  run_all(targets_yaml, lint_script, lock_path, repo_root) → (list, bool)
  _commit_target(target, timestamp, repo_root)  — patchable in tests
"""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import gather as gather_module

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"
LINT_SCRIPT = REPO_ROOT / ".claude" / "skills" / "lookout" / "scripts" / "lint.py"
LOCK_PATH = Path("/tmp/lookout-all.lock")


def load_targets_from_yaml(path):
    """Return list of target names from the given targets.yaml path."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return list(data.get("targets", {}).keys())


def _commit_target(target, timestamp, repo_root):
    """Add vault snapshot files and commit. Separated for test patching."""
    vault_path = f"vault/projects/{target}/raw"
    subprocess.run(["git", "add", "-f", vault_path], cwd=repo_root, check=False)
    subprocess.run(
        ["git", "commit", "-m", f"lookout({target}): snapshot {timestamp}"],
        cwd=repo_root,
    )


def run_one(target, targets_yaml, lint_script, repo_root):
    """Run the full pipeline for one target.

    Returns:
        (success: bool, reason: str)
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Gather
    gather_module.REPO_ROOT = repo_root
    gather_module.TARGETS_YAML = targets_yaml
    try:
        gather_module.gather(target)
    except SystemExit as exc:
        code = exc.code if exc.code is not None else 0
        if code != 0:
            return False, f"gather exited with code {code}"
    except Exception as exc:
        return False, f"gather raised {type(exc).__name__}: {exc}"

    # Lint
    lint_result = subprocess.run(
        [sys.executable, str(lint_script)],
        cwd=repo_root,
        capture_output=True,
    )
    if lint_result.returncode != 0:
        return False, f"lint failed (exit {lint_result.returncode})"

    # Commit
    _commit_target(target, timestamp, repo_root)
    return True, "ok"


def run_all(targets_yaml=None, lint_script=None, lock_path=None, repo_root=None):
    """Run the full pipeline for every registered target.

    Acquires a mkdir-based lock to prevent concurrent invocations. Processes
    each target independently — a failure on one target does not abort the rest.

    Returns:
        (results: list[(target, success, reason)], any_failed: bool)
    """
    _targets_yaml = targets_yaml or TARGETS_YAML
    _lint_script = lint_script or LINT_SCRIPT
    _lock_path = Path(lock_path) if lock_path else LOCK_PATH
    _repo_root = repo_root or REPO_ROOT

    # Acquire lock
    try:
        _lock_path.mkdir()
    except FileExistsError:
        print(
            f"Another run is in progress (lock: {_lock_path}). Exiting.",
            file=sys.stderr,
        )
        sys.exit(1)

    targets = load_targets_from_yaml(_targets_yaml)
    results = []

    try:
        for target in targets:
            print(f"\n--- [{target}] ---")
            success, reason = run_one(target, _targets_yaml, _lint_script, _repo_root)
            results.append((target, success, reason))
            status = "ok" if success else f"FAILED: {reason}"
            print(f"[{target}] {status}")
    finally:
        try:
            _lock_path.rmdir()
        except Exception:
            pass

    # Summary
    any_failed = any(not r[1] for r in results)
    print("\n=== lookout --all summary ===")
    for target, success, reason in results:
        if success:
            print(f"  {target}: success")
        else:
            print(f"  {target}: failed — {reason}")

    return results, any_failed

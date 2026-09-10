"""all_runner.py — lookout --all pipeline: run every registered target.

Exported entry points:
  load_targets_from_yaml(path) → list[str]
  _load_snapshot_branch(targets_yaml_path) → str
  _get_current_branch(repo_root) → str
  _update_manifest_committed(target, repo_root, committed) → None
  run_one(target, targets_yaml, lint_script, repo_root, snapshot_branch) → (bool, str)
  run_all(targets_yaml, lint_script, lock_path, repo_root) → (list, bool)
  _commit_target(target, timestamp, repo_root, snapshot_branch)  — patchable in tests
  _update_sweep_status(prev, results, now) → dict
  _write_sweep_status(vault_dir, status) → None
  _commit_sweep_status(repo_root, snapshot_branch)  — patchable in tests
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import gather as gather_module
import derive as derive_module

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"
LINT_SCRIPT = REPO_ROOT / ".claude" / "skills" / "lookout" / "scripts" / "lint.py"
LOCK_PATH = Path("/tmp/lookout-all.lock")
SWEEP_STATUS_JSON = "sweep-status.json"
SWEEP_STATUS_MD = "sweep-status.md"
_LINT_DETAIL_LINES = 20


def load_targets_from_yaml(path):
    """Return list of target names from the given targets.yaml path."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return list(data.get("targets", {}).keys())


def _load_snapshot_branch(targets_yaml_path):
    """Return the configured snapshot branch, defaulting to 'develop'."""
    with open(targets_yaml_path) as f:
        data = yaml.safe_load(f)
    return data.get("snapshot_branch", "develop")


def _get_current_branch(repo_root):
    """Return the name of the currently checked-out branch."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _update_manifest_committed(target, repo_root, committed):
    """Update the latest snapshot manifest.json with the committed status."""
    raw_dir = Path(repo_root) / "vault" / "projects" / target / "raw"
    if not raw_dir.exists():
        return
    snapshots = sorted(d for d in raw_dir.iterdir() if d.is_dir())
    if not snapshots:
        return
    manifest_path = snapshots[-1] / "manifest.json"
    if not manifest_path.exists():
        return
    try:
        with open(manifest_path) as f:
            data = json.load(f)
        data["committed"] = committed
        with open(manifest_path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _commit_target(target, timestamp, repo_root, snapshot_branch=None):
    """Add vault snapshot files and commit. Separated for test patching.

    Skips the commit (with a printed message) when the working tree is not on
    the expected snapshot branch. The working tree is never switched — the run
    must not move a developer's checkout out from under them.
    """
    _snapshot_branch = snapshot_branch or "develop"
    current_branch = _get_current_branch(repo_root)

    if current_branch != _snapshot_branch:
        print(
            f"lookout: skipping commit — current branch is '{current_branch}', "
            f"expected '{_snapshot_branch}'. Vault files written but not committed."
        )
        _update_manifest_committed(target, repo_root, committed=False)
        return

    vault_path = f"vault/projects/{target}/raw"
    subprocess.run(["git", "add", "-f", vault_path], cwd=repo_root, check=False)
    # Derived notes are not ignored, but still need staging to be committed.
    subprocess.run(["git", "add", "vault"], cwd=repo_root, check=False)
    result = subprocess.run(
        ["git", "commit", "-m", f"lookout({target}): snapshot {timestamp}"],
        cwd=repo_root,
    )
    _update_manifest_committed(target, repo_root, committed=(result.returncode == 0))


def _load_sweep_status(vault_dir: Path) -> dict:
    path = vault_dir / SWEEP_STATUS_JSON
    if not path.exists():
        return {"updated": "", "targets": {}}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"updated": "", "targets": {}}
    if not isinstance(data, dict):
        return {"updated": "", "targets": {}}
    targets = data.get("targets")
    if not isinstance(targets, dict):
        data["targets"] = {}
    return data


def _update_sweep_status(prev: dict, results: list, now: str) -> dict:
    """Fold this run's per-target results into the persisted sweep status."""
    targets = dict(prev.get("targets") or {})
    for name, success, reason in results:
        entry = dict(targets.get(name) or {})
        if success:
            entry["last_ok"] = True
            entry["consecutive_failures"] = 0
            entry["last_reason"] = ""
            entry["last_success_at"] = now
        else:
            prev_fail = int(entry.get("consecutive_failures") or 0)
            if entry.get("last_ok") is False:
                entry["consecutive_failures"] = prev_fail + 1
            else:
                entry["consecutive_failures"] = 1
            entry["last_ok"] = False
            entry["last_reason"] = reason
            entry["last_failure_at"] = now
        targets[name] = entry
    return {"updated": now, "targets": targets}


def _render_sweep_status(status: dict) -> str:
    lines = [
        "# Sweep status",
        "",
        "_Machine-owned. Regenerated by `lookout --all`. Do not edit._",
        "",
        "| Target | Last result | Consecutive failures | Last success | Last failure reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    repeating = []
    for name in sorted(status.get("targets") or {}):
        entry = status["targets"][name]
        ok = entry.get("last_ok")
        result = "success" if ok else "failed"
        consecutive = int(entry.get("consecutive_failures") or 0)
        last_success = entry.get("last_success_at") or "—"
        reason = (entry.get("last_reason") or "—").replace("\n", " ").strip()
        lines.append(
            f"| `{name}` | {result} | {consecutive} | {last_success} | {reason} |"
        )
        if not ok and consecutive >= 2:
            repeating.append(
                f"- `{name}` has failed {consecutive} runs in a row ({reason})"
            )
    lines.append("")
    if repeating:
        lines.append("## Repeating failures")
        lines.append("")
        lines.extend(repeating)
        lines.append("")
    return "\n".join(lines)


def _write_sweep_status(vault_dir: Path, status: dict) -> None:
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / SWEEP_STATUS_JSON).write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n"
    )
    (vault_dir / SWEEP_STATUS_MD).write_text(_render_sweep_status(status))


def _print_sweep_summary(results: list, status: dict) -> None:
    print("\n=== lookout --all summary ===")
    records = status.get("targets") or {}
    for target, success, reason in results:
        entry = records.get(target) or {}
        if success:
            print(f"  {target}: success")
            continue
        consecutive = int(entry.get("consecutive_failures") or 1)
        last_success = entry.get("last_success_at")
        extra = f"consecutive failures: {consecutive}"
        if last_success:
            extra += f"; last success {last_success}"
        print(f"  {target}: failed — {reason}  [{extra}]")
    repeating = [
        (name, entry)
        for name, entry in sorted(records.items())
        if not entry.get("last_ok") and int(entry.get("consecutive_failures") or 0) >= 2
    ]
    if repeating:
        print("\n=== repeating failures ===")
        for name, entry in repeating:
            n = entry.get("consecutive_failures")
            reason = entry.get("last_reason") or ""
            print(f"  {name}: {n} consecutive — {reason}")


def _commit_sweep_status(repo_root, snapshot_branch=None):
    """Commit only the sweep-status files. Skips off the snapshot branch."""
    _snapshot_branch = snapshot_branch or "develop"
    current_branch = _get_current_branch(repo_root)
    if current_branch != _snapshot_branch:
        print(
            f"lookout: skipping sweep-status commit — current branch is "
            f"'{current_branch}', expected '{_snapshot_branch}'."
        )
        return
    vault_dir = Path(repo_root) / "vault"
    paths = [
        str(vault_dir / SWEEP_STATUS_JSON),
        str(vault_dir / SWEEP_STATUS_MD),
    ]
    subprocess.run(["git", "add", "--", *paths], cwd=repo_root, check=False)
    subprocess.run(
        ["git", "commit", "-m", "lookout: sweep status"],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )


def run_one(target, targets_yaml, lint_script, repo_root, snapshot_branch=None):
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

    # Derive — per-target notes. Vault-wide stages run once in run_all(), after
    # every target, so map.md and the ideas ledger see the whole fleet.
    derive_results = derive_module.derive_target(target, repo_root / "vault")
    derive_module.print_summary(f"Derive: {target}", derive_results)
    if derive_module.any_error(derive_results):
        failed = [r["stage"] for r in derive_results if r["status"] == derive_module.ERROR]
        return False, f"derive failed: {', '.join(failed)}"

    # Lint
    lint_result = subprocess.run(
        [sys.executable, str(lint_script)],
        cwd=repo_root,
        capture_output=True,
    )
    if lint_result.returncode != 0:
        def _blob(value):
            if not value:
                return ""
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return str(value)

        text = (_blob(lint_result.stdout) + _blob(lint_result.stderr)).strip()
        if text:
            lines = text.splitlines()
            shown = lines[:_LINT_DETAIL_LINES]
            print("\n".join(shown))
            if len(lines) > _LINT_DETAIL_LINES:
                print(f"... ({len(lines) - _LINT_DETAIL_LINES} more lint lines)")
        return False, f"lint failed (exit {lint_result.returncode})"

    # Commit (guarded by branch check inside _commit_target)
    _commit_target(target, timestamp, repo_root, snapshot_branch=snapshot_branch)
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

    snapshot_branch = _load_snapshot_branch(_targets_yaml)

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
            success, reason = run_one(
                target, _targets_yaml, _lint_script, _repo_root,
                snapshot_branch=snapshot_branch,
            )
            results.append((target, success, reason))
            status = "ok" if success else f"FAILED: {reason}"
            print(f"[{target}] {status}")
    finally:
        try:
            _lock_path.rmdir()
        except Exception:
            pass

    # Vault-wide derive — runs once, after every target, so map.md and the
    # ideas ledger are built from the complete fleet rather than a partial one.
    vault_results = derive_module.derive_vault(_repo_root / "vault")
    derive_module.print_summary("Derive: vault-wide", vault_results)

    vault_dir = Path(_repo_root) / "vault"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = _update_sweep_status(_load_sweep_status(vault_dir), results, now)
    _write_sweep_status(vault_dir, status)
    _commit_sweep_status(_repo_root, snapshot_branch=snapshot_branch)
    _print_sweep_summary(results, status)

    any_failed = any(not r[1] for r in results)
    return results, any_failed

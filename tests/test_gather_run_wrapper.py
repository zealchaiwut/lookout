"""Tests for issue #9: Wire gather into lookout run wrapper with degradation."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
BIN_LOOKOUT = REPO_ROOT / "bin" / "lookout"
TARGETS_YAML = REPO_ROOT / "targets.yaml"
LINT_SCRIPT = REPO_ROOT / ".claude" / "skills" / "lookout" / "scripts" / "lint.py"


def _valid_target():
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    return next(iter(data["targets"]))


def _setup_clone(tmpdir):
    """Clone repo and inject current working copies of bin/lookout and scripts."""
    subprocess.run(
        ["git", "clone", str(REPO_ROOT), tmpdir],
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmpdir, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmpdir, check=True,
    )
    for rel in ["bin/lookout", "gather.py", "journal_delta.py"]:
        src = REPO_ROOT / rel
        dst = Path(tmpdir) / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(src), str(dst))
        if rel.startswith("bin/"):
            dst.chmod(0o755)
    lint_src = LINT_SCRIPT
    lint_dst = Path(tmpdir) / ".claude" / "skills" / "lookout" / "scripts" / "lint.py"
    lint_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(str(lint_src), str(lint_dst))
    return Path(tmpdir) / "bin" / "lookout"


# AC1: bin/lookout <target> invokes gather.py and writes at least one snapshot file under raw/
def test_invocation_writes_snapshot_under_raw():
    target = _valid_target()
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _setup_clone(tmpdir)
        subprocess.run(
            [str(script), target], capture_output=True, text=True, cwd=tmpdir,
        )
        raw_dir = Path(tmpdir) / "vault" / "projects" / target / "raw"
        assert raw_dir.exists(), f"Expected raw/ directory at {raw_dir}"
        snapshots = [d for d in raw_dir.iterdir() if d.is_dir()]
        assert len(snapshots) >= 1, "Expected at least one snapshot under raw/"
        assert any((s / "manifest.json").exists() for s in snapshots), (
            "Expected manifest.json inside at least one snapshot directory"
        )


# AC2: summary table printed to stdout with source, status, and item count columns
def test_summary_table_in_stdout():
    target = _valid_target()
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _setup_clone(tmpdir)
        result = subprocess.run(
            [str(script), target], capture_output=True, text=True, cwd=tmpdir,
        )
        stdout = result.stdout.lower()
        assert "source" in stdout or "status" in stdout, (
            f"Expected summary table header in stdout:\n{result.stdout}"
        )
        assert "commander" in stdout, "Expected 'commander' in summary table"
        assert "notion" in stdout, "Expected 'notion' in summary table"
        assert "journal" in stdout, "Expected 'journal' in summary table"


# AC3: lint.py runs after gather and its report is printed to stdout
def test_lint_report_in_stdout():
    target = _valid_target()
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _setup_clone(tmpdir)
        result = subprocess.run(
            [str(script), target], capture_output=True, text=True, cwd=tmpdir,
        )
        combined = result.stdout + result.stderr
        assert "[PASS]" in combined or "[FAIL]" in combined, (
            f"Expected lint [PASS]/[FAIL] in output:\n{combined}"
        )


# AC4: exactly one git commit per invocation with format lookout(<target>): snapshot <ISO-8601>
def test_single_commit_snapshot_format():
    target = _valid_target()
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _setup_clone(tmpdir)

        log_before = subprocess.run(
            ["git", "log", "--oneline"],
            capture_output=True, text=True, cwd=tmpdir,
        ).stdout.strip()
        before_count = len(log_before.splitlines()) if log_before else 0

        subprocess.run(
            [str(script), target], capture_output=True, text=True, cwd=tmpdir,
        )

        log_after = subprocess.run(
            ["git", "log", "--oneline"],
            capture_output=True, text=True, cwd=tmpdir,
        ).stdout.strip()
        after_count = len(log_after.splitlines()) if log_after else 0

        assert after_count == before_count + 1, (
            f"Expected exactly one new commit; before={before_count}, after={after_count}"
        )

        latest_msg = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            capture_output=True, text=True, cwd=tmpdir,
        ).stdout.strip()

        assert latest_msg.startswith(f"lookout({target}): snapshot"), (
            f"Commit must start with 'lookout({target}): snapshot'; got: {latest_msg}"
        )
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", latest_msg), (
            f"Commit must contain ISO-8601 timestamp; got: {latest_msg}"
        )


# AC5: second invocation appends a new snapshot without modifying or deleting the first
def test_second_invocation_appends_without_overwriting():
    target = _valid_target()
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _setup_clone(tmpdir)

        subprocess.run(
            [str(script), target], capture_output=True, text=True, cwd=tmpdir,
        )

        raw_dir = Path(tmpdir) / "vault" / "projects" / target / "raw"
        first_snapshots = {d.name for d in raw_dir.iterdir() if d.is_dir()}
        assert len(first_snapshots) == 1, "Expected exactly one snapshot after first run"
        first_snap_dir = next(d for d in raw_dir.iterdir() if d.is_dir())
        first_manifest_text = (first_snap_dir / "manifest.json").read_text()

        time.sleep(1)

        subprocess.run(
            [str(script), target], capture_output=True, text=True, cwd=tmpdir,
        )

        second_snapshots = {d.name for d in raw_dir.iterdir() if d.is_dir()}
        assert len(second_snapshots) == 2, (
            f"Expected exactly two snapshots after second run; got {second_snapshots}"
        )
        assert first_snapshots < second_snapshots, (
            "First snapshot must still exist after second run"
        )
        # First snapshot must not have been modified
        assert (first_snap_dir / "manifest.json").read_text() == first_manifest_text, (
            "First snapshot manifest.json must not be modified by second invocation"
        )


# AC6: lint.py emits a staleness warning when the newest snapshot is older than 7 days
def test_lint_staleness_warning():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir) / "vault"
        stale_project = "stale-project"
        old_ts = "2020-01-01T00:00:00Z"
        snap_dir = vault / "projects" / stale_project / "raw" / old_ts
        snap_dir.mkdir(parents=True)
        (snap_dir / "manifest.json").write_text(json.dumps({
            "timestamp": old_ts,
            "target": stale_project,
            "health": {},
            "sources": {},
        }))
        (vault / "projects" / stale_project).mkdir(exist_ok=True)
        (vault / "index.md").write_text(f"# Vault\n\n- {stale_project}\n")

        result = subprocess.run(
            [sys.executable, str(LINT_SCRIPT), "--vault", str(vault)],
            capture_output=True, text=True,
        )
        combined = result.stdout + result.stderr
        assert (
            "stale" in combined.lower()
            or "days" in combined.lower()
            or "7" in combined
        ), f"Expected staleness warning in lint output:\n{combined}"
        assert stale_project in combined, (
            f"Expected stale target name '{stale_project}' in lint output:\n{combined}"
        )


# AC7: running with all sources unavailable produces exit code 0
def test_unavailable_sources_exit_zero():
    target = _valid_target()
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _setup_clone(tmpdir)
        result = subprocess.run(
            [str(script), target], capture_output=True, text=True, cwd=tmpdir,
        )
        assert result.returncode == 0, (
            f"Expected exit 0 when sources unavailable; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# AC8: summary table shows commander, notion, journal each with status absent and count 0
def test_absent_sources_in_summary_table():
    target = _valid_target()
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _setup_clone(tmpdir)
        result = subprocess.run(
            [str(script), target], capture_output=True, text=True, cwd=tmpdir,
        )
        stdout_lower = result.stdout.lower()
        assert "commander" in stdout_lower, "Expected 'commander' in summary table"
        assert "notion" in stdout_lower, "Expected 'notion' in summary table"
        assert "journal" in stdout_lower, "Expected 'journal' in summary table"
        assert "absent" in stdout_lower, "Expected 'absent' status in summary table"
        assert "0" in result.stdout, "Expected count of 0 in summary table"


# AC9: no unhandled exceptions when sources are unavailable
def test_no_unhandled_exceptions_when_sources_unavailable():
    target = _valid_target()
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _setup_clone(tmpdir)
        result = subprocess.run(
            [str(script), target], capture_output=True, text=True, cwd=tmpdir,
        )
        combined = result.stdout + result.stderr
        assert "Traceback" not in combined, (
            f"Python traceback should not appear:\n{combined}"
        )
        assert "Unhandled" not in combined, (
            f"Unhandled exception message should not appear:\n{combined}"
        )

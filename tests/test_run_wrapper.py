"""Tests for issue #4: bin/lookout run wrapper script and README."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
BIN_LOOKOUT = REPO_ROOT / "bin" / "lookout"
TARGETS_YAML = REPO_ROOT / "targets.yaml"
README = REPO_ROOT / "README.md"


def _valid_target():
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    return next(iter(data["targets"]))


def run_script(args, cwd=None):
    return subprocess.run(
        [str(BIN_LOOKOUT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
    )


# AC: bin/lookout is executable without additional arguments
def test_bin_lookout_exists_and_is_executable():
    assert BIN_LOOKOUT.exists(), "bin/lookout must exist"
    assert os.access(BIN_LOOKOUT, os.X_OK), "bin/lookout must be executable"


# AC: reads targets.yaml and extracts valid target names at runtime
def test_reads_valid_targets_from_yaml():
    result = run_script(["nonexistent-target"])
    assert result.returncode != 0
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    for target_name in data["targets"]:
        assert target_name in result.stderr, (
            f"Expected '{target_name}' in stderr when listing valid targets"
        )


# AC: valid target prints stub message about gather not yet implemented
def test_valid_target_prints_stub_message():
    target = _valid_target()
    result = run_script([target])
    combined = result.stdout + result.stderr
    assert "gather" in combined.lower(), "Expected 'gather' in output"
    assert (
        "not yet" in combined.lower()
        or "not yet built" in combined.lower()
        or "stub" in combined.lower()
    ), "Expected stub/not-yet message in output"


# AC: valid target executes lint.py and surfaces its exit code
def test_valid_target_runs_lint():
    target = _valid_target()
    result = run_script([target])
    combined = result.stdout + result.stderr
    # lint.py prints [PASS] or [FAIL] lines
    assert "[PASS]" in combined or "[FAIL]" in combined, (
        "Expected lint output ([PASS] or [FAIL]) in script output"
    )


# AC: unknown target exits non-zero and prints valid targets to stderr
def test_unknown_target_exits_nonzero():
    result = run_script(["totally-unknown-target-xyz"])
    assert result.returncode != 0, "Unknown target must exit non-zero"


def test_unknown_target_prints_valid_targets_to_stderr():
    result = run_script(["totally-unknown-target-xyz"])
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    for target_name in data["targets"]:
        assert target_name in result.stderr, (
            f"Expected valid target '{target_name}' in stderr"
        )


def _setup_clone(tmpdir):
    """Clone the repo and inject the current (possibly uncommitted) bin/lookout."""
    subprocess.run(["git", "clone", str(REPO_ROOT), tmpdir], capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir)
    # Inject the current bin/lookout in case it hasn't been committed yet
    import shutil
    clone_bin = Path(tmpdir) / "bin"
    clone_bin.mkdir(exist_ok=True)
    dest = clone_bin / "lookout"
    shutil.copy(str(BIN_LOOKOUT), str(dest))
    dest.chmod(0o755)
    return clone_bin / "lookout"


# AC: when invoked with valid target and files have changed, creates exactly one commit
def test_valid_target_creates_commit_when_files_changed():
    target = _valid_target()
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _setup_clone(tmpdir)

        # Touch a file to make the working tree dirty
        dirty_file = Path(tmpdir) / "vault" / "_test_dirty.md"
        dirty_file.write_text("# dirty\n")

        log_before = subprocess.run(
            ["git", "log", "--oneline"],
            capture_output=True, text=True, cwd=tmpdir,
        ).stdout.strip()

        subprocess.run(
            [str(script), target],
            capture_output=True,
            text=True,
            cwd=tmpdir,
        )

        log_after = subprocess.run(
            ["git", "log", "--oneline"],
            capture_output=True, text=True, cwd=tmpdir,
        ).stdout.strip()

        new_commits = log_after.split("\n") if log_after else []
        old_commits = log_before.split("\n") if log_before else []
        assert len(new_commits) == len(old_commits) + 1, (
            "Expected exactly one new commit after running with dirty files"
        )

        # Verify commit message format
        latest_msg = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            capture_output=True, text=True, cwd=tmpdir,
        ).stdout.strip()
        assert latest_msg.startswith(f"lookout({target}):"), (
            f"Commit message must start with 'lookout({target}):'; got: {latest_msg}"
        )
        assert "scaffold run" in latest_msg, (
            f"Commit message must contain 'scaffold run'; got: {latest_msg}"
        )


# AC: when nothing has changed, script makes zero git commits
def test_no_commit_when_nothing_changed():
    target = _valid_target()
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _setup_clone(tmpdir)

        log_before = subprocess.run(
            ["git", "log", "--oneline"],
            capture_output=True, text=True, cwd=tmpdir,
        ).stdout.strip()

        subprocess.run(
            [str(script), target],
            capture_output=True, text=True, cwd=tmpdir,
        )

        log_after = subprocess.run(
            ["git", "log", "--oneline"],
            capture_output=True, text=True, cwd=tmpdir,
        ).stdout.strip()

        assert log_before == log_after, (
            "Expected no new commits when working tree is clean"
        )


# AC: paths resolved relative to repo root; no writes outside repo
def test_paths_resolved_relative_to_repo_root():
    # The script must not reference absolute paths outside the repo
    script_text = BIN_LOOKOUT.read_text()
    # It should use a mechanism to detect its own repo root (git rev-parse or dirname)
    assert "rev-parse" in script_text or "__file__" in script_text or "dirname" in script_text, (
        "Script must resolve paths relative to repo root"
    )


# AC: README.md exists at repo root
def test_readme_exists():
    assert README.exists(), "README.md must exist at repo root"


# AC: README contains a three-sentence description
def test_readme_has_description():
    content = README.read_text()
    # The description section should have at least 3 sentences
    # A rough heuristic: count sentences (periods/exclamation/question marks)
    sentences = re.split(r'[.!?]+', content)
    non_empty = [s.strip() for s in sentences if s.strip()]
    assert len(non_empty) >= 3, "README must contain at least three sentences"


# AC: README contains the exact run command
def test_readme_has_run_command():
    content = README.read_text()
    assert "bin/lookout" in content, "README must show the exact invocation command"


# AC: README references PRODUCT.md and DESIGN.md
def test_readme_references_product_md():
    content = README.read_text()
    assert "PRODUCT.md" in content, "README must reference PRODUCT.md"


def test_readme_references_design_md():
    content = README.read_text()
    assert "DESIGN.md" in content, "README must reference DESIGN.md"


# AC: README has status line about sprint-2 collectors and sprint-3 synthesis
def test_readme_has_sprint_status():
    content = README.read_text()
    lower = content.lower()
    assert "sprint-2" in lower or "sprint 2" in lower, (
        "README must mention sprint-2 collectors"
    )
    assert "sprint-3" in lower or "sprint 3" in lower, (
        "README must mention sprint-3 synthesis"
    )
    assert "collector" in lower, "README must mention collectors arriving in sprint-2"
    assert "synthesis" in lower, "README must mention synthesis arriving in sprint-3"

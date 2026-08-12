"""Tests for issue #26: Track shipped status via linked GitHub issue closure.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
SHIP_PASS_PY = REPO_ROOT / "ship_pass.py"
LINT_SCRIPT = REPO_ROOT / ".claude" / "skills" / "lookout" / "scripts" / "lint.py"
VAULT_ROOT = REPO_ROOT / "vault"

MACHINE_DELIMITER = "<!-- BEGIN MACHINE ASSESSMENT -->"
MACHINE_END = "<!-- END MACHINE ASSESSMENT -->"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_ship_pass():
    spec = importlib.util.spec_from_file_location("ship_pass", str(SHIP_PASS_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_idea_note(
    directory: Path,
    filename: str,
    slug: str,
    status: str = "promoted",
    issues: list | None = None,
    targets: list | None = None,
    assessment_body: str = "No assessment yet.\n",
) -> Path:
    t = targets if targets is not None else []
    i = issues if issues is not None else []
    fm = "\n".join([
        "---",
        f"slug: {slug}",
        "created: 2026-01-10",
        f"status: {status}",
        f"targets: {t!r}",
        f"issues: {i!r}",
        "assessed: 2026-08-01",
        "---",
    ]) + "\n\n"
    body = (
        "Some idea content.\n"
        + "\n"
        + MACHINE_DELIMITER
        + "\n## Assessment\n\n"
        + assessment_body
        + MACHINE_END
        + "\n"
    )
    path = directory / filename
    path.write_text(fm + body, encoding="utf-8")
    return path


def _make_snapshot(vault_dir: Path, target: str, issues: list[dict]) -> Path:
    """Create a fake snapshot with issues.json for a target."""
    snap_dir = vault_dir / "projects" / target / "raw" / "2026-08-10T00:00:00Z"
    snap_dir.mkdir(parents=True, exist_ok=True)
    payload = {"issues": issues, "prs": []}
    (snap_dir / "issues.json").write_text(json.dumps(payload), encoding="utf-8")
    return snap_dir


def _make_vault_with_snapshot(tmp_path: Path, issues: list[dict]) -> Path:
    """Create a minimal vault with a snapshot containing the given issues."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    _make_snapshot(vault_dir, "test-target", issues)
    return vault_dir


def run_lint(vault_path, targets_yaml=None, extra_args=None):
    cmd = [sys.executable, str(LINT_SCRIPT), "--vault", str(vault_path)]
    if targets_yaml is not None:
        cmd += ["--targets-yaml", str(targets_yaml)]
    if extra_args:
        cmd += extra_args
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Module exists
# ---------------------------------------------------------------------------

def test_ship_pass_module_exists():
    """ship_pass.py exists at repo root."""
    assert SHIP_PASS_PY.exists(), f"ship_pass.py not found at {SHIP_PASS_PY}"


# ---------------------------------------------------------------------------
# AC1: Pipeline fetches issue states from target snapshots
# ---------------------------------------------------------------------------

def test_load_issue_states_returns_empty_when_no_snapshots(tmp_path):
    """AC1: load_issue_states returns empty dict when no target snapshots exist."""
    sp = _load_ship_pass()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "projects").mkdir()
    states = sp.load_issue_states(vault_dir)
    assert states == {}


def test_load_issue_states_reads_issues_from_snapshot(tmp_path):
    """AC1 + AC3 (issue #76): load_issue_states reads state keyed by project then number."""
    sp = _load_ship_pass()
    vault_dir = _make_vault_with_snapshot(tmp_path, [
        {"number": 101, "title": "Fix login bug", "state": "CLOSED"},
        {"number": 102, "title": "Add dark mode", "state": "OPEN"},
    ])
    states = sp.load_issue_states(vault_dir)
    assert "test-target" in states, f"Project 'test-target' not found in states: {states}"
    assert 101 in states["test-target"], f"Issue 101 not found: {states}"
    assert 102 in states["test-target"], f"Issue 102 not found: {states}"
    assert states["test-target"][101]["state"] == "CLOSED"
    assert states["test-target"][102]["state"] == "OPEN"


def test_load_issue_states_uses_latest_snapshot(tmp_path):
    """AC1: load_issue_states uses the most recent snapshot directory."""
    sp = _load_ship_pass()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    # Older snapshot: issue 101 is OPEN
    old_snap = vault_dir / "projects" / "test-target" / "raw" / "2026-08-09T00:00:00Z"
    old_snap.mkdir(parents=True)
    (old_snap / "issues.json").write_text(
        json.dumps({"issues": [{"number": 101, "title": "Fix", "state": "OPEN"}], "prs": []})
    )
    # Newer snapshot: issue 101 is CLOSED
    new_snap = vault_dir / "projects" / "test-target" / "raw" / "2026-08-10T00:00:00Z"
    new_snap.mkdir(parents=True)
    (new_snap / "issues.json").write_text(
        json.dumps({"issues": [{"number": 101, "title": "Fix", "state": "CLOSED"}], "prs": []})
    )
    states = sp.load_issue_states(vault_dir)
    assert states["test-target"][101]["state"] == "CLOSED", (
        "Should use newest snapshot; expected CLOSED but got OPEN"
    )


def test_load_issue_states_aggregates_across_targets(tmp_path):
    """AC1 + AC3 (issue #76): load_issue_states reads from all targets, keyed by project."""
    sp = _load_ship_pass()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    _make_snapshot(vault_dir, "target-a", [{"number": 101, "title": "A", "state": "CLOSED"}])
    _make_snapshot(vault_dir, "target-b", [{"number": 102, "title": "B", "state": "OPEN"}])
    states = sp.load_issue_states(vault_dir)
    assert "target-a" in states and 101 in states["target-a"] and states["target-a"][101]["state"] == "CLOSED"
    assert "target-b" in states and 102 in states["target-b"] and states["target-b"][102]["state"] == "OPEN"


# ---------------------------------------------------------------------------
# AC2: All closed → advance to shipped
# ---------------------------------------------------------------------------

def test_run_ship_pass_advances_to_shipped_when_all_closed(tmp_path):
    """AC2: idea with all linked issues closed is advanced to 'shipped'."""
    sp = _load_ship_pass()
    vault_dir = _make_vault_with_snapshot(tmp_path, [
        {"number": 101, "title": "Issue A", "state": "CLOSED"},
        {"number": 102, "title": "Issue B", "state": "CLOSED"},
    ])
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "2026-01-10-my-idea.md",
                           slug="my-idea", status="promoted", issues=[101, 102],
                           targets=["test-target"])
    sp.run_ship_pass(ideas_dir, vault_dir)
    content = idea.read_text(encoding="utf-8")
    assert "status: shipped" in content, (
        f"Expected status to advance to 'shipped':\n{content}"
    )


def test_run_ship_pass_skips_idea_with_no_issues(tmp_path):
    """AC2: idea with empty issues list is not advanced to shipped."""
    sp = _load_ship_pass()
    vault_dir = _make_vault_with_snapshot(tmp_path, [])
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "2026-01-10-my-idea.md",
                           slug="my-idea", status="promoted", issues=[])
    sp.run_ship_pass(ideas_dir, vault_dir)
    content = idea.read_text(encoding="utf-8")
    assert "status: promoted" in content, (
        f"Idea with empty issues list must stay promoted:\n{content}"
    )


def test_run_ship_pass_skips_non_promoted_ideas(tmp_path):
    """AC2: only ideas with status=promoted are candidates for ship advancement."""
    sp = _load_ship_pass()
    vault_dir = _make_vault_with_snapshot(tmp_path, [
        {"number": 101, "title": "Issue A", "state": "CLOSED"},
    ])
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "2026-01-10-my-idea.md",
                           slug="my-idea", status="assessed", issues=[101])
    sp.run_ship_pass(ideas_dir, vault_dir)
    content = idea.read_text(encoding="utf-8")
    assert "status: assessed" in content, (
        f"Non-promoted idea must not have its status changed:\n{content}"
    )


# ---------------------------------------------------------------------------
# AC3: Any open issue → keep promoted, add per-issue state table
# ---------------------------------------------------------------------------

def test_run_ship_pass_keeps_promoted_when_any_issue_open(tmp_path):
    """AC3: idea stays promoted when at least one linked issue is open."""
    sp = _load_ship_pass()
    vault_dir = _make_vault_with_snapshot(tmp_path, [
        {"number": 101, "title": "Issue A", "state": "CLOSED"},
        {"number": 102, "title": "Issue B", "state": "OPEN"},
    ])
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "2026-01-10-my-idea.md",
                           slug="my-idea", status="promoted", issues=[101, 102],
                           targets=["test-target"])
    sp.run_ship_pass(ideas_dir, vault_dir)
    content = idea.read_text(encoding="utf-8")
    assert "status: promoted" in content, (
        f"Idea with open issues must stay 'promoted':\n{content}"
    )


def test_run_ship_pass_adds_issue_table_when_any_open(tmp_path):
    """AC3: Assessment section includes per-issue state table when any issue is open."""
    sp = _load_ship_pass()
    vault_dir = _make_vault_with_snapshot(tmp_path, [
        {"number": 101, "title": "Fix login bug", "state": "CLOSED"},
        {"number": 102, "title": "Add dark mode", "state": "OPEN"},
    ])
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "2026-01-10-my-idea.md",
                           slug="my-idea", status="promoted", issues=[101, 102],
                           targets=["test-target"])
    sp.run_ship_pass(ideas_dir, vault_dir)
    content = idea.read_text(encoding="utf-8")
    # Table must be inside the machine assessment block
    start = content.find(MACHINE_DELIMITER)
    end = content.find(MACHINE_END)
    assert start != -1 and end != -1
    machine_block = content[start:end]
    assert "101" in machine_block, f"Issue #101 not in assessment block:\n{machine_block}"
    assert "102" in machine_block, f"Issue #102 not in assessment block:\n{machine_block}"
    assert "closed" in machine_block.lower() or "open" in machine_block.lower(), (
        f"Issue states missing from assessment block:\n{machine_block}"
    )


# ---------------------------------------------------------------------------
# AC4: Fixture — one closed, one open → promoted with mixed state table
# ---------------------------------------------------------------------------

def test_fixture_mixed_issues_produces_promoted_with_table(tmp_path):
    """AC4: One closed, one open → promoted status with both states in Assessment."""
    sp = _load_ship_pass()
    vault_dir = _make_vault_with_snapshot(tmp_path, [
        {"number": 101, "title": "Issue 101", "state": "CLOSED"},
        {"number": 102, "title": "Issue 102", "state": "OPEN"},
    ])
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "2026-01-10-fixture.md",
                           slug="fixture", status="promoted", issues=[101, 102],
                           targets=["test-target"])
    sp.run_ship_pass(ideas_dir, vault_dir)
    content = idea.read_text(encoding="utf-8")

    # Status must stay promoted
    assert "status: promoted" in content, (
        f"Status must remain 'promoted' with one open issue:\n{content}"
    )
    # Both issues visible in assessment
    start = content.find(MACHINE_DELIMITER)
    end = content.find(MACHINE_END)
    machine_block = content[start:end]
    assert "101" in machine_block and "102" in machine_block, (
        f"Both issue numbers must appear in Assessment:\n{machine_block}"
    )
    # Both states visible
    lower_block = machine_block.lower()
    assert "closed" in lower_block, f"'closed' state not found in Assessment:\n{machine_block}"
    assert "open" in lower_block, f"'open' state not found in Assessment:\n{machine_block}"


# ---------------------------------------------------------------------------
# AC5: Closing both issues → shipped with no open-issue table
# ---------------------------------------------------------------------------

def test_fixture_all_closed_produces_shipped_no_table(tmp_path):
    """AC5: Closing all issues produces 'shipped' with no open-issue table."""
    sp = _load_ship_pass()
    vault_dir = _make_vault_with_snapshot(tmp_path, [
        {"number": 101, "title": "Issue 101", "state": "CLOSED"},
        {"number": 102, "title": "Issue 102", "state": "CLOSED"},
    ])
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "2026-01-10-fixture.md",
                           slug="fixture", status="promoted", issues=[101, 102],
                           targets=["test-target"])
    sp.run_ship_pass(ideas_dir, vault_dir)
    content = idea.read_text(encoding="utf-8")

    assert "status: shipped" in content, (
        f"Expected status 'shipped' when all issues closed:\n{content}"
    )
    # No open-issue table in Assessment
    start = content.find(MACHINE_DELIMITER)
    end = content.find(MACHINE_END)
    machine_block = content[start:end] if start != -1 else ""
    assert "open" not in machine_block.lower() or (
        "open" not in machine_block.lower()
    ), f"No 'open' state should appear in Assessment when shipped:\n{machine_block}"


def test_transition_from_mixed_to_all_closed(tmp_path):
    """AC5: Running again after closing all issues advances status from promoted to shipped."""
    sp = _load_ship_pass()
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "2026-01-10-fixture.md",
                           slug="fixture", status="promoted", issues=[101, 102],
                           targets=["test-target"])

    # First run: one open
    vault_dir = _make_vault_with_snapshot(tmp_path, [
        {"number": 101, "title": "Issue 101", "state": "CLOSED"},
        {"number": 102, "title": "Issue 102", "state": "OPEN"},
    ])
    sp.run_ship_pass(ideas_dir, vault_dir)
    content1 = idea.read_text(encoding="utf-8")
    assert "status: promoted" in content1, "After first run, should still be promoted"

    # Second run: all closed — update snapshot
    new_snap = vault_dir / "projects" / "test-target" / "raw" / "2026-08-11T00:00:00Z"
    new_snap.mkdir(parents=True)
    (new_snap / "issues.json").write_text(json.dumps({
        "issues": [
            {"number": 101, "title": "Issue 101", "state": "CLOSED"},
            {"number": 102, "title": "Issue 102", "state": "CLOSED"},
        ],
        "prs": [],
    }))
    sp.run_ship_pass(ideas_dir, vault_dir)
    content2 = idea.read_text(encoding="utf-8")
    assert "status: shipped" in content2, (
        f"After second run with all issues closed, should be shipped:\n{content2}"
    )


# ---------------------------------------------------------------------------
# AC6: lint warns when status=promoted and issues=[]  (AC8: automated test)
# ---------------------------------------------------------------------------

def _make_lint_vault(tmp_path, snapshot_issues=None, snapshot_target=None):
    """Minimal vault with ideas/ directory for lint tests.

    If snapshot_issues is given, also creates a snapshot for snapshot_target
    (default: 'test-target') and adds that target to index.md.
    """
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "projects").mkdir()
    index_lines = ["# Vault Index\n\n## Projects\n\n"]
    if snapshot_issues is not None:
        target = snapshot_target or "test-target"
        _make_snapshot(vault_dir, target, snapshot_issues)
        index_lines.append(f"- [[{target}]]\n")
    (vault_dir / "index.md").write_text("".join(index_lines))
    ideas_dir = vault_dir / "ideas"
    ideas_dir.mkdir()
    return vault_dir, ideas_dir


def test_lint_warns_promoted_with_empty_issues(tmp_path):
    """AC6 + AC8: lint emits a warning when status=promoted and issues=[]."""
    vault_dir, ideas_dir = _make_lint_vault(tmp_path)
    _make_idea_note(ideas_dir, "2026-01-10-promoted-no-issues.md",
                    slug="promoted-no-issues", status="promoted", issues=[])
    result = run_lint(vault_dir)
    assert "promoted" in result.stdout.lower() or "missing" in result.stdout.lower() or \
           "issues" in result.stdout.lower(), (
        f"Expected lint warning about promoted idea with empty issues:\n{result.stdout}"
    )
    assert result.returncode == 0, (
        f"Warning must be non-fatal (exit 0), got {result.returncode}\n{result.stdout}"
    )


def test_lint_no_warn_promoted_with_nonempty_issues(tmp_path):
    """AC6: lint does NOT warn when status=promoted and issues is non-empty."""
    vault_dir, ideas_dir = _make_lint_vault(tmp_path)
    _make_idea_note(ideas_dir, "2026-01-10-promoted-with-issues.md",
                    slug="promoted-with-issues", status="promoted", issues=[101])
    result = run_lint(vault_dir)
    # No promoted-missing-issues warning for this idea
    relevant = [
        ln for ln in result.stdout.splitlines()
        if "promoted-with-issues" in ln and "issue" in ln.lower()
    ]
    assert not relevant, (
        f"Unexpected warning for promoted idea with non-empty issues:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# AC7: lint errors when status=shipped and any issue is open  (AC8: automated test)
# ---------------------------------------------------------------------------

def test_lint_errors_shipped_with_open_issue(tmp_path):
    """AC7 + AC8: lint emits an error when status=shipped and an issue is open."""
    vault_dir, ideas_dir = _make_lint_vault(tmp_path, snapshot_issues=[
        {"number": 200, "title": "Open issue", "state": "OPEN"},
    ])
    _make_idea_note(ideas_dir, "2026-01-10-shipped-open.md",
                    slug="shipped-open", status="shipped", issues=[200])
    result = run_lint(vault_dir)
    assert "200" in result.stdout or "shipped" in result.stdout.lower() or \
           "open" in result.stdout.lower(), (
        f"Expected lint error about shipped idea with open issue:\n{result.stdout}"
    )
    assert result.returncode != 0, (
        f"Error must block the run (non-zero exit), got {result.returncode}\n{result.stdout}"
    )


def test_lint_no_error_shipped_with_all_closed(tmp_path):
    """AC7: lint does NOT error when status=shipped and all issues are closed."""
    vault_dir, ideas_dir = _make_lint_vault(tmp_path, snapshot_issues=[
        {"number": 200, "title": "Closed issue", "state": "CLOSED"},
    ])
    _make_idea_note(ideas_dir, "2026-01-10-shipped-closed.md",
                    slug="shipped-closed", status="shipped", issues=[200])
    result = run_lint(vault_dir)
    shipped_errors = [
        ln for ln in result.stdout.splitlines()
        if "shipped-closed" in ln and ("error" in ln.lower() or "open" in ln.lower())
    ]
    assert not shipped_errors, (
        f"Unexpected error for shipped idea with all closed issues:\n{result.stdout}"
    )
    assert result.returncode == 0, (
        f"No error expected when all issues closed:\n{result.stdout}"
    )


def test_lint_no_snapshot_data_does_not_error_for_shipped(tmp_path):
    """AC7: When no snapshot data available, lint does not falsely error for shipped ideas."""
    vault_dir, ideas_dir = _make_lint_vault(tmp_path)
    _make_idea_note(ideas_dir, "2026-01-10-shipped-no-snap.md",
                    slug="shipped-no-snap", status="shipped", issues=[200])
    # No snapshot created — lint cannot verify issue state
    result = run_lint(vault_dir)
    # Should not error since we can't confirm the issue is open
    assert result.returncode == 0, (
        f"Without snapshot data, lint must not falsely error:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# UAT Step 5: exit code checks
# ---------------------------------------------------------------------------

def test_promoted_empty_issues_exits_zero(tmp_path):
    """UAT Step 5: lint with promoted+empty issues exits 0 (warning, not error)."""
    vault_dir, ideas_dir = _make_lint_vault(tmp_path)
    _make_idea_note(ideas_dir, "2026-01-10-promoted-no-issues.md",
                    slug="promoted-no-issues", status="promoted", issues=[])
    result = run_lint(vault_dir)
    assert result.returncode == 0, (
        f"Warning must not block pipeline (exit 0): got {result.returncode}\n"
        f"stdout:\n{result.stdout}"
    )


def test_shipped_open_issue_exits_nonzero(tmp_path):
    """UAT Step 5: lint with shipped+open issue exits non-zero (error)."""
    vault_dir, ideas_dir = _make_lint_vault(tmp_path, snapshot_issues=[
        {"number": 200, "title": "Open issue", "state": "OPEN"},
    ])
    _make_idea_note(ideas_dir, "2026-01-10-shipped-open.md",
                    slug="shipped-open", status="shipped", issues=[200])
    result = run_lint(vault_dir)
    assert result.returncode != 0, (
        f"Error must block pipeline (non-zero exit): got {result.returncode}\n"
        f"stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Issue #76: Per-project issue scoping and closed-issue collection
# ---------------------------------------------------------------------------

def test_load_issue_states_keyed_by_project(tmp_path):
    """AC3 (#76): load_issue_states keys state by project name then issue number."""
    sp = _load_ship_pass()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    _make_snapshot(vault_dir, "alpha", [{"number": 42, "title": "Alpha 42", "state": "CLOSED"}])
    _make_snapshot(vault_dir, "beta", [{"number": 42, "title": "Beta 42", "state": "OPEN"}])
    states = sp.load_issue_states(vault_dir)
    assert "alpha" in states, f"Project 'alpha' missing from states: {states}"
    assert "beta" in states, f"Project 'beta' missing from states: {states}"
    assert states["alpha"][42]["state"] == "CLOSED"
    assert states["beta"][42]["state"] == "OPEN"
    assert states["alpha"][42]["title"] == "Alpha 42"
    assert states["beta"][42]["title"] == "Beta 42"


def test_cross_project_collision_scoped_to_idea_target_open(tmp_path):
    """AC4 + AC8 (#76): Issue CLOSED in another project does NOT satisfy check when idea targets the OPEN one."""
    sp = _load_ship_pass()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    _make_snapshot(vault_dir, "project-a", [{"number": 42, "title": "A-42 closed", "state": "CLOSED"}])
    _make_snapshot(vault_dir, "project-b", [{"number": 42, "title": "B-42 open", "state": "OPEN"}])

    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "idea.md", slug="idea", status="promoted",
                           issues=[42], targets=["project-b"])

    issue_states = sp.load_issue_states(vault_dir)
    sp.check_idea(idea, issue_states)

    content = idea.read_text(encoding="utf-8")
    assert "status: promoted" in content, (
        "Idea targeting project-b (where #42 is OPEN) must stay promoted, "
        "even though project-a has a CLOSED #42"
    )


def test_cross_project_collision_scoped_to_idea_target_closed(tmp_path):
    """AC6 + AC8 + AC9 (#76): Idea ships when its issue is CLOSED in its own target."""
    sp = _load_ship_pass()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    _make_snapshot(vault_dir, "project-a", [{"number": 42, "title": "A-42 closed", "state": "CLOSED"}])
    _make_snapshot(vault_dir, "project-b", [{"number": 42, "title": "B-42 open", "state": "OPEN"}])

    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "idea.md", slug="idea", status="promoted",
                           issues=[42], targets=["project-a"])

    issue_states = sp.load_issue_states(vault_dir)
    sp.check_idea(idea, issue_states)

    content = idea.read_text(encoding="utf-8")
    assert "status: shipped" in content, (
        "Idea targeting project-a (where #42 is CLOSED) must ship, "
        "even though project-b has an OPEN #42"
    )


def test_unresolvable_issue_leaves_status_unchanged(tmp_path):
    """AC5 + AC9 (#76): Idea targeting a project with no snapshot stays promoted, renders (unknown)."""
    sp = _load_ship_pass()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "projects").mkdir()

    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "idea.md", slug="idea", status="promoted",
                           issues=[99], targets=["missing-target"])

    issue_states = sp.load_issue_states(vault_dir)
    sp.check_idea(idea, issue_states)

    content = idea.read_text(encoding="utf-8")
    assert "status: promoted" in content, (
        "Idea targeting a project with no snapshot must stay promoted"
    )
    assert "(unknown)" in content, (
        "Unresolvable issue must render title as (unknown)"
    )


def test_empty_targets_leaves_status_unchanged(tmp_path):
    """AC5 (#76): Idea with empty targets list stays promoted even if issue closed somewhere."""
    sp = _load_ship_pass()
    vault_dir = _make_vault_with_snapshot(tmp_path, [
        {"number": 99, "title": "Some issue", "state": "CLOSED"},
    ])
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "idea.md", slug="idea", status="promoted",
                           issues=[99], targets=[])

    issue_states = sp.load_issue_states(vault_dir)
    sp.check_idea(idea, issue_states)

    content = idea.read_text(encoding="utf-8")
    assert "status: promoted" in content, (
        "Idea with empty targets must stay promoted even if issue is CLOSED somewhere"
    )


def test_run_ship_pass_cross_project_isolation(tmp_path):
    """AC9 (#76): run_ship_pass: cross-project collision resolves correctly per idea."""
    sp = _load_ship_pass()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    _make_snapshot(vault_dir, "project-x", [{"number": 10, "title": "X-10 open", "state": "OPEN"}])
    _make_snapshot(vault_dir, "project-y", [{"number": 10, "title": "Y-10 closed", "state": "CLOSED"}])

    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea_x = _make_idea_note(ideas_dir, "2026-01-01-idea-x.md", slug="idea-x",
                              status="promoted", issues=[10], targets=["project-x"])
    idea_y = _make_idea_note(ideas_dir, "2026-01-01-idea-y.md", slug="idea-y",
                              status="promoted", issues=[10], targets=["project-y"])

    sp.run_ship_pass(ideas_dir, vault_dir)

    content_x = idea_x.read_text(encoding="utf-8")
    content_y = idea_y.read_text(encoding="utf-8")
    assert "status: promoted" in content_x, (
        "idea-x targeting project-x (OPEN) must stay promoted"
    )
    assert "status: shipped" in content_y, (
        "idea-y targeting project-y (CLOSED) must ship"
    )


def test_issue_table_shows_real_title_from_target(tmp_path):
    """AC7 (#76): Issue table shows the real title from the idea's own target, not another project's."""
    sp = _load_ship_pass()
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    _make_snapshot(vault_dir, "my-project", [{"number": 5, "title": "Real Title Here", "state": "OPEN"}])
    _make_snapshot(vault_dir, "other-project", [{"number": 5, "title": "Wrong Title", "state": "OPEN"}])

    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    idea = _make_idea_note(ideas_dir, "idea.md", slug="idea", status="promoted",
                           issues=[5], targets=["my-project"])

    issue_states = sp.load_issue_states(vault_dir)
    sp.check_idea(idea, issue_states)

    content = idea.read_text(encoding="utf-8")
    assert "Real Title Here" in content, (
        "Issue table must show the title from the idea's own target project"
    )
    assert "Wrong Title" not in content, (
        "Issue table must NOT show the title from a different project"
    )

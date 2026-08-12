"""Tests for issue #81: Pin idea-referenced issues in gather so ship_pass can resolve them at any age.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import gather
import ship_pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gh_issue(number, title, state):
    return {
        "number": number,
        "title": title,
        "state": state,
        "labels": [],
        "assignees": [],
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }


def _make_idea_note(ideas_dir: Path, filename: str, targets: list, issues: list) -> Path:
    """Write a minimal idea note with given targets and issues."""
    content = (
        "---\n"
        f"slug: {filename.replace('.md', '')}\n"
        "created: 2026-08-10\n"
        "status: promoted\n"
        f"targets: {targets!r}\n"
        f"issues: {issues!r}\n"
        "assessed: 2026-08-10\n"
        "---\n\n"
        "Idea body.\n"
    )
    path = ideas_dir / filename
    path.write_text(content)
    return path


def _fake_run_factory(bulk_open=None, bulk_closed=None, pinned_map=None):
    """Return a fake subprocess.run that serves bulk and pinned gh calls."""
    bulk_open = bulk_open or []
    bulk_closed = bulk_closed or []
    pinned_map = pinned_map or {}

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0

        if "issue" in cmd and "list" in cmd:
            state_arg = cmd[cmd.index("--state") + 1] if "--state" in cmd else "all"
            if state_arg == "open":
                result.stdout = json.dumps(bulk_open)
            else:
                result.stdout = json.dumps(bulk_closed)
        elif "issue" in cmd and "view" in cmd:
            # gh issue view <number> --repo <slug> --json <fields>
            number = int(cmd[cmd.index("view") + 1])
            if number in pinned_map:
                result.stdout = json.dumps(pinned_map[number])
            else:
                result.returncode = 1
                result.stdout = ""
                result.stderr = f"issue #{number} not found"
        else:
            result.stdout = json.dumps([])
        return result

    return fake_run


# ---------------------------------------------------------------------------
# AC1: gather reads vault/ideas/*.md and builds pinned set for the target
# ---------------------------------------------------------------------------

def test_read_pinned_idea_issues_returns_empty_when_no_ideas(tmp_path):
    """AC1: Returns empty set when ideas directory has no idea notes."""
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    result = gather._read_pinned_idea_issues(ideas_dir, "perf-coach")
    assert result == set(), f"Expected empty set, got {result}"


def test_read_pinned_idea_issues_returns_empty_when_dir_missing(tmp_path):
    """AC1: Returns empty set when ideas directory does not exist."""
    ideas_dir = tmp_path / "nonexistent"
    result = gather._read_pinned_idea_issues(ideas_dir, "perf-coach")
    assert result == set()


def test_read_pinned_idea_issues_returns_issues_for_matching_target(tmp_path):
    """AC1: Returns issue numbers from ideas whose targets include the given target."""
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    _make_idea_note(ideas_dir, "2026-08-10-trend-alerts.md",
                    targets=["perf-coach"], issues=[62])
    result = gather._read_pinned_idea_issues(ideas_dir, "perf-coach")
    assert 62 in result, f"Expected {{62}} in result, got {result}"


def test_read_pinned_idea_issues_skips_index_md(tmp_path):
    """AC1: index.md is skipped (it is the ledger, not an idea note)."""
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    # Write a file that looks like an index
    (ideas_dir / "index.md").write_text(
        "---\ntargets: [perf-coach]\nissues: [999]\n---\n# Index\n"
    )
    result = gather._read_pinned_idea_issues(ideas_dir, "perf-coach")
    assert 999 not in result, "index.md must be skipped"


def test_read_pinned_idea_issues_aggregates_multiple_ideas(tmp_path):
    """AC1: Aggregates issue numbers across multiple matching idea notes."""
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    _make_idea_note(ideas_dir, "2026-08-10-idea-a.md",
                    targets=["perf-coach"], issues=[62])
    _make_idea_note(ideas_dir, "2026-08-10-idea-b.md",
                    targets=["perf-coach"], issues=[77, 88])
    result = gather._read_pinned_idea_issues(ideas_dir, "perf-coach")
    assert result == {62, 77, 88}, f"Expected {{62, 77, 88}}, got {result}"


# ---------------------------------------------------------------------------
# AC10: An idea referencing a different target contributes no lookups
# ---------------------------------------------------------------------------

def test_read_pinned_idea_issues_scoped_to_target(tmp_path):
    """AC10: Issues from ideas that do NOT target the gathered project are excluded."""
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    _make_idea_note(ideas_dir, "2026-08-10-perf-idea.md",
                    targets=["perf-coach"], issues=[62])
    _make_idea_note(ideas_dir, "2026-08-10-asset-idea.md",
                    targets=["asset-studio"], issues=[99])
    result = gather._read_pinned_idea_issues(ideas_dir, "perf-coach")
    assert 62 in result
    assert 99 not in result, "Issues from non-matching targets must not appear"


# ---------------------------------------------------------------------------
# AC9: An idea with empty targets list contributes no lookups
# ---------------------------------------------------------------------------

def test_read_pinned_idea_issues_empty_targets_excluded(tmp_path):
    """AC9: An idea with empty targets: [] contributes no lookups to any target."""
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    _make_idea_note(ideas_dir, "2026-08-10-no-target.md",
                    targets=[], issues=[42])
    result = gather._read_pinned_idea_issues(ideas_dir, "perf-coach")
    assert 42 not in result, "Empty targets must contribute no pinned lookups"


# ---------------------------------------------------------------------------
# AC2: Pinned issues not in bulk are fetched individually by exact number
# ---------------------------------------------------------------------------

def test_collect_gh_fetches_pinned_issue_not_in_bulk(tmp_path, monkeypatch):
    """AC2: A pinned issue absent from bulk open/closed results is fetched individually."""
    bulk_issues = [_make_gh_issue(1, "Open #1", "OPEN")]
    pinned_issue = _make_gh_issue(62, "Trend alerts", "CLOSED")

    monkeypatch.setattr(gather.subprocess, "run",
                        _fake_run_factory(bulk_open=bulk_issues, pinned_map={62: pinned_issue}))

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    gather._collect_gh("owner/repo", out_dir, pinned_numbers={62})

    payload = json.loads((out_dir / "issues.json").read_text())
    numbers = {i["number"] for i in payload["issues"]}
    assert 62 in numbers, f"Pinned issue #62 must appear in issues.json; got {numbers}"


def test_collect_gh_pinned_issue_state_is_correct(tmp_path, monkeypatch):
    """AC3: The fetched pinned issue has its real state (CLOSED), not assumed OPEN."""
    bulk_issues = [_make_gh_issue(1, "Open #1", "OPEN")]
    pinned_issue = _make_gh_issue(62, "Old closed issue", "CLOSED")

    monkeypatch.setattr(gather.subprocess, "run",
                        _fake_run_factory(bulk_open=bulk_issues, pinned_map={62: pinned_issue}))

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    gather._collect_gh("owner/repo", out_dir, pinned_numbers={62})

    payload = json.loads((out_dir / "issues.json").read_text())
    issue_62 = next((i for i in payload["issues"] if i["number"] == 62), None)
    assert issue_62 is not None, "Issue #62 must be in issues.json"
    assert issue_62["state"] == "CLOSED", (
        f"Fetched issue must have real state CLOSED, got {issue_62['state']!r}"
    )


# ---------------------------------------------------------------------------
# AC4: No duplicate entries
# ---------------------------------------------------------------------------

def test_collect_gh_no_duplicate_when_pinned_already_in_bulk(tmp_path, monkeypatch):
    """AC4: When a pinned issue is already in the bulk fetch, it is NOT fetched again."""
    bulk_issues = [_make_gh_issue(62, "Trend alerts", "CLOSED")]
    view_calls = []

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        if "issue" in cmd and "list" in cmd:
            state_arg = cmd[cmd.index("--state") + 1] if "--state" in cmd else "all"
            result.stdout = json.dumps(bulk_issues if state_arg == "closed" else [])
        elif "issue" in cmd and "view" in cmd:
            view_calls.append(cmd)
            result.stdout = json.dumps(bulk_issues[0])
        else:
            result.stdout = json.dumps([])
        return result

    monkeypatch.setattr(gather.subprocess, "run", fake_run)

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    gather._collect_gh("owner/repo", out_dir, pinned_numbers={62})

    payload = json.loads((out_dir / "issues.json").read_text())
    count_62 = sum(1 for i in payload["issues"] if i["number"] == 62)
    assert count_62 == 1, f"Issue #62 must appear exactly once; found {count_62}"
    assert not view_calls, (
        f"gh issue view must NOT be called when issue is already in bulk results; "
        f"got {len(view_calls)} view call(s)"
    )


def test_collect_gh_no_duplicate_entries_in_output(tmp_path, monkeypatch):
    """AC4: issues.json contains each issue number at most once."""
    bulk_open = [_make_gh_issue(1, "Open", "OPEN")]
    bulk_closed = [_make_gh_issue(100, "Closed", "CLOSED")]
    pinned_issue = _make_gh_issue(200, "Pinned", "CLOSED")

    monkeypatch.setattr(gather.subprocess, "run",
                        _fake_run_factory(bulk_open=bulk_open,
                                          bulk_closed=bulk_closed,
                                          pinned_map={200: pinned_issue}))

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    gather._collect_gh("owner/repo", out_dir, pinned_numbers={200})

    payload = json.loads((out_dir / "issues.json").read_text())
    numbers = [i["number"] for i in payload["issues"]]
    assert len(numbers) == len(set(numbers)), (
        f"Duplicate issue numbers found in issues.json: {numbers}"
    )


# ---------------------------------------------------------------------------
# AC7: Failed or unresolvable individual lookup is non-fatal
# ---------------------------------------------------------------------------

def test_collect_gh_failed_pinned_lookup_is_nonfatal(tmp_path, monkeypatch):
    """AC7: A failed gh issue view does not crash the run (exits 0, issue absent)."""
    bulk_issues = [_make_gh_issue(1, "Open #1", "OPEN")]

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        if "view" in cmd:
            result.returncode = 1
            result.stdout = ""
            result.stderr = "not found"
        else:
            result.returncode = 0
            state_arg = cmd[cmd.index("--state") + 1] if "--state" in cmd else "all"
            result.stdout = json.dumps(bulk_issues if state_arg == "open" else [])
        return result

    monkeypatch.setattr(gather.subprocess, "run", fake_run)

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    result = gather._collect_gh("owner/repo", out_dir, pinned_numbers={9999})

    assert result["status"] == "ok", (
        f"Failed pinned lookup must not cause status=absent; got {result['status']!r}"
    )
    payload = json.loads((out_dir / "issues.json").read_text())
    numbers = {i["number"] for i in payload["issues"]}
    assert 9999 not in numbers, "Unresolvable pinned issue must not appear in issues.json"


def test_collect_gh_no_pinned_numbers_unchanged_behavior(tmp_path, monkeypatch):
    """AC12: When no pinned numbers supplied, behavior is identical to pre-#81."""
    bulk_open = [_make_gh_issue(1, "Open #1", "OPEN")]
    bulk_closed = [_make_gh_issue(100, "Closed #100", "CLOSED")]

    monkeypatch.setattr(gather.subprocess, "run",
                        _fake_run_factory(bulk_open=bulk_open, bulk_closed=bulk_closed))

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    result = gather._collect_gh("owner/repo", out_dir)

    assert result["status"] == "ok"
    payload = json.loads((out_dir / "issues.json").read_text())
    numbers = {i["number"] for i in payload["issues"]}
    assert 1 in numbers and 100 in numbers


# ---------------------------------------------------------------------------
# AC8: manifest records pinned_requested and pinned_resolved
# ---------------------------------------------------------------------------

def test_collect_gh_returns_pinned_counts_on_success(tmp_path, monkeypatch):
    """AC8: _collect_gh returns pinned_requested and pinned_resolved counts."""
    bulk_open = [_make_gh_issue(1, "Open #1", "OPEN")]
    pinned_62 = _make_gh_issue(62, "Pinned closed", "CLOSED")

    monkeypatch.setattr(gather.subprocess, "run",
                        _fake_run_factory(bulk_open=bulk_open, pinned_map={62: pinned_62}))

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    result = gather._collect_gh("owner/repo", out_dir, pinned_numbers={62})

    assert "pinned_requested" in result, "result must have pinned_requested"
    assert "pinned_resolved" in result, "result must have pinned_resolved"
    assert result["pinned_requested"] == 1, (
        f"Expected pinned_requested=1, got {result['pinned_requested']}"
    )
    assert result["pinned_resolved"] == 1, (
        f"Expected pinned_resolved=1, got {result['pinned_resolved']}"
    )


def test_collect_gh_pinned_resolved_less_than_requested_on_failure(tmp_path, monkeypatch):
    """AC8: When a pinned lookup fails, resolved < requested so the failure is visible."""
    bulk_open = [_make_gh_issue(1, "Open #1", "OPEN")]

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        if "view" in cmd:
            result.returncode = 1
            result.stdout = ""
        else:
            result.returncode = 0
            state_arg = cmd[cmd.index("--state") + 1] if "--state" in cmd else "all"
            result.stdout = json.dumps(bulk_open if state_arg == "open" else [])
        return result

    monkeypatch.setattr(gather.subprocess, "run", fake_run)

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    result = gather._collect_gh("owner/repo", out_dir, pinned_numbers={9999})

    assert result["pinned_requested"] == 1
    assert result["pinned_resolved"] == 0, (
        f"A failed lookup must yield pinned_resolved=0; got {result['pinned_resolved']}"
    )


def test_collect_gh_no_pinned_yields_zero_counts(tmp_path, monkeypatch):
    """AC8: When no pinned numbers requested, counts are both 0."""
    monkeypatch.setattr(gather.subprocess, "run",
                        _fake_run_factory())

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    result = gather._collect_gh("owner/repo", out_dir)

    assert result.get("pinned_requested", 0) == 0
    assert result.get("pinned_resolved", 0) == 0


def test_collect_gh_pinned_already_in_bulk_counts_zero_requested(tmp_path, monkeypatch):
    """AC8: Pinned issue already in bulk results → pinned_requested=0 (no fetch needed)."""
    bulk_closed = [_make_gh_issue(62, "Already here", "CLOSED")]

    monkeypatch.setattr(gather.subprocess, "run",
                        _fake_run_factory(bulk_closed=bulk_closed))

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    result = gather._collect_gh("owner/repo", out_dir, pinned_numbers={62})

    assert result["pinned_requested"] == 0, (
        "Issue already in bulk should not count as a pinned request"
    )
    assert result["pinned_resolved"] == 0


# ---------------------------------------------------------------------------
# AC11: ship_pass.py performs NO network calls
# ---------------------------------------------------------------------------

def test_ship_pass_makes_no_subprocess_calls(tmp_path):
    """AC11: ship_pass.run_ship_pass must not invoke subprocess or gh."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    snap_dir = vault_dir / "projects" / "perf-coach" / "raw" / "2026-08-10T00:00:00Z"
    snap_dir.mkdir(parents=True)
    (snap_dir / "issues.json").write_text(json.dumps({
        "issues": [{"number": 62, "title": "Trend alerts", "state": "CLOSED"}],
        "prs": [],
    }))

    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    _make_idea_note(ideas_dir, "2026-08-10-trend.md",
                    targets=["perf-coach"], issues=[62])

    call_log = []

    original_run = subprocess.run

    def spy_run(cmd, **kwargs):
        call_log.append(cmd)
        return original_run(cmd, **kwargs)

    with patch("subprocess.run", side_effect=spy_run):
        ship_pass.run_ship_pass(ideas_dir, vault_dir)

    assert not call_log, (
        f"ship_pass must make NO subprocess calls; got: {call_log}"
    )


def test_ship_pass_module_has_no_subprocess_import_for_gh():
    """AC11: ship_pass.py does not invoke gh directly — verify by checking module attributes."""
    import inspect
    source = inspect.getsource(ship_pass)
    assert "subprocess.run" not in source, (
        "ship_pass.py must not contain subprocess.run — it must be offline"
    )
    assert 'import subprocess' not in source or (
        'subprocess.run' not in source
    ), "ship_pass.py must not call subprocess"


# ---------------------------------------------------------------------------
# AC12: Bulk limits from #78 are unchanged
# ---------------------------------------------------------------------------

def test_open_and_closed_limits_unchanged(monkeypatch):
    """AC12: _OPEN_LIMIT and _CLOSED_LIMIT retain their values from #78."""
    assert gather._OPEN_LIMIT == 500, (
        f"_OPEN_LIMIT must remain 500 (from #78), got {gather._OPEN_LIMIT}"
    )
    assert gather._CLOSED_LIMIT == 200, (
        f"_CLOSED_LIMIT must remain 200 (from #78), got {gather._CLOSED_LIMIT}"
    )


# ---------------------------------------------------------------------------
# Integration: pinned issue enables ship_pass transition
# ---------------------------------------------------------------------------

def test_pinned_issue_enables_ship_pass_transition(tmp_path, monkeypatch):
    """End-to-end: gather fetches pinned #62, then ship_pass advances to shipped."""
    # Set up vault with a snapshot where pinned issue #62 is CLOSED
    ideas_dir = tmp_path / "vault" / "ideas"
    ideas_dir.mkdir(parents=True)
    _make_idea_note(ideas_dir, "2026-08-10-trend.md",
                    targets=["perf-coach"], issues=[62])

    snap_dir = tmp_path / "vault" / "projects" / "perf-coach" / "raw" / "2026-08-10T00:00:00Z"
    snap_dir.mkdir(parents=True)
    pinned_issue = _make_gh_issue(62, "Trend alerts", "CLOSED")
    (snap_dir / "issues.json").write_text(json.dumps({
        "issues": [pinned_issue],
        "prs": [],
    }))

    # ship_pass reads from the snapshot — no network needed
    shipped = ship_pass.run_ship_pass(ideas_dir, tmp_path / "vault")

    assert len(shipped) == 1, (
        f"Expected 1 shipped idea, got {len(shipped)}"
    )
    content = (ideas_dir / "2026-08-10-trend.md").read_text()
    assert "status: shipped" in content, (
        f"Expected status: shipped after pinned issue resolved:\n{content}"
    )

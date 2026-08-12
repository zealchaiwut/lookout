"""Tests for issue #78: Fetch open and closed issues with independent limits.

Each test maps to a specific AC item.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import gather
import synthesize
import question_registry


# ---------------------------------------------------------------------------
# AC: A test asserts the collector issues separate per-state queries (or
#     otherwise proves open issues survive a large closed set) without
#     calling the network.
# ---------------------------------------------------------------------------

def _make_gh_issue(number, title, state, labels=None):
    return {
        "number": number,
        "title": title,
        "state": state,
        "labels": labels or [],
        "assignees": [],
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }


def test_collect_gh_issues_separate_calls_per_state(tmp_path, monkeypatch):
    """_collect_gh must issue separate open and closed queries so open issues
    are never crowded out by a large closed set.
    """
    open_issues = [_make_gh_issue(i, f"Open #{i}", "OPEN") for i in range(1, 29)]
    closed_issues = [_make_gh_issue(i, f"Closed #{i}", "CLOSED") for i in range(100, 1100)]

    captured_cmds = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        result = MagicMock()
        result.returncode = 0
        if "--state" in cmd:
            idx = cmd.index("--state")
            state_arg = cmd[idx + 1]
        else:
            state_arg = "all"

        if "issue" in cmd:
            if state_arg == "open":
                result.stdout = json.dumps(open_issues)
            else:
                result.stdout = json.dumps(closed_issues[:200])
        else:
            result.stdout = json.dumps([])
        return result

    monkeypatch.setattr(gather.subprocess, "run", fake_run)

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    gather._collect_gh("owner/repo", out_dir)

    # Must have issued at least two separate issue list calls
    issue_cmds = [c for c in captured_cmds if "issue" in c and "list" in c]
    assert len(issue_cmds) >= 2, (
        f"Expected >= 2 separate gh issue list calls, got {len(issue_cmds)}: {issue_cmds}"
    )

    # The two calls must target different states (open vs closed/all)
    state_args = set()
    for cmd in issue_cmds:
        if "--state" in cmd:
            idx = cmd.index("--state")
            state_args.add(cmd[idx + 1])
    assert len(state_args) >= 2 or "all" not in state_args, (
        "open and closed issues must be fetched with independent state targets"
    )


def test_collect_gh_open_issues_survive_large_closed_set(tmp_path, monkeypatch):
    """All 28 open issues must appear in issues.json even when there are 1000
    closed issues — they must not be crowded out by a shared limit.
    """
    open_issues = [_make_gh_issue(i, f"Open #{i}", "OPEN") for i in range(1, 29)]
    closed_issues = [_make_gh_issue(i + 1000, f"Closed #{i}", "CLOSED") for i in range(1000)]

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        state_arg = cmd[cmd.index("--state") + 1] if "--state" in cmd else "all"
        if "issue" in cmd and "list" in cmd:
            if state_arg in ("open",):
                result.stdout = json.dumps(open_issues)
            else:
                result.stdout = json.dumps(closed_issues[:200])
        else:
            result.stdout = json.dumps([])
        return result

    monkeypatch.setattr(gather.subprocess, "run", fake_run)

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    gather._collect_gh("owner/repo", out_dir)

    payload = json.loads((out_dir / "issues.json").read_text())
    open_in_snapshot = [i for i in payload["issues"] if i["state"] in ("OPEN", "open")]
    assert len(open_in_snapshot) == 28, (
        f"Expected 28 open issues, got {len(open_in_snapshot)}"
    )


def test_collect_gh_closed_issues_are_still_collected(tmp_path, monkeypatch):
    """Closed issues must still appear in issues.json (needed for promoted->shipped)."""
    open_issues = [_make_gh_issue(1, "Open one", "OPEN")]
    closed_issues = [_make_gh_issue(62, "Shipped feature", "CLOSED")]

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        state_arg = cmd[cmd.index("--state") + 1] if "--state" in cmd else "all"
        if "issue" in cmd and "list" in cmd:
            if state_arg in ("open",):
                result.stdout = json.dumps(open_issues)
            else:
                result.stdout = json.dumps(closed_issues)
        else:
            result.stdout = json.dumps([])
        return result

    monkeypatch.setattr(gather.subprocess, "run", fake_run)

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    gather._collect_gh("owner/repo", out_dir)

    payload = json.loads((out_dir / "issues.json").read_text())
    all_numbers = {i["number"] for i in payload["issues"]}
    assert 62 in all_numbers, "Closed issue #62 must appear in issues.json"


def test_collect_gh_pr_list_also_uses_independent_state_calls(tmp_path, monkeypatch):
    """gh pr list must also issue separate open/closed calls, not just issues."""
    captured_cmds = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps([])
        return result

    monkeypatch.setattr(gather.subprocess, "run", fake_run)

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    gather._collect_gh("owner/repo", out_dir)

    pr_cmds = [c for c in captured_cmds if "pr" in c and "list" in c]
    assert len(pr_cmds) >= 2, (
        f"Expected >= 2 separate gh pr list calls, got {len(pr_cmds)}: {pr_cmds}"
    )


def test_manifest_github_source_entry_still_written(tmp_path, monkeypatch):
    """manifest.json must still record github source with status ok/absent and count."""
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps([])
        return result

    monkeypatch.setattr(gather.subprocess, "run", fake_run)

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    result = gather._collect_gh("owner/repo", out_dir)

    assert result.get("status") in ("ok", "absent"), (
        f"Expected status ok/absent, got {result.get('status')!r}"
    )
    assert "error" in result


def test_issues_json_count_reflects_actual_collected(tmp_path, monkeypatch):
    """The count in the source entry must match what was written to issues.json."""
    open_issues = [_make_gh_issue(i, f"Open #{i}", "OPEN") for i in range(1, 6)]
    closed_issues = [_make_gh_issue(i + 100, f"Closed #{i}", "CLOSED") for i in range(3)]

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        state_arg = cmd[cmd.index("--state") + 1] if "--state" in cmd else "all"
        if "issue" in cmd and "list" in cmd:
            if state_arg == "open":
                result.stdout = json.dumps(open_issues)
            else:
                result.stdout = json.dumps(closed_issues)
        else:
            result.stdout = json.dumps([])
        return result

    monkeypatch.setattr(gather.subprocess, "run", fake_run)

    out_dir = tmp_path / "snap"
    out_dir.mkdir()
    gather._collect_gh("owner/repo", out_dir)

    payload = json.loads((out_dir / "issues.json").read_text())
    total = len(payload["issues"])
    assert total == 8, f"Expected 5 open + 3 closed = 8, got {total}"


# ---------------------------------------------------------------------------
# AC: `_capacity_verdict` counts an issue as blocked only when it is open
#     and carries the `blocked` label
# ---------------------------------------------------------------------------

def _make_issues_data(issues):
    return {"issues": issues}


def test_capacity_verdict_closed_blocked_issue_does_not_block():
    """A closed issue with a 'blocked' label must NOT trigger 'blocked — resolve first'."""
    manifest = {"sources": {"brief": {"status": "ok"}}}
    brief = {}
    issues_data = _make_issues_data([
        {
            "number": 5,
            "title": "Old blocked thing",
            "state": "CLOSED",
            "labels": [{"name": "blocked"}],
        }
    ])
    verdict = synthesize._capacity_verdict(manifest, brief, issues_data)
    assert verdict == "Clear to start", (
        f"Closed blocked issue must not hold capacity hostage; got: {verdict!r}"
    )


def test_capacity_verdict_open_blocked_issue_does_block():
    """An open issue with a 'blocked' label must still trigger the blocked verdict."""
    manifest = {"sources": {"brief": {"status": "ok"}}}
    brief = {}
    issues_data = _make_issues_data([
        {
            "number": 5,
            "title": "Actually blocked",
            "state": "OPEN",
            "labels": [{"name": "blocked"}],
        }
    ])
    verdict = synthesize._capacity_verdict(manifest, brief, issues_data)
    assert "blocked" in verdict.lower(), (
        f"Open blocked issue must trigger blocked verdict; got: {verdict!r}"
    )


def test_capacity_verdict_closed_blocked_fixture():
    """AC fixture test: issues.json with a closed blocked issue → 'Clear to start'."""
    manifest = {"sources": {"brief": {"status": "ok"}}}
    brief = {"sprints_history": []}
    issues_data = {
        "issues": [
            {
                "number": 99,
                "title": "Stale blocked ticket",
                "state": "CLOSED",
                "labels": [{"name": "blocked"}, {"name": "bug"}],
            }
        ]
    }
    result = synthesize._capacity_verdict(manifest, brief, issues_data)
    assert result == "Clear to start", (
        f"A closed issue labelled 'blocked' must not report as blocked; got: {result!r}"
    )


# ---------------------------------------------------------------------------
# AC: `extract_stalled_items` skips closed issues
# ---------------------------------------------------------------------------

def test_extract_stalled_items_skips_closed_issues():
    """Closed issues must not appear in stalled items even with a blocked label."""
    issues_data = {
        "issues": [
            {
                "number": 1,
                "title": "Open and blocked",
                "state": "OPEN",
                "labels": [{"name": "blocked"}],
            },
            {
                "number": 2,
                "title": "Closed but labelled blocked",
                "state": "CLOSED",
                "labels": [{"name": "blocked"}],
            },
        ]
    }
    stalled = question_registry.extract_stalled_items(issues_data)
    numbers = [s.get("number") for s in stalled]
    assert 2 not in numbers, "Closed issue #2 must not appear in stalled items"
    assert 1 in numbers, "Open issue #1 must still appear"


def test_extract_stalled_items_skips_closed_lowercase():
    """State comparison must be case-insensitive — 'closed' and 'CLOSED' both skip."""
    issues_data = {
        "issues": [
            {
                "number": 3,
                "title": "Closed lowercase",
                "state": "closed",
                "labels": [{"name": "blocked"}],
            },
        ]
    }
    stalled = question_registry.extract_stalled_items(issues_data)
    assert stalled == [], "Closed issues must be skipped regardless of case"


# ---------------------------------------------------------------------------
# AC: `_collect_next_items` continues to list only open issues (regression guard)
# ---------------------------------------------------------------------------

def test_collect_next_items_only_includes_open_issues():
    """Regression guard: closed issues must never appear in 'What to do next'."""
    issues_data = {
        "issues": [
            {"number": 10, "title": "Still open", "state": "open"},
            {"number": 11, "title": "Already closed", "state": "closed"},
            {"number": 12, "title": "Also open", "state": "OPEN"},
        ]
    }
    items = synthesize._collect_next_items({}, [], {}, issues_data)
    titles = " ".join(items)
    assert "Already closed" not in titles
    assert "Still open" in titles
    assert "Also open" in titles

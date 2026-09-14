"""Tests for Decision Hub + decisions_lib enricher."""
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import decide  # noqa: E402
import decisions_lib as dl  # noqa: E402
import project_decisions_view as pdv  # noqa: E402


def _write_decision(ddir: Path, name: str, fm: dict, body: str) -> Path:
    ddir.mkdir(parents=True, exist_ok=True)
    path = ddir / name
    dump = yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip()
    path.write_text(f"---\n{dump}\n---\n\n{body}", encoding="utf-8")
    return path


def _snap(project: Path, issues=None, prs=None):
    snap = project / "raw" / "t1"
    snap.mkdir(parents=True)
    (snap / "issues.json").write_text(json.dumps({
        "issues": issues or [],
        "prs": prs or [],
    }))


def test_enrich_issue_pr_sprint_status(tmp_path):
    project = tmp_path / "projects" / "demo"
    _snap(
        project,
        issues=[{
            "number": 10,
            "state": "CLOSED",
            "title": "Do the thing",
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-05T00:00:00Z",
            "closedAt": "2026-01-05T00:00:00Z",
            "labels": [{"name": "sprint-3"}],
        }],
        prs=[{
            "number": 20,
            "state": "MERGED",
            "title": "Implement thing",
            "createdAt": "2026-01-02T00:00:00Z",
            "updatedAt": "2026-01-04T00:00:00Z",
            "mergedAt": "2026-01-04T12:00:00Z",
        }],
    )
    _write_decision(
        project / "decisions",
        "2026-01-03-thing.md",
        {
            "id": "DM-D1",
            "date": "2026-01-03",
            "status": "active",
            "targets": ["demo"],
            "issues": [10],
            "prs": [20],
            "sprints": ["sprint-3"],
        },
        "# DM-D1 — Do the thing\n\n## Context\n\nWhy.\n\n## Decision\n\nShip it.\n",
    )
    gh = dl.load_gh_index(project)
    decisions = dl.load_decisions(project, gh)
    assert len(decisions) == 1
    d = decisions[0]
    assert d["issue_states"][0]["state"] == "closed"
    assert d["pr_states"][0]["state"] == "merged"
    assert d["sprint_states"][0]["state"] == "finished"
    assert d["issue_created_at"].startswith("2026-01-01")
    assert d["implemented_at"].startswith("2026-01-04")


def test_hub_has_three_timelines(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    project = vault / "projects" / "demo"
    _snap(
        project,
        issues=[{
            "number": 1,
            "state": "OPEN",
            "title": "Open work",
            "createdAt": "2026-02-01T00:00:00Z",
            "labels": [{"name": "sprint-1"}],
        }],
    )
    _write_decision(
        project / "decisions",
        "2026-02-10-open.md",
        {
            "id": "DM-D2",
            "date": "2026-02-10",
            "status": "proposed",
            "targets": ["demo"],
            "issues": [1],
            "prs": [],
            "sprints": ["sprint-1"],
        },
        "# DM-D2 — Open work\n\n## Decision\n\nWait.\n",
    )
    out = pdv.generate_decisions_view("demo", vault)
    text = out.read_text()
    assert "## Timeline by decided date" in text
    assert "## Timeline by issue created" in text
    assert "## Timeline by implemented" in text
    assert "DM-D2" in text
    assert "#1 open" in text or "#1 `open`" in text or "1 open" in text
    assert "sprint-1" in text


def test_status_transition_and_cli_create(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    project = vault / "projects" / "demo"
    project.mkdir(parents=True)
    targets = tmp_path / "targets.yaml"
    targets.write_text("targets:\n  demo:\n    local: /tmp\n")
    monkeypatch.setattr(decide, "TARGETS_YAML", targets)

    code = decide.main([
        "demo", "--vault", str(vault),
        "--title", "Try feature X",
        "--issue", "5",
        "--sprint", "sprint-9",
        "--status", "proposed",
    ])
    assert code == 0
    decisions = dl.load_decisions(project, gh={})
    assert len(decisions) == 1
    assert decisions[0]["status"] == "proposed"
    did = decisions[0]["id"]

    code = decide.main([
        "demo", "--vault", str(vault),
        "--set-status", did, "--status", "active",
    ])
    assert code == 0
    assert dl.load_decisions(project, gh={})[0]["status"] == "active"

    with pytest.raises(dl.DecisionError):
        dl.set_decision_status(decisions[0]["path"], "proposed")


def test_unknown_issue_shows_unknown(tmp_path):
    project = tmp_path / "projects" / "demo"
    _snap(project, issues=[])
    _write_decision(
        project / "decisions",
        "2026-03-01-missing.md",
        {
            "id": "DM-D9",
            "date": "2026-03-01",
            "status": "active",
            "issues": [999],
            "prs": [],
            "sprints": [],
        },
        "# DM-D9 — Missing\n\n## Decision\n\nX.\n",
    )
    d = dl.load_decisions(project)[0]
    assert d["issue_states"][0]["state"] == "unknown"

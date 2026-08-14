"""Tests for the read-surfaces table, per-project flow/changelog, and site IA."""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import capability_card  # noqa: E402
import project_changelog  # noqa: E402
import project_flow  # noqa: E402
import render_site as site_mod  # noqa: E402


def test_read_surfaces_is_a_three_column_table():
    endpoints = [
        {
            "path": "/api/health",
            "description": "Health check",
            "example": "curl -sS http://localhost:8000/api/health",
            "response": "200 JSON — Health check",
        },
        {
            "path": "/api/projects/{slug}/brief",
            "description": "Per-project brief",
        },
    ]
    section = capability_card._build_read_surfaces_section(endpoints, target="commander")
    assert section.startswith("| API name | API | Example |")
    assert "`GET /api/health`" in section
    assert "curl -sS http://localhost:8000/api/health" in section
    assert "200 JSON — Health check" in section
    assert "curl -sS http://localhost:8000/api/projects/commander/brief" in section
    assert capability_card.extract_read_surface_paths(
        "## Read surfaces\n\n" + section + "\n\n## Next\n"
    ) == ["/api/health", "/api/projects/{slug}/brief"]


def test_read_surfaces_empty_when_no_endpoints():
    assert "No read surfaces" in capability_card._build_read_surfaces_section([])


def test_flow_uses_workflow_stage_headings_not_invented_features(tmp_path):
    local = tmp_path / "src"
    (local / "docs").mkdir(parents=True)
    (local / "docs" / "workflow.md").write_text(
        "# Workflow\n\n"
        "How work flows, driven by Commander.\n\n"
        "## Stage 1 — Bulk Create\n\n"
        "BA drafts tickets.\n\n"
        "## Stage 2 — Run Sprint\n\n"
        "Coder then tester.\n"
    )
    (local / "PRODUCT.md").write_text(
        "# Product\n\n"
        "## Core User Flows\n\n"
        "1. **Pick account** — select the brand.\n"
        "2. **Create assets** — characters and backgrounds.\n"
        "3. **Build carousel** — compose slides and export.\n"
    )
    (local / "docs" / "architecture.md").write_text("# Architecture\n\n_No diagram._\n")
    vault = tmp_path / "vault"
    project = vault / "projects" / "alpha"
    (project / "atlas").mkdir(parents=True)
    (project / "atlas" / "index.md").write_text("# Atlas\n")
    (project / "raw" / "t").mkdir(parents=True)
    (project / "raw" / "t" / "docs_manifest.json").write_text(
        json.dumps({"files": [{"path": "docs/workflow.md"}]})
    )

    yaml_path = tmp_path / "targets.yaml"
    yaml_path.write_text("targets:\n  alpha:\n    local: " + str(local) + "\n")
    original = project_flow.TARGETS_YAML
    project_flow.TARGETS_YAML = yaml_path
    try:
        out = project_flow.generate_flow("alpha", vault)
    finally:
        project_flow.TARGETS_YAML = original

    text = out.read_text()
    # Product flow from PRODUCT.md is the lifecycle, not the Commander template.
    assert "## Product lifecycle" in text
    assert "Pick account" in text
    assert "Create assets" in text
    assert "Build carousel" in text
    assert "flowchart LR" in text
    assert "invented-feature" not in text
    # Commander template is secondary.
    assert "## How work ships" in text
    assert "Stage 1 — Bulk Create" in text
    assert "[[projects/alpha/atlas/index]]" in text
    assert "`docs/workflow.md`" in text


def test_commander_template_without_product_steps_is_not_the_lifecycle(tmp_path):
    local = tmp_path / "src"
    (local / "docs").mkdir(parents=True)
    (local / "docs" / "workflow.md").write_text(
        "# Workflow\n\ndriven by Commander.\n\n"
        "## Stage 1 — Bulk Create\n\nBA.\n\n"
        "## Stage 2 — Run Sprint\n\nCoder.\n"
    )
    (local / "PRODUCT.md").write_text("# Product\n\nA tool. No numbered flows.\n")
    vault = tmp_path / "vault"
    (vault / "projects" / "alpha").mkdir(parents=True)
    yaml_path = tmp_path / "targets.yaml"
    yaml_path.write_text("targets:\n  alpha:\n    local: " + str(local) + "\n")
    original = project_flow.TARGETS_YAML
    project_flow.TARGETS_YAML = yaml_path
    try:
        text = project_flow.generate_flow("alpha", vault).read_text()
    finally:
        project_flow.TARGETS_YAML = original
    product_block = text.split("## How work ships")[0]
    assert "Stage 1 — Bulk Create" not in product_block
    assert "How work ships" in text
    assert "Bulk Create" in text.split("## How work ships")[1]


def test_flow_without_workflow_says_so(tmp_path):
    vault = tmp_path / "vault"
    (vault / "projects" / "beta").mkdir(parents=True)
    yaml_path = tmp_path / "targets.yaml"
    yaml_path.write_text("targets:\n  beta:\n    local: " + str(tmp_path / "missing") + "\n")
    original = project_flow.TARGETS_YAML
    project_flow.TARGETS_YAML = yaml_path
    try:
        text = project_flow.generate_flow("beta", vault).read_text()
    finally:
        project_flow.TARGETS_YAML = original
    assert "No `PRODUCT.md` or `docs/workflow.md`" in text


def test_changelog_lists_merged_prs_and_joins_atlas_issues(tmp_path):
    vault = tmp_path / "vault"
    project = vault / "projects" / "alpha"
    atlas = project / "atlas"
    snap = project / "raw" / "t"
    atlas.mkdir(parents=True)
    snap.mkdir(parents=True)
    (atlas / "dashboard.md").write_text("# Dashboard\n\nRelated: #12\n")
    (snap / "issues.json").write_text(json.dumps({
        "issues": [],
        "prs": [
            {
                "number": 99,
                "title": "feat: dashboard strip (issue #12)",
                "state": "MERGED",
                "updatedAt": "2026-08-01T00:00:00Z",
            }
        ],
    }))
    (snap / "gitlog.txt").write_text(
        "=== branch ===\nmain\n\n=== log ===\nabc1234 feat: dashboard (issue #12)\n\n=== status ===\n"
    )
    (vault / "decisions.md").write_text("# Decisions\n")

    yaml_path = tmp_path / "targets.yaml"
    yaml_path.write_text("targets:\n  alpha:\n    github: zealchaiwut/alpha\n")
    original = project_changelog.TARGETS_YAML
    project_changelog.TARGETS_YAML = yaml_path
    try:
        text = project_changelog.generate_changelog("alpha", vault).read_text()
    finally:
        project_changelog.TARGETS_YAML = original

    assert "[#99](https://github.com/zealchaiwut/alpha/pull/99)" in text
    assert "feat: dashboard strip (issue #12)" in text
    assert "[[projects/alpha/atlas/dashboard]]" in text
    assert "`abc1234`" in text
    assert "No decisions recorded" in text


def test_sidebar_nests_ideas_under_fleet_and_under_the_project(tmp_path):
    v = tmp_path / "vault"
    (v / "projects" / "alpha").mkdir(parents=True)
    (v / "ideas").mkdir()
    (v / "journal").mkdir()
    (v / "index.md").write_text("# Index\n")
    (v / "projects" / "alpha" / "situation.md").write_text("# s\n")
    (v / "ideas" / "2026-01-10-dark-mode.md").write_text(
        "---\nslug: dark-mode\nstatus: idea\ntargets: [alpha]\n---\n\nA theme.\n"
    )
    (v / "journal" / "index.md").write_text("# Journal\n")
    out = tmp_path / "site"
    site_mod.generate_site(v, out)
    page = (out / "notes" / "ideas" / "2026-01-10-dark-mode.html").read_text()
    assert "<summary>Fleet" in page
    assert "This idea belongs to" in page
    assert ">alpha</a>" in page
    assert "status <strong>idea</strong>" in page
    # Project group also lists the idea
    alpha_block = page.split("<summary>alpha</summary>")[1].split("<summary>Fleet")[0]
    assert "dark-mode" in alpha_block

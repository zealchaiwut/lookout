"""Tests for issue #98: atlas trace coverage report.

Each test maps to an AC item.
"""
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import atlas_coverage  # noqa: E402

TRACED_NOTE = """---
feature: Widget Flow
---

## Flowchart

```mermaid
flowchart LR
  widgets_py[widgets.py]
  helpers_py[helpers.py]
  widgets_py --> helpers_py
```
"""

EMPTY_NOTE = """---
feature: Brand Settings
---

## Flowchart

```mermaid
flowchart LR
```
"""


@pytest.fixture
def fleet(tmp_path):
    """A vault with one project, plus that project's source tree."""
    vault = tmp_path / "vault"
    atlas = vault / "projects" / "alpha" / "atlas"
    atlas.mkdir(parents=True)
    (atlas / "index.md").write_text("# index\n")
    (atlas / "widget-flow.md").write_text(TRACED_NOTE)
    (atlas / "brand-settings.md").write_text(EMPTY_NOTE)

    src = tmp_path / "alpha-src"
    (src / "tests").mkdir(parents=True)
    (src / "widgets.py").write_text("import helpers\n")
    (src / "helpers.py").write_text("pass\n")
    (src / "tests" / "test_widget_flow.py").write_text("import widgets\n")

    ty = tmp_path / "targets.yaml"
    ty.write_text(yaml.dump({"targets": {"alpha": {"local": str(src)}}}))
    return vault, src, ty


def test_traced_feature_is_counted_as_traced(fleet):
    vault, src, _ = fleet
    r = atlas_coverage.analyse_target("alpha", src, vault)
    assert r["traced"] == ["widget-flow"]


def test_feature_without_a_diagram_is_counted_as_blocked(fleet):
    vault, src, _ = fleet
    r = atlas_coverage.analyse_target("alpha", src, vault)
    assert [b[0] for b in r["blocked"]] == ["brand-settings"]


def test_index_note_is_not_counted_as_a_feature(fleet):
    vault, src, _ = fleet
    r = atlas_coverage.analyse_target("alpha", src, vault)
    assert r["total"] == 2


def test_blocked_feature_names_the_file_that_would_unlock_it(fleet):
    vault, src, _ = fleet
    r = atlas_coverage.analyse_target("alpha", src, vault)
    _slug, _name, reason, action = r["blocked"][0]
    assert reason == "no entry point"
    assert "tests/test_brand_settings.py" in action


def test_suggested_filename_follows_the_test_convention():
    assert atlas_coverage.suggested_test_filename("multi-ratio-rendering") == (
        "tests/test_multi_ratio_rendering.py"
    )


def test_existing_but_unfollowable_entry_gets_different_advice(fleet):
    """A test that imports nothing local exists — telling the reader to add one would be wrong."""
    vault, src, _ = fleet
    (src / "tests" / "test_brand_settings.py").write_text(
        "from fastapi.testclient import TestClient\n"
    )
    r = atlas_coverage.analyse_target("alpha", src, vault)
    _slug, _name, reason, action = r["blocked"][0]
    assert reason == "entry imports nothing local"
    assert "test_brand_settings.py" in action
    assert not action.startswith("add ")


def test_missing_local_checkout_is_unavailable_not_blocked(fleet, tmp_path):
    vault, _src, _ = fleet
    r = atlas_coverage.analyse_target("alpha", tmp_path / "gone", vault)
    assert r["status"] == atlas_coverage.UNAVAILABLE
    assert r["blocked"] == []
    assert r["total"] == 2


def test_report_contains_a_summary_and_a_fleet_row(fleet):
    vault, _src, ty = fleet
    out = atlas_coverage.generate_coverage(vault, ty)
    text = out.read_text()
    assert "## Summary" in text
    assert "| alpha | 1 | 1 | 2 | 50% |" in text
    assert "**Fleet**" in text


def test_report_lists_blocked_features_with_actions(fleet):
    vault, _src, ty = fleet
    text = atlas_coverage.generate_coverage(vault, ty).read_text()
    assert "## Blocked features" in text
    assert "### alpha" in text
    assert "tests/test_brand_settings.py" in text


def test_report_writes_to_the_vault_root(fleet):
    vault, _src, ty = fleet
    out = atlas_coverage.generate_coverage(vault, ty)
    assert out == vault / "atlas-coverage.md"


def test_report_is_byte_identical_across_runs(fleet):
    vault, _src, ty = fleet
    first = atlas_coverage.generate_coverage(vault, ty).read_bytes()
    second = atlas_coverage.generate_coverage(vault, ty).read_bytes()
    assert first == second


def test_report_carries_no_timestamp(fleet):
    """A timestamp would make an unchanged fleet produce a diff every run."""
    import re
    vault, _src, ty = fleet
    text = atlas_coverage.generate_coverage(vault, ty).read_text()
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text)


def test_unavailable_target_does_not_break_the_report(fleet, tmp_path):
    vault, _src, _ = fleet
    ty = tmp_path / "bad.yaml"
    ty.write_text(yaml.dump({"targets": {"alpha": {"local": str(tmp_path / "gone")}}}))
    text = atlas_coverage.generate_coverage(vault, ty).read_text()
    assert "unavailable" in text


def test_project_with_no_atlas_directory_is_skipped(fleet, tmp_path):
    vault, src, _ = fleet
    ty = tmp_path / "two.yaml"
    ty.write_text(yaml.dump({"targets": {
        "alpha": {"local": str(src)},
        "ghost": {"local": str(src)},
    }}))
    text = atlas_coverage.generate_coverage(vault, ty).read_text()
    assert "| ghost |" not in text


def test_discovery_is_reused_from_atlas_trace():
    """The report must not reimplement resolution, or it will drift from tracing."""
    import ast
    tree = ast.parse((REPO_ROOT / "atlas_coverage.py").read_text())
    names = {n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)}
    assert "atlas_trace" in names


def test_report_is_linked_from_the_vault_index():
    assert "atlas-coverage" in (REPO_ROOT / "vault" / "index.md").read_text()

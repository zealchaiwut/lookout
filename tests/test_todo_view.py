"""Tests for issue #11: todo-view routine.

Each test maps to a specific AC item from the issue.
Tests run against todo_view.py at repo root.
"""
import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
TODO_VIEW_PY = REPO_ROOT / "todo_view.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_todo_view():
    spec = importlib.util.spec_from_file_location("todo_view_test", str(TODO_VIEW_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC: todo_view.py exists
# ---------------------------------------------------------------------------

def test_todo_view_py_exists():
    assert TODO_VIEW_PY.exists(), "todo_view.py must exist at repo root"


# ---------------------------------------------------------------------------
# AC: generate_todo_view returns a string with exactly two sections
# ---------------------------------------------------------------------------

def test_generate_returns_string():
    mod = _load_todo_view()
    result = mod.generate_todo_view(notion_todos=[], docs_todo_content="")
    assert isinstance(result, str)


def test_exactly_two_sections():
    """AC5: todo-view.md has exactly two sections."""
    mod = _load_todo_view()
    result = mod.generate_todo_view(
        notion_todos=[{"title": "Do X", "status": "in_progress"}],
        docs_todo_content="- [ ] Fix bug\n",
    )
    h2_sections = [line for line in result.splitlines() if line.startswith("## ")]
    assert len(h2_sections) == 2, (
        f"Expected exactly 2 ## sections, got {len(h2_sections)}: {h2_sections}"
    )


# ---------------------------------------------------------------------------
# AC: Section 1 — Notion todos + Notion banner
# ---------------------------------------------------------------------------

def test_section_one_contains_notion_banner():
    """AC6: section one has a banner naming Notion as authoritative write home."""
    mod = _load_todo_view()
    result = mod.generate_todo_view(
        notion_todos=[{"title": "Task A", "status": "open"}],
        docs_todo_content="",
    )
    assert "Notion" in result, "todo-view.md must name Notion in section one banner"


def test_section_one_renders_notion_todos():
    """AC6: section one renders Notion todos."""
    mod = _load_todo_view()
    todos = [
        {"title": "Write tests", "status": "in_progress"},
        {"title": "Ship feature", "status": "open"},
    ]
    result = mod.generate_todo_view(notion_todos=todos, docs_todo_content="")
    assert "Write tests" in result, "Section one must render Notion todo titles"
    assert "Ship feature" in result, "Section one must render Notion todo titles"


def test_section_one_banner_present_when_notion_empty():
    """AC9: Notion banner is present even when Notion returns zero todos."""
    mod = _load_todo_view()
    result = mod.generate_todo_view(notion_todos=[], docs_todo_content="")
    assert "Notion" in result, "Notion banner must be present even when todos list is empty"


# ---------------------------------------------------------------------------
# AC: Section 2 — docs/todo.md mirror + commander banner
# ---------------------------------------------------------------------------

def test_section_two_contains_commander_banner():
    """AC7: section two has a banner naming commander as maintainer."""
    mod = _load_todo_view()
    result = mod.generate_todo_view(
        notion_todos=[],
        docs_todo_content="- [ ] Fix issue #42\n",
    )
    assert "commander" in result.lower(), (
        "todo-view.md must name commander in section two banner"
    )


def test_section_two_mirrors_docs_todo_verbatim():
    """AC7: section two mirrors docs/todo.md content verbatim."""
    mod = _load_todo_view()
    docs_content = "- [ ] Fix issue #42\n- [x] Implement auth\n"
    result = mod.generate_todo_view(notion_todos=[], docs_todo_content=docs_content)
    assert "Fix issue #42" in result, "Section two must mirror docs/todo.md content"
    assert "Implement auth" in result, "Section two must mirror docs/todo.md content"


def test_section_two_banner_present_when_docs_todo_empty():
    """AC9: commander banner is present even when docs/todo.md is empty."""
    mod = _load_todo_view()
    result = mod.generate_todo_view(notion_todos=[], docs_todo_content="")
    assert "commander" in result.lower(), (
        "Commander banner must be present even when docs/todo.md is empty"
    )


# ---------------------------------------------------------------------------
# AC: Both banners present in every generated todo-view.md
# ---------------------------------------------------------------------------

def test_both_banners_present_with_both_sources_populated():
    """AC9: both banners present when both sources have content."""
    mod = _load_todo_view()
    result = mod.generate_todo_view(
        notion_todos=[{"title": "Task A", "status": "open"}],
        docs_todo_content="- [ ] Fix bug\n",
    )
    assert "Notion" in result, "Notion banner must be present"
    assert "commander" in result.lower(), "commander banner must be present"


def test_both_banners_present_with_both_sources_empty():
    """AC9: both banners present when both sources are empty."""
    mod = _load_todo_view()
    result = mod.generate_todo_view(notion_todos=[], docs_todo_content="")
    assert "Notion" in result, "Notion banner must be present even when empty"
    assert "commander" in result.lower(), "commander banner must be present even when empty"


# ---------------------------------------------------------------------------
# AC: No instruction to edit todo-view.md directly
# ---------------------------------------------------------------------------

def test_no_edit_instructions_in_output():
    """AC8: todo-view.md contains no instruction telling contributors to edit it."""
    mod = _load_todo_view()
    result = mod.generate_todo_view(
        notion_todos=[{"title": "Task A", "status": "open"}],
        docs_todo_content="- [ ] Fix bug\n",
    )
    edit_phrases = [
        "do not edit",
        "don't edit",
        "edit this file",
        "edit directly",
        "modify this file",
        "do not modify",
    ]
    lower = result.lower()
    for phrase in edit_phrases:
        assert phrase not in lower, (
            f"todo-view.md must not contain edit instruction '{phrase}'; found in output"
        )


# ---------------------------------------------------------------------------
# AC: write_todo_view writes todo-view.md to the given path
# ---------------------------------------------------------------------------

def test_write_todo_view_creates_file(tmp_path):
    """write_todo_view writes todo-view.md."""
    mod = _load_todo_view()
    output_path = tmp_path / "todo-view.md"
    mod.write_todo_view(
        notion_todos=[{"title": "Task A", "status": "open"}],
        docs_todo_content="- [ ] Fix bug\n",
        output_path=output_path,
    )
    assert output_path.exists(), "write_todo_view must create the output file"


def test_write_todo_view_content_matches_generate(tmp_path):
    """write_todo_view output matches generate_todo_view string."""
    mod = _load_todo_view()
    todos = [{"title": "Task A", "status": "open"}]
    docs_content = "- [ ] Fix bug\n"
    expected = mod.generate_todo_view(notion_todos=todos, docs_todo_content=docs_content)
    output_path = tmp_path / "todo-view.md"
    mod.write_todo_view(notion_todos=todos, docs_todo_content=docs_content, output_path=output_path)
    assert output_path.read_text() == expected

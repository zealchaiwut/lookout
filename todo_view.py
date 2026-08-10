"""
todo_view.py — todo-view.md generator for Lookout.

Writes todo-view.md with two sections:
  Section 1: Notion todos scoped to this project (read-only mirror)
  Section 2: docs/todo.md verbatim mirror

Both sections carry a banner identifying their authoritative source.
The output file is read-only — contributors must edit Notion or
docs/todo.md, not this file.

Usage
-----
    from todo_view import generate_todo_view, write_todo_view
    content = generate_todo_view(notion_todos=todos, docs_todo_content=text)
    write_todo_view(notion_todos=todos, docs_todo_content=text, output_path=path)

Or CLI:
    python todo_view.py <target-name> [--vault <vault_dir>] [--docs-todo <path>]
"""
import sys
from pathlib import Path


_NOTION_BANNER = (
    "> **Source: Notion** — This section is a read-only mirror of Notion todos "
    "scoped to this project. Notion is the authoritative write home for these items."
)

_COMMANDER_BANNER = (
    "> **Source: commander** — This section mirrors `docs/todo.md` verbatim. "
    "Commander is the maintainer of that file."
)


def generate_todo_view(notion_todos: list[dict], docs_todo_content: str) -> str:
    """
    Generate the content of todo-view.md.

    Parameters
    ----------
    notion_todos : list of dicts
        Each dict has at least 'title' and 'status' keys.
    docs_todo_content : str
        Verbatim content of docs/todo.md (may be empty string).

    Returns
    -------
    str — the full content of todo-view.md.
    """
    lines: list[str] = [
        "# Todo View",
        "",
        "_This file is auto-generated. See each section's source banner for where to make edits._",
        "",
    ]

    # Section 1: Notion todos
    lines.append("## Notion Todos")
    lines.append("")
    lines.append(_NOTION_BANNER)
    lines.append("")
    if notion_todos:
        for todo in notion_todos:
            title = todo.get("title", "")
            status = todo.get("status", "")
            if title:
                checkbox = "[x]" if status.lower() in ("done", "completed", "closed", "archived") else "[ ]"
                lines.append(f"- {checkbox} {title}")
    else:
        lines.append("_No Notion todos found for this project._")
    lines.append("")

    # Section 2: docs/todo.md mirror
    lines.append("## Commander Todos")
    lines.append("")
    lines.append(_COMMANDER_BANNER)
    lines.append("")
    if docs_todo_content.strip():
        lines.append(docs_todo_content.rstrip())
    else:
        lines.append("_docs/todo.md is empty._")
    lines.append("")

    return "\n".join(lines)


def write_todo_view(
    notion_todos: list[dict],
    docs_todo_content: str,
    output_path: Path,
) -> None:
    """Write todo-view.md to output_path."""
    content = generate_todo_view(notion_todos=notion_todos, docs_todo_content=docs_todo_content)
    output_path.write_text(content)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _run_cli(target_name: str, vault_dir: Path | None = None, docs_todo_path: Path | None = None) -> Path:
    if vault_dir is None:
        vault_dir = Path(__file__).parent / "vault"

    project_dir = vault_dir / "projects" / target_name
    snapshot_dir = _find_latest_snapshot(project_dir)

    import json

    notion_todos: list[dict] = []
    if snapshot_dir and (snapshot_dir / "notion_todos.json").exists():
        raw = json.loads((snapshot_dir / "notion_todos.json").read_text())
        notion_todos = raw if isinstance(raw, list) else raw.get("todos", [])

    if docs_todo_path is None:
        docs_todo_path = Path(__file__).parent / "docs" / "todo.md"

    docs_todo_content = ""
    if docs_todo_path.exists():
        docs_todo_content = docs_todo_path.read_text()

    output_path = project_dir / "todo-view.md"
    project_dir.mkdir(parents=True, exist_ok=True)
    write_todo_view(
        notion_todos=notion_todos,
        docs_todo_content=docs_todo_content,
        output_path=output_path,
    )
    print(f"Wrote {output_path}")
    return output_path


def _find_latest_snapshot(project_dir: Path) -> Path | None:
    raw_dir = project_dir / "raw"
    if not raw_dir.exists():
        return None
    dirs = sorted(
        d for d in raw_dir.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )
    return dirs[-1] if dirs else None


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python todo_view.py <target-name> [--vault <vault_dir>] [--docs-todo <path>]",
            file=sys.stderr,
        )
        sys.exit(1)
    target = sys.argv[1]
    vault_dir = None
    docs_todo_path = None
    if "--vault" in sys.argv:
        idx = sys.argv.index("--vault")
        vault_dir = Path(sys.argv[idx + 1])
    if "--docs-todo" in sys.argv:
        idx = sys.argv.index("--docs-todo")
        docs_todo_path = Path(sys.argv[idx + 1])
    _run_cli(target, vault_dir, docs_todo_path)


if __name__ == "__main__":
    main()

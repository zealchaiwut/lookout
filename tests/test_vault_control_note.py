"""Tests for issue #2: vault/agents.md control note and vault/index.md index stub."""
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_path(relative):
    return os.path.join(REPO_ROOT, relative)


def read_file(relative):
    with open(repo_path(relative)) as f:
        return f.read()


# AC1: vault/agents.md lists all machine-owned file types
MACHINE_OWNED = [
    "situation",
    "capability body",
    "drift",
    "todo-view",
    "atlas",
    "index",
    "journal index",
    "ideas ledger",
    "assessment blocks",
    "packs",
]


def test_agents_md_exists():
    assert os.path.isfile(repo_path("vault/agents.md"))


def test_agents_md_lists_machine_owned_situation():
    content = read_file("vault/agents.md").lower()
    assert "situation" in content


def test_agents_md_lists_machine_owned_capability_body():
    content = read_file("vault/agents.md").lower()
    assert "capability body" in content


def test_agents_md_lists_machine_owned_drift():
    content = read_file("vault/agents.md").lower()
    assert "drift" in content


def test_agents_md_lists_machine_owned_todo_view():
    content = read_file("vault/agents.md").lower()
    assert "todo-view" in content


def test_agents_md_lists_machine_owned_atlas():
    content = read_file("vault/agents.md").lower()
    assert "atlas" in content


def test_agents_md_lists_machine_owned_index():
    content = read_file("vault/agents.md").lower()
    assert "index" in content


def test_agents_md_lists_machine_owned_journal_index():
    content = read_file("vault/agents.md").lower()
    assert "journal index" in content


def test_agents_md_lists_machine_owned_ideas_ledger():
    content = read_file("vault/agents.md").lower()
    assert "ideas ledger" in content


def test_agents_md_lists_machine_owned_assessment_blocks():
    content = read_file("vault/agents.md").lower()
    assert "assessment blocks" in content


def test_agents_md_lists_machine_owned_packs():
    content = read_file("vault/agents.md").lower()
    assert "packs" in content


# AC2: vault/agents.md lists all human-owned file types
def test_agents_md_lists_human_owned_notes():
    content = read_file("vault/agents.md").lower()
    assert "notes" in content


def test_agents_md_lists_human_owned_learning():
    content = read_file("vault/agents.md").lower()
    assert "learning" in content


def test_agents_md_lists_human_owned_decisions():
    content = read_file("vault/agents.md").lower()
    assert "decisions" in content


def test_agents_md_lists_human_owned_agents_md():
    content = read_file("vault/agents.md").lower()
    assert "agents.md" in content


def test_agents_md_lists_human_owned_idea_freeform_tops():
    content = read_file("vault/agents.md").lower()
    assert "idea freeform" in content


# AC3: read-only invariant present
def test_agents_md_contains_readonly_invariant():
    content = read_file("vault/agents.md").lower()
    has_readonly = "read-only" in content or "readonly" in content
    has_write = "may not write" in content or "no tool" in content or "must not write" in content
    assert has_readonly or has_write, "read-only invariant not found"


def test_agents_md_invariant_covers_target_project():
    content = read_file("vault/agents.md").lower()
    assert "target" in content or "target project" in content


def test_agents_md_invariant_covers_github():
    content = read_file("vault/agents.md").lower()
    assert "github" in content


def test_agents_md_invariant_covers_notion():
    content = read_file("vault/agents.md").lower()
    assert "notion" in content


def test_agents_md_invariant_covers_journal_repo():
    content = read_file("vault/agents.md").lower()
    assert "journal" in content


# AC4: raw/ source of truth statement
def test_agents_md_states_raw_source_of_truth():
    content = read_file("vault/agents.md").lower()
    assert "raw/" in content


def test_agents_md_states_source_of_truth():
    content = read_file("vault/agents.md").lower()
    assert "source of truth" in content


# AC5 & AC6: vault/index.md has valid GFM table with exactly 5 columns
def test_index_md_exists():
    assert os.path.isfile(repo_path("vault/index.md"))


def test_index_md_has_five_column_header():
    content = read_file("vault/index.md")
    lines = content.splitlines()
    header_lines = [ln for ln in lines if "target" in ln.lower() and "one-liner" in ln.lower()]
    assert len(header_lines) == 1, "Expected exactly one header row with 'target' and 'one-liner'"
    header = header_lines[0]
    cols = [c.strip() for c in header.strip().strip("|").split("|")]
    assert len(cols) == 5, f"Expected 5 columns, got {len(cols)}: {cols}"


def test_index_md_column_order():
    content = read_file("vault/index.md")
    lines = content.splitlines()
    header_lines = [ln for ln in lines if "target" in ln.lower() and "one-liner" in ln.lower()]
    assert header_lines, "No header row found"
    header = header_lines[0]
    cols = [c.strip().lower() for c in header.strip().strip("|").split("|")]
    assert cols[0] == "target"
    assert cols[1] == "one-liner"
    assert cols[2] == "capacity"
    assert cols[3] == "todos"
    assert cols[4] == "last run"


def test_index_md_has_separator_row():
    content = read_file("vault/index.md")
    lines = content.splitlines()
    sep_lines = [ln for ln in lines if re.match(r"^\s*\|?\s*---", ln)]
    assert len(sep_lines) >= 1, "No separator row found"


def test_index_md_separator_has_five_columns():
    content = read_file("vault/index.md")
    lines = content.splitlines()
    sep_lines = [ln for ln in lines if re.match(r"^\s*\|?\s*---", ln)]
    assert sep_lines, "No separator row found"
    sep = sep_lines[0]
    cols = [c.strip() for c in sep.strip().strip("|").split("|")]
    assert len(cols) == 5, f"Separator should have 5 columns, got {len(cols)}"


def test_index_md_has_zero_data_rows():
    content = read_file("vault/index.md")
    lines = content.splitlines()
    table_lines = [ln for ln in lines if "|" in ln]
    # Remove header and separator rows
    data_rows = []
    found_sep = False
    for line in table_lines:
        if re.match(r"^\s*\|?\s*---", line):
            found_sep = True
            continue
        if found_sep and "|" in line:
            data_rows.append(line)
    assert len(data_rows) == 0, f"Expected 0 data rows, found {len(data_rows)}: {data_rows}"


# AC7: no stray frontmatter in either file
def test_agents_md_no_frontmatter():
    content = read_file("vault/agents.md")
    assert not content.startswith("---"), "vault/agents.md must not have YAML frontmatter"


def test_index_md_no_frontmatter():
    content = read_file("vault/index.md")
    assert not content.startswith("---"), "vault/index.md must not have YAML frontmatter"


def test_index_md_no_placeholder_data_rows():
    content = read_file("vault/index.md")
    # A placeholder row would have non-separator, non-header pipe-delimited content
    lines = content.splitlines()
    data_rows = []
    found_sep = False
    for line in lines:
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            continue
        if re.match(r"^\s*\|?\s*---", line):
            found_sep = True
            continue
        if found_sep:
            data_rows.append(line)
    assert data_rows == [], f"Unexpected placeholder rows: {data_rows}"

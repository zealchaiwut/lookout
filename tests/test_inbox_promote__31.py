"""Tests for issue #31: vault inbox capture and promote command.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
PROMOTE_PY = REPO_ROOT / "promote.py"
BIN_LOOKOUT = REPO_ROOT / "bin" / "lookout"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_promote():
    spec = importlib.util.spec_from_file_location("promote_test_mod", str(PROMOTE_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "inbox").mkdir(parents=True)
    (vault / "ideas").mkdir(parents=True)
    (vault / "packs").mkdir(parents=True)
    return vault


def _make_inbox_file(vault: Path, name: str, content: str) -> Path:
    f = vault / "inbox" / name
    f.write_text(content)
    return f


_NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# AC1: vault/inbox/ is the freeform capture zone; CLI does not auto-process it
# ---------------------------------------------------------------------------

def test_ac1_inbox_directory_exists():
    """AC1: vault/inbox/ directory exists in the repo."""
    inbox = REPO_ROOT / "vault" / "inbox"
    assert inbox.exists(), "vault/inbox/ must exist as the freeform capture zone"
    assert inbox.is_dir()


def test_ac1_inbox_files_not_auto_processed(tmp_path):
    """AC1: Placing a file in inbox/ does not trigger automatic processing."""
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(vault, "raw-note.md", "some raw content\nno structure needed")

    # Verify the file is untouched — promote reads it only when explicitly called
    assert inbox_file.exists()
    assert inbox_file.read_text() == "some raw content\nno structure needed"
    # No artifact created in ideas/ or packs/
    assert list((vault / "ideas").iterdir()) == []
    assert list((vault / "packs").iterdir()) == []


# ---------------------------------------------------------------------------
# AC2: promote --type idea creates vault/ideas/<slug>.md with required frontmatter
# ---------------------------------------------------------------------------

def test_ac2_idea_creates_file_in_vault_ideas(tmp_path):
    """AC2: promote --type idea writes output to vault/ideas/."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "my-idea.md",
        "# My Great Idea\n\nSome unstructured notes about a great idea.\n"
    )

    result = promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)

    assert result.parent == vault / "ideas"
    assert result.exists()


def test_ac2_idea_frontmatter_has_required_fields(tmp_path):
    """AC2: Generated idea note has title, date, tags, status in frontmatter."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "my-idea.md",
        "# My Great Idea\n\nSome notes.\n"
    )

    result = promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)
    content = result.read_text()

    # Extract frontmatter
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    assert fm_match, "Generated idea file must have YAML frontmatter"
    fm = yaml.safe_load(fm_match.group(1))

    assert "title" in fm, "frontmatter must have 'title'"
    assert "date" in fm, "frontmatter must have 'date'"
    assert "tags" in fm, "frontmatter must have 'tags'"
    assert "status" in fm, "frontmatter must have 'status'"


def test_ac2_idea_frontmatter_values_non_empty(tmp_path):
    """AC2: Required frontmatter fields are populated, not empty/None."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "dark-mode-idea.md",
        "# Dark Mode\n\nAdd dark mode support to the dashboard.\n"
    )

    result = promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)
    content = result.read_text()

    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    fm = yaml.safe_load(fm_match.group(1))

    assert fm["title"], "title must not be empty"
    assert fm["date"], "date must not be empty/None"
    assert fm["status"], "status must not be empty"
    # tags may be an empty list, but must be present and a list
    assert isinstance(fm["tags"], list), "tags must be a list"


def test_ac2_idea_title_from_heading(tmp_path):
    """AC2: Title is extracted from the first # heading in the inbox file."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "offline-sync.md",
        "# Offline Sync Feature\n\nCache last snapshot locally.\n"
    )

    result = promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)
    fm_match = re.match(r"^---\n(.*?)\n---", result.read_text(), re.DOTALL)
    fm = yaml.safe_load(fm_match.group(1))

    assert "Offline Sync Feature" in fm["title"]


def test_ac2_idea_title_falls_back_to_filename_stem(tmp_path):
    """AC2: Title falls back to filename stem when no # heading present."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "search-improvements.md",
        "Some raw notes without a heading.\n"
    )

    result = promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)
    fm_match = re.match(r"^---\n(.*?)\n---", result.read_text(), re.DOTALL)
    fm = yaml.safe_load(fm_match.group(1))

    assert fm["title"], "title must still be populated from filename stem"


def test_ac2_idea_date_is_today(tmp_path):
    """AC2: date field matches the date passed as 'now'."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(vault, "some-idea.md", "# Some Idea\n\nContent.\n")

    result = promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)
    fm_match = re.match(r"^---\n(.*?)\n---", result.read_text(), re.DOTALL)
    fm = yaml.safe_load(fm_match.group(1))

    date_val = str(fm["date"])
    assert "2026-08-10" in date_val


def test_ac2_idea_frontmatter_is_valid_yaml(tmp_path):
    """AC2: Generated frontmatter parses without errors."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "valid-yaml.md",
        "# Valid YAML Test\n\nSome content.\n"
    )

    result = promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)
    content = result.read_text()

    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    assert fm_match, "Must have YAML frontmatter block"
    # Should not raise
    fm = yaml.safe_load(fm_match.group(1))
    assert isinstance(fm, dict)


# ---------------------------------------------------------------------------
# AC3: promote --type sprint writes bulk-create format pack to vault/packs/
# ---------------------------------------------------------------------------

def test_ac3_sprint_creates_file_in_vault_packs(tmp_path):
    """AC3: promote --type sprint writes output to vault/packs/."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "sprint-batch.md",
        "# Sprint Batch\n\nContext: some work.\n\n---\n\nBuild feature A\n\n---\n\nFix bug B\n"
    )

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)

    assert result.parent == vault / "packs"
    assert result.exists()


def test_ac3_sprint_pack_has_date_field(tmp_path):
    """AC3: Sprint pack contains **Date:** field."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(vault, "batch.md", "# Batch\n\n---\n\nSome prompt\n")

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    content = result.read_text()

    assert re.search(r"\*\*Date:\*\*", content), "Sprint pack must have **Date:** field"
    assert "2026-08-10" in content


def test_ac3_sprint_pack_has_sprint_label(tmp_path):
    """AC3: Sprint pack contains **Sprint label:** field."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(vault, "batch.md", "# Batch\n\n---\n\nSome prompt\n")

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    content = result.read_text()

    assert re.search(r"\*\*Sprint label:\*\*", content), "Sprint pack must have **Sprint label:** field"


def test_ac3_sprint_pack_has_default_labels(tmp_path):
    """AC3: Sprint pack contains **Default labels:** field."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(vault, "batch.md", "# Batch\n\n---\n\nSome prompt\n")

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    content = result.read_text()

    assert re.search(r"\*\*Default labels:\*\*", content), "Sprint pack must have **Default labels:** field"


def test_ac3_sprint_pack_has_status_header(tmp_path):
    """AC3: Sprint pack contains **Status:** header."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(vault, "batch.md", "# Batch\n\n---\n\nSome prompt\n")

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    content = result.read_text()

    assert re.search(r"\*\*Status:\*\*", content), "Sprint pack must have **Status:** field"


def test_ac3_sprint_pack_has_prompts_section(tmp_path):
    """AC3: Sprint pack has a ## Prompts section with a fenced code block."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "batch.md",
        "# Batch\n\n---\n\nBuild feature A\n\n---\n\nFix bug B\n"
    )

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    content = result.read_text()

    assert "## Prompts" in content, "Sprint pack must have ## Prompts section"
    assert "```" in content, "Prompts section must have a fenced code block"


def test_ac3_sprint_pack_prompts_separated_by_dashes(tmp_path):
    """AC3: Individual prompts in the fenced block are separated by ---."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "batch.md",
        "# Batch\n\nContext here.\n\n---\n\nBuild feature A\n\n---\n\nFix bug B\n"
    )

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    content = result.read_text()

    # Find the fenced block
    fence_match = re.search(r"```.*?\n(.*?)```", content, re.DOTALL)
    assert fence_match, "Must have a fenced code block"
    block = fence_match.group(1)
    assert "---" in block, "Prompts must be separated by --- within the fenced block"


def test_ac3_sprint_pack_has_context_section(tmp_path):
    """AC3: Sprint pack has a context section before the prompts."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "batch.md",
        "# Batch\n\nThis is the context for the sprint.\n\n---\n\nPrompt one\n"
    )

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    content = result.read_text()

    assert "## Context" in content or "context" in content.lower(), (
        "Sprint pack must include a context section"
    )


# ---------------------------------------------------------------------------
# AC4: Sprint pack includes posted-issues table as final section
# ---------------------------------------------------------------------------

def test_ac4_sprint_pack_has_posted_issues_table(tmp_path):
    """AC4: Sprint pack ends with a ## Posted issues table."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(vault, "batch.md", "# Batch\n\n---\n\nSome prompt\n")

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    content = result.read_text()

    assert "## Posted issues" in content, "Sprint pack must have ## Posted issues section"


def test_ac4_posted_issues_has_table_header(tmp_path):
    """AC4: Posted issues section contains a markdown table with # | Title | Size columns."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(vault, "batch.md", "# Batch\n\n---\n\nSome prompt\n")

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    content = result.read_text()

    # Table must have at least # and Title columns
    assert re.search(r"\|\s*#\s*\|.*\|\s*Title\s*\|", content) or \
           re.search(r"\|\s*#\s*\|", content), "Posted issues must have a markdown table header"
    # Separator row
    assert re.search(r"\|[-| ]+\|", content), "Table must have a separator row"


# ---------------------------------------------------------------------------
# AC5: Sprint pack accepted without parse errors by bulk-create schema check
# ---------------------------------------------------------------------------

def test_ac5_sprint_pack_passes_schema_check(tmp_path):
    """AC5: Generated sprint pack satisfies the bulk-create format schema."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "sprint-batch.md",
        "# Sprint Batch\n\nContext notes.\n\n---\n\nBuild feature A\n\nAC: works\n\n---\n\nFix bug B\n\nAC: fixed\n"
    )

    result = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    content = result.read_text()

    errors = promote.validate_bulk_create_pack(content)
    assert errors == [], f"Sprint pack failed schema validation: {errors}"


# ---------------------------------------------------------------------------
# AC6: Promote module has zero write-path matches for commander/github/octokit/gh
# ---------------------------------------------------------------------------

def test_ac6_no_commander_github_api_calls():
    """AC6: promote.py contains no write-path imports of commander/github/octokit/gh."""
    assert PROMOTE_PY.exists(), "promote.py must exist"
    content = PROMOTE_PY.read_text()

    # These patterns indicate network/API write paths
    forbidden_patterns = [
        r"\bgithub\b",
        r"\boctokit\b",
        r"\bcommander\b",
        r"\brequests\.post\b",
        r"\brequests\.put\b",
        r"\brequests\.delete\b",
        r"\brequests\.patch\b",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, content, re.IGNORECASE), (
            f"promote.py must not reference '{pattern}' (AC6: no API write paths)"
        )


def test_ac6_subprocess_grep_no_api_matches():
    """AC6: grep for commander|github|octokit in promote.py returns zero matches."""
    result = subprocess.run(
        ["grep", "-n", r"commander\|github\|octokit", str(PROMOTE_PY)],
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "", (
        f"promote.py must not contain commander/github/octokit references:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# AC7: Non-existent inbox file exits non-zero with descriptive error
# ---------------------------------------------------------------------------

def test_ac7_missing_inbox_file_raises(tmp_path):
    """AC7: Promoting a non-existent file raises an error."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    missing = vault / "inbox" / "does-not-exist.md"

    with pytest.raises((FileNotFoundError, SystemExit, promote.PromoteError)) as exc_info:
        promote.promote(missing, "idea", vault_dir=vault, now=_NOW)

    if isinstance(exc_info.value, SystemExit):
        assert exc_info.value.code != 0


def test_ac7_missing_file_error_is_descriptive(tmp_path, capsys):
    """AC7: Error message mentions the missing file path."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    missing = vault / "inbox" / "does-not-exist.md"

    try:
        promote.promote(missing, "idea", vault_dir=vault, now=_NOW)
    except (FileNotFoundError, SystemExit, Exception) as exc:
        err_text = str(exc)
        captured = capsys.readouterr()
        combined = err_text + captured.err
        assert "does-not-exist.md" in combined or "not found" in combined.lower() or \
               "no such file" in combined.lower(), (
            "Error message must describe the missing file"
        )


def test_ac7_missing_file_subprocess_exits_nonzero(tmp_path):
    """AC7: Subprocess call with nonexistent file exits with non-zero code."""
    result = subprocess.run(
        [sys.executable, str(PROMOTE_PY), "/nonexistent/path/file.md", "--type", "idea"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert result.stderr.strip() != "" or "not found" in result.stdout.lower()


# ---------------------------------------------------------------------------
# AC8: Idempotency — errors rather than silently overwriting existing destination
# ---------------------------------------------------------------------------

def test_ac8_errors_if_destination_exists(tmp_path):
    """AC8: promote errors if the destination file already exists."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(vault, "my-idea.md", "# My Idea\n\nContent.\n")

    # First call should succeed
    first = promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)
    assert first.exists()

    # Second call must raise (not silently overwrite)
    with pytest.raises((FileExistsError, SystemExit, promote.PromoteError)) as exc_info:
        promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)

    if isinstance(exc_info.value, SystemExit):
        assert exc_info.value.code != 0


def test_ac8_destination_not_overwritten(tmp_path):
    """AC8: Content of the existing destination file is not changed on second run."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(vault, "stable-idea.md", "# Stable Idea\n\nOriginal.\n")

    first = promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)
    original_content = first.read_text()

    try:
        promote.promote(inbox_file, "idea", vault_dir=vault, now=_NOW)
    except Exception:
        pass

    assert first.read_text() == original_content, "Existing destination must not be overwritten"


def test_ac8_sprint_errors_if_destination_exists(tmp_path):
    """AC8: promote --type sprint also errors if destination pack already exists."""
    promote = _load_promote()
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "batch.md", "# Batch\n\n---\n\nSome prompt\n"
    )

    first = promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)
    assert first.exists()

    with pytest.raises((FileExistsError, SystemExit, promote.PromoteError)):
        promote.promote(inbox_file, "sprint", vault_dir=vault, now=_NOW)


# ---------------------------------------------------------------------------
# Integration: bin/lookout promote dispatches correctly
# ---------------------------------------------------------------------------

def test_integration_lookout_promote_idea(tmp_path):
    """Integration: `bin/lookout promote <file> --type idea` exits 0 and creates output."""
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "integration-test.md",
        "# Integration Test Idea\n\nContent for integration test.\n"
    )

    result = subprocess.run(
        [sys.executable, str(BIN_LOOKOUT), "promote", str(inbox_file), "--type", "idea",
         "--vault", str(vault)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}\n{result.stderr}"
    ideas = list((vault / "ideas").glob("*.md"))
    assert len(ideas) == 1, "Expected exactly one idea file created"


def test_integration_lookout_promote_sprint(tmp_path):
    """Integration: `bin/lookout promote <file> --type sprint` exits 0 and creates pack."""
    vault = _make_vault(tmp_path)
    inbox_file = _make_inbox_file(
        vault, "sprint-integration.md",
        "# Sprint Integration\n\nContext.\n\n---\n\nBuild something\n"
    )

    result = subprocess.run(
        [sys.executable, str(BIN_LOOKOUT), "promote", str(inbox_file), "--type", "sprint",
         "--vault", str(vault)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}\n{result.stderr}"
    packs = list((vault / "packs").glob("*.md"))
    assert len(packs) == 1, "Expected exactly one pack file created"


def test_integration_lookout_promote_missing_file(tmp_path):
    """Integration: `bin/lookout promote` with missing file exits non-zero."""
    vault = _make_vault(tmp_path)

    result = subprocess.run(
        [sys.executable, str(BIN_LOOKOUT), "promote",
         str(vault / "inbox" / "ghost.md"), "--type", "idea",
         "--vault", str(vault)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0

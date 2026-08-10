"""Tests for issue #3: lint.py wikilink and index/folder checks.
Extended for issue #13: decision question refs and stale question notices.
Extended for issue #17: atlas note path checks.
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LINT_SCRIPT = Path(__file__).parent.parent / ".claude/skills/lookout/scripts/lint.py"
VAULT_ROOT = Path(__file__).parent.parent / "vault"


def run_lint(vault_path):
    result = subprocess.run(
        [sys.executable, str(LINT_SCRIPT), "--vault", str(vault_path)],
        capture_output=True,
        text=True,
    )
    return result


# AC: script exists and is importable (basic sanity)
def test_lint_script_exists():
    assert LINT_SCRIPT.exists(), f"lint.py not found at {LINT_SCRIPT}"


# AC: running against the scaffolded vault exits 0 with no failures
def test_lint_passes_on_scaffolded_vault():
    result = run_lint(VAULT_ROOT)
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}\n{result.stdout}\n{result.stderr}"


# (a) Wikilink check passes on a clean fixture
def test_wikilink_check_passes_clean(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note-a.md").write_text("# Note A\n\nSee [[note-b]]\n")
    (vault / "note-b.md").write_text("# Note B\n")
    result = run_lint(vault)
    assert result.returncode == 0, f"Clean vault should pass\n{result.stdout}"


# (b) Wikilink check fails and names the broken link and source file
def test_wikilink_check_fails_names_broken_link(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note-a.md").write_text("# Note A\n\n[[nonexistent-note]]\n")
    result = run_lint(vault)
    assert result.returncode == 1
    assert "note-a.md" in result.stdout
    assert "nonexistent-note" in result.stdout


# (c) Index/folder check passes on a clean fixture
def test_index_folder_check_passes_clean(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    projects = vault / "projects"
    projects.mkdir()
    (projects / "my-project").mkdir()
    (vault / "index.md").write_text("# Vault\n\n- my-project\n")
    result = run_lint(vault)
    assert result.returncode == 0, f"Clean index/folder should pass\n{result.stdout}"


# (d-1) Index/folder check fails: index row has no matching directory
def test_index_folder_check_fails_missing_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "projects").mkdir()
    (vault / "index.md").write_text("# Vault\n\n- missing-project\n")
    result = run_lint(vault)
    assert result.returncode == 1
    assert "missing-project" in result.stdout


# (d-2) Index/folder check fails: orphan directory not in index
def test_index_folder_check_fails_orphan_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    projects = vault / "projects"
    projects.mkdir()
    (projects / "orphan-project").mkdir()
    (vault / "index.md").write_text("# Vault\n")
    result = run_lint(vault)
    assert result.returncode == 1
    assert "orphan-project" in result.stdout


# AC: wikilink check with wikilink-format project references
def test_wikilink_index_format_supported(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    projects = vault / "projects"
    projects.mkdir()
    (projects / "cool-project").mkdir()
    (vault / "index.md").write_text("# Vault\n\n- [[cool-project]]\n")
    result = run_lint(vault)
    assert result.returncode == 0, f"Wikilink-format index row should pass\n{result.stdout}"


# AC: exit code 1 when broken wikilink is present (UAT step 2 scenario)
def test_broken_wikilink_causes_exit_1(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    tmp_file = vault / "temp-note.md"
    tmp_file.write_text("# Temp\n\n[[nonexistent-note]]\n")
    result = run_lint(vault)
    assert result.returncode == 1
    assert "temp-note.md" in result.stdout
    assert "nonexistent-note" in result.stdout


# ---------------------------------------------------------------------------
# AC7: warn when decision entry references unknown question ID
# ---------------------------------------------------------------------------

def _make_questions_json(questions: dict, prefix: str = "CM", next_id: int = 2) -> str:
    return json.dumps({"prefix": prefix, "next_id": next_id, "questions": questions}, indent=2)


def _make_clean_vault(tmp_path, project_name: str = "my-project"):
    """Create a minimal valid vault with one project, no unresolved wikilinks."""
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    projects = vault / "projects"
    projects.mkdir(exist_ok=True)
    proj = projects / project_name
    proj.mkdir(exist_ok=True)
    (vault / "index.md").write_text(f"# Vault\n\n- {project_name}\n")
    return vault, proj


def test_lint_warns_unknown_question_id(tmp_path):
    """AC7: decision entry references a question ID not in any project registry."""
    vault, proj = _make_clean_vault(tmp_path)

    # Registry has CMQ1 only
    known_qs = {"CMQ1": {"id": "CMQ1", "status": "open", "created": "2026-08-01", "text": "Q1"}}
    (proj / "questions.json").write_text(_make_questions_json(known_qs))

    # decisions.md references CMQ999 which doesn't exist
    (vault / "decisions.md").write_text("# Decisions\n\n## Fix it (resolves CMQ999)\n\nWe did it.\n")

    result = run_lint(vault)
    assert "CMQ999" in result.stdout, f"Expected CMQ999 warning in output:\n{result.stdout}"
    # WARN is non-fatal — exit code must remain 0
    assert result.returncode == 0, f"Expected exit 0 for WARN, got {result.returncode}"


def test_lint_no_warn_when_question_id_exists(tmp_path):
    """AC7: no warning when decision references a valid question ID."""
    vault, proj = _make_clean_vault(tmp_path)

    known_qs = {"CMQ1": {"id": "CMQ1", "status": "open", "created": "2026-08-01", "text": "Q1"}}
    (proj / "questions.json").write_text(_make_questions_json(known_qs))
    (vault / "decisions.md").write_text("# Decisions\n\n## Fix it (resolves CMQ1)\n\nDone.\n")

    result = run_lint(vault)
    assert "CMQ999" not in result.stdout
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# AC8: info notice for open questions > 14 days old
# ---------------------------------------------------------------------------

def test_lint_info_stale_open_question(tmp_path):
    """AC8: open question created 15 days ago → info notice."""
    vault, proj = _make_clean_vault(tmp_path)

    old_date = (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%Y-%m-%d")
    stale_qs = {"CMQ1": {"id": "CMQ1", "status": "open", "created": old_date, "text": "Old Q"}}
    (proj / "questions.json").write_text(_make_questions_json(stale_qs))

    result = run_lint(vault)
    assert "CMQ1" in result.stdout, f"Expected CMQ1 in stale-question notice:\n{result.stdout}"
    assert result.returncode == 0, "INFO notice must not cause exit code 1"


def test_lint_no_info_for_fresh_question(tmp_path):
    """AC8: question created today is not flagged."""
    vault, proj = _make_clean_vault(tmp_path)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fresh_qs = {"CMQ1": {"id": "CMQ1", "status": "open", "created": today, "text": "Fresh Q"}}
    (proj / "questions.json").write_text(_make_questions_json(fresh_qs))

    result = run_lint(vault)
    output_lower = result.stdout.lower()
    assert "overdue" not in output_lower and "stale" not in output_lower, \
        f"Fresh question must not trigger stale notice:\n{result.stdout}"


def test_lint_no_info_for_resolved_old_question(tmp_path):
    """AC8: resolved question older than 14 days must NOT be flagged."""
    vault, proj = _make_clean_vault(tmp_path)

    old_date = (datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%d")
    resolved_qs = {
        "CMQ1": {"id": "CMQ1", "status": "resolved", "created": old_date,
                 "text": "Old resolved Q", "resolved_by": "some decision"}
    }
    (proj / "questions.json").write_text(_make_questions_json(resolved_qs))

    result = run_lint(vault)
    # Resolved question must not trigger stale-question info notice
    assert "overdue" not in result.stdout, \
        f"Resolved question must not trigger overdue notice:\n{result.stdout}"


# ---------------------------------------------------------------------------
# AC6, AC7 (issue #17): warn for atlas notes with paths absent from target repo
# ---------------------------------------------------------------------------


def _make_atlas_note_with_files(atlas_dir: Path, slug: str, feature: str, files: list) -> None:
    atlas_dir.mkdir(parents=True, exist_ok=True)
    if files:
        files_yaml = "files:\n" + "\n".join(f"  - {f}" for f in files)
    else:
        files_yaml = "files: []"
    (atlas_dir / f"{slug}.md").write_text(
        f"---\nfeature: {feature}\n{files_yaml}\ntraced: null\nstale: true\n---\n"
    )


def _make_targets_yaml(parent_dir: Path, project_name: str, local_path: Path) -> None:
    (parent_dir / "targets.yaml").write_text(
        f"targets:\n  {project_name}:\n    local: {local_path}\n"
    )


def run_lint_with_targets(vault_path, targets_yaml_path=None):
    """Run lint.py, optionally passing --targets-yaml."""
    cmd = [sys.executable, str(LINT_SCRIPT), "--vault", str(vault_path)]
    if targets_yaml_path:
        cmd += ["--targets-yaml", str(targets_yaml_path)]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_lint_warns_missing_atlas_file_path(tmp_path):
    """AC6/AC7: atlas note files list containing absent path triggers a warning."""
    vault = tmp_path / "vault"
    vault.mkdir()
    projects = vault / "projects"
    projects.mkdir()
    proj = projects / "my-project"
    proj.mkdir()
    (vault / "index.md").write_text("# Vault\n\n- my-project\n")

    # Note referencing a non-existent file
    atlas_dir = proj / "atlas"
    _make_atlas_note_with_files(atlas_dir, "my-feature", "My Feature", ["src/does_not_exist.py"])

    # Local repo dir without the referenced file
    local_dir = tmp_path / "local-repo"
    local_dir.mkdir()
    targets_yaml = tmp_path / "targets.yaml"
    _make_targets_yaml(tmp_path, "my-project", local_dir)

    result = run_lint_with_targets(vault, targets_yaml)
    combined = result.stdout + result.stderr
    assert "does_not_exist.py" in combined, (
        f"Expected missing-path warning in output:\n{combined}"
    )


def test_lint_no_warn_valid_atlas_file_path(tmp_path):
    """AC7: atlas note files list containing a valid path does not trigger warning."""
    vault = tmp_path / "vault"
    vault.mkdir()
    projects = vault / "projects"
    projects.mkdir()
    proj = projects / "my-project"
    proj.mkdir()
    (vault / "index.md").write_text("# Vault\n\n- my-project\n")

    atlas_dir = proj / "atlas"
    _make_atlas_note_with_files(atlas_dir, "my-feature", "My Feature", ["src/real_file.py"])

    # Create the actual file in the local repo
    local_dir = tmp_path / "local-repo"
    (local_dir / "src").mkdir(parents=True)
    (local_dir / "src" / "real_file.py").write_text("# real")
    _make_targets_yaml(tmp_path, "my-project", local_dir)

    result = run_lint_with_targets(vault, tmp_path / "targets.yaml")
    combined = result.stdout + result.stderr
    # Valid path must not generate a missing-path warning
    assert "does_not_exist" not in combined
    assert result.returncode == 0, f"Lint should pass with valid path:\n{combined}"

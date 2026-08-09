"""Tests for issue #3: lint.py wikilink and index/folder checks."""
import subprocess
import sys
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

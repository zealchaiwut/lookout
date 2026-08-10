"""Tests for issue #23: Full vault lint pass — six check families, summary table, clean exit.

Each test maps to a specific AC item.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
LINT_SCRIPT = REPO_ROOT / ".claude" / "skills" / "lookout" / "scripts" / "lint.py"
LINT_PY_ROOT = REPO_ROOT / "lint.py"
VAULT_ROOT = REPO_ROOT / "vault"


def run_lint(vault_path, targets_yaml=None):
    cmd = [sys.executable, str(LINT_SCRIPT), "--vault", str(vault_path)]
    if targets_yaml is not None:
        cmd += ["--targets-yaml", str(targets_yaml)]
    return subprocess.run(cmd, capture_output=True, text=True)


def _make_targets_yaml(tmp_path, projects: list[str]) -> Path:
    lines = ["sources:\n  commander_api: http://localhost:8000\ntargets:\n"]
    for name in projects:
        lines.append(f"  {name}:\n    commander_slug: {name}\n    github: owner/{name}\n")
    ty = tmp_path / "targets.yaml"
    ty.write_text("".join(lines))
    return ty


def _make_vault(tmp_path, projects: list[str] = None):
    vault = tmp_path / "vault"
    vault.mkdir()
    projects_dir = vault / "projects"
    projects_dir.mkdir()
    index_lines = ["# Vault Index\n\n## Projects\n\n"]
    for name in (projects or []):
        (projects_dir / name).mkdir()
        index_lines.append(f"- [[{name}]]\n")
    (vault / "index.md").write_text("".join(index_lines))
    return vault


# ---------------------------------------------------------------------------
# AC1: lint.py executes all six check families
# ---------------------------------------------------------------------------

def test_lint_script_exists():
    assert LINT_SCRIPT.exists(), f"lint.py not found at {LINT_SCRIPT}"


def test_six_check_families_all_referenced_in_source():
    """AC1: all six check families have implementations in lint.py."""
    source = LINT_SCRIPT.read_text(encoding="utf-8")
    for fn_name in (
        "check_wikilinks",
        "check_index_folders",
        "check_ownership_warnings",
        "check_staleness",
        "check_card_token_budget",
        "check_decision_question_refs",
    ):
        assert fn_name in source, f"check family not implemented: {fn_name}"


def test_all_six_families_produce_output_on_run(tmp_path):
    """AC1: running lint prints at least one status line per check family."""
    vault = _make_vault(tmp_path, [])
    targets_yaml = _make_targets_yaml(tmp_path, [])
    result = run_lint(vault, targets_yaml)
    output = result.stdout
    # Each family produces a [PASS], [WARN], or [INFO] line with its name
    for label in (
        "Wikilink",
        "Index",
        "Ownership",
        "Staleness",
        "token budget",
        "question",
    ):
        assert label.lower() in output.lower(), (
            f"No output for check family matching '{label}':\n{output}"
        )


# ---------------------------------------------------------------------------
# AC2: summary table printed
# ---------------------------------------------------------------------------

def test_summary_table_is_printed(tmp_path):
    """AC2: running lint prints a summary table with expected headers."""
    vault = _make_vault(tmp_path, [])
    targets_yaml = _make_targets_yaml(tmp_path, [])
    result = run_lint(vault, targets_yaml)
    output = result.stdout.lower()
    assert "files" in output, f"Summary table missing 'files' column:\n{result.stdout}"
    assert "warnings" in output or "warn" in output, (
        f"Summary table missing warnings column:\n{result.stdout}"
    )
    assert "errors" in output or "error" in output, (
        f"Summary table missing errors column:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# AC3: clean exit on full vault
# ---------------------------------------------------------------------------

def test_lint_exits_clean_on_full_vault():
    """AC3: running against the real vault exits 0 with zero errors."""
    targets_yaml = REPO_ROOT / "targets.yaml"
    result = run_lint(VAULT_ROOT, targets_yaml if targets_yaml.exists() else None)
    assert result.returncode == 0, (
        f"Expected exit 0 on full vault, got {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Ownership warnings check (AC1 detail)
# ---------------------------------------------------------------------------

def test_ownership_warns_project_not_in_targets(tmp_path):
    """Ownership check: project in vault but not in targets.yaml → [WARN]."""
    vault = _make_vault(tmp_path, ["unknown-project"])
    targets_yaml = _make_targets_yaml(tmp_path, [])  # empty targets
    result = run_lint(vault, targets_yaml)
    assert "unknown-project" in result.stdout, (
        f"Expected ownership warning for unregistered project:\n{result.stdout}"
    )
    assert result.returncode == 0, "Ownership warning must be non-fatal (exit 0)"


def test_ownership_no_warn_registered_project(tmp_path):
    """Ownership check: project in vault AND in targets.yaml → no ownership warning."""
    vault = _make_vault(tmp_path, ["my-proj"])
    targets_yaml = _make_targets_yaml(tmp_path, ["my-proj"])
    result = run_lint(vault, targets_yaml)
    # Must not warn about my-proj for ownership
    lines_with_proj = [
        ln for ln in result.stdout.splitlines()
        if "my-proj" in ln and ("own" in ln.lower() or "unregistered" in ln.lower())
    ]
    assert not lines_with_proj, (
        f"Unexpected ownership warning for registered project:\n{result.stdout}"
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Card token budget check (AC1 detail)
# ---------------------------------------------------------------------------

def test_card_token_budget_warns_over_limit(tmp_path):
    """Card token budget: capability.md over 1500 tokens → [WARN]."""
    vault = _make_vault(tmp_path, ["my-proj"])
    cap_md = vault / "projects" / "my-proj" / "capability.md"
    # 1501 words → 1501 tokens (whitespace tokenizer)
    cap_md.write_text(" ".join(["word"] * 1501))
    targets_yaml = _make_targets_yaml(tmp_path, ["my-proj"])
    result = run_lint(vault, targets_yaml)
    output_lower = result.stdout.lower()
    assert "my-proj" in result.stdout, (
        f"Expected budget warning mentioning my-proj:\n{result.stdout}"
    )
    assert "token" in output_lower or "budget" in output_lower, (
        f"Expected token/budget keyword in output:\n{result.stdout}"
    )
    assert result.returncode == 0, "Token budget warning must be non-fatal (exit 0)"


def test_card_token_budget_passes_under_limit(tmp_path):
    """Card token budget: capability.md at exactly 1500 tokens → no warning."""
    vault = _make_vault(tmp_path, ["my-proj"])
    cap_md = vault / "projects" / "my-proj" / "capability.md"
    cap_md.write_text(" ".join(["word"] * 1500))
    targets_yaml = _make_targets_yaml(tmp_path, ["my-proj"])
    result = run_lint(vault, targets_yaml)
    budget_lines = [
        ln for ln in result.stdout.splitlines()
        if "token" in ln.lower() or "budget" in ln.lower()
        if "my-proj" in ln
    ]
    assert not budget_lines, (
        f"Unexpected token budget warning for 1500-token card:\n{result.stdout}"
    )
    assert result.returncode == 0


def test_card_token_budget_no_capability_md(tmp_path):
    """Card token budget: project with no capability.md → no error."""
    vault = _make_vault(tmp_path, ["my-proj"])
    targets_yaml = _make_targets_yaml(tmp_path, ["my-proj"])
    result = run_lint(vault, targets_yaml)
    assert result.returncode == 0, (
        f"Missing capability.md must not cause exit 1:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Root-level lint.py entry point
# ---------------------------------------------------------------------------

def test_root_lint_py_exists():
    """AC2 entry point: lint.py exists at repo root."""
    assert LINT_PY_ROOT.exists(), f"lint.py not found at repo root: {LINT_PY_ROOT}"


def test_root_lint_py_runs(tmp_path):
    """Root lint.py delegates to full lint and exits 0 on a clean vault."""
    vault = _make_vault(tmp_path, [])
    targets_yaml = _make_targets_yaml(tmp_path, [])
    result = subprocess.run(
        [sys.executable, str(LINT_PY_ROOT), "--vault", str(vault),
         "--targets-yaml", str(targets_yaml)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Root lint.py failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Regression: Markdown link in index.md must not be parsed as a project name
# ---------------------------------------------------------------------------

def test_index_parser_ignores_markdown_links(tmp_path):
    """Regression: [text](url) lines in index.md must not be treated as project names."""
    vault = _make_vault(tmp_path, [])
    (vault / "index.md").write_text(
        "# Vault Index\n\n## Projects\n\n"
        "- [[real-project]]\n\n"
        "## Cross-project\n\n"
        "- [map.md](map.md) — machine-generated map\n"
    )
    (vault / "projects" / "real-project").mkdir()
    targets_yaml = _make_targets_yaml(tmp_path, ["real-project"])
    result = run_lint(vault, targets_yaml)
    assert "map.md" not in result.stdout or "[FAIL]" not in result.stdout, (
        f"Markdown link [map.md](map.md) should not be flagged as missing project:\n{result.stdout}"
    )
    # The [FAIL] index check must not trigger for the markdown link
    fail_lines = [ln for ln in result.stdout.splitlines() if "[FAIL]" in ln]
    assert not fail_lines, (
        f"Unexpected FAIL lines — markdown link treated as project name:\n{result.stdout}"
    )
    assert result.returncode == 0

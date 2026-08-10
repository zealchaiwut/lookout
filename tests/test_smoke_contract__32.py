"""Tests for issue #32: Hermes reader contract.

Each test maps to a specific AC item from the issue.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
CONTRACT_DOC = REPO_ROOT / "docs" / "hermes-contract.md"
TARGETS_YAML = REPO_ROOT / "targets.yaml"
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "smoke_contract.py"
README = REPO_ROOT / "README.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"


# ---------------------------------------------------------------------------
# AC1: docs/hermes-contract.md exists and documents every stable read path
# ---------------------------------------------------------------------------

def test_contract_doc_exists():
    assert CONTRACT_DOC.exists(), "docs/hermes-contract.md must exist"


def test_contract_doc_covers_targets_yaml():
    text = CONTRACT_DOC.read_text()
    assert "targets.yaml" in text, "contract must document the targets.yaml path"


def test_contract_doc_covers_situation_md():
    text = CONTRACT_DOC.read_text()
    assert "situation.md" in text, "contract must document per-project situation.md"


def test_contract_doc_covers_capability_md():
    text = CONTRACT_DOC.read_text()
    assert "capability.md" in text, "contract must document per-project capability.md"


def test_contract_doc_covers_ideas_ledger():
    text = CONTRACT_DOC.read_text()
    assert "ideas" in text.lower(), "contract must document the ideas ledger files"


# ---------------------------------------------------------------------------
# AC2: Each path entry has full relative path pattern, purpose, and example
# ---------------------------------------------------------------------------

def test_contract_has_path_patterns():
    text = CONTRACT_DOC.read_text()
    assert "vault/projects/" in text, \
        "contract must show relative path patterns for project files"
    assert "vault/ideas/" in text, \
        "contract must show relative path pattern for ideas ledger"


def test_contract_has_code_examples():
    text = CONTRACT_DOC.read_text()
    assert "```" in text, "contract must include concrete examples in fenced code blocks"


# ---------------------------------------------------------------------------
# AC3: Every frontmatter field listed with type, required/optional, example
# ---------------------------------------------------------------------------

def test_contract_lists_situation_frontmatter_fields():
    text = CONTRACT_DOC.read_text()
    for field in ("target", "run", "sources_ok"):
        assert field in text, f"contract must list situation.md frontmatter field '{field}'"


def test_contract_lists_ideas_frontmatter_fields():
    text = CONTRACT_DOC.read_text()
    for field in ("slug", "created", "status", "targets", "issues", "assessed"):
        assert field in text, f"contract must list ideas ledger frontmatter field '{field}'"


def test_contract_indicates_required_optional():
    text = CONTRACT_DOC.read_text()
    lower = text.lower()
    assert "required" in lower or "optional" in lower, \
        "contract must indicate required/optional status for frontmatter fields"


# ---------------------------------------------------------------------------
# AC4: targets.yaml has contract_version; contract doc says bump it on changes
# ---------------------------------------------------------------------------

def test_targets_yaml_has_contract_version():
    with open(TARGETS_YAML) as f:
        data = yaml.safe_load(f)
    assert "contract_version" in data, \
        "targets.yaml must have a top-level contract_version field"
    assert isinstance(data["contract_version"], int), \
        "contract_version must be an integer"


def test_contract_doc_mentions_contract_version():
    text = CONTRACT_DOC.read_text()
    assert "contract_version" in text, \
        "contract doc must mention the contract_version field"


def test_contract_doc_states_bump_policy():
    text = CONTRACT_DOC.read_text()
    lower = text.lower()
    assert "bump" in lower or "increment" in lower, \
        "contract doc must state that contract_version must be bumped on breaking changes"


# ---------------------------------------------------------------------------
# AC5: Smoke script exists
# ---------------------------------------------------------------------------

def test_smoke_script_exists():
    assert SMOKE_SCRIPT.exists(), "scripts/smoke_contract.py must exist"


# ---------------------------------------------------------------------------
# AC6: Smoke script exits 0 on current, unmodified vault
# ---------------------------------------------------------------------------

def test_smoke_script_exits_zero_on_current_vault():
    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        "smoke_contract.py must exit 0 on the current vault.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC7: Exits non-zero with VIOLATION message when required situation.md field absent
# ---------------------------------------------------------------------------

def test_smoke_script_detects_missing_situation_field():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        proj_dir = tmp_path / "vault" / "projects" / "test-proj"
        proj_dir.mkdir(parents=True)
        # situation.md missing 'sources_ok' required field
        broken = (
            "---\n"
            "target: test-proj\n"
            'run: "2026-08-10T00:00:00Z"\n'
            "---\n\n"
            "## One-liner\n\nBroken card missing sources_ok.\n"
        )
        (proj_dir / "situation.md").write_text(broken)

        result = subprocess.run(
            [sys.executable, str(SMOKE_SCRIPT), "--vault", str(tmp_path / "vault")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode != 0, \
            "smoke_contract.py must exit non-zero when situation.md is missing 'sources_ok'"
        output = result.stdout + result.stderr
        assert "VIOLATION" in output, \
            f"output must contain 'VIOLATION'.\nActual output: {output}"
        assert "sources_ok" in output or "situation.md" in output, \
            f"violation message must name the offending field or file.\nActual output: {output}"


# ---------------------------------------------------------------------------
# AC7: Exits non-zero with VIOLATION when required ideas ledger field absent
# ---------------------------------------------------------------------------

def test_smoke_script_detects_missing_idea_field():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        ideas_dir = tmp_path / "vault" / "ideas"
        ideas_dir.mkdir(parents=True)
        # Missing required 'status' field
        broken = (
            "---\n"
            "slug: test-idea\n"
            "created: 2026-08-10\n"
            "targets: []\n"
            "issues: []\n"
            "assessed: null\n"
            "---\n\n"
            "An idea note missing the required status field.\n"
        )
        (ideas_dir / "2026-08-10-test-idea.md").write_text(broken)

        result = subprocess.run(
            [sys.executable, str(SMOKE_SCRIPT), "--vault", str(tmp_path / "vault")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode != 0, \
            "smoke_contract.py must exit non-zero when idea note is missing 'status'"
        output = result.stdout + result.stderr
        assert "VIOLATION" in output, \
            f"output must contain 'VIOLATION'.\nActual output: {output}"
        assert "status" in output or "test-idea" in output, \
            f"violation message must name the field or file.\nActual output: {output}"


# ---------------------------------------------------------------------------
# AC8: Contract doc and smoke script referenced from README or CONTRIBUTING.md
# ---------------------------------------------------------------------------

def test_contract_referenced_in_docs():
    readme_text = README.read_text() if README.exists() else ""
    contrib_text = CONTRIBUTING.read_text() if CONTRIBUTING.exists() else ""
    combined = readme_text + contrib_text
    assert "hermes-contract" in combined, \
        "hermes-contract.md must be referenced in README.md or CONTRIBUTING.md"


def test_smoke_script_referenced_in_docs():
    readme_text = README.read_text() if README.exists() else ""
    contrib_text = CONTRIBUTING.read_text() if CONTRIBUTING.exists() else ""
    combined = readme_text + contrib_text
    assert "smoke_contract" in combined, \
        "smoke_contract must be referenced in README.md or CONTRIBUTING.md"

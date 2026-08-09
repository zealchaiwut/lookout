"""Tests for issue #1: scaffold lookout repo structure per DESIGN.md §1."""
import os
import subprocess

import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_path(relative):
    return os.path.join(REPO_ROOT, relative)


# AC: vault markdown files exist
def test_vault_index_md_exists():
    assert os.path.isfile(repo_path("vault/index.md"))


def test_vault_agents_md_exists():
    assert os.path.isfile(repo_path("vault/agents.md"))


def test_vault_map_md_exists():
    assert os.path.isfile(repo_path("vault/map.md"))


def test_vault_decisions_md_exists():
    assert os.path.isfile(repo_path("vault/decisions.md"))


def test_vault_journal_index_md_exists():
    assert os.path.isfile(repo_path("vault/journal/index.md"))


def test_vault_ideas_index_md_exists():
    assert os.path.isfile(repo_path("vault/ideas/index.md"))


def test_vault_learning_global_md_exists():
    assert os.path.isfile(repo_path("vault/learning/global.md"))


# AC: empty directories tracked via .gitkeep
def test_vault_packs_gitkeep_exists():
    assert os.path.isfile(repo_path("vault/packs/.gitkeep"))


def test_vault_projects_gitkeep_exists():
    assert os.path.isfile(repo_path("vault/projects/.gitkeep"))


def test_claude_skills_lookout_scripts_gitkeep_exists():
    assert os.path.isfile(repo_path(".claude/skills/lookout/scripts/.gitkeep"))


# AC: targets.yaml exists and is valid YAML
def test_targets_yaml_exists():
    assert os.path.isfile(repo_path("targets.yaml"))


def test_targets_yaml_valid_yaml():
    with open(repo_path("targets.yaml")) as f:
        data = yaml.safe_load(f)
    assert data is not None


# AC: targets.yaml perf-coach entry
def test_targets_yaml_perf_coach_local():
    with open(repo_path("targets.yaml")) as f:
        data = yaml.safe_load(f)
    assert data["targets"]["perf-coach"]["local"] == "~/dev/perf-coach/uat"


def test_targets_yaml_perf_coach_github():
    with open(repo_path("targets.yaml")) as f:
        data = yaml.safe_load(f)
    assert data["targets"]["perf-coach"]["github"] == "zealchaiwut/perf-coach"


def test_targets_yaml_perf_coach_commander_slug():
    with open(repo_path("targets.yaml")) as f:
        data = yaml.safe_load(f)
    assert data["targets"]["perf-coach"]["commander_slug"] == "perf-coach"


# AC: targets.yaml commander entry
def test_targets_yaml_commander_local():
    with open(repo_path("targets.yaml")) as f:
        data = yaml.safe_load(f)
    assert data["targets"]["commander"]["local"] == "~/dev/commander/uat"


def test_targets_yaml_commander_github():
    with open(repo_path("targets.yaml")) as f:
        data = yaml.safe_load(f)
    assert data["targets"]["commander"]["github"] == "zealchaiwut/commander"


def test_targets_yaml_commander_commander_slug():
    with open(repo_path("targets.yaml")) as f:
        data = yaml.safe_load(f)
    assert data["targets"]["commander"]["commander_slug"] == "commander"


# AC: targets.yaml sources block
def test_targets_yaml_sources_commander_api():
    with open(repo_path("targets.yaml")) as f:
        data = yaml.safe_load(f)
    assert data["sources"]["commander_api"] == "http://localhost:8000"


def test_targets_yaml_sources_notion_todos_db_key_exists():
    with open(repo_path("targets.yaml")) as f:
        data = yaml.safe_load(f)
    assert "notion_todos_db" in data["sources"]


def test_targets_yaml_sources_journal_entries():
    with open(repo_path("targets.yaml")) as f:
        data = yaml.safe_load(f)
    assert data["sources"]["journal_entries"] == "~/dev/journal/entries"


# AC: .env.example exists with required keys
def test_env_example_exists():
    assert os.path.isfile(repo_path(".env.example"))


def test_env_example_contains_notion_token():
    with open(repo_path(".env.example")) as f:
        content = f.read()
    assert "NOTION_TOKEN" in content


def test_env_example_contains_commander_api():
    with open(repo_path(".env.example")) as f:
        content = f.read()
    assert "COMMANDER_API" in content


# AC: subprocess parse check exits 0 with no output
def test_targets_yaml_parseable_subprocess():
    result = subprocess.run(
        ["python3", "-c", "import yaml; yaml.safe_load(open('targets.yaml'))"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0
    assert result.stdout == ""

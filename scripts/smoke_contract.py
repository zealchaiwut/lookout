"""smoke_contract.py — Validate the live vault against the Hermes reader contract.

Checks:
  1. Per-project situation.md frontmatter (target, run, sources_ok all required)
  2. Per-project capability.md required sections
  3. Ideas ledger frontmatter (slug, created, status, targets, issues, assessed all required)

Exit codes:
  0 — all checks pass
  1 — one or more VIOLATION lines printed
"""
import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

_FM_RE = re.compile(r"^---\n(.*?)---\n", re.DOTALL)

SITUATION_REQUIRED = ("target", "run", "sources_ok")
IDEA_REQUIRED = ("slug", "created", "status", "targets", "issues", "assessed")
CAPABILITY_REQUIRED_SECTIONS = (
    "## What it is",
    "## Data it owns",
    "## Read surfaces",
    "## How to make it do things",
    "## Constraints",
)


def _parse_frontmatter_keys(text):
    m = _FM_RE.match(text)
    if not m:
        return None
    fm_body = m.group(1)
    keys = set()
    for line in fm_body.splitlines():
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("-"):
            key = stripped.split(":")[0].strip()
            if key:
                keys.add(key)
    return keys


def _check_situation_files(vault_dir, violations):
    projects_dir = vault_dir / "projects"
    if not projects_dir.exists():
        return
    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        sit_path = proj_dir / "situation.md"
        if not sit_path.exists():
            continue
        text = sit_path.read_text(encoding="utf-8", errors="replace")
        keys = _parse_frontmatter_keys(text)
        if keys is None:
            rel = sit_path.relative_to(vault_dir.parent)
            violations.append(
                f"VIOLATION: missing YAML frontmatter in {rel}"
            )
            continue
        for field in SITUATION_REQUIRED:
            if field not in keys:
                rel = sit_path.relative_to(vault_dir.parent)
                violations.append(
                    f"VIOLATION: missing required frontmatter field '{field}' in {rel}"
                )


def _check_capability_files(vault_dir, violations):
    projects_dir = vault_dir / "projects"
    if not projects_dir.exists():
        return
    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        cap_path = proj_dir / "capability.md"
        if not cap_path.exists():
            continue
        text = cap_path.read_text(encoding="utf-8", errors="replace")
        for section in CAPABILITY_REQUIRED_SECTIONS:
            if section not in text:
                rel = cap_path.relative_to(vault_dir.parent)
                violations.append(
                    f"VIOLATION: missing required section '{section}' in {rel}"
                )


def _check_idea_files(vault_dir, violations):
    ideas_dir = vault_dir / "ideas"
    if not ideas_dir.exists():
        return
    for idea_path in sorted(ideas_dir.glob("*.md")):
        if idea_path.name == "index.md":
            continue
        text = idea_path.read_text(encoding="utf-8", errors="replace")
        keys = _parse_frontmatter_keys(text)
        if keys is None:
            rel = idea_path.relative_to(vault_dir.parent)
            violations.append(
                f"VIOLATION: missing YAML frontmatter in {rel}"
            )
            continue
        for field in IDEA_REQUIRED:
            if field not in keys:
                rel = idea_path.relative_to(vault_dir.parent)
                violations.append(
                    f"VIOLATION: missing required frontmatter field '{field}' in {rel}"
                )


def smoke(vault_dir=None):
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    vault_dir = Path(vault_dir)
    violations = []
    _check_situation_files(vault_dir, violations)
    _check_capability_files(vault_dir, violations)
    _check_idea_files(vault_dir, violations)
    return violations


def main():
    parser = argparse.ArgumentParser(
        description="Validate vault against the Hermes reader contract."
    )
    parser.add_argument(
        "--vault",
        default=str(REPO_ROOT / "vault"),
        help="Path to the vault directory (default: ./vault)",
    )
    args = parser.parse_args()

    violations = smoke(args.vault)
    if violations:
        for v in violations:
            print(v)
        sys.exit(1)
    print("smoke_contract: all checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()

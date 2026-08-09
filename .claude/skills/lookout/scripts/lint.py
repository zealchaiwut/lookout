#!/usr/bin/env python3
"""Vault integrity linter: wikilink and index/folder checks."""
import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# Traverse: scripts/ -> lookout/ -> skills/ -> .claude/ -> repo_root
_DEFAULT_VAULT = SCRIPT_DIR.parents[3] / "vault"

WIKILINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]')


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def check_wikilinks(vault_path: Path) -> list[str]:
    """Scan every .md file under vault_path for [[...]] links and verify each resolves."""
    all_md = {f for f in vault_path.rglob("*.md")}
    # Build a name-to-path index for O(1) lookups (files and directories)
    name_index: dict[str, Path] = {}
    for f in all_md:
        name_index[f.stem] = f
        # Also index by relative path stem for path-style links
        rel = f.relative_to(vault_path)
        name_index[str(rel.with_suffix(""))] = f
    for d in vault_path.rglob("*"):
        if d.is_dir():
            name_index[d.name] = d
            name_index[str(d.relative_to(vault_path))] = d

    failures: list[str] = []
    for md_file in sorted(all_md):
        text = md_file.read_text(encoding="utf-8")
        for m in WIKILINK_RE.finditer(text):
            target = m.group(1).strip()
            if not _resolve_wikilink(target, vault_path, name_index):
                rel = md_file.relative_to(vault_path)
                failures.append(f"  {rel}: unresolved wikilink [[{target}]]")
    return failures


def _resolve_wikilink(target: str, vault_path: Path, name_index: dict) -> bool:
    if target in name_index:
        return True
    # Direct path relative to vault root
    if (vault_path / (target + ".md")).exists():
        return True
    if (vault_path / target).is_dir():
        return True
    return False


def check_index_folders(vault_path: Path) -> list[str]:
    """Verify index.md rows match vault/projects/ directories bidirectionally."""
    index_path = vault_path / "index.md"
    index_projects = _parse_project_names(index_path)
    dir_projects = _get_project_dirs(vault_path)

    failures: list[str] = []
    for name in sorted(index_projects - dir_projects):
        failures.append(
            f"  index.md references '{name}' but vault/projects/{name}/ does not exist"
        )
    for name in sorted(dir_projects - index_projects):
        failures.append(
            f"  vault/projects/{name}/ exists but is not referenced in index.md"
        )
    return failures


def _parse_project_names(index_path: Path) -> set[str]:
    if not index_path.exists():
        return set()
    names: set[str] = set()
    for line in index_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        wikilinks = WIKILINK_RE.findall(stripped)
        if wikilinks:
            for target in wikilinks:
                # Strip a leading 'projects/' prefix if present
                name = re.sub(r"^projects/", "", target.strip())
                if name:
                    names.add(name)
        else:
            # Skip GFM table rows (header, separator, data)
            if stripped.startswith("|"):
                continue
            # Plain bullet or bare text
            name = re.sub(r"^[-*+]\s+", "", stripped).strip()
            if name:
                names.add(name)
    return names


def _get_project_dirs(vault_path: Path) -> set[str]:
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return set()
    return {d.name for d in projects_dir.iterdir() if d.is_dir()}


# ---------------------------------------------------------------------------
# Check registry — add new checks here without touching the runner
# ---------------------------------------------------------------------------

CHECKS: list[tuple[str, object]] = [
    ("Wikilink check", check_wikilinks),
    ("Index/folder check", check_index_folders),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_checks(vault_path: Path) -> bool:
    all_passed = True
    for name, check_fn in CHECKS:
        failures = check_fn(vault_path)
        if failures:
            all_passed = False
            print(f"[FAIL] {name}:")
            for line in failures:
                print(line)
        else:
            print(f"[PASS] {name}")
    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Lookout vault integrity linter")
    parser.add_argument(
        "--vault",
        type=Path,
        default=_DEFAULT_VAULT,
        help="Path to the vault directory (default: auto-detected from script location)",
    )
    args = parser.parse_args()

    vault_path = args.vault.resolve()
    if not vault_path.is_dir():
        print(f"ERROR: vault directory not found: {vault_path}", file=sys.stderr)
        return 1

    passed = run_all_checks(vault_path)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

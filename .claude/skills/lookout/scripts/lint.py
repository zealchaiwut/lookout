#!/usr/bin/env python3
"""Vault integrity linter: wikilink, index/folder, staleness, and question checks."""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
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


_STALENESS_DAYS = 7
_QUESTION_ID_RE = re.compile(r'\b([A-Z]{2}Q\d+)\b')
_STALE_QUESTION_DAYS = 14


def check_staleness(vault_path: Path) -> list[str]:
    """Return warning strings for project snapshots older than _STALENESS_DAYS days."""
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=_STALENESS_DAYS)
    warnings = []

    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        raw_dir = project_dir / "raw"
        if not raw_dir.exists():
            continue
        snapshots = [d for d in raw_dir.iterdir() if d.is_dir()]
        if not snapshots:
            continue
        newest = max(snapshots, key=lambda d: d.name)
        try:
            ts = datetime.strptime(newest.name, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        if ts < cutoff:
            age_days = (datetime.now(timezone.utc) - ts).days
            warnings.append(
                f"  {project_dir.name}: newest snapshot is {age_days} days old"
                f" (threshold: {_STALENESS_DAYS} days)"
            )

    return warnings


def check_decision_question_refs(vault_path: Path) -> list[str]:
    """Warn when a decision entry references a question ID not in any project registry.

    Scans vault/decisions.md and vault/projects/*/decisions.md for <PREFIX>Q<n>
    patterns, then verifies each ID exists in the corresponding questions.json.
    Exit code remains 0 (WARN is non-fatal).
    """
    projects_dir = vault_path / "projects"

    # Build the complete set of known question IDs across all registries
    known_ids: set = set()
    if projects_dir.exists():
        for proj_dir in projects_dir.iterdir():
            if not proj_dir.is_dir():
                continue
            qfile = proj_dir / "questions.json"
            if not qfile.exists():
                continue
            try:
                data = json.loads(qfile.read_text(encoding='utf-8'))
                known_ids.update(data.get("questions", {}).keys())
            except Exception:
                pass

    # Scan decisions files
    decisions_paths = [vault_path / "decisions.md"]
    if projects_dir.exists():
        for proj_dir in projects_dir.iterdir():
            if proj_dir.is_dir():
                decisions_paths.append(proj_dir / "decisions.md")

    warnings: list[str] = []
    seen: set = set()
    for dpath in decisions_paths:
        if not dpath.exists():
            continue
        try:
            text = dpath.read_text(encoding='utf-8')
        except Exception:
            continue
        for m in _QUESTION_ID_RE.finditer(text):
            qid = m.group(1)
            key = (str(dpath), qid)
            if key in seen:
                continue
            seen.add(key)
            if qid not in known_ids:
                try:
                    rel = dpath.relative_to(vault_path)
                except ValueError:
                    rel = dpath
                warnings.append(
                    f"  {rel}: references unknown question ID {qid}"
                )

    return warnings


def check_stale_questions(vault_path: Path) -> list[str]:
    """Emit info notices for open questions whose creation date is more than 14 days ago."""
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return []

    cutoff_date = (
        datetime.now(timezone.utc) - timedelta(days=_STALE_QUESTION_DAYS)
    ).strftime("%Y-%m-%d")

    notices: list[str] = []
    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        qfile = proj_dir / "questions.json"
        if not qfile.exists():
            continue
        try:
            data = json.loads(qfile.read_text(encoding='utf-8'))
        except Exception:
            continue
        for qid, q in data.get("questions", {}).items():
            if q.get("status") != "open":
                continue
            created = q.get("created", "")
            if created and created < cutoff_date:
                notices.append(
                    f"  {proj_dir.name}/{qid}: open question created {created}"
                    f" is overdue for resolution (>{_STALE_QUESTION_DAYS} days)"
                )

    return notices


# ---------------------------------------------------------------------------
# Atlas path check (issue #17)
# ---------------------------------------------------------------------------

_ATLAS_FILES_BLOCK_RE = re.compile(r"^files:\s*\n((?:[ \t]+-\s*.+\n?)*)", re.MULTILINE)
_ATLAS_FILES_INLINE_RE = re.compile(r"^files:\s*(.+)$", re.MULTILINE)
_ATLAS_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _parse_atlas_note_files(text: str) -> list[str]:
    """Return the files list from an atlas note's YAML frontmatter."""
    fm_m = _ATLAS_FM_RE.match(text)
    if not fm_m:
        return []
    fm = fm_m.group(1)

    block = _ATLAS_FILES_BLOCK_RE.search(fm)
    if block:
        items = re.findall(r"^[ \t]+-\s*(.+)$", block.group(1), re.MULTILINE)
        return [x.strip() for x in items if x.strip()]

    inline = _ATLAS_FILES_INLINE_RE.search(fm)
    if inline:
        val = inline.group(1).strip()
        if val in ("[]", "null", "pending", ""):
            return []
        m2 = re.match(r"\[([^\]]+)\]", val)
        if m2:
            return [x.strip() for x in m2.group(1).split(",") if x.strip()]
    return []


def _load_targets_yaml(targets_yaml: Path) -> dict:
    """Load targets.yaml and return the targets mapping."""
    if not targets_yaml.exists():
        return {}
    try:
        import yaml  # noqa: PLC0415
        with open(targets_yaml, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("targets", {})
    except Exception:
        return {}


def check_atlas_paths(vault_path: Path, targets_yaml: Path | None = None) -> list[str]:
    """Warn for atlas notes whose files list contains paths absent from the target repo.

    Uses targets_yaml (default: vault_path.parent/targets.yaml) to look up the
    local path for each project. Non-fatal: returns warning strings only.
    """
    if targets_yaml is None:
        targets_yaml = vault_path.parent / "targets.yaml"

    targets = _load_targets_yaml(targets_yaml)
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return []

    warnings: list[str] = []
    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        target_name = proj_dir.name
        target_cfg = targets.get(target_name, {})
        local_str = target_cfg.get("local", "")
        if not local_str:
            continue
        local_path = Path(local_str).expanduser()
        if not local_path.exists():
            continue

        atlas_dir = proj_dir / "atlas"
        if not atlas_dir.exists():
            continue

        for note_path in sorted(atlas_dir.glob("*.md")):
            if note_path.name == "index.md":
                continue
            try:
                text = note_path.read_text(encoding="utf-8")
            except Exception:
                continue
            for fpath in _parse_atlas_note_files(text):
                if not (local_path / fpath).exists():
                    try:
                        rel = note_path.relative_to(vault_path)
                    except ValueError:
                        rel = note_path
                    warnings.append(
                        f"  {rel}: files list contains path absent from repo: {fpath}"
                    )

    return warnings


# ---------------------------------------------------------------------------
# Check registry — add new checks here without touching the runner
# ---------------------------------------------------------------------------

CHECKS: list[tuple[str, object]] = [
    ("Wikilink check", check_wikilinks),
    ("Index/folder check", check_index_folders),
]

WARNINGS: list[tuple[str, object]] = [
    ("Staleness check", check_staleness),
    ("Decision question refs", check_decision_question_refs),
    ("Atlas path check", check_atlas_paths),
]

NOTICES: list[tuple[str, object]] = [
    ("Stale open questions", check_stale_questions),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_checks(vault_path: Path, targets_yaml: Path | None = None) -> bool:
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

    for name, warn_fn in WARNINGS:
        if name == "Atlas path check":
            warnings = warn_fn(vault_path, targets_yaml)
        else:
            warnings = warn_fn(vault_path)
        if warnings:
            print(f"[WARN] {name}:")
            for line in warnings:
                print(line)

    for name, notice_fn in NOTICES:
        notices = notice_fn(vault_path)
        if notices:
            print(f"[INFO] {name}:")
            for line in notices:
                print(line)

    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Lookout vault integrity linter")
    parser.add_argument(
        "--vault",
        type=Path,
        default=_DEFAULT_VAULT,
        help="Path to the vault directory (default: auto-detected from script location)",
    )
    parser.add_argument(
        "--targets-yaml",
        type=Path,
        default=None,
        help="Path to targets.yaml (default: vault parent directory)",
    )
    args = parser.parse_args()

    vault_path = args.vault.resolve()
    if not vault_path.is_dir():
        print(f"ERROR: vault directory not found: {vault_path}", file=sys.stderr)
        return 1

    passed = run_all_checks(vault_path, targets_yaml=args.targets_yaml)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

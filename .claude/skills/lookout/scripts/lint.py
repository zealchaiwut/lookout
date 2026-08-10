#!/usr/bin/env python3
"""Vault integrity linter — six check families: wikilinks, index sync,
ownership warnings, snapshot age, card token budget, question ID rules."""
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
_MD_LINK_RE = re.compile(r'^\[([^\]]+)\]\([^)]*\)')  # [text](url) — not a wikilink
_TOKEN_LIMIT = 1500


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def check_wikilinks(vault_path: Path) -> tuple[list[str], int]:
    """Scan every .md file for [[...]] links and verify each resolves."""
    all_md = {f for f in vault_path.rglob("*.md")}
    files_scanned = len(all_md)
    name_index: dict[str, Path] = {}
    for f in all_md:
        name_index[f.stem] = f
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
    return failures, files_scanned


def _resolve_wikilink(target: str, vault_path: Path, name_index: dict) -> bool:
    if target in name_index:
        return True
    if (vault_path / (target + ".md")).exists():
        return True
    if (vault_path / target).is_dir():
        return True
    return False


def check_index_folders(vault_path: Path) -> tuple[list[str], int]:
    """Verify index.md rows match vault/projects/ directories bidirectionally."""
    index_path = vault_path / "index.md"
    index_projects = _parse_project_names(index_path)
    dir_projects = _get_project_dirs(vault_path)
    files_scanned = 1 + len(dir_projects)

    failures: list[str] = []
    for name in sorted(index_projects - dir_projects):
        failures.append(
            f"  index.md references '{name}' but vault/projects/{name}/ does not exist"
        )
    for name in sorted(dir_projects - index_projects):
        failures.append(
            f"  vault/projects/{name}/ exists but is not referenced in index.md"
        )
    return failures, files_scanned


def _parse_project_names(index_path: Path) -> set[str]:
    if not index_path.exists():
        return set()
    names: set[str] = set()
    for line in index_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        wikilinks = WIKILINK_RE.findall(stripped)
        if wikilinks:
            for target in wikilinks:
                name = re.sub(r"^projects/", "", target.strip())
                if name:
                    names.add(name)
        else:
            # Strip bullet marker then check for Markdown link [text](url)
            bare = re.sub(r"^[-*+]\s+", "", stripped).strip()
            if not bare or _MD_LINK_RE.match(bare):
                continue
            names.add(bare)
    return names


def _get_project_dirs(vault_path: Path) -> set[str]:
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return set()
    return {d.name for d in projects_dir.iterdir() if d.is_dir()}


def check_ownership_warnings(
    vault_path: Path, targets_yaml: Path | None = None
) -> tuple[list[str], int]:
    """Warn for projects in vault/projects/ that have no entry in targets.yaml.

    A project with no targets.yaml entry has no registered owner or steward.
    Non-fatal: returns warning strings only.
    """
    if targets_yaml is None:
        targets_yaml = vault_path.parent / "targets.yaml"

    registered = _load_target_names(targets_yaml)
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return [], 0

    project_dirs = [d for d in projects_dir.iterdir() if d.is_dir()]
    files_scanned = len(project_dirs)
    warnings: list[str] = []
    for proj_dir in sorted(project_dirs):
        if proj_dir.name not in registered:
            warnings.append(
                f"  {proj_dir.name}: project has no registered owner"
                " (not found in targets.yaml)"
            )
    return warnings, files_scanned


def _load_target_names(targets_yaml: Path) -> set[str]:
    if not targets_yaml or not targets_yaml.exists():
        return set()
    try:
        import yaml  # noqa: PLC0415
        with open(targets_yaml, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return set((data.get("targets") or {}).keys())
    except Exception:
        return set()


_STALENESS_DAYS = 7


def check_staleness(vault_path: Path) -> tuple[list[str], int]:
    """Warn for project snapshots older than _STALENESS_DAYS days."""
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return [], 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=_STALENESS_DAYS)
    project_dirs = [d for d in projects_dir.iterdir() if d.is_dir()]
    files_scanned = len(project_dirs)
    warnings: list[str] = []

    for project_dir in sorted(project_dirs):
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

    return warnings, files_scanned


def _count_tokens(text: str) -> int:
    return len(text.split())


def check_card_token_budget(vault_path: Path) -> tuple[list[str], int]:
    """Warn for capability.md files in vault/projects/*/ that exceed 1500 tokens.

    Token count uses the project-standard whitespace tokenizer.
    Non-fatal: returns warning strings only.
    """
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return [], 0

    cap_files = list(projects_dir.glob("*/capability.md"))
    files_scanned = len(cap_files)
    warnings: list[str] = []
    for cap_path in sorted(cap_files):
        try:
            text = cap_path.read_text(encoding="utf-8")
        except Exception:
            continue
        token_count = _count_tokens(text)
        if token_count > _TOKEN_LIMIT:
            try:
                rel = cap_path.relative_to(vault_path)
            except ValueError:
                rel = cap_path
            warnings.append(
                f"  {rel}: {token_count} tokens exceeds {_TOKEN_LIMIT}-token budget"
            )
    return warnings, files_scanned


_QUESTION_ID_RE = re.compile(r'\b([A-Z]{2,}Q\d+)\b')
_STALE_QUESTION_DAYS = 14


def check_decision_question_refs(vault_path: Path) -> tuple[list[str], int]:
    """Warn when a decision entry references a question ID not in any project registry."""
    projects_dir = vault_path / "projects"

    known_ids: set = set()
    decisions_paths = [vault_path / "decisions.md"]
    if projects_dir.exists():
        for proj_dir in projects_dir.iterdir():
            if not proj_dir.is_dir():
                continue
            qfile = proj_dir / "questions.json"
            if qfile.exists():
                try:
                    data = json.loads(qfile.read_text(encoding='utf-8'))
                    known_ids.update(data.get("questions", {}).keys())
                except Exception:
                    pass
            decisions_paths.append(proj_dir / "decisions.md")

    files_scanned = sum(1 for p in decisions_paths if p.exists())
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
                warnings.append(f"  {rel}: references unknown question ID {qid}")

    return warnings, files_scanned


def check_stale_questions(vault_path: Path) -> tuple[list[str], int]:
    """Emit info notices for open questions more than 14 days old."""
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return [], 0

    cutoff_date = (
        datetime.now(timezone.utc) - timedelta(days=_STALE_QUESTION_DAYS)
    ).strftime("%Y-%m-%d")

    qfiles = list(projects_dir.glob("*/questions.json"))
    files_scanned = len(qfiles)
    notices: list[str] = []
    for qfile in sorted(qfiles):
        proj_dir = qfile.parent
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

    return notices, files_scanned


# ---------------------------------------------------------------------------
# Atlas path check (issue #17)
# ---------------------------------------------------------------------------

_ATLAS_FILES_BLOCK_RE = re.compile(r"^files:\s*\n((?:[ \t]+-\s*.+\n?)*)", re.MULTILINE)
_ATLAS_FILES_INLINE_RE = re.compile(r"^files:\s*(.+)$", re.MULTILINE)
_ATLAS_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _parse_atlas_note_files(text: str) -> list[str]:
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


def check_atlas_paths(
    vault_path: Path, targets_yaml: Path | None = None
) -> tuple[list[str], int]:
    """Warn for atlas notes whose files list contains paths absent from the target repo."""
    if targets_yaml is None:
        targets_yaml = vault_path.parent / "targets.yaml"

    targets = _load_targets_yaml(targets_yaml)
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return [], 0

    atlas_notes = list(projects_dir.glob("*/atlas/*.md"))
    files_scanned = len(atlas_notes)
    warnings: list[str] = []
    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        target_cfg = targets.get(proj_dir.name, {})
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
    return warnings, files_scanned


def _load_targets_yaml(targets_yaml: Path) -> dict:
    if not targets_yaml or not targets_yaml.exists():
        return {}
    try:
        import yaml  # noqa: PLC0415
        with open(targets_yaml, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("targets") or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Check registry
# Six canonical families + atlas path (bonus warning)
# ---------------------------------------------------------------------------

CHECKS: list[tuple[str, object]] = [
    ("Wikilink check", check_wikilinks),
    ("Index/folder check", check_index_folders),
]

WARNINGS: list[tuple[str, object]] = [
    ("Ownership warnings", check_ownership_warnings),
    ("Staleness check", check_staleness),
    ("Card token budget", check_card_token_budget),
    ("Decision question refs", check_decision_question_refs),
    ("Atlas path check", check_atlas_paths),
]

NOTICES: list[tuple[str, object]] = [
    ("Stale open questions", check_stale_questions),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _print_summary_table(rows: list[tuple[str, int, int, int]]) -> None:
    name_w = max(len(r[0]) for r in rows) + 2
    print()
    print("=== Lint Summary ===")
    header = f"{'Check':<{name_w}}  {'Files':>6}  {'Warnings':>8}  {'Errors':>6}"
    print(header)
    print("-" * len(header))
    for name, files, warns, errors in rows:
        print(f"{name:<{name_w}}  {files:>6}  {warns:>8}  {errors:>6}")
    total_files = sum(r[1] for r in rows)
    total_warns = sum(r[2] for r in rows)
    total_errors = sum(r[3] for r in rows)
    print("-" * len(header))
    print(f"{'Total':<{name_w}}  {total_files:>6}  {total_warns:>8}  {total_errors:>6}")


def run_all_checks(vault_path: Path, targets_yaml: Path | None = None) -> bool:
    all_passed = True
    summary_rows: list[tuple[str, int, int, int]] = []

    for name, check_fn in CHECKS:
        result, files = check_fn(vault_path)
        if result:
            all_passed = False
            print(f"[FAIL] {name}:")
            for line in result:
                print(line)
            summary_rows.append((name, files, 0, len(result)))
        else:
            print(f"[PASS] {name}")
            summary_rows.append((name, files, 0, 0))

    for name, warn_fn in WARNINGS:
        if name in ("Ownership warnings", "Atlas path check"):
            result, files = warn_fn(vault_path, targets_yaml)
        else:
            result, files = warn_fn(vault_path)
        if result:
            print(f"[WARN] {name}:")
            for line in result:
                print(line)
        else:
            print(f"[PASS] {name}")
        summary_rows.append((name, files, len(result), 0))

    for name, notice_fn in NOTICES:
        result, files = notice_fn(vault_path)
        if result:
            print(f"[INFO] {name}:")
            for line in result:
                print(line)
        summary_rows.append((name, files, len(result), 0))

    _print_summary_table(summary_rows)

    total_errors = sum(r[3] for r in summary_rows)
    result_label = "PASS" if all_passed else "FAIL"
    exit_code = 0 if all_passed else 1
    print(f"\nResult: {result_label} (exit {exit_code})")

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

"""
derive.py — run the derive stages that turn a raw snapshot into vault notes.

`gather` writes evidence; the derive stages read that evidence and write the
notes a human or agent actually reads. Until this module existed the derive
stages were reachable only as individual CLI commands, so `bin/lookout <target>`
and the nightly `lookout --all` sweep produced snapshots and nothing else.

Two groups, run in this order:

  Per target (derive_target)
    1. capability_card  — capability.md
    2. drift            — drift.md
    3. synthesize       — situation.md
    4. todo_view        — todo-view.md
    5. project_flow     — flow.md           (workflow.md + atlas sitemap)
    6. project_changelog — changelog.md     (merged PRs + git log)
    7. project_discovery — discovery.md     (start-here: flow + API + modules)

  Vault-wide (derive_vault), once after every target
    8. capability_map
    9. ideas_ledger
   10. assessment_pass
   11. ship_pass

Ordering is load-bearing: capability.md must exist before synthesize reads its
description, and drift.md must exist before situation.md cites it.

Every stage is isolated. A stage that raises is recorded as `error` and the rest
still run — the same tolerance gather.py applies to unreachable sources, so one
broken target never costs a whole nightly sweep.

Stage 4 of the original design, `journal_crosslink`, is deliberately absent: it
requires a journal_delta.json that no stage in this pipeline produces. See
docs/pipeline.md.

Usage:
    python derive.py <target> [--vault <dir>] [--skip-vault-wide]
    python derive.py --vault-only
"""
import sys
import traceback
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

# Result status values
OK = "ok"
SKIPPED = "skipped"
ERROR = "error"


def _target_local_path(target: str, targets_yaml: Path = TARGETS_YAML) -> Path | None:
    try:
        with open(targets_yaml) as fh:
            data = yaml.safe_load(fh) or {}
        local = (data.get("targets", {}).get(target) or {}).get("local")
        return Path(local).expanduser() if local else None
    except Exception:
        return None


def _run_stage(name: str, fn) -> dict:
    """Run one derive stage, converting any failure into a result record."""
    try:
        detail = fn()
        return {"stage": name, "status": OK, "detail": detail or ""}
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return {"stage": name, "status": ERROR, "detail": f"{type(exc).__name__}: {exc}"}


def derive_target(target: str, vault_dir: Path | None = None) -> list[dict]:
    """Run every per-target derive stage. Returns one result dict per stage."""
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"

    project_dir = vault_dir / "projects" / target
    raw_dir = project_dir / "raw"
    if not raw_dir.is_dir() or not any(raw_dir.iterdir()):
        return [{
            "stage": "derive",
            "status": SKIPPED,
            "detail": "no snapshot — run gather first",
        }]

    import capability_card
    import drift as drift_module
    import project_changelog
    import project_discovery
    import project_flow
    import synthesize as synthesize_module
    import todo_view

    results = []

    results.append(_run_stage(
        "capability_card",
        lambda: str(capability_card.generate_capability_card(target, vault_dir).name),
    ))

    results.append(_run_stage(
        "drift",
        lambda: str(drift_module._run_cli(target, vault_dir).name),
    ))

    results.append(_run_stage(
        "synthesize",
        lambda: str(synthesize_module.synthesize(target, vault_dir).name),
    ))

    local = _target_local_path(target)
    docs_todo = (local / "docs" / "todo.md") if local else None
    results.append(_run_stage(
        "todo_view",
        lambda: str(todo_view._run_cli(target, vault_dir, docs_todo).name),
    ))

    results.append(_run_stage(
        "project_flow",
        lambda: str(project_flow.generate_flow(target, vault_dir).name),
    ))

    results.append(_run_stage(
        "project_changelog",
        lambda: str(project_changelog.generate_changelog(target, vault_dir).name),
    ))

    results.append(_run_stage(
        "project_discovery",
        lambda: str(project_discovery.generate_discovery(target, vault_dir).name),
    ))

    return results


def derive_vault(vault_dir: Path | None = None) -> list[dict]:
    """Run every vault-wide derive stage. Returns one result dict per stage."""
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"

    import assessment_pass
    import capability_map
    import ideas_ledger
    import ship_pass

    ideas_dir = vault_dir / "ideas"
    results = []

    results.append(_run_stage(
        "capability_map",
        lambda: str(capability_map.generate_map(vault_dir).name),
    ))

    if not ideas_dir.is_dir():
        results.append({"stage": "ideas", "status": SKIPPED, "detail": "no vault/ideas/"})
        return results

    results.append(_run_stage(
        "ideas_ledger",
        lambda: str(ideas_ledger.regenerate_ledger(ideas_dir).name),
    ))
    results.append(_run_stage(
        "assessment_pass",
        lambda: f"{len(assessment_pass.run_assessment_pass(ideas_dir, vault_dir))} assessed",
    ))
    results.append(_run_stage(
        "ship_pass",
        lambda: f"{len(ship_pass.run_ship_pass(ideas_dir, vault_dir))} shipped",
    ))

    return results


def print_summary(title: str, results: list[dict]) -> None:
    name_w = 18
    status_w = 8
    print()
    print(f"--- {title} ---")
    print(f"{'stage':<{name_w}}  {'status':<{status_w}}  detail")
    print("-" * (name_w + status_w + 28))
    for r in results:
        print(f"{r['stage']:<{name_w}}  {r['status']:<{status_w}}  {r['detail']}")
    print()


def any_error(results: list[dict]) -> bool:
    return any(r["status"] == ERROR for r in results)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="derive.py")
    parser.add_argument("target", nargs="?", help="target name (omit with --vault-only)")
    parser.add_argument("--vault", default=None, help="vault directory")
    parser.add_argument("--vault-only", action="store_true",
                        help="run only the vault-wide stages")
    parser.add_argument("--skip-vault-wide", action="store_true",
                        help="run only the per-target stages")
    args = parser.parse_args()

    vault_dir = Path(args.vault) if args.vault else None
    failed = False

    if not args.vault_only:
        if not args.target:
            parser.error("a target is required unless --vault-only is given")
        results = derive_target(args.target, vault_dir)
        print_summary(f"Derive: {args.target}", results)
        failed = failed or any_error(results)

    if not args.skip_vault_wide:
        results = derive_vault(vault_dir)
        print_summary("Derive: vault-wide", results)
        failed = failed or any_error(results)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

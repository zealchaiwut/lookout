"""promote_spec.py — copy an approved Spec pack from the vault into the target clone.

The only outbound write from Lookout into a tracked project. Requires
``status.yaml`` to be ``approved``. After a successful copy, flips status to
``promoted``.

Usage:
  python promote_spec.py <target> [--vault DIR] [--dry-run]
  bin/lookout promote-spec <target>
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

sys.path.insert(0, str(REPO_ROOT))
import spec_workspace as sw  # noqa: E402

# Portable files promote may copy (canonical names in the workspace).
PROMOTE_FILES = ("PRODUCT.md", "DESIGN.md", "SCHEMA.md", "api.yaml")


class PromoteSpecError(ValueError):
    """Promotion cannot proceed."""


def _load_local(target: str) -> Path:
    data = yaml.safe_load(TARGETS_YAML.read_text()) or {}
    entry = (data.get("targets") or {}).get(target)
    if not entry:
        raise PromoteSpecError(f"Unknown target {target!r}")
    local = entry.get("local")
    if not local:
        raise PromoteSpecError(f"Target {target!r} has no local: path")
    path = Path(local).expanduser()
    if not path.is_dir():
        raise PromoteSpecError(f"Target local path does not exist: {path}")
    return path


def promote_spec(
    target: str,
    vault_dir: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict:
    """Copy approved Spec files into the target clone. Returns a summary dict."""
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    directory = sw.spec_dir(target, vault_dir)
    if not directory.is_dir():
        raise PromoteSpecError(f"Spec workspace missing for {target}: {directory}")

    status = sw.read_status(directory)
    if status["status"] != "approved":
        raise PromoteSpecError(
            f"promote-spec requires status=approved (currently {status['status']!r}); "
            "run `lookout spec approve` first"
        )

    local = _load_local(target)
    copied: list[str] = []
    skipped: list[str] = []
    for name in PROMOTE_FILES:
        src = directory / name
        if not src.is_file():
            skipped.append(name)
            continue
        dest = local / name
        if dry_run:
            copied.append(name)
            continue
        shutil.copy2(src, dest)
        copied.append(name)

    if not copied:
        raise PromoteSpecError("No Spec pack files present in the workspace to promote")

    if not dry_run:
        sw.set_status(
            target, "promoted", vault_dir,
            note=f"promoted {', '.join(copied)} → {local}",
        )

    return {
        "target": target,
        "local": str(local),
        "copied": copied,
        "skipped": skipped,
        "dry_run": dry_run,
        "status": "promoted" if not dry_run else status["status"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lookout promote-spec")
    parser.add_argument("target")
    parser.add_argument("--vault", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without writing the clone or flipping status",
    )
    args = parser.parse_args(argv)
    vault = args.vault or (REPO_ROOT / "vault")
    # Allow tests to monkeypatch TARGETS_YAML via module attribute.
    try:
        result = promote_spec(args.target, vault, dry_run=args.dry_run)
    except PromoteSpecError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except sw.SpecWorkspaceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    verb = "Would promote" if result["dry_run"] else "Promoted"
    print(
        f"{verb}: {result['target']} → {result['local']}\n"
        f"  copied: {', '.join(result['copied']) or '(none)'}\n"
        f"  skipped: {', '.join(result['skipped']) or '(none)'}\n"
        f"  status: {result['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

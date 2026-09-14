"""spec_workspace.py — vault Spec pack workspace + status machine.

Owns ``vault/projects/<target>/spec/``: portable Spec files live here until
``lookout promote-spec`` copies them into the target clone. Nightly gather stays
read-only against targets; this module only writes under the vault.

Status machine: draft → in-review → approved → promoted
  (and limited reverse edges for rework / next cycle).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

VALID_STATUSES = ("draft", "in-review", "approved", "promoted")

# Forward and limited reverse edges (rework / next cycle).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"in-review"}),
    "in-review": frozenset({"draft", "approved"}),
    "approved": frozenset({"in-review", "promoted"}),
    "promoted": frozenset({"draft"}),
}

# Portable pack files mirrored into the workspace (first candidate wins).
_PACK_CANDIDATES: list[tuple[str, tuple[str, ...]]] = [
    ("PRODUCT.md", ("PRODUCT.md",)),
    ("DESIGN.md", ("DESIGN.md",)),
    ("SCHEMA.md", ("SCHEMA.md", "schema.yaml", "schema.yml")),
    ("api.yaml", ("api.yaml", "openapi.yaml", "openapi.yml")),
]


class SpecWorkspaceError(ValueError):
    """Invalid status transition or missing workspace."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_local(target: str) -> Path | None:
    try:
        data = yaml.safe_load(TARGETS_YAML.read_text()) or {}
        local = (data.get("targets", {}).get(target) or {}).get("local")
        return Path(local).expanduser() if local else None
    except Exception:
        return None


def spec_dir(target: str, vault_dir: Path) -> Path:
    return vault_dir / "projects" / target / "spec"


def default_status() -> dict:
    return {
        "status": "draft",
        "updated": _now_iso(),
        "history": [{"status": "draft", "at": _now_iso(), "note": "workspace created"}],
        "files": {},
        "notes": "",
    }


def read_status(directory: Path) -> dict:
    path = directory / "status.yaml"
    if not path.is_file():
        return default_status()
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        return default_status()
    status = data.get("status", "draft")
    if status not in VALID_STATUSES:
        status = "draft"
    out = {
        "status": status,
        "updated": data.get("updated") or _now_iso(),
        "history": list(data.get("history") or []),
        "files": dict(data.get("files") or {}),
        "notes": data.get("notes") or "",
    }
    if data.get("last_validated"):
        out["last_validated"] = data["last_validated"]
    return out


def write_status(directory: Path, data: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "status.yaml"
    payload = {
        "status": data["status"],
        "updated": data.get("updated") or _now_iso(),
        "history": data.get("history") or [],
        "files": data.get("files") or {},
        "notes": data.get("notes") or "",
    }
    if data.get("last_validated"):
        payload["last_validated"] = data["last_validated"]
    path.write_text(yaml.dump(payload, default_flow_style=False, sort_keys=False))
    return path


def can_transition(current: str, new: str) -> bool:
    if current == new:
        return True
    return new in ALLOWED_TRANSITIONS.get(current, frozenset())


def set_status(
    target: str,
    new_status: str,
    vault_dir: Path,
    *,
    note: str = "",
) -> dict:
    """Flip status with transition checks. Returns the written status dict."""
    if new_status not in VALID_STATUSES:
        raise SpecWorkspaceError(
            f"Invalid status {new_status!r}; expected one of {VALID_STATUSES}"
        )
    directory = spec_dir(target, vault_dir)
    if not directory.is_dir():
        raise SpecWorkspaceError(f"Spec workspace missing for {target}: {directory}")
    current = read_status(directory)
    cur = current["status"]
    if not can_transition(cur, new_status):
        allowed = sorted(ALLOWED_TRANSITIONS.get(cur, frozenset()))
        raise SpecWorkspaceError(
            f"Cannot transition {cur!r} → {new_status!r}; allowed: {allowed}"
        )
    if cur != new_status:
        history = list(current.get("history") or [])
        entry = {"status": new_status, "at": _now_iso()}
        if note:
            entry["note"] = note
        history.append(entry)
        current["history"] = history
        current["status"] = new_status
        current["updated"] = _now_iso()
        if note:
            current["notes"] = note
        write_status(directory, current)
    return current


def _inventory_files(directory: Path) -> dict:
    inv: dict[str, str] = {}
    for canonical, _cands in _PACK_CANDIDATES:
        path = directory / canonical
        inv[canonical] = "present" if path.is_file() else "absent"
    inv["mock/"] = "present" if (directory / "mock").is_dir() else "absent"
    return inv


def _sync_missing_from_local(directory: Path, local: Path | None) -> list[str]:
    """Copy pack files from the clone only when the vault copy is absent."""
    copied: list[str] = []
    if local is None or not local.is_dir():
        return copied
    for canonical, candidates in _PACK_CANDIDATES:
        dest = directory / canonical
        if dest.is_file():
            continue
        for rel in candidates:
            src = local / rel
            if src.is_file():
                dest.write_bytes(src.read_bytes())
                copied.append(canonical)
                break
    return copied


def _ensure_plan(directory: Path, target: str) -> None:
    path = directory / "plan.md"
    if path.is_file():
        return
    path.write_text(
        f"# Spec plan — {target}\n\n"
        "## Intent\n\n"
        "_What changes and why._\n\n"
        "## Acceptance\n\n"
        "- [ ] Spec pack files reviewed\n"
        "- [ ] Mock validate passes\n"
        "- [ ] Approved in status.yaml\n\n"
        "## Notes\n\n"
    )


def _ensure_readme(directory: Path, target: str) -> None:
    path = directory / "README.md"
    if path.is_file():
        return
    path.write_text(
        f"# {target} — Spec workspace (Lookout)\n\n"
        "Working Spec pack living in Lookout. Portable files here are meant to be\n"
        "promoted into the target clone when approved (`lookout promote-spec`).\n\n"
        "See `status.yaml` for draft → in-review → approved → promoted.\n"
    )


def ensure_workspace(target: str, vault_dir: Path | None = None) -> Path:
    """Create/refresh the Spec workspace. Idempotent. Returns the spec/ path."""
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    directory = spec_dir(target, vault_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "mock").mkdir(exist_ok=True)

    _ensure_readme(directory, target)

    local = _load_local(target)
    _sync_missing_from_local(directory, local)

    status = read_status(directory)
    # Preserve status/history; refresh file inventory.
    if not (directory / "status.yaml").is_file():
        status = default_status()
    status["files"] = _inventory_files(directory)
    status["updated"] = status.get("updated") or _now_iso()
    write_status(directory, status)
    return directory


def generate_workspace(target: str, vault_dir: Path | None = None) -> Path:
    """Derive-stage entry: ensure workspace and return status.yaml path."""
    directory = ensure_workspace(target, vault_dir)
    return directory / "status.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ensure Spec workspace + status.yaml")
    parser.add_argument("target")
    parser.add_argument("--vault", type=Path, default=None)
    parser.add_argument(
        "--set-status",
        choices=VALID_STATUSES,
        default=None,
        help="Optionally flip status (with transition checks)",
    )
    parser.add_argument("--note", default="", help="Note for status transition")
    args = parser.parse_args(argv)
    vault = args.vault or (REPO_ROOT / "vault")
    path = ensure_workspace(args.target, vault)
    print(f"Spec workspace: {path}")
    if args.set_status:
        try:
            data = set_status(args.target, args.set_status, vault, note=args.note)
        except SpecWorkspaceError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Status: {data['status']}")
    else:
        print(f"Status: {read_status(path)['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

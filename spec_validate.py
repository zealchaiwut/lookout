"""spec_validate.py — mock-validate Spec workspace + approve CLI helpers.

Validates ``vault/projects/<target>/spec/api.yaml`` as an OpenAPI subset and
optional ``mock/`` fixtures. Does not call live project APIs.

Approve flips ``in-review`` → ``approved`` only after validate passes.
Submit flips ``draft`` → ``in-review`` after validate passes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

import spec_workspace as sw  # noqa: E402

_HTTP_METHODS = frozenset({
    "get", "put", "post", "delete", "options", "head", "patch", "trace",
})


class SpecValidateError(ValueError):
    """Validation failed."""


def _load_api(directory: Path) -> dict:
    path = directory / "api.yaml"
    if not path.is_file():
        # openapi.yaml alias
        alt = directory / "openapi.yaml"
        if alt.is_file():
            path = alt
        else:
            raise SpecValidateError("Missing api.yaml (or openapi.yaml) in Spec workspace")
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise SpecValidateError(f"api.yaml is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise SpecValidateError("api.yaml root must be a mapping")
    return data


def validate_openapi(data: dict) -> list[str]:
    """Return a list of human-readable errors (empty = ok)."""
    errors: list[str] = []
    version = data.get("openapi") or data.get("swagger")
    if not version:
        errors.append("missing openapi or swagger version field")
    paths = data.get("paths")
    if not isinstance(paths, dict) or not paths:
        errors.append("paths must be a non-empty mapping")
        return errors
    for path, item in paths.items():
        if not isinstance(item, dict):
            errors.append(f"{path}: path item must be a mapping")
            continue
        ops = {k: v for k, v in item.items() if k.lower() in _HTTP_METHODS}
        if not ops:
            errors.append(f"{path}: no HTTP operations")
            continue
        for method, op in ops.items():
            if not isinstance(op, dict):
                errors.append(f"{path} {method}: operation must be a mapping")
                continue
            responses = op.get("responses")
            if not isinstance(responses, dict) or not responses:
                errors.append(f"{path} {method}: responses must be a non-empty mapping")
    return errors


def validate_mocks(directory: Path, api: dict) -> list[str]:
    """Validate optional mock/*.json fixtures named after path templates."""
    mock_dir = directory / "mock"
    if not mock_dir.is_dir():
        return []
    errors: list[str] = []
    known_paths = set((api.get("paths") or {}).keys())
    for fixture in sorted(mock_dir.glob("*.json")):
        try:
            json.loads(fixture.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"mock/{fixture.name}: invalid JSON ({exc})")
            continue
        # Optional: fixture stem like `_api_health` maps to `/api/health`
        stem = fixture.stem
        if stem.startswith("_"):
            guessed = "/" + stem[1:].replace("_", "/")
            if known_paths and guessed not in known_paths:
                # Soft warning as error only if no paths match loosely
                if not any(p.replace("{", "").replace("}", "").replace("/", "_").strip("_")
                           in stem for p in known_paths):
                    errors.append(
                        f"mock/{fixture.name}: no matching OpenAPI path for guessed {guessed!r}"
                    )
    return errors


def validate_target(target: str, vault_dir: Path | None = None) -> dict:
    """Run mock validate. Raises SpecValidateError on failure.

    Returns a summary dict: {paths, operations, mocks_checked, status}.
    """
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    directory = sw.spec_dir(target, vault_dir)
    if not directory.is_dir():
        raise SpecValidateError(f"Spec workspace missing for {target}: {directory}")

    api = _load_api(directory)
    errors = validate_openapi(api)
    errors.extend(validate_mocks(directory, api))
    if errors:
        raise SpecValidateError("; ".join(errors))

    paths = api.get("paths") or {}
    ops = 0
    for item in paths.values():
        if isinstance(item, dict):
            ops += sum(1 for k in item if k.lower() in _HTTP_METHODS)

    # Record last validation on status.yaml without changing lifecycle status.
    status = sw.read_status(directory)
    status["notes"] = status.get("notes") or ""
    status["last_validated"] = sw._now_iso()
    status["files"] = sw._inventory_files(directory)
    # Preserve unknown keys by re-writing known shape + last_validated
    path = directory / "status.yaml"
    payload = {
        "status": status["status"],
        "updated": status.get("updated") or sw._now_iso(),
        "history": status.get("history") or [],
        "files": status.get("files") or {},
        "notes": status.get("notes") or "",
        "last_validated": status["last_validated"],
    }
    path.write_text(yaml.dump(payload, default_flow_style=False, sort_keys=False))

    return {
        "target": target,
        "paths": len(paths),
        "operations": ops,
        "status": status["status"],
        "last_validated": status["last_validated"],
    }


def submit_for_review(
    target: str,
    vault_dir: Path | None = None,
    *,
    note: str = "",
) -> dict:
    """Validate then draft → in-review."""
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    summary = validate_target(target, vault_dir)
    cur = summary["status"]
    if cur != "draft":
        raise SpecValidateError(
            f"submit requires status=draft (currently {cur!r}); "
            "use approve when in-review"
        )
    data = sw.set_status(
        target, "in-review", vault_dir,
        note=note or "mock validate passed",
    )
    summary["status"] = data["status"]
    return summary


def approve_spec(
    target: str,
    vault_dir: Path | None = None,
    *,
    note: str = "",
) -> dict:
    """Validate then in-review → approved."""
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    summary = validate_target(target, vault_dir)
    cur = summary["status"]
    if cur != "in-review":
        raise SpecValidateError(
            f"approve requires status=in-review (currently {cur!r}); "
            "run `lookout spec submit` first"
        )
    data = sw.set_status(
        target, "approved", vault_dir,
        note=note or "approved after mock validate",
    )
    summary["status"] = data["status"]
    return summary


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        summary = validate_target(args.target, Path(args.vault) if args.vault else None)
    except SpecValidateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK: {summary['target']} — {summary['paths']} paths, "
        f"{summary['operations']} operations (status={summary['status']})"
    )
    return 0


def _cmd_submit(args: argparse.Namespace) -> int:
    try:
        summary = submit_for_review(
            args.target,
            Path(args.vault) if args.vault else None,
            note=args.note or "",
        )
    except (SpecValidateError, sw.SpecWorkspaceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Submitted: {summary['target']} → {summary['status']}")
    return 0


def _cmd_approve(args: argparse.Namespace) -> int:
    try:
        summary = approve_spec(
            args.target,
            Path(args.vault) if args.vault else None,
            note=args.note or "",
        )
    except (SpecValidateError, sw.SpecWorkspaceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Approved: {summary['target']} → {summary['status']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lookout spec")
    parser.add_argument("--vault", default=None)
    sub = parser.add_subparsers(dest="action", required=True)

    p_val = sub.add_parser("validate", help="Mock-validate api.yaml + mock/")
    p_val.add_argument("target")
    p_val.set_defaults(func=_cmd_validate)

    p_sub = sub.add_parser("submit", help="Validate and draft → in-review")
    p_sub.add_argument("target")
    p_sub.add_argument("--note", default="")
    p_sub.set_defaults(func=_cmd_submit)

    p_app = sub.add_parser("approve", help="Validate and in-review → approved")
    p_app.add_argument("target")
    p_app.add_argument("--note", default="")
    p_app.set_defaults(func=_cmd_approve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

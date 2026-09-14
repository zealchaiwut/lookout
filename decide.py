"""decide.py — scaffold and status-flip for Lookout decision records.

Usage:
  python decide.py <target> --title "..." [--issue N] [--pr N] [--sprint S]
  python decide.py <target> --set-status ID --status superseded [--by ID]
  bin/lookout decide ...
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

sys.path.insert(0, str(REPO_ROOT))
import decisions_lib as dl  # noqa: E402


def _prefix_for(target: str) -> str:
    # viral-radar → VR, perf-coach → PC, commander → CM
    parts = target.replace("_", "-").split("-")
    if len(parts) == 1:
        return target[:2].upper()
    return "".join(p[0] for p in parts if p).upper()[:4]


def _project_dir(target: str, vault: Path) -> Path:
    return vault / "projects" / target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lookout decide")
    parser.add_argument("target")
    parser.add_argument("--vault", type=Path, default=REPO_ROOT / "vault")
    parser.add_argument("--title", default=None, help="Create a new decision")
    parser.add_argument("--issue", type=int, action="append", default=[])
    parser.add_argument("--pr", type=int, action="append", default=[])
    parser.add_argument("--sprint", action="append", default=[])
    parser.add_argument(
        "--status",
        default="proposed",
        choices=list(dl.VALID_STATUSES),
        help="Initial status when creating, or new status with --set-status",
    )
    parser.add_argument(
        "--set-status",
        metavar="ID",
        default=None,
        help="Flip status for an existing decision id (e.g. VR-D1)",
    )
    parser.add_argument(
        "--by",
        default=None,
        help="Successor decision id when superseding",
    )
    args = parser.parse_args(argv)

    # Validate target exists in targets.yaml when present
    if TARGETS_YAML.is_file():
        data = yaml.safe_load(TARGETS_YAML.read_text()) or {}
        if args.target not in (data.get("targets") or {}):
            print(f"Error: unknown target {args.target!r}", file=sys.stderr)
            return 1

    project_dir = _project_dir(args.target, args.vault)

    if args.set_status:
        decisions = dl.load_decisions(project_dir, gh={})
        match = next((d for d in decisions if d["id"] == args.set_status), None)
        if match is None:
            print(f"Error: no decision {args.set_status!r}", file=sys.stderr)
            return 1
        try:
            dl.set_decision_status(
                match["path"],
                args.status,
                superseded_by=args.by,
            )
            # If superseding, also mark the successor as superseding this one
            if args.by and args.status == "superseded":
                succ = next((d for d in decisions if d["id"] == args.by), None)
                if succ:
                    text = succ["path"].read_text(encoding="utf-8")
                    fm, body = dl._parse_frontmatter(text)
                    fm["supersedes"] = args.set_status
                    dump = yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip()
                    succ["path"].write_text(
                        f"---\n{dump}\n---\n{body.lstrip()}", encoding="utf-8"
                    )
        except dl.DecisionError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Updated {args.set_status} → {args.status}")
        return 0

    if not args.title:
        print("Error: provide --title to create, or --set-status to flip", file=sys.stderr)
        return 1

    try:
        path = dl.create_decision(
            project_dir,
            title=args.title,
            target=args.target,
            prefix=_prefix_for(args.target),
            issues=args.issue,
            prs=args.pr,
            sprints=args.sprint,
            status=args.status,
        )
    except dl.DecisionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Created {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

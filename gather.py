"""
gather.py — point-in-time snapshot collector for Lookout.

Resolves a named target from targets.yaml, calls Commander's read-only GET
APIs, and writes a structured vault artifact under:
  vault/projects/<name>/raw/<ISO-8601-timestamp>/

Manifest JSON shape
-------------------
{
    "timestamp": str,       # ISO-8601 UTC timestamp of this snapshot run
    "target": str,          # target name as resolved from targets.yaml
    "health": {             # from GET /api/health; empty dict when absent
        "status": str,      # health summary field returned by Commander
        ...                 # any additional fields returned by /api/health
    },
    "sources": {
        "<source_name>": {  # e.g. "brief", "sprints_history"
            "status": str,  # "ok" or "absent"
            "error": str    # empty string when ok; error description when absent
        }
    }
}

Exit codes
----------
0 — successful run OR Commander unreachable (absent path)
1 — configuration or usage error (unknown target, missing targets.yaml)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_TIMEOUT = 10


def _load_targets():
    with open(TARGETS_YAML) as f:
        return yaml.safe_load(f)


def _safe_get(url):
    """Perform a GET request with a fixed timeout.

    Returns (data, error_str). On success data is the parsed JSON and
    error_str is an empty string. On any failure data is None and error_str
    is a non-empty description of the problem.
    """
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        if not resp.ok:
            return None, f"HTTP {resp.status_code}"
        return resp.json(), ""
    except Exception as exc:
        return None, str(exc)


def gather(target_name):
    """Run a snapshot for *target_name* and write the vault artifact."""
    data = _load_targets()
    targets = data.get("targets", {})

    if target_name not in targets:
        known = ", ".join(targets) if targets else "(none)"
        print(
            f"Error: unknown target '{target_name}'.\n"
            f"Check targets.yaml for valid target names. Known: {known}",
            file=sys.stderr,
        )
        sys.exit(1)

    target = targets[target_name]
    commander_api = data.get("sources", {}).get("commander_api", "http://localhost:8000")
    slug = target.get("commander_slug", target_name)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir = REPO_ROOT / "vault" / "projects" / target_name / "raw" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    health_data, _ = _safe_get(f"{commander_api}/api/health")
    health = health_data if isinstance(health_data, dict) else {}

    brief_data, brief_err = _safe_get(f"{commander_api}/api/projects/{slug}/brief")
    history_data, history_err = _safe_get(f"{commander_api}/api/sprints/history")

    if isinstance(history_data, list):
        filtered_history = [
            entry for entry in history_data
            if entry.get("slug") == slug or entry.get("project") == slug
        ]
    else:
        filtered_history = []

    brief_json = {
        "brief": brief_data,
        "sprints_history": filtered_history if history_data is not None else [],
    }
    with open(out_dir / "brief.json", "w") as fh:
        json.dump(brief_json, fh, indent=2)

    sources = {
        "brief": {
            "status": "ok" if brief_err == "" else "absent",
            "error": brief_err,
        },
        "sprints_history": {
            "status": "ok" if history_err == "" else "absent",
            "error": history_err,
        },
    }

    manifest = {
        "timestamp": timestamp,
        "target": target_name,
        "health": health,
        "sources": sources,
    }
    with open(out_dir / "manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"gather: snapshot written to {out_dir}")


def main():
    if len(sys.argv) < 2 or not sys.argv[1]:
        print("Usage: python gather.py <target-name>", file=sys.stderr)
        sys.exit(1)
    gather(sys.argv[1])


if __name__ == "__main__":
    main()

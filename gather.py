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

Local collector outputs (written alongside manifest.json)
----------------------------------------------------------
issues.json        — gh issue list + gh pr list for the target's GitHub slug
gitlog.txt         — git log --oneline -30, branch name, and porcelain status
docs_manifest.json — path/sha256/heading/mtime for each tracked doc file;
                     includes "changed_files" key when a prior snapshot exists

Exit codes
----------
0 — successful run OR Commander/local collectors unreachable (absent path)
1 — configuration or usage error (unknown target, missing targets.yaml,
    target local path does not exist)
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_TIMEOUT = 10

_DOC_FILENAMES = ["README.md", "PRODUCT.md", "DESIGN.md", "SCHEMA.md"]


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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _first_heading(path: Path) -> str:
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("# "):
            return line
    return ""


def _collect_gh(slug: str, out_dir: Path) -> dict:
    """Write issues.json from gh issue list + gh pr list.

    Returns a sources entry dict.
    """
    try:
        issue_result = subprocess.run(
            ["gh", "issue", "list", "--repo", slug, "--json",
             "number,title,state,labels,assignees,createdAt,updatedAt", "--limit", "100"],
            capture_output=True, text=True,
        )
        pr_result = subprocess.run(
            ["gh", "pr", "list", "--repo", slug, "--json",
             "number,title,state,labels,assignees,createdAt,updatedAt", "--limit", "100"],
            capture_output=True, text=True,
        )

        issues = json.loads(issue_result.stdout) if issue_result.returncode == 0 and issue_result.stdout.strip() else []
        prs = json.loads(pr_result.stdout) if pr_result.returncode == 0 and pr_result.stdout.strip() else []

        payload = {"issues": issues, "prs": prs}
        with open(out_dir / "issues.json", "w") as fh:
            json.dump(payload, fh, indent=2)
        return {"status": "ok", "error": ""}

    except FileNotFoundError:
        return {"status": "absent", "error": "gh CLI not found"}
    except Exception as exc:
        return {"status": "absent", "error": str(exc)}


def _collect_git(local_path: Path, out_dir: Path) -> dict:
    """Write gitlog.txt from git log, branch, and status.

    Returns a sources entry dict.
    """
    try:
        log_result = subprocess.run(
            ["git", "-C", str(local_path), "log", "--oneline", "-30"],
            capture_output=True, text=True,
        )
        branch_result = subprocess.run(
            ["git", "-C", str(local_path), "branch", "--show-current"],
            capture_output=True, text=True,
        )
        status_result = subprocess.run(
            ["git", "-C", str(local_path), "status", "--porcelain"],
            capture_output=True, text=True,
        )

        if log_result.returncode != 0:
            err = log_result.stderr.strip() or "git log failed"
            return {"status": "absent", "error": err}

        lines = [
            "=== branch ===",
            branch_result.stdout.strip(),
            "",
            "=== log ===",
            log_result.stdout.strip(),
            "",
            "=== status ===",
            status_result.stdout.strip(),
        ]
        (out_dir / "gitlog.txt").write_text("\n".join(lines))
        return {"status": "ok", "error": ""}

    except FileNotFoundError:
        return {"status": "absent", "error": "git CLI not found"}
    except Exception as exc:
        return {"status": "absent", "error": str(exc)}


def _compute_changed_files(prior: dict, current: dict) -> list:
    """Return paths that differ (added, removed, or sha256-changed) between two manifests."""
    prior_files = prior.get("files", prior) if isinstance(prior, dict) else prior
    current_files = current.get("files", current) if isinstance(current, dict) else current

    if isinstance(prior_files, list):
        prior_map = {e["path"]: e["sha256"] for e in prior_files}
    else:
        prior_map = {}

    if isinstance(current_files, list):
        current_map = {e["path"]: e["sha256"] for e in current_files}
    else:
        current_map = {}

    changed = []
    all_paths = set(prior_map) | set(current_map)
    for path in sorted(all_paths):
        if prior_map.get(path) != current_map.get(path):
            changed.append(path)
    return changed


def _collect_docs_manifest(local_path: Path, out_dir: Path, vault_project_dir: Path) -> dict:
    """Scan doc files and write docs_manifest.json.

    Returns a sources entry dict.
    """
    try:
        files = []

        # Standard doc filenames at root
        for name in _DOC_FILENAMES:
            p = local_path / name
            if p.exists() and p.is_file():
                files.append({
                    "path": name,
                    "sha256": _sha256(p),
                    "heading": _first_heading(p),
                    "mtime": p.stat().st_mtime,
                })

        # Everything under docs/
        docs_dir = local_path / "docs"
        if docs_dir.exists() and docs_dir.is_dir():
            for p in sorted(docs_dir.rglob("*")):
                if p.is_file():
                    rel = str(p.relative_to(local_path))
                    heading = _first_heading(p) if p.suffix == ".md" else ""
                    files.append({
                        "path": rel,
                        "sha256": _sha256(p),
                        "heading": heading,
                        "mtime": p.stat().st_mtime,
                    })

        manifest = {"files": files}

        # Find the most recent prior snapshot with docs_manifest.json
        raw_dir = vault_project_dir / "raw"
        if raw_dir.exists():
            prior_snapshots = sorted(
                (d for d in raw_dir.iterdir() if d.is_dir() and (d / "docs_manifest.json").exists()),
                key=lambda d: d.name,
            )
            if prior_snapshots:
                prior_data = json.loads((prior_snapshots[-1] / "docs_manifest.json").read_text())
                manifest["changed_files"] = _compute_changed_files(prior_data, manifest)

        with open(out_dir / "docs_manifest.json", "w") as fh:
            json.dump(manifest, fh, indent=2)
        return {"status": "ok", "error": ""}

    except Exception as exc:
        return {"status": "absent", "error": str(exc)}


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
    github_slug = target.get("github", "")

    # Resolve local path and abort early if it doesn't exist
    local_str = target.get("local", "")
    local_path = Path(local_str).expanduser() if local_str else None
    if local_path is not None and not local_path.exists():
        print(
            f"Error: target local path does not exist: {local_path}\n"
            f"Check the 'local' field for target '{target_name}' in targets.yaml.",
            file=sys.stderr,
        )
        sys.exit(1)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    vault_project_dir = REPO_ROOT / "vault" / "projects" / target_name
    out_dir = vault_project_dir / "raw" / timestamp
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

    # Local collectors
    if github_slug and local_path is not None:
        sources["gh"] = _collect_gh(github_slug, out_dir)
    elif github_slug:
        sources["gh"] = _collect_gh(github_slug, out_dir)

    if local_path is not None:
        sources["git"] = _collect_git(local_path, out_dir)
        sources["docs_manifest"] = _collect_docs_manifest(local_path, out_dir, vault_project_dir)

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

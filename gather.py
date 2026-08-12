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
            "error": str    # empty string when ok; error desc when absent
        }
    }
}

Local collector outputs (written alongside manifest.json)
----------------------------------------------------------
issues.json        — gh issue list + gh pr list for the target's GitHub slug
gitlog.txt         — git log --oneline -30, branch name, and porcelain
                     status
docs_manifest.json — path/sha256/heading/mtime for each tracked doc file;
                     includes "changed_files" key when a prior snapshot exists
notion_todos.json  — todos from the configured Notion database, normalized to
                     {id, title, status, project, url, last_edited}; written
                     only when notion_todos_db is configured in sources and
                     NOTION_TOKEN is set in .env

Exit codes
----------
0 — successful run OR Commander/local collectors unreachable (absent path)
1 — configuration or usage error (unknown target, missing targets.yaml,
    target local path does not exist)
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

from collectors.notion import collect_notion_todos as _collect_notion_todos

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
        _fields = "number,title,state,labels,assignees,createdAt,updatedAt"
        issue_result = subprocess.run(
            ["gh", "issue", "list", "--repo", slug, "--json",
             _fields, "--limit", "100"],
            capture_output=True, text=True,
        )
        pr_result = subprocess.run(
            ["gh", "pr", "list", "--repo", slug, "--json",
             _fields, "--limit", "100"],
            capture_output=True, text=True,
        )

        issues = (
            json.loads(issue_result.stdout)
            if issue_result.returncode == 0 and issue_result.stdout.strip()
            else []
        )
        prs = (
            json.loads(pr_result.stdout)
            if pr_result.returncode == 0 and pr_result.stdout.strip()
            else []
        )

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
    """Return paths that differ (added, removed, or sha256-changed)."""
    prior_files = (
        prior.get("files", prior) if isinstance(prior, dict) else prior
    )
    current_files = (
        current.get("files", current) if isinstance(current, dict) else current
    )

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


def _collect_docs_manifest(
    local_path: Path, out_dir: Path, vault_project_dir: Path
) -> dict:
    """Scan doc files and write docs_manifest.json.

    Returns a sources entry dict.
    """
    try:
        files = []

        # Standard doc filenames at root — always recorded; absent files get null fields
        for name in _DOC_FILENAMES:
            p = local_path / name
            if p.exists() and p.is_file():
                files.append({
                    "path": name,
                    "sha256": _sha256(p),
                    "heading": _first_heading(p),
                    "mtime": p.stat().st_mtime,
                })
            else:
                files.append({
                    "path": name,
                    "sha256": None,
                    "heading": None,
                    "mtime": None,
                    "absent": True,
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
                (
                    d for d in raw_dir.iterdir()
                    if d.is_dir() and (d / "docs_manifest.json").exists()
                ),
                key=lambda d: d.name,
            )
            if prior_snapshots:
                prior_json = prior_snapshots[-1] / "docs_manifest.json"
                prior_data = json.loads(prior_json.read_text())
                manifest["changed_files"] = _compute_changed_files(
                    prior_data, manifest
                )

        with open(out_dir / "docs_manifest.json", "w") as fh:
            json.dump(manifest, fh, indent=2)
        return {"status": "ok", "error": ""}

    except Exception as exc:
        return {"status": "absent", "error": str(exc)}


# ---------------------------------------------------------------------------
# Endpoint collection
# ---------------------------------------------------------------------------

# Matches a Markdown table row of the form:
#   | `GET` | `/api/jobs` | List all jobs |
# Method and path may or may not be wrapped in backticks.
_ENDPOINT_ROW_RE = re.compile(
    r"^\|\s*`?(?P<method>GET|POST|PUT|PATCH|DELETE)`?\s*"
    r"\|\s*`?(?P<path>/[^`|]*?)`?\s*"
    r"\|(?P<description>[^|]*)\|?\s*$",
    re.IGNORECASE,
)


def _parse_endpoint_tables(text: str) -> list:
    """Extract GET endpoints from Markdown method/path tables in `text`.

    Only GET rows are returned — capability cards document read surfaces. Rows
    are deduplicated by path, keeping the first description seen.
    """
    seen: set[str] = set()
    endpoints: list = []
    for line in text.splitlines():
        m = _ENDPOINT_ROW_RE.match(line.strip())
        if not m:
            continue
        if m.group("method").upper() != "GET":
            continue
        path = m.group("path").strip()
        if not path.startswith("/") or path in seen:
            continue
        seen.add(path)
        endpoints.append({
            "path": path,
            "description": m.group("description").strip().strip("`"),
            "source": "readme-table",
        })
    return endpoints


def _collect_endpoints(local_path: Path, out_dir: Path) -> dict:
    """Scan the target's README and docs/ for API endpoint tables.

    Writes endpoints.json in the schema capability_card.py expects:
        {"get_endpoints": [{"path", "description", "example"}], "source_files": [...]}

    Doc tables are the evidence source rather than live introspection: Lookout is
    read-only against targets and must not start or call a target's server.
    """
    try:
        endpoints: list = []
        source_files: list = []
        seen: set[str] = set()

        candidates = [local_path / "README.md"]
        docs_dir = local_path / "docs"
        if docs_dir.exists() and docs_dir.is_dir():
            candidates.extend(sorted(docs_dir.rglob("*.md")))

        for p in candidates:
            if not p.is_file():
                continue
            found = _parse_endpoint_tables(p.read_text(encoding="utf-8", errors="replace"))
            fresh = [e for e in found if e["path"] not in seen]
            if not fresh:
                continue
            rel = str(p.relative_to(local_path))
            for e in fresh:
                seen.add(e["path"])
                e["source"] = rel
                e["example"] = f"curl http://localhost:8000{e['path']}"
            endpoints.extend(fresh)
            source_files.append(rel)

        with open(out_dir / "endpoints.json", "w") as fh:
            json.dump(
                {"get_endpoints": endpoints, "source_files": source_files},
                fh,
                indent=2,
            )
        return {"status": "ok" if endpoints else "absent", "error": "", "count": len(endpoints)}

    except Exception as exc:
        return {"status": "absent", "error": str(exc), "count": 0}


# ---------------------------------------------------------------------------
# Atlas staleness detection and trace-cap selection (issue #17)
# ---------------------------------------------------------------------------

def _parse_atlas_files(text: str) -> list:
    """Extract the files list from atlas note YAML frontmatter."""
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return []
    fm = m.group(1)
    # Multi-line files: block
    block = re.search(r"^files:\s*\n((?:[ \t]+-\s*.+\n?)*)", fm, re.MULTILINE)
    if block:
        items = re.findall(r"^[ \t]+-\s*(.+)$", block.group(1), re.MULTILINE)
        return [x.strip() for x in items if x.strip()]
    # Inline: files: [] or files: [a, b]
    inline = re.search(r"^files:\s*(.+)$", fm, re.MULTILINE)
    if inline:
        val = inline.group(1).strip()
        if val in ("[]", "null", "pending", ""):
            return []
        m2 = re.match(r"\[([^\]]+)\]", val)
        if m2:
            return [x.strip() for x in m2.group(1).split(",") if x.strip()]
    return []


def _set_frontmatter_stale(text: str, stale: bool) -> str:
    """Update the stale field in YAML frontmatter, preserving all other content."""
    val = "true" if stale else "false"
    if re.search(r"^stale:.*$", text, re.MULTILINE):
        return re.sub(r"^stale:.*$", f"stale: {val}", text, flags=re.MULTILINE, count=1)
    return re.sub(r"\n---\n$", f"\nstale: {val}\n---\n", text, count=1)


def _get_git_changed_files(local_path: Path) -> set:
    """Return set of file paths that appear in recent git log commits."""
    result = subprocess.run(
        ["git", "-C", str(local_path), "log", "--name-only", "--format=", "-20"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    changed = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            changed.add(line)
    return changed


def _get_traced_date(text: str):
    """Return the traced date string from atlas note frontmatter, or None."""
    m = re.search(r"^traced:\s*(.+)$", text, re.MULTILINE)
    if not m:
        return None
    val = m.group(1).strip()
    return None if val in ("null", "", "None") else val


def _is_note_needs_trace(text: str) -> bool:
    """Return True when note is stale or has never been traced."""
    stale_m = re.search(r"^stale:\s*(.+)$", text, re.MULTILINE)
    is_stale = bool(stale_m and stale_m.group(1).strip().lower() == "true")
    return is_stale or _get_traced_date(text) is None


def _update_atlas_index_stale(atlas_dir: Path, stale_slugs: list) -> None:
    """Update atlas index.md rows to reflect stale: true for the given note slugs."""
    index_path = atlas_dir / "index.md"
    if not index_path.exists():
        return

    slug_to_feature = {}
    for slug in stale_slugs:
        note_path = atlas_dir / f"{slug}.md"
        if note_path.exists():
            text = note_path.read_text()
            fm = re.search(r"^feature:\s*(.+)$", text, re.MULTILINE)
            if fm:
                slug_to_feature[slug] = fm.group(1).strip()

    index_text = index_path.read_text()
    for feature_name in slug_to_feature.values():
        escaped = re.escape(feature_name)
        index_text = re.sub(
            r"(\| " + escaped + r" \|[^|]+\|[^|]+\|)\s*false\s*(\|)",
            r"\1 true \2",
            index_text,
        )
    index_path.write_text(index_text)


def mark_stale_atlas_notes(local_path: Path, atlas_dir: Path) -> list:
    """Mark atlas notes stale when their files appear in git log changed files.

    Writes stale: true into each matching note's frontmatter and updates the
    atlas index.md. Returns list of note slugs that were marked stale.
    """
    atlas_dir = Path(atlas_dir)
    if not atlas_dir.exists():
        return []
    changed_files = _get_git_changed_files(Path(local_path))
    if not changed_files:
        return []

    marked = []
    for note_path in sorted(atlas_dir.glob("*.md")):
        if note_path.name == "index.md":
            continue
        text = note_path.read_text()
        files = _parse_atlas_files(text)
        if files and any(f in changed_files for f in files):
            note_path.write_text(_set_frontmatter_stale(text, True))
            marked.append(note_path.stem)

    if marked:
        _update_atlas_index_stale(atlas_dir, marked)

    return marked


def _write_atlas_pending_queue(atlas_dir: Path, pending_slugs: list) -> None:
    """Append or replace a pending queue section in atlas/index.md."""
    index_path = atlas_dir / "index.md"

    pending_lines = ["", "## Pending Queue", ""]
    for slug in pending_slugs:
        note_path = atlas_dir / f"{slug}.md"
        feature_name = slug
        if note_path.exists():
            text = note_path.read_text()
            fm = re.search(r"^feature:\s*(.+)$", text, re.MULTILINE)
            if fm:
                feature_name = fm.group(1).strip()
        pending_lines.append(f"- {feature_name} (`{slug}`)")
    pending_lines.append("")

    pending_block = "\n".join(pending_lines)

    if index_path.exists():
        index_text = index_path.read_text()
        # Remove any existing pending queue section before rewriting
        index_text = re.sub(
            r"\n## Pending Queue\n.*?(?=\n##|\Z)",
            "",
            index_text,
            flags=re.DOTALL,
        )
        index_path.write_text(index_text.rstrip() + "\n" + pending_block)
    else:
        index_path.write_text("# Atlas Index\n" + pending_block)


def select_trace_batch(atlas_dir: Path, max_batch: int = 3) -> list:
    """Return slugs of at most max_batch notes to trace next (oldest-traced first).

    Candidates are notes with stale: true or traced: null. After selecting the
    batch, the remaining candidates are written into a pending queue section of
    atlas/index.md. Notes not in either group are untouched.
    """
    atlas_dir = Path(atlas_dir)
    if not atlas_dir.exists():
        return []

    candidates = []
    for note_path in sorted(atlas_dir.glob("*.md")):
        if note_path.name == "index.md":
            continue
        text = note_path.read_text()
        if _is_note_needs_trace(text):
            traced = _get_traced_date(text)
            candidates.append((traced, note_path.stem))

    # None (untraced) sorts before any ISO date string
    candidates.sort(key=lambda item: ("0000" if item[0] is None else item[0], item[1]))

    batch_slugs = [slug for _, slug in candidates[:max_batch]]
    pending_slugs = [slug for _, slug in candidates[max_batch:]]

    if pending_slugs:
        _write_atlas_pending_queue(atlas_dir, pending_slugs)

    return batch_slugs


def _collect_notion(notion_db: str, notion_token: str, target_name: str, out_dir: Path) -> dict:
    """Query Notion todos database or return absent when not configured.

    Returns {"status", "count", "error"} for the summary table.
    Also writes notion_todos.json to out_dir when successful.
    """
    if not notion_db or notion_db == "<placeholder>":
        return {"status": "absent", "count": 0, "error": "not configured"}
    result = _collect_notion_todos(target_name, notion_token, notion_db, out_dir)
    count = result.get("count", 0)
    return {"status": result["status"], "count": count, "error": result.get("error", "")}


def _collect_journal_summary(entries_path_str: str) -> dict:
    """Check journal entries path and count entries. Returns {"status", "count", "error"}."""
    if not entries_path_str:
        return {"status": "absent", "count": 0, "error": "not configured"}
    entries_path = Path(entries_path_str).expanduser()
    if not entries_path.exists():
        return {"status": "absent", "count": 0, "error": f"path not found: {entries_path}"}
    try:
        count = sum(1 for p in entries_path.iterdir() if p.suffix == ".md" and p.is_file())
        return {"status": "ok", "count": count, "error": ""}
    except Exception as exc:
        return {"status": "absent", "count": 0, "error": str(exc)}


def gather(target_name):
    """Run a snapshot for *target_name* and return a summary dict.

    Returns:
        {"commander": {"status", "count"}, "notion": {"status", "count"}, "journal": {"status", "count"}}
    """
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
    sources_cfg = data.get("sources", {})
    commander_api = sources_cfg.get("commander_api", "http://localhost:8000")
    notion_db = sources_cfg.get("notion_todos_db", "")
    journal_entries_str = sources_cfg.get("journal_entries", "")
    slug = target.get("commander_slug", target_name)
    github_slug = target.get("github", "")

    # Resolve local path and abort early if it doesn't exist
    local_str = target.get("local", "")
    local_path = Path(local_str).expanduser() if local_str else None
    if local_path is not None and not local_path.exists():
        print(
            f"Error: target local path does not exist: {local_path}\n"
            f"Check the 'local' field for target"
            f" '{target_name}' in targets.yaml.",
            file=sys.stderr,
        )
        sys.exit(1)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    vault_project_dir = REPO_ROOT / "vault" / "projects" / target_name
    out_dir = vault_project_dir / "raw" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    health_data, _ = _safe_get(f"{commander_api}/api/health")
    health = health_data if isinstance(health_data, dict) else {}

    brief_data, brief_err = _safe_get(
        f"{commander_api}/api/projects/{slug}/brief"
    )
    history_data, history_err = _safe_get(
        f"{commander_api}/api/sprints/history"
    )

    if isinstance(history_data, list):
        filtered_history = [
            entry for entry in history_data
            if entry.get("slug") == slug or entry.get("project") == slug
        ]
    else:
        filtered_history = []

    brief_json = {
        "brief": brief_data,
        "sprints_history": (
            filtered_history if history_data is not None else []
        ),
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

    # Local collectors — output files absent on failure
    if github_slug:
        _collect_gh(github_slug, out_dir)

    if local_path is not None:
        _collect_git(local_path, out_dir)
        _collect_docs_manifest(local_path, out_dir, vault_project_dir)
        endpoints_result = _collect_endpoints(local_path, out_dir)
        sources["endpoints"] = {
            "status": endpoints_result["status"],
            "error": endpoints_result["error"],
            "count": endpoints_result["count"],
        }

    # Notion and journal collectors
    load_dotenv(REPO_ROOT / ".env", override=False)
    notion_token = os.environ.get("NOTION_TOKEN", "")
    notion_result = _collect_notion(notion_db, notion_token, target_name, out_dir)
    if notion_db and notion_db != "<placeholder>":
        sources["notion_todos"] = {
            "status": notion_result["status"],
            "error": notion_result["error"],
        }
    journal_result = _collect_journal_summary(journal_entries_str)

    manifest = {
        "timestamp": timestamp,
        "target": target_name,
        "health": health,
        "sources": sources,
    }
    with open(out_dir / "manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"gather: snapshot written to {out_dir}")

    # Build commander summary from brief + sprints_history
    commander_ok = brief_err == "" or history_err == ""
    commander_count = (
        (1 if brief_err == "" and brief_data is not None else 0)
        + len(filtered_history)
    )
    commander_result = {
        "status": "ok" if commander_ok else "absent",
        "count": commander_count,
    }

    return {
        "commander": commander_result,
        "notion": {"status": notion_result["status"], "count": notion_result["count"]},
        "journal": {"status": journal_result["status"], "count": journal_result["count"]},
    }


def main():
    if len(sys.argv) < 2 or not sys.argv[1]:
        print("Usage: python gather.py <target-name>", file=sys.stderr)
        sys.exit(1)
    gather(sys.argv[1])


if __name__ == "__main__":
    main()

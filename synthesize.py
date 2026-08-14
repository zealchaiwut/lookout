"""
synthesize.py — situation.md synthesis engine for Lookout.

Reads the newest snapshot, the previous situation.md, and notes.md, then
regenerates situation.md from structured snapshot data.

Output (vault/projects/<target>/situation.md)
---------------------------------------------
YAML frontmatter:
  target: str       — target name
  run: str          — ISO-8601 UTC timestamp of this synthesis run
  sources_ok: bool  — true only when all expected sources resolved

Seven sections:
  ## One-liner       — single sentence summarising current state
  ## Capacity        — verdict from brief + health
  ## Since last run  — changed fields vs prior snapshot
  ## What to do next — up to 5 ordered wikilinked items
  ## From the journal — entries from journal snapshot
  ## Open questions  — unresolved question items
  ## Drift           — top 3 drift signals

Exit codes
----------
0 — success
1 — configuration or usage error
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent

try:
    import question_registry as _qreg
except ImportError:
    _qreg = None  # type: ignore[assignment]
TARGETS_YAML = REPO_ROOT / "targets.yaml"


# ---------------------------------------------------------------------------
# Snapshot discovery
# ---------------------------------------------------------------------------

def _find_latest_snapshot(project_dir: Path) -> Path | None:
    raw_dir = project_dir / "raw"
    if not raw_dir.exists():
        return None
    dirs = sorted(
        d for d in raw_dir.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )
    return dirs[-1] if dirs else None


def _find_previous_snapshot(project_dir: Path, current: Path) -> Path | None:
    raw_dir = project_dir / "raw"
    dirs = sorted(
        d for d in raw_dir.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )
    for i, d in enumerate(dirs):
        if d.name == current.name and i > 0:
            return dirs[i - 1]
    return None


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {} if default is None else default


# ---------------------------------------------------------------------------
# sources_ok logic
# ---------------------------------------------------------------------------

def _compute_sources_ok(manifest: dict, extra_missing: list) -> bool:
    """True only when all manifest sources resolved and no extra files missing."""
    if extra_missing:
        return False
    sources = manifest.get("sources", {})
    if not sources:
        return False
    return all(v.get("status") == "ok" for v in sources.values())


def _is_commander_absent(manifest: dict) -> bool:
    sources = manifest.get("sources", {})
    return sources.get("brief", {}).get("status", "absent") != "ok"


# ---------------------------------------------------------------------------
# Capacity verdict
# ---------------------------------------------------------------------------

def _capacity_verdict(manifest: dict, brief_json: dict, issues_data: dict) -> str:
    if _is_commander_absent(manifest):
        return "commander unreachable — state unverified"

    # Active sprint from sprints_history
    sprints = brief_json.get("sprints_history", [])
    for sprint in sprints:
        state = str(sprint.get("state", sprint.get("status", ""))).lower()
        if state in ("active", "running", "in_progress", "in-progress"):
            return "Sprint running — wait"

    # Active sprint from health field
    health = manifest.get("health", {})
    sprint_state = str(health.get("sprint_state", health.get("sprint_status", ""))).lower()
    if sprint_state in ("active", "running"):
        return "Sprint running — wait"

    # Blocked issues — only open issues count; a closed ticket cannot block work
    issues = issues_data.get("issues", []) if isinstance(issues_data, dict) else []
    blocked = [
        issue for issue in issues
        if str(issue.get("state", "open")).lower() == "open"
        and any(
            label.get("name", "").lower() == "blocked"
            for label in issue.get("labels", [])
        )
    ]
    if blocked:
        n = len(blocked)
        return f"{n} blocked — resolve first"

    return "Clear to start"


# ---------------------------------------------------------------------------
# Since last run diff
# ---------------------------------------------------------------------------

def _flatten_manifest(d: dict, prefix: str = "") -> dict:
    """Flatten a nested dict; skip 'timestamp' and derivative 'error' fields."""
    items: dict = {}
    for k, v in d.items():
        if k in ("timestamp", "error"):
            continue
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(_flatten_manifest(v, key))
        else:
            items[key] = v
    return items


# Manifest fields that move on their own between runs. Two snapshots taken
# minutes apart differ in all of them, so reporting them as "since last run"
# changes buries every real signal — and, because the Drift section falls back
# to these same diffs, poisons drift too. Health is a point-in-time reading of
# the Commander host, not a fact about the target.
_VOLATILE_DIFF_PREFIXES = ("health.",)
_VOLATILE_DIFF_KEYS = {"health"}


def _is_volatile_diff_key(key: str) -> bool:
    return key in _VOLATILE_DIFF_KEYS or key.startswith(_VOLATILE_DIFF_PREFIXES)


def _diff_manifests(current: dict, previous: dict) -> list[str]:
    """Return list of '`field`: old → new' strings for changed fields.

    Volatile host-telemetry fields are excluded; see _VOLATILE_DIFF_PREFIXES.
    A change in overall health status is still surfaced — via the One-liner,
    which reads `health.status` directly.
    """
    curr_flat = _flatten_manifest(current)
    prev_flat = _flatten_manifest(previous)
    changes = []
    for key in sorted(set(curr_flat) | set(prev_flat)):
        if _is_volatile_diff_key(key):
            continue
        curr_val = curr_flat.get(key, "<absent>")
        prev_val = prev_flat.get(key, "<absent>")
        if curr_val != prev_val:
            changes.append(f"`{key}`: {prev_val!r} → {curr_val!r}")
    return changes


# ---------------------------------------------------------------------------
# What to do next
# ---------------------------------------------------------------------------

# Marks a next-item that is prose rather than the name of a vault note — a
# GitHub issue title, a Commander suggestion, a sprint label. Wikilinking those
# emits a link that can never resolve, and the vault linter fails the run for
# exactly that. Only items derived from doc paths become wikilinks.
_PLAIN_ITEM_PREFIX = "\x00plain\x00"


def _plain(text: str) -> str:
    return f"{_PLAIN_ITEM_PREFIX}{text}"


def _to_wikilink(title: str) -> str:
    if title.startswith(_PLAIN_ITEM_PREFIX):
        return title[len(_PLAIN_ITEM_PREFIX):]
    clean = re.sub(r"[`*_#\[\]]", "", title)
    clean = re.sub(r"\.(md|json|txt|py|yaml|yml)$", "", clean, flags=re.IGNORECASE)
    parts = re.split(r"[/\-_\s]+", clean)
    page = " ".join(p.capitalize() for p in parts if p)
    return f"[[{page}]]"


# Keys a Commander brief may carry forward work under. The first five are the
# generic names this function originally looked for; the rest are the names the
# live Commander /api/briefs payload actually uses, without which this section
# was empty for every target.
_BRIEF_NEXT_KEYS = (
    "actions", "tasks", "next_steps", "todo", "forward_items",
    "suggested_next", "waiting_on_you", "up_next", "blocked",
)


# Keys a brief item may carry its human-readable label under, in priority order.
# Commander suggestions use `text`; sprint lookahead entries use `label`. An item
# with none of these is skipped rather than stringified — `str(some_dict)` in a
# "What to do next" list is noise, and it used to reach situation.md verbatim.
_ITEM_TITLE_KEYS = ("title", "text", "name", "label", "summary")


def _item_title(item) -> str:
    """Return a human-readable label for a brief item, or '' if it has none."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in _ITEM_TITLE_KEYS:
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def _collect_next_items(
    brief_data,
    notion_todos: list,
    docs_manifest: dict,
    issues_data: dict | None = None,
) -> list[str]:
    items: list[str] = []

    # From brief action fields
    if isinstance(brief_data, dict):
        for key in _BRIEF_NEXT_KEYS:
            val = brief_data.get(key, [])
            if not isinstance(val, list):
                val = [val]
            for item in val:
                title = _item_title(item)
                if title:
                    items.append(_plain(title))

    # From open GitHub issues. A target can have a quiet brief and still have
    # real queued work; without this the section reads "no items" next to a
    # backlog of twenty open issues.
    if isinstance(issues_data, dict):
        for issue in issues_data.get("issues", []):
            if not isinstance(issue, dict):
                continue
            if str(issue.get("state", "open")).lower() != "open":
                continue
            title = issue.get("title", "")
            number = issue.get("number", "")
            if title:
                items.append(
                    _plain(f"#{number} — {title}" if number else title)
                )

    # From Notion todos (exclude done/completed/archived)
    if isinstance(notion_todos, list):
        for todo in notion_todos:
            status = str(todo.get("status", "")).lower()
            if status not in ("done", "completed", "archived", "closed"):
                title = todo.get("title", "")
                if title:
                    items.append(title)

    # From changed doc files. These are paths in the *target* repo
    # (README.md, docs/todo.md, …), not vault notes — wikilinking them
    # produces [[Readme]] / [[Docs Todo]] that lint cannot resolve.
    if isinstance(docs_manifest, dict):
        for f in docs_manifest.get("changed_files", []):
            if isinstance(f, str):
                items.append(_plain(f))

    # Deduplicate, limit to 5
    seen: set = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
        if len(result) == 5:
            break
    return result


# ---------------------------------------------------------------------------
# Journal section
# ---------------------------------------------------------------------------

def _build_journal_lines(entries: list) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        date = entry.get("date", "")
        target_lines = entry.get("target_lines", [])
        concern_lines = entry.get("concerns_lines", [])
        if target_lines or concern_lines:
            if date:
                lines.append(f"**{date}**")
            for line in target_lines[:3]:
                lines.append(f"- {line.strip()}")
            for line in concern_lines[:2]:
                lines.append(f"- {line.strip()}")
    return lines


# ---------------------------------------------------------------------------
# Open questions
# ---------------------------------------------------------------------------

def _build_open_questions(issues_data: dict, journal_entries: list) -> list[str]:
    questions: list[str] = []

    issues = issues_data.get("issues", []) if isinstance(issues_data, dict) else []
    for issue in issues:
        labels = [lbl.get("name", "").lower() for lbl in issue.get("labels", [])]
        if "question" in labels or "needs-answer" in labels:
            questions.append(f"#{issue.get('number', '?')}: {issue.get('title', '')}")

    for entry in journal_entries:
        for line in entry.get("concerns_lines", []):
            if "?" in line:
                questions.append(line.strip())

    return questions


def _format_registry_questions(open_qs: list) -> list[str]:
    """Format open question registry entries as display strings."""
    lines: list[str] = []
    for q in open_qs:
        qid = q.get("id", "?")
        text = q.get("text", "")
        evidence = q.get("evidence", "")
        options = q.get("options", [])
        lines.append(f"**{qid}**: {text}")
        if evidence:
            lines.append(f"  _Evidence: {evidence}_")
        if options:
            for opt in options[:3]:
                lines.append(f"  - {opt}")
    return lines


def _format_resolved_questions(resolved_qs: list) -> list[str]:
    """Format resolved questions as cross-link entries for situation.md."""
    if not resolved_qs:
        return []
    lines: list[str] = ["", "_Resolved this run:_"]
    for q in resolved_qs:
        qid = q.get("id", "?")
        decision = q.get("resolved_by", "decisions.md")
        lines.append(f"- ~~{qid}~~ → [[Decisions]] ({decision})")
    return lines


# ---------------------------------------------------------------------------
# Drift signals
# ---------------------------------------------------------------------------

def _read_drift_md_signals(drift_md_path: Path) -> list[str]:
    """Extract flag summaries from drift.md (claim lines) for situation.md."""
    if not drift_md_path.exists():
        return []
    signals: list[str] = []
    for line in drift_md_path.read_text().splitlines():
        if line.startswith("**Claim:**"):
            claim = line.removeprefix("**Claim:**").strip()
            if claim:
                signals.append(claim)
    return signals[:3]


def _build_drift_signals(
    current_manifest: dict,
    prev_manifest: dict | None,
    docs_manifest: dict,
    drift_md_path: Path | None = None,
) -> list[str]:
    signals: list[str] = []

    # Prefer drift.md flags when they exist — they are more specific
    if drift_md_path is not None:
        drift_flags = _read_drift_md_signals(drift_md_path)
        if drift_flags:
            return drift_flags[:3]

    if prev_manifest:
        changes = _diff_manifests(current_manifest, prev_manifest)
        for change in changes[:2]:
            signals.append(change)

    changed_docs = docs_manifest.get("changed_files", []) if isinstance(docs_manifest, dict) else []
    if changed_docs:
        names = ", ".join(str(f) for f in changed_docs[:3])
        signals.append(f"{len(changed_docs)} doc(s) changed: {names}")

    return signals[:3]


# ---------------------------------------------------------------------------
# One-liner
# ---------------------------------------------------------------------------

def _capability_what_it_is(project_dir: Path) -> str:
    """Return the '## What it is' body from the target's capability card, or ''.

    Reused rather than regenerated so a target costs at most one description
    call per run (capability_card.py owns that call). See docs/llm-usage.md.
    """
    cap_path = project_dir / "capability.md"
    if not cap_path.exists():
        return ""
    try:
        text = cap_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"## What it is\s*\n+(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not m:
        return ""
    body = " ".join(m.group(1).split())
    # The generic fallback card says nothing a reader can use; treat it as absent.
    if "is a project tracked by Lookout" in body:
        return ""
    return body


def _build_one_liner(
    target: str, manifest: dict, brief_data, project_dir: Path | None = None
) -> str:
    health = manifest.get("health", {})
    health_status = health.get("status", "unknown") if isinstance(health, dict) else "unknown"

    description = ""
    if isinstance(brief_data, dict):
        description = brief_data.get("description", brief_data.get("name", ""))
    if not description and project_dir is not None:
        description = _capability_what_it_is(project_dir)

    if not description:
        return f"Target `{target}` health is {health_status}."

    # Lead with what the target is; health is a trailing qualifier. Putting the
    # health word first produced lines like "asset-studio is unknown: <paragraph>".
    first_sentence = description.split(". ")[0].rstrip(".")
    return f"`{target}` — {first_sentence}. (health: {health_status})"


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def _render_situation(
    *,
    target: str,
    run: str,
    sources_ok: bool,
    one_liner: str,
    capacity: str,
    since_last_run: list[str],
    what_to_do_next: list[str],
    journal: list[str],
    open_questions: list[str],
    drift: list[str],
    missing_sources: list[str],
    snapshot_name: str,
    registry_open: list | None = None,
    registry_resolved: list | None = None,
) -> str:
    lines = [
        "---",
        f"target: {target}",
        f'run: "{run}"',
        f"sources_ok: {'true' if sources_ok else 'false'}",
        "---",
        "",
        "## One-liner",
        "",
        one_liner,
        "_(source: manifest.json, brief.json)_",
        "",
        "## Capacity",
        "",
        capacity,
        "_(source: manifest.json, brief.json, issues.json)_",
        "",
        "## Since last run",
        "",
    ]

    if since_last_run:
        for item in since_last_run:
            lines.append(f"- {item}")
    else:
        lines.append("_No changes detected._")
    lines.append("_(source: manifest.json)_")
    lines.append("")

    lines.append("## What to do next")
    lines.append("")
    if what_to_do_next:
        for i, item in enumerate(what_to_do_next, 1):
            lines.append(f"{i}. {item}")
    else:
        lines.append("_No items found._")
    lines.append("_(source: brief.json, notion_todos.json, docs_manifest.json)_")
    lines.append("")

    lines.append("## From the journal")
    lines.append("")
    if journal:
        lines.extend(journal)
    else:
        lines.append("_No journal entries found._")
    lines.append("_(source: journal_delta.json)_")
    lines.append("")

    lines.append("## Open questions")
    lines.append("")
    if registry_open or registry_resolved:
        if registry_open:
            lines.extend(_format_registry_questions(registry_open))
        else:
            lines.append("_No open questions._")
        if registry_resolved:
            lines.extend(_format_resolved_questions(registry_resolved))
    elif open_questions:
        for q in open_questions:
            lines.append(f"- {q}")
    else:
        lines.append("_No open questions._")
    lines.append("")
    lines.append("_(source: issues.json, questions.json)_")
    lines.append("")

    lines.append("## Drift")
    lines.append("")
    if drift:
        for signal in drift:
            lines.append(f"- {signal}")
    else:
        lines.append("_No drift signals._")
    lines.append("_(source: manifest.json, docs_manifest.json)_")
    lines.append("")

    if missing_sources:
        lines.append("---")
        lines.append("")
        lines.append("**Note:** The following expected sources were absent during this run:")
        lines.append("")
        for src in missing_sources:
            lines.append(f"- `{src}`")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def synthesize(target_name: str, vault_dir: Path | None = None) -> Path:
    """Generate situation.md for target_name from its latest snapshot.

    Returns the path to the written situation.md.
    Raises SystemExit(1) on configuration errors.
    Never mutates notes.md.
    """
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"

    project_dir = vault_dir / "projects" / target_name
    situation_path = project_dir / "situation.md"
    notes_path = project_dir / "notes.md"

    # Record notes.md content before anything else
    notes_bytes_before = notes_path.read_bytes() if notes_path.exists() else None

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Find latest snapshot
    snapshot_dir = _find_latest_snapshot(project_dir)

    # Load snapshot files; track those that are missing
    missing_sources: list[str] = []

    if snapshot_dir is None:
        missing_sources.append("manifest.json")
        manifest: dict = {}
    else:
        manifest = _load_json(snapshot_dir / "manifest.json")

    brief_json: dict = {}
    if snapshot_dir and (snapshot_dir / "brief.json").exists():
        brief_json = _load_json(snapshot_dir / "brief.json")
    else:
        if "brief" not in missing_sources:
            missing_sources.append("brief.json")

    issues_data: dict = {}
    if snapshot_dir and (snapshot_dir / "issues.json").exists():
        issues_data = _load_json(snapshot_dir / "issues.json")

    docs_manifest: dict = {}
    if snapshot_dir and (snapshot_dir / "docs_manifest.json").exists():
        docs_manifest = _load_json(snapshot_dir / "docs_manifest.json")

    notion_todos: list = []
    if snapshot_dir and (snapshot_dir / "notion_todos.json").exists():
        raw = _load_json(snapshot_dir / "notion_todos.json", default=[])
        notion_todos = raw if isinstance(raw, list) else raw.get("todos", [])

    journal_entries: list = []
    if snapshot_dir and (snapshot_dir / "journal_delta.json").exists():
        jd = _load_json(snapshot_dir / "journal_delta.json")
        journal_entries = jd.get("entries", [])
    elif (REPO_ROOT / "journal_delta.json").exists():
        jd = _load_json(REPO_ROOT / "journal_delta.json")
        journal_entries = jd.get("entries", [])

    # Collect sources declared absent in manifest
    for src_name, src_entry in manifest.get("sources", {}).items():
        if src_entry.get("status") != "ok" and src_name not in missing_sources:
            missing_sources.append(src_name)

    sources_ok = _compute_sources_ok(manifest, missing_sources)

    # Previous snapshot for diff
    prev_manifest: dict | None = None
    if snapshot_dir:
        prev_snap = _find_previous_snapshot(project_dir, snapshot_dir)
        if prev_snap:
            prev_manifest = _load_json(prev_snap / "manifest.json")

    # Build content
    brief_data = brief_json.get("brief", {})

    one_liner = _build_one_liner(target_name, manifest, brief_data, project_dir)
    capacity = _capacity_verdict(manifest, brief_json, issues_data)
    since_last_run = _diff_manifests(manifest, prev_manifest) if prev_manifest else []
    next_raw = _collect_next_items(brief_data, notion_todos, docs_manifest, issues_data)
    what_to_do_next = [_to_wikilink(item) for item in next_raw]
    journal = _build_journal_lines(journal_entries)
    open_questions = _build_open_questions(issues_data, journal_entries)
    drift_md_path = project_dir / "drift.md"
    drift = _build_drift_signals(manifest, prev_manifest, docs_manifest, drift_md_path=drift_md_path)

    # Question generation and read-back pass
    registry_open: list = []
    registry_resolved: list = []
    if _qreg is not None:
        drift_flags = _qreg.parse_drift_md_flags(drift_md_path)
        stalled_items = _qreg.extract_stalled_items(issues_data)
        notes_path = project_dir / "notes.md"
        human_notes = _qreg.extract_human_note_carryovers(notes_path)
        _qreg.generate_questions(project_dir, target_name, drift_flags, stalled_items, human_notes)
        _qreg.resolve_questions(project_dir, vault_dir, target_name)
        registry_open = _qreg.get_open_questions(project_dir)
        registry_resolved = _qreg.get_resolved_questions(project_dir)
        # Detect contradictions with logged decisions and extend drift signals
        contradiction_flags = _qreg.detect_decision_contradictions(project_dir, vault_dir, docs_manifest)
        if contradiction_flags and len(drift) < 3:
            for cf in contradiction_flags:
                if len(drift) >= 3:
                    break
                drift.append(cf.get("claim", ""))

    content = _render_situation(
        target=target_name,
        run=run_ts,
        sources_ok=sources_ok,
        one_liner=one_liner,
        capacity=capacity,
        since_last_run=since_last_run,
        what_to_do_next=what_to_do_next,
        journal=journal,
        open_questions=open_questions,
        drift=drift,
        missing_sources=missing_sources,
        snapshot_name=snapshot_dir.name if snapshot_dir else "",
        registry_open=registry_open,
        registry_resolved=registry_resolved,
    )

    project_dir.mkdir(parents=True, exist_ok=True)
    situation_path.write_text(content)

    # Verify notes.md was never touched
    if notes_bytes_before is not None:
        notes_bytes_after = notes_path.read_bytes()
        assert notes_bytes_before == notes_bytes_after, "synthesize() must not mutate notes.md"

    return situation_path


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1]:
        print("Usage: python synthesize.py <target-name>", file=sys.stderr)
        sys.exit(1)
    synthesize(sys.argv[1])


if __name__ == "__main__":
    main()

"""
question_registry.py — stable question ID registry for Lookout.

Generates questions from drift flags, stalled issues, and human-note
carry-overs. IDs are in the format <PREFIX>Q<n> (e.g. SKQ1) and are
never reused across runs. Implements the read-back pass that marks
resolved questions by scanning decisions.md files.

Registry file: vault/projects/<target>/questions.json
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

QUESTION_ID_RE = re.compile(r'\b([A-Z]{2}Q\d+)\b')
_DEPRECATED_RE = re.compile(
    r'^\*\*(?:Deprecated|Removes|Revokes):\*\*\s*(.+)$', re.MULTILINE
)


# ---------------------------------------------------------------------------
# Prefix + registry I/O
# ---------------------------------------------------------------------------

def _get_prefix(target_name: str) -> str:
    """Return two-letter uppercase prefix derived from target name."""
    clean = re.sub(r'[^a-zA-Z]', '', target_name)
    return (clean[:2] if len(clean) >= 2 else (clean + 'X')[:2]).upper()


def load_registry(project_dir: Path) -> dict:
    """Load questions.json from project_dir; return empty registry if absent."""
    path = project_dir / "questions.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {"prefix": "", "next_id": 1, "questions": {}}


def save_registry(project_dir: Path, registry: dict) -> None:
    registry_path = project_dir / "questions.json"
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding='utf-8')


def _issue_id(registry: dict, prefix: str) -> str:
    n = registry.get("next_id", 1)
    qid = f"{prefix}Q{n}"
    registry["next_id"] = n + 1
    return qid


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------

def generate_questions(
    project_dir: Path,
    target_name: str,
    drift_flags: list,
    stalled_items: list,
    human_notes: list,
    snapshot_context: str = "",
) -> list:
    """
    Create question entries for every new signal.  Signals already captured in
    a previous run are skipped so IDs are stable and never reused.

    Returns the list of newly created question dicts.
    """
    registry = load_registry(project_dir)
    prefix = _get_prefix(target_name)
    if not registry.get("prefix"):
        registry["prefix"] = prefix

    questions = registry.setdefault("questions", {})

    existing_signals: set = {
        q.get("signal_text", "")
        for q in questions.values()
        if q.get("status") == "open"
    }

    new_qs: list = []
    today = _today()

    for flag in drift_flags:
        claim = flag.get("claim", "")
        signal_text = f"drift:{claim[:80]}"
        if signal_text in existing_signals:
            continue
        qid = _issue_id(registry, prefix)
        q = {
            "id": qid,
            "created": today,
            "signal_type": flag.get("signal_type", "drift_flag"),
            "signal_text": signal_text,
            "text": f"How should we resolve: {claim}?",
            "evidence": flag.get("evidence_path", "drift.md"),
            "options": _drift_options(flag),
            "status": "open",
        }
        questions[qid] = q
        existing_signals.add(signal_text)
        new_qs.append(q)

    for item in stalled_items:
        title = item.get("title", item) if isinstance(item, dict) else str(item)
        signal_text = f"stalled:{title[:80]}"
        if signal_text in existing_signals:
            continue
        qid = _issue_id(registry, prefix)
        q = {
            "id": qid,
            "created": today,
            "signal_type": "stalled_item",
            "signal_text": signal_text,
            "text": f"What is blocking: {title}?",
            "evidence": f"issues.json (stalled: {title})",
            "options": [
                "Unblock by addressing the dependency",
                "Descope the item from the current sprint",
                "Escalate to stakeholders for prioritization",
            ],
            "status": "open",
        }
        questions[qid] = q
        existing_signals.add(signal_text)
        new_qs.append(q)

    for note_line in human_notes:
        signal_text = f"note:{note_line[:80]}"
        if signal_text in existing_signals:
            continue
        qid = _issue_id(registry, prefix)
        q = {
            "id": qid,
            "created": today,
            "signal_type": "human_note",
            "signal_text": signal_text,
            "text": note_line.strip().rstrip("?") + "?",
            "evidence": "notes.md (human carry-over)",
            "options": [
                "Address in the next planning session",
                "Document the answer in decisions.md",
            ],
            "status": "open",
        }
        questions[qid] = q
        existing_signals.add(signal_text)
        new_qs.append(q)

    registry["questions"] = questions
    save_registry(project_dir, registry)
    return new_qs


def _drift_options(flag: dict) -> list:
    signal_type = flag.get("signal_type", "")
    suggested = flag.get("suggested_fix", "")
    options: list = []
    if suggested:
        options.append(suggested[:120])
    if signal_type == "removed_feature":
        options.append("Remove the stale documentation reference")
        options.append("Re-introduce the feature in a new PR")
    elif signal_type == "todo_still_open":
        options.append("Mark the todo as done in the doc file")
        options.append("Re-open the task in the issue tracker")
    elif signal_type == "schema_name_diverges":
        options.append("Rename the SCHEMA.md heading to match the migration file")
        options.append("Rename the migration file to match the SCHEMA.md heading")
    else:
        options.append("Update the documentation to reflect current state")
        options.append("Revert the change that caused the drift")
    return options[:3]


# ---------------------------------------------------------------------------
# Decision read-back
# ---------------------------------------------------------------------------

def _parse_decisions_refs(decisions_path: Path) -> dict:
    """Return {question_id: decision_heading} for all question IDs in decisions_path."""
    if not decisions_path.exists():
        return {}
    text = decisions_path.read_text(encoding='utf-8')
    refs: dict = {}
    current_heading = ""
    for line in text.splitlines():
        if line.startswith("#"):
            current_heading = line.lstrip("#").strip()
        for m in QUESTION_ID_RE.finditer(line):
            qid = m.group(1)
            if qid not in refs:
                refs[qid] = current_heading or line.strip()
    return refs


def resolve_questions(
    project_dir: Path,
    vault_dir: Path,
    target_name: str,
) -> list:
    """
    Parse vault and project decisions.md; mark matching open questions as resolved.
    Returns the list of questions resolved in this pass.
    """
    registry = load_registry(project_dir)
    questions = registry.get("questions", {})

    resolved_by: dict = {}
    for path in (vault_dir / "decisions.md", project_dir / "decisions.md"):
        for qid, heading in _parse_decisions_refs(path).items():
            if qid not in resolved_by:
                resolved_by[qid] = heading

    newly_resolved: list = []
    for qid, q in questions.items():
        if q.get("status") == "open" and qid in resolved_by:
            q["status"] = "resolved"
            q["resolved_by"] = resolved_by[qid]
            newly_resolved.append(q)

    registry["questions"] = questions
    save_registry(project_dir, registry)
    return newly_resolved


def get_open_questions(project_dir: Path) -> list:
    """Return list of open question dicts."""
    registry = load_registry(project_dir)
    return [q for q in registry.get("questions", {}).values() if q.get("status") == "open"]


def get_resolved_questions(project_dir: Path) -> list:
    """Return list of resolved question dicts."""
    registry = load_registry(project_dir)
    return [q for q in registry.get("questions", {}).values() if q.get("status") == "resolved"]


# ---------------------------------------------------------------------------
# Decision-contradiction drift detection
# ---------------------------------------------------------------------------

def detect_decision_contradictions(
    project_dir: Path,
    vault_dir: Path,
    docs_manifest: dict,
) -> list:
    """
    Raise a drift flag when a target doc's content mentions an item explicitly
    deprecated/removed in decisions.md.

    Decisions may annotate deprecated items with:
        **Deprecated:** <text>
        **Removes:** <text>
        **Revokes:** <text>

    Returns a list of drift flag dicts in the same format used by detect_drift().
    """
    deprecated_items: list = []
    for decisions_path in (vault_dir / "decisions.md", project_dir / "decisions.md"):
        if not decisions_path.exists():
            continue
        text = decisions_path.read_text(encoding='utf-8')
        current_heading = ""
        for line in text.splitlines():
            if line.startswith("#"):
                current_heading = line.lstrip("#").strip()
            m = _DEPRECATED_RE.match(line)
            if m:
                deprecated_items.append((m.group(1).strip(), current_heading))

    if not deprecated_items:
        return []

    doc_files: list = []
    if isinstance(docs_manifest, dict):
        doc_files = docs_manifest.get("files", docs_manifest.get("changed_files", []))

    flags: list = []
    for file_entry in doc_files:
        if isinstance(file_entry, str):
            path, content = file_entry, ""
        elif isinstance(file_entry, dict):
            path = file_entry.get("path", "")
            content = file_entry.get("content", "")
        else:
            continue
        if not content:
            continue
        for item, heading in deprecated_items:
            if item.lower() in content.lower():
                flags.append({
                    "signal_type": "decision_contradiction",
                    "claim": (
                        f"`{path}` still mentions '{item}' which was "
                        f"deprecated/removed per decision: {heading}"
                    ),
                    "evidence_path": f"{path} + decisions.md",
                    "suggested_fix": (
                        f"Update `{path}` to remove or replace the reference to '{item}' "
                        f"as logged in decision: {heading}"
                    ),
                })
    return flags


# ---------------------------------------------------------------------------
# Helpers for synthesize.py
# ---------------------------------------------------------------------------

def parse_drift_md_flags(drift_md_path: Path) -> list:
    """
    Parse drift.md into a list of flag dicts for question generation.
    Reads Claim, Evidence, and Suggested fix from each Flag section.
    """
    if not drift_md_path.exists():
        return []
    text = drift_md_path.read_text(encoding='utf-8')
    flags: list = []
    current: dict = {}
    for line in text.splitlines():
        if line.startswith("## Flag"):
            if current.get("claim"):
                flags.append(current)
            stype = re.sub(r"^## Flag \d+:\s*", "", line).lower().replace(" ", "_")
            current = {"signal_type": stype, "claim": "", "evidence_path": "", "suggested_fix": ""}
        elif line.startswith("**Claim:**"):
            current["claim"] = line.removeprefix("**Claim:**").strip()
        elif line.startswith("**Evidence:**"):
            current["evidence_path"] = line.removeprefix("**Evidence:**").strip()
        elif line.startswith("**Suggested fix:**"):
            current["suggested_fix"] = line.removeprefix("**Suggested fix:**").strip()
    if current.get("claim"):
        flags.append(current)
    return flags


def extract_human_note_carryovers(notes_path: Path) -> list:
    """
    Return lines from notes.md that qualify as carry-overs:
      - Lines ending with '?'
      - Lines beginning with '> ' (blockquote carry-over marker)
    """
    if not notes_path.exists():
        return []
    carryovers: list = []
    for line in notes_path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith("?") or stripped.startswith("> "):
            carryovers.append(stripped.lstrip("> ").strip())
    return carryovers


def extract_stalled_items(issues_data: dict) -> list:
    """Return stalled/blocked issue dicts from issues.json data.

    Closed issues are excluded — a closed ticket cannot be stalled or block work.
    """
    issues = issues_data.get("issues", []) if isinstance(issues_data, dict) else []
    stalled: list = []
    for issue in issues:
        state = str(issue.get("state", "")).lower()
        if state == "closed":
            continue
        labels = [lbl.get("name", "").lower() for lbl in issue.get("labels", [])]
        if any(l in labels for l in ("blocked", "stalled", "needs-answer")) or state == "stalled":
            stalled.append(issue)
    return stalled

"""decisions_lib.py — load, validate, and enrich per-project decision records.

Human-authored ADR-lite files live under::

    vault/projects/<target>/decisions/YYYY-MM-DD-slug.md

Lookout never invents decisions from PR titles. This module only reads those
files and joins linked issue/PR/sprint state from the latest ``issues.json``
snapshot.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent

VALID_STATUSES = ("proposed", "active", "superseded", "reverted")

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed": frozenset({"active", "reverted"}),
    "active": frozenset({"superseded", "reverted"}),
    "superseded": frozenset({"active"}),
    "reverted": frozenset(),
}

_FM_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


class DecisionError(ValueError):
    """Invalid decision record or status transition."""


def decisions_dir(project_dir: Path) -> Path:
    return project_dir / "decisions"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, text[m.end():]


def _as_int_list(val) -> list[int]:
    if val is None:
        return []
    if isinstance(val, int):
        return [val]
    out: list[int] = []
    for item in val if isinstance(val, list) else []:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _as_str_list(val) -> list[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    return [str(x) for x in val] if isinstance(val, list) else []


def _section(body: str, *prefixes: str) -> str:
    lines = body.splitlines()
    collecting = False
    out: list[str] = []
    for line in lines:
        if re.match(r"^##\s+", line):
            title = re.sub(r"^##\s+", "", line).strip().lower()
            if collecting:
                break
            collecting = any(title.startswith(p.lower()) for p in prefixes)
            continue
        if collecting:
            out.append(line)
    return "\n".join(out).strip()


def _first_para(text: str, max_lines: int = 6) -> str:
    para: list[str] = []
    for ln in text.splitlines():
        if not ln.strip():
            if para:
                break
            continue
        para.append(ln.rstrip())
        if len(para) >= max_lines:
            break
    return "\n".join(para).strip()


def _latest_snapshot(project_dir: Path) -> Path | None:
    raw = project_dir / "raw"
    if not raw.is_dir():
        return None
    snaps = sorted(d for d in raw.iterdir() if d.is_dir())
    return snaps[-1] if snaps else None


def load_gh_index(project_dir: Path) -> dict:
    """Build issue/PR lookup from the latest snapshot issues.json."""
    snap = _latest_snapshot(project_dir)
    index = {"issues": {}, "prs": {}, "sprint_labels": {}}
    if snap is None or not (snap / "issues.json").is_file():
        return index
    try:
        import json
        data = json.loads((snap / "issues.json").read_text(encoding="utf-8"))
    except Exception:
        return index

    for iss in data.get("issues") or []:
        try:
            n = int(iss["number"])
        except (KeyError, TypeError, ValueError):
            continue
        labels = []
        for lab in iss.get("labels") or []:
            name = lab.get("name") if isinstance(lab, dict) else str(lab)
            if name:
                labels.append(name)
        index["issues"][n] = {
            "number": n,
            "state": str(iss.get("state") or "UNKNOWN").upper(),
            "title": iss.get("title") or "",
            "createdAt": iss.get("createdAt") or "",
            "updatedAt": iss.get("updatedAt") or "",
            "closedAt": iss.get("closedAt") or "",
            "labels": labels,
        }
        for name in labels:
            if name.lower().startswith("sprint"):
                index["sprint_labels"].setdefault(name, {"issues": [], "open": 0, "closed": 0})
                index["sprint_labels"][name]["issues"].append(n)
                if index["issues"][n]["state"] == "OPEN":
                    index["sprint_labels"][name]["open"] += 1
                else:
                    index["sprint_labels"][name]["closed"] += 1

    for pr in data.get("prs") or []:
        try:
            n = int(pr["number"])
        except (KeyError, TypeError, ValueError):
            continue
        state = str(pr.get("state") or "UNKNOWN").upper()
        # gh often uses MERGED; keep as-is
        index["prs"][n] = {
            "number": n,
            "state": state,
            "title": pr.get("title") or "",
            "createdAt": pr.get("createdAt") or "",
            "updatedAt": pr.get("updatedAt") or "",
            "mergedAt": pr.get("mergedAt") or "",
            "closedAt": pr.get("closedAt") or "",
        }
    return index


def _sprint_status(name: str, gh: dict) -> str:
    info = (gh.get("sprint_labels") or {}).get(name)
    if not info:
        return "unknown"
    if info["open"] > 0:
        return "active"
    if info["closed"] > 0:
        return "finished"
    return "unknown"


def _implemented_at(decision: dict, gh: dict) -> str:
    """Best-effort implement time: PR mergedAt/updatedAt, else issue closedAt."""
    for n in decision.get("prs") or []:
        pr = (gh.get("prs") or {}).get(n)
        if not pr:
            continue
        if pr["state"] == "MERGED":
            return pr.get("mergedAt") or pr.get("updatedAt") or pr.get("createdAt") or ""
        if pr["state"] == "CLOSED":
            return pr.get("closedAt") or pr.get("updatedAt") or ""
    for n in decision.get("issues") or []:
        iss = (gh.get("issues") or {}).get(n)
        if not iss:
            continue
        if iss["state"] == "CLOSED":
            return iss.get("closedAt") or iss.get("updatedAt") or ""
    return ""


def _issue_created_at(decision: dict, gh: dict) -> str:
    times = []
    for n in decision.get("issues") or []:
        iss = (gh.get("issues") or {}).get(n)
        if iss and iss.get("createdAt"):
            times.append(iss["createdAt"])
    return min(times) if times else ""


def parse_decision_file(path: Path, gh: dict | None = None) -> dict:
    """Parse one decision markdown file into an enriched dict."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _parse_frontmatter(text)
    title_m = _HEADING_RE.search(body)
    title = (title_m.group(1).strip() if title_m else path.stem)

    status = str(fm.get("status") or "proposed").lower()
    if status not in VALID_STATUSES:
        status = "proposed"

    decision = {
        "path": path,
        "stem": path.stem,
        "id": str(fm.get("id") or path.stem),
        "date": str(fm.get("date") or "")[:10],
        "status": status,
        "title": title,
        "targets": _as_str_list(fm.get("targets")),
        "issues": _as_int_list(fm.get("issues")),
        "prs": _as_int_list(fm.get("prs")),
        "sprints": _as_str_list(fm.get("sprints")),
        "supersedes": fm.get("supersedes"),
        "superseded_by": fm.get("superseded_by"),
        "questions": _as_str_list(fm.get("questions")),
        "context": _first_para(_section(body, "context"), 8),
        "decision": _first_para(_section(body, "decision"), 8),
        "consequences": _first_para(_section(body, "consequences"), 6),
        "body": body,
        "issue_states": [],
        "pr_states": [],
        "sprint_states": [],
        "issue_created_at": "",
        "implemented_at": "",
    }

    if gh is None:
        return decision

    for n in decision["issues"]:
        iss = (gh.get("issues") or {}).get(n)
        if iss:
            decision["issue_states"].append(
                {"number": n, "state": iss["state"].lower(), "title": iss["title"]}
            )
        else:
            decision["issue_states"].append(
                {"number": n, "state": "unknown", "title": ""}
            )

    # Infer sprint labels from issues only when frontmatter omitted them.
    if not decision["sprints"]:
        inferred: list[str] = []
        for n in decision["issues"]:
            iss = (gh.get("issues") or {}).get(n)
            if not iss:
                continue
            for lab in iss.get("labels") or []:
                if lab.lower().startswith("sprint") and lab not in inferred:
                    inferred.append(lab)
        decision["sprints"] = inferred

    for n in decision["prs"]:
        pr = (gh.get("prs") or {}).get(n)
        if pr:
            decision["pr_states"].append(
                {"number": n, "state": pr["state"].lower(), "title": pr["title"]}
            )
        else:
            decision["pr_states"].append(
                {"number": n, "state": "unknown", "title": ""}
            )

    for sp in decision["sprints"]:
        decision["sprint_states"].append(
            {"name": sp, "state": _sprint_status(sp, gh)}
        )

    decision["issue_created_at"] = _issue_created_at(decision, gh)
    decision["implemented_at"] = _implemented_at(decision, gh)
    return decision


def load_decisions(project_dir: Path, gh: dict | None = None) -> list[dict]:
    """Load all decision files for a project, enriched when gh index given."""
    if gh is None:
        gh = load_gh_index(project_dir)
    ddir = decisions_dir(project_dir)
    if not ddir.is_dir():
        return []
    files = sorted(ddir.glob("*.md"))
    # Skip README/TEMPLATE
    files = [f for f in files if f.stem.upper() not in ("README", "TEMPLATE")]
    return [parse_decision_file(f, gh) for f in files]


def validate_frontmatter(fm: dict) -> list[str]:
    errors = []
    if not fm.get("id"):
        errors.append("missing id")
    if not fm.get("date"):
        errors.append("missing date")
    status = str(fm.get("status") or "").lower()
    if status and status not in VALID_STATUSES:
        errors.append(f"invalid status {status!r}")
    return errors


def can_transition(current: str, new: str) -> bool:
    if current == new:
        return True
    return new in ALLOWED_TRANSITIONS.get(current, frozenset())


def set_decision_status(
    path: Path,
    new_status: str,
    *,
    superseded_by: str | None = None,
    note_issue: int | None = None,
) -> dict:
    """Flip status in frontmatter; returns updated fm."""
    if new_status not in VALID_STATUSES:
        raise DecisionError(f"Invalid status {new_status!r}")
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    cur = str(fm.get("status") or "proposed").lower()
    if not can_transition(cur, new_status):
        raise DecisionError(
            f"Cannot transition {cur!r} → {new_status!r}; "
            f"allowed: {sorted(ALLOWED_TRANSITIONS.get(cur, frozenset()))}"
        )
    fm["status"] = new_status
    if superseded_by:
        fm["superseded_by"] = superseded_by
    if note_issue is not None:
        issues = _as_int_list(fm.get("issues"))
        if note_issue not in issues:
            issues.append(note_issue)
            fm["issues"] = issues
    # Rewrite file
    dump = yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip()
    path.write_text(f"---\n{dump}\n---\n{body.lstrip()}", encoding="utf-8")
    return fm


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")[:50]


def next_decision_id(project_dir: Path, prefix: str) -> str:
    """Return next ID like VR-D3 given existing VR-D* files."""
    prefix = prefix.upper().rstrip("-")
    nums = []
    for d in load_decisions(project_dir, gh={}):
        m = re.match(rf"^{re.escape(prefix)}-D(\d+)$", str(d["id"]), re.I)
        if m:
            nums.append(int(m.group(1)))
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}-D{n}"


def create_decision(
    project_dir: Path,
    *,
    title: str,
    target: str,
    prefix: str,
    issues: list[int] | None = None,
    prs: list[int] | None = None,
    sprints: list[str] | None = None,
    status: str = "proposed",
    date: str | None = None,
) -> Path:
    """Scaffold a new decision markdown file."""
    if status not in VALID_STATUSES:
        raise DecisionError(f"Invalid status {status!r}")
    ddir = decisions_dir(project_dir)
    ddir.mkdir(parents=True, exist_ok=True)
    did = next_decision_id(project_dir, prefix)
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = slugify(title) or "decision"
    path = ddir / f"{date}-{slug}.md"
    if path.exists():
        path = ddir / f"{date}-{slug}-{did.lower().replace('-', '')}.md"
    fm = {
        "id": did,
        "date": date,
        "status": status,
        "targets": [target],
        "issues": issues or [],
        "prs": prs or [],
        "sprints": sprints or [],
        "supersedes": None,
        "superseded_by": None,
        "questions": [],
    }
    body = (
        f"# {did} — {title}\n\n"
        "## Context\n\n"
        "_Why this came up._\n\n"
        "## Decision\n\n"
        f"{title}\n\n"
        "## Consequences\n\n"
        "_What follows from this choice._\n\n"
        "## Links\n\n"
    )
    for n in issues or []:
        body += f"- Issue: #{n}\n"
    for n in prs or []:
        body += f"- PR: #{n}\n"
    for s in sprints or []:
        body += f"- Sprint: `{s}`\n"
    dump = yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip()
    path.write_text(f"---\n{dump}\n---\n\n{body}", encoding="utf-8")
    return path


def format_status_cell(decision: dict) -> str:
    """Compact status badges for a timeline table cell."""
    bits = [f"`{decision['status']}`"]
    for iss in decision.get("issue_states") or []:
        bits.append(f"#{iss['number']} {iss['state']}")
    for pr in decision.get("pr_states") or []:
        bits.append(f"PR #{pr['number']} {pr['state']}")
    for sp in decision.get("sprint_states") or []:
        bits.append(f"{sp['name']} {sp['state']}")
    return " · ".join(bits)


def sort_key_decided(d: dict) -> str:
    return d.get("date") or ""


def sort_key_issue_created(d: dict) -> str:
    return d.get("issue_created_at") or ""


def sort_key_implemented(d: dict) -> str:
    return d.get("implemented_at") or ""

"""
project_changelog.py — per-target PR / git / feature history note.

Writes vault/projects/<target>/changelog.md from the latest snapshot's
issues.json (merged PRs) and gitlog.txt, then joins PR titles' `#N` references
to atlas notes that mention the same issue.

Lookout does not invent decisions. The human-owned vault/decisions.md is
linked when it has content; otherwise the note says so.

Usage:
    python project_changelog.py <target> [--vault <dir>]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_ISSUE_RE = re.compile(r"#(\d+)")
_LOG_LINE_RE = re.compile(r"^([0-9a-f]{7,})\s+(.*)$")
_MAX_PRS = 40
_MAX_COMMITS = 30


def _load_github_slug(target: str, targets_yaml: Path | None = None) -> str:
    path = targets_yaml or TARGETS_YAML
    try:
        data = yaml.safe_load(path.read_text()) or {}
        return (data.get("targets", {}).get(target) or {}).get("github", "")
    except Exception:
        return ""


def _latest_snapshot(project_dir: Path) -> Path | None:
    raw = project_dir / "raw"
    if not raw.is_dir():
        return None
    dirs = sorted(d for d in raw.iterdir() if d.is_dir())
    return dirs[-1] if dirs else None


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _pr_url(slug: str, number) -> str:
    if slug:
        return f"https://github.com/{slug}/pull/{number}"
    return f"#{number}"


def _issue_url(slug: str, number) -> str:
    if slug:
        return f"https://github.com/{slug}/issues/{number}"
    return f"#{number}"


def _merged_prs(payload: dict) -> list[dict]:
    prs = payload.get("prs")
    if not isinstance(prs, list):
        # Older snapshots stuffed PRs into issues[] with state MERGED.
        prs = [
            i for i in payload.get("issues", [])
            if isinstance(i, dict) and str(i.get("state", "")).upper() == "MERGED"
        ]
    else:
        prs = [p for p in prs if isinstance(p, dict)]
    merged = [
        p for p in prs
        if str(p.get("state", "")).upper() in ("MERGED", "CLOSED")
    ]
    merged.sort(key=lambda p: p.get("updatedAt") or p.get("createdAt") or "", reverse=True)
    return merged


def _atlas_issue_index(project_dir: Path, target: str) -> dict[str, list[str]]:
    """Map issue number (as str) → list of atlas wikilink targets."""
    index: dict[str, list[str]] = {}
    atlas_dir = project_dir / "atlas"
    if not atlas_dir.is_dir():
        return index
    for path in sorted(atlas_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = f"projects/{target}/atlas/{path.stem}"
        for num in _ISSUE_RE.findall(text):
            index.setdefault(num, [])
            if rel not in index[num]:
                index[num].append(rel)
    return index


def _parse_gitlog(text: str) -> list[tuple[str, str]]:
    commits = []
    in_log = False
    for line in text.splitlines():
        if line.strip() == "=== log ===":
            in_log = True
            continue
        if in_log and line.startswith("==="):
            break
        if not in_log:
            continue
        m = _LOG_LINE_RE.match(line.strip())
        if m:
            commits.append((m.group(1), m.group(2)))
    return commits[:_MAX_COMMITS]


def _md_cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def generate_changelog(target: str, vault_dir: Path | None = None) -> Path:
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    project_dir = vault_dir / "projects" / target
    project_dir.mkdir(parents=True, exist_ok=True)
    snapshot = _latest_snapshot(project_dir)
    slug = _load_github_slug(target)
    atlas_idx = _atlas_issue_index(project_dir, target)

    lines = [
        f"# {target} — Changelog\n",
        "Merged PRs and recent git history from the latest snapshot, "
        "joined to atlas notes when a PR title cites `#N` and that issue "
        "appears on a feature page. Decisions are human-owned and are not "
        "inferred from commit messages.\n",
    ]

    payload = {}
    if snapshot and (snapshot / "issues.json").exists():
        payload = _load_json(snapshot / "issues.json")

    prs = _merged_prs(payload)[:_MAX_PRS]
    lines.append("## Pull requests\n")
    if prs:
        lines.append("| Date | PR | Title | Issue | Feature |")
        lines.append("|---|---|---|---|---|")
        for pr in prs:
            number = pr.get("number", "")
            title = _md_cell(pr.get("title", ""))
            date = (pr.get("updatedAt") or pr.get("createdAt") or "")[:10]
            url = _pr_url(slug, number)
            pr_cell = f"[#{number}]({url})" if slug else f"#{number}"
            cited = _ISSUE_RE.findall(pr.get("title", ""))
            if cited:
                issue_cell = ", ".join(
                    f"[#{n}]({_issue_url(slug, n)})" if slug else f"#{n}"
                    for n in cited
                )
            else:
                issue_cell = "—"
            features: list[str] = []
            for n in cited:
                for rel in atlas_idx.get(n, []):
                    features.append(f"[[{rel}]]")
            feat_cell = ", ".join(features) if features else "—"
            lines.append(
                f"| {date} | {pr_cell} | {title} | {issue_cell} | {feat_cell} |"
            )
        lines.append("")
        if len(_merged_prs(payload)) > _MAX_PRS:
            lines.append(f"_Showing the {_MAX_PRS} most recently updated PRs._\n")
    else:
        lines.append("_No merged or closed PRs in the latest snapshot._\n")

    lines.append("## Git history\n")
    gitlog = ""
    if snapshot and (snapshot / "gitlog.txt").exists():
        gitlog = (snapshot / "gitlog.txt").read_text(encoding="utf-8", errors="replace")
    commits = _parse_gitlog(gitlog)
    if commits:
        lines.append("| SHA | Subject |")
        lines.append("|---|---|")
        for sha, subject in commits:
            cited = _ISSUE_RE.findall(subject)
            extra = ""
            if cited:
                feats = []
                for n in cited:
                    feats.extend(f"[[{rel}]]" for rel in atlas_idx.get(n, []))
                if feats:
                    extra = " — " + ", ".join(dict.fromkeys(feats))
            lines.append(f"| `{sha}` | {_md_cell(subject)}{extra} |")
        lines.append("")
    else:
        lines.append("_No git log in the latest snapshot._\n")

    lines.append("## Decisions\n")
    decisions = vault_dir / "decisions.md"
    body = ""
    if decisions.exists():
        body = decisions.read_text(encoding="utf-8", errors="replace").strip()
    if body and body not in ("# Decisions", "# Decisions\n"):
        lines.append("Fleet decisions: [[decisions]].\n")
    else:
        lines.append(
            "No decisions recorded yet. That file is human-owned "
            "(`vault/decisions.md`) — the pipeline will not fill it in from "
            "PR titles.\n"
        )

    out = project_dir / "changelog.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate changelog.md for a target")
    parser.add_argument("target")
    parser.add_argument("--vault", default=str(REPO_ROOT / "vault"))
    args = parser.parse_args()
    out = generate_changelog(args.target, Path(args.vault))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

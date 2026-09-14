"""project_decisions_view.py — Decision Hub (readable SoT).

Writes vault/projects/<target>/decisions-view.md with:
  - status counts
  - three timelines (decided / issue created / implemented)
  - per-decision cards with GitHub status badges

Machine-owned whole file. Decision markdown under decisions/ stays human-owned.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

import decisions_lib as dl  # noqa: E402


def _md_cell(text: str) -> str:
    return (text or "—").replace("|", "\\|").replace("\n", " ")


def _anchor(decision_id: str) -> str:
    return dl.slugify(decision_id) or "decision"


def _short_date(iso: str) -> str:
    if not iso:
        return "—"
    return iso[:10]


def _timeline_table(
    decisions: list[dict],
    *,
    sort_key,
    empty_label: str,
) -> list[str]:
    lines = [
        "| Date | ID | Decision | Status · GitHub |",
        "|---|---|---|---|",
    ]
    ranked = sorted(
        decisions,
        key=lambda d: sort_key(d) or "",
        reverse=True,
    )
    # Put undated/unimplemented at the end when sorting by that axis
    dated = [d for d in ranked if sort_key(d)]
    undated = [d for d in ranked if not sort_key(d)]
    rows = dated + undated
    if not rows:
        lines.append(f"| — | — | {empty_label} | — |")
        return lines
    for d in rows:
        date = _short_date(sort_key(d) or d.get("date") or "")
        aid = _anchor(d["id"])
        title = d["title"]
        # Strip leading "VR-D1 — " duplication if already in title
        link = f"[{d['id']}](#{aid})"
        lines.append(
            f"| {date} | {link} | {_md_cell(title)} | "
            f"{_md_cell(dl.format_status_cell(d))} |"
        )
    lines.append("")
    return lines


def _counts(decisions: list[dict]) -> dict[str, int]:
    counts = {s: 0 for s in dl.VALID_STATUSES}
    for d in decisions:
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    return counts


def _card(d: dict, target: str) -> list[str]:
    lines = [f"## {d['id']}\n", f"**{d['title']}**\n"]
    lines.append(
        f"**Status:** `{d['status']}` · **Decided:** {d.get('date') or '—'}\n"
    )
    if d.get("supersedes"):
        lines.append(f"**Supersedes:** `{d['supersedes']}`\n")
    if d.get("superseded_by"):
        lines.append(f"**Superseded by:** `{d['superseded_by']}`\n")

    lines.append("### GitHub links\n")
    if d.get("issue_states"):
        for iss in d["issue_states"]:
            title = f" — {iss['title']}" if iss.get("title") else ""
            lines.append(f"- Issue #{iss['number']}: `{iss['state']}`{title}")
        lines.append("")
    else:
        lines.append("_No issues linked._\n")
    if d.get("pr_states"):
        for pr in d["pr_states"]:
            title = f" — {pr['title']}" if pr.get("title") else ""
            lines.append(f"- PR #{pr['number']}: `{pr['state']}`{title}")
        lines.append("")
    if d.get("sprint_states"):
        for sp in d["sprint_states"]:
            lines.append(f"- Sprint `{sp['name']}`: `{sp['state']}`")
        lines.append("")

    lines.append("### Clocks\n")
    lines.append(f"- Decided (planning): `{d.get('date') or '—'}`")
    lines.append(
        f"- Issue created: `{_short_date(d.get('issue_created_at') or '')}`"
    )
    lines.append(
        f"- Implemented: `{_short_date(d.get('implemented_at') or '')}`"
    )
    lines.append("")

    if d.get("context"):
        lines.append("### Context\n")
        lines.append(d["context"])
        lines.append("")
    if d.get("decision"):
        lines.append("### Decision\n")
        lines.append(d["decision"])
        lines.append("")
    if d.get("consequences"):
        lines.append("### Consequences\n")
        lines.append(d["consequences"])
        lines.append("")

    rel = f"projects/{target}/decisions/{d['stem']}"
    lines.append(f"_(source: [[{rel}|decisions/{d['stem']}.md]])_\n")
    return lines


def generate_decisions_view(target: str, vault_dir: Path | None = None) -> Path:
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    project_dir = vault_dir / "projects" / target
    project_dir.mkdir(parents=True, exist_ok=True)

    gh = dl.load_gh_index(project_dir)
    decisions = dl.load_decisions(project_dir, gh)
    counts = _counts(decisions)

    lines = [
        f"# {target} — Decisions\n",
        "History of product/architecture choices for this project. "
        "Human-authored under `decisions/`; this page joins GitHub issue/PR/"
        "sprint **status from the latest snapshot**. Lookout does not invent "
        "decisions from PR titles.\n",
        "## Summary\n",
        f"- **{counts.get('active', 0)}** active · "
        f"**{counts.get('proposed', 0)}** proposed · "
        f"**{counts.get('superseded', 0)}** superseded · "
        f"**{counts.get('reverted', 0)}** reverted "
        f"(total {len(decisions)})\n",
        "## Contents\n",
        "- [Timeline by decided date](#timeline-by-decided-date)",
        "- [Timeline by issue created](#timeline-by-issue-created)",
        "- [Timeline by implemented](#timeline-by-implemented)",
        "- [Decision cards](#decision-cards)",
        "",
    ]

    if not decisions:
        lines.append(
            "_No decision files yet. Add "
            f"`vault/projects/{target}/decisions/YYYY-MM-DD-slug.md` "
            "or run `bin/lookout decide <target> --title \"...\"`._\n"
        )
    else:
        lines.append("## Timeline by decided date\n")
        lines.append("Sorted by planning markdown `date:` (newest first).\n")
        lines.extend(
            _timeline_table(
                decisions,
                sort_key=dl.sort_key_decided,
                empty_label="_No decisions._",
            )
        )

        lines.append("## Timeline by issue created\n")
        lines.append(
            "Sorted by earliest linked issue `createdAt` from the snapshot. "
            "Rows without a known issue date sink to the bottom.\n"
        )
        lines.extend(
            _timeline_table(
                decisions,
                sort_key=dl.sort_key_issue_created,
                empty_label="_No decisions._",
            )
        )

        lines.append("## Timeline by implemented\n")
        lines.append(
            "Sorted by linked PR merge/close time, else issue closed time. "
            "Unimplemented decisions sink to the bottom.\n"
        )
        lines.extend(
            _timeline_table(
                decisions,
                sort_key=dl.sort_key_implemented,
                empty_label="_No decisions._",
            )
        )

        lines.append("## Decision cards\n")
        # Newest decided first for cards
        for d in sorted(decisions, key=dl.sort_key_decided, reverse=True):
            lines.extend(_card(d, target))

    out = project_dir / "decisions-view.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate decisions-view.md")
    parser.add_argument("target")
    parser.add_argument("--vault", default=str(REPO_ROOT / "vault"))
    args = parser.parse_args()
    out = generate_decisions_view(args.target, Path(args.vault))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

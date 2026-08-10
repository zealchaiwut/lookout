"""
discuss_pack.py — discuss pack generator for Lookout.

Bundles open questions, capability card, situation snapshot, and cited
drift/atlas excerpts for a target or idea into a focused discussion pack.

Output: vault/packs/<YYYY-MM-DD>-discuss-<slug>.md

Usage:
  python discuss_pack.py <target-or-idea> [--vault <dir>]

Exit codes:
  0 — success
  1 — unknown target or idea
"""
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"


class UnknownArgumentError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Helpers: targets.yaml
# ---------------------------------------------------------------------------

def _load_valid_targets(targets_yaml: Path) -> set:
    with open(targets_yaml) as f:
        data = yaml.safe_load(f)
    return set(data.get("targets", {}).keys())


# ---------------------------------------------------------------------------
# Helpers: situation.md extractors (same logic as pack.py)
# ---------------------------------------------------------------------------

def _extract_section_first_line(content: str, section_header: str) -> str:
    m = re.search(
        r"^" + re.escape(section_header) + r"\s*\n(.*?)(?=\n#+ |\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        return ""
    for line in m.group(1).splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("_("):
            return stripped
    return ""


def _extract_one_liner(content: str) -> str:
    return _extract_section_first_line(content, "## One-liner")


def _extract_capacity(content: str) -> str:
    return _extract_section_first_line(content, "## Capacity")


# ---------------------------------------------------------------------------
# Helpers: questions
# ---------------------------------------------------------------------------

def _load_open_questions(project_dir: Path) -> list:
    """Return open question dicts from questions.json."""
    path = project_dir / "questions.json"
    if not path.exists():
        return []
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        return [
            q for q in data.get("questions", {}).values()
            if q.get("status") == "open"
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Helpers: drift excerpts
# ---------------------------------------------------------------------------

def _parse_drift_sections(drift_md_path: Path) -> list:
    """Parse drift.md into a list of (claim, full_section_text) tuples."""
    if not drift_md_path.exists():
        return []
    text = drift_md_path.read_text(encoding="utf-8")
    sections = []
    current_lines = []
    current_claim = ""
    current_evidence = ""
    in_flag = False

    for line in text.splitlines():
        if re.match(r"^## Flag \d+:", line):
            if in_flag and current_claim:
                sections.append({
                    "claim": current_claim,
                    "evidence_path": current_evidence,
                    "text": "\n".join(current_lines).strip(),
                })
            current_lines = [line]
            current_claim = ""
            current_evidence = ""
            in_flag = True
        elif in_flag:
            current_lines.append(line)
            if line.startswith("**Claim:**"):
                current_claim = line.removeprefix("**Claim:**").strip()
            elif line.startswith("**Evidence:**"):
                current_evidence = line.removeprefix("**Evidence:**").strip()
        else:
            pass

    if in_flag and current_claim:
        sections.append({
            "claim": current_claim,
            "evidence_path": current_evidence,
            "text": "\n".join(current_lines).strip(),
        })
    return sections


def _collect_cited_excerpts(open_questions: list, drift_md_path: Path) -> list:
    """Return drift section texts cited by at least one open question."""
    if not open_questions:
        return []

    open_signal_texts = {q.get("signal_text", "") for q in open_questions}
    open_evidences = {q.get("evidence", "") for q in open_questions}

    sections = _parse_drift_sections(drift_md_path)
    cited = []
    for section in sections:
        claim = section["claim"]
        evidence_path = section["evidence_path"]
        drift_signal = f"drift:{claim[:80]}"

        # Cited if: signal_text matches OR evidence_path matches a question's evidence
        if drift_signal in open_signal_texts or evidence_path in open_evidences:
            cited.append(section["text"])
    return cited


# ---------------------------------------------------------------------------
# Helpers: ideas
# ---------------------------------------------------------------------------

def _find_idea_note(argument: str, vault_dir: Path) -> Path | None:
    """Return path to idea note if argument resolves to one, else None."""
    ideas_dir = vault_dir / "ideas"
    if not ideas_dir.exists():
        return None
    candidate = ideas_dir / f"{argument}.md"
    return candidate if candidate.exists() else None


def _extract_affected_targets(idea_content: str, valid_targets: set) -> list:
    """Return list of valid target names mentioned in the idea note."""
    found = []
    for target in valid_targets:
        pattern = re.compile(re.escape(target), re.IGNORECASE)
        if pattern.search(idea_content):
            found.append(target)
    return found


# ---------------------------------------------------------------------------
# Core: target discuss pack
# ---------------------------------------------------------------------------

def _render_question_block(q: dict) -> list:
    lines = []
    qid = q.get("id", "?")
    text = q.get("text", "")
    evidence = q.get("evidence", "")
    options = q.get("options", [])

    lines.append(f"### {qid}: {text}")
    lines.append("")
    if evidence:
        lines.append(f"**Evidence:** {evidence}")
        lines.append("")
    if options:
        lines.append("**Options:**")
        for opt in options:
            lines.append(f"- {opt}")
        lines.append("")
    return lines


def _render_target_section(target: str, vault_dir: Path) -> list:
    """Render situation + capability + open questions + excerpts for a target."""
    lines = []
    project_dir = vault_dir / "projects" / target

    # Situation
    lines.append("---")
    lines.append("")
    lines.append(f"## {target} — Situation")
    lines.append("")
    situation_path = project_dir / "situation.md"
    if situation_path.exists():
        content = situation_path.read_text(encoding="utf-8")
        one_liner = _extract_one_liner(content)
        capacity = _extract_capacity(content)
        if one_liner:
            lines.append(one_liner)
        if capacity:
            lines.append(f"Capacity: {capacity}")
    lines.append("")

    # Capability card
    lines.append("---")
    lines.append("")
    lines.append(f"## {target} — Capability Card")
    lines.append("")
    cap_path = project_dir / "capability.md"
    if cap_path.exists():
        lines.append(cap_path.read_text(encoding="utf-8").rstrip())
    lines.append("")

    # Open questions
    open_qs = _load_open_questions(project_dir)
    lines.append("---")
    lines.append("")
    lines.append(f"## {target} — Open Questions ({len(open_qs)})")
    lines.append("")
    for q in open_qs:
        lines.extend(_render_question_block(q))

    # Cited excerpts
    drift_path = project_dir / "drift.md"
    cited = _collect_cited_excerpts(open_qs, drift_path)
    if cited:
        lines.append("---")
        lines.append("")
        lines.append(f"## {target} — Referenced Excerpts")
        lines.append("")
        for excerpt in cited:
            lines.append(excerpt)
            lines.append("")

    return lines


# ---------------------------------------------------------------------------
# Core: idea discuss pack
# ---------------------------------------------------------------------------

def _render_idea_section(idea_content: str) -> list:
    lines = []
    lines.append("---")
    lines.append("")
    lines.append("## Idea Note")
    lines.append("")
    lines.append(idea_content.rstrip())
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_discuss_pack(
    argument: str,
    vault_dir: Path,
    targets_yaml: Path = None,
    now: datetime = None,
) -> Path:
    """Generate a discuss pack for a target or idea and return its path.

    Raises UnknownArgumentError if argument is neither a known target nor a
    resolvable idea in the vault.
    """
    if targets_yaml is None:
        targets_yaml = TARGETS_YAML
    if now is None:
        now = datetime.now(timezone.utc)

    valid_targets = _load_valid_targets(targets_yaml)

    date_str = now.strftime("%Y-%m-%d")
    pack_dir = vault_dir / "packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack_path = pack_dir / f"{date_str}-discuss-{argument}.md"

    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = []

    if argument in valid_targets:
        # Target pack
        lines.append(f"# Discuss Pack: {argument}")
        lines.append("")
        lines.append(f"Generated: {timestamp}")
        lines.append(f"Target: {argument}")
        lines.append("")
        lines.extend(_render_target_section(argument, vault_dir))

    else:
        # Check if argument is an idea
        idea_path = _find_idea_note(argument, vault_dir)
        if idea_path is None:
            msg = f"cannot resolve '{argument}' — not a known target or idea in the vault"
            print(f"Error: {msg}", file=sys.stderr)
            raise UnknownArgumentError(msg)

        idea_content = idea_path.read_text(encoding="utf-8")
        affected = _extract_affected_targets(idea_content, valid_targets)

        lines.append(f"# Discuss Pack: {argument} (idea)")
        lines.append("")
        lines.append(f"Generated: {timestamp}")
        lines.append(f"Idea: {argument}")
        lines.append("")
        lines.extend(_render_idea_section(idea_content))

        if affected:
            lines.append("---")
            lines.append("")
            lines.append("## Affected Target Assessments")
            lines.append("")
            for target in affected:
                lines.extend(_render_target_section(target, vault_dir))

    pack_path.write_text("\n".join(lines) + "\n")
    return pack_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a discuss pack for a target or idea"
    )
    parser.add_argument("argument", help="Target name or idea slug")
    parser.add_argument(
        "--vault",
        default=str(REPO_ROOT / "vault"),
        help="Path to vault directory",
    )
    args = parser.parse_args()

    try:
        pack_path = generate_discuss_pack(
            argument=args.argument,
            vault_dir=Path(args.vault),
        )
        print(f"Discuss pack written: {pack_path}")
    except UnknownArgumentError:
        sys.exit(1)


if __name__ == "__main__":
    main()

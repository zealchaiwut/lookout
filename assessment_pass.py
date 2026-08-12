"""
assessment_pass.py — Idea assessment pass.

Scans vault/ideas/ for ideas that need assessment (new or human-edited since
their `assessed` date), generates Assessment sections grounded in atlas notes
and capability cards found in the vault, and writes results back.

Convention (DESIGN.md §9):
  - At most 3 ideas are assessed per run (cap enforced in select step)
  - Each Assessment section has 5 fields: Already exists / Must be built /
    Effort / Dependencies / Suggested first slice
  - Every claim cites a source by wikilink; unknowns become numbered open questions
  - No new fields are written to frontmatter until assessment completes without errors

Usage:
  python assessment_pass.py [--ideas-dir <path>] [--vault <path>]

Exit codes:
  0 — pass completed (0 or more ideas assessed)
  1 — fatal error (cannot read ideas directory)
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

import llm

REPO_ROOT = Path(__file__).parent
_DEFAULT_IDEAS_DIR = REPO_ROOT / "vault" / "ideas"
_DEFAULT_VAULT_DIR = REPO_ROOT / "vault"

MACHINE_DELIMITER = "<!-- BEGIN MACHINE ASSESSMENT -->"
MACHINE_END = "<!-- END MACHINE ASSESSMENT -->"
MAX_PER_RUN = 3

_FM_RE = re.compile(r"^---\n(.*?)---\n", re.DOTALL)
_KV_RE = re.compile(r"^(\w+):\s*(.*)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Frontmatter parsing and manipulation
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict | None:
    m = _FM_RE.match(text)
    if not m:
        return None
    fm_body = m.group(1)
    result: dict = {}
    for kv in _KV_RE.finditer(fm_body):
        key = kv.group(1)
        val = kv.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                result[key] = [
                    x.strip().strip("'\"") for x in inner.split(",") if x.strip()
                ]
        else:
            result[key] = val if val not in ("null", "~", "") else None
    return result


def _write_frontmatter_field(text: str, field: str, value: str) -> str:
    """Update an existing frontmatter field, or add it before the closing ---."""
    m = _FM_RE.match(text)
    if not m:
        return text
    fm_body = m.group(1)
    new_fm_body, count = re.subn(
        rf"^{re.escape(field)}:.*$", f"{field}: {value}", fm_body,
        flags=re.MULTILINE,
    )
    if not count:
        new_fm_body = fm_body.rstrip("\n") + f"\n{field}: {value}\n"
    return f"---\n{new_fm_body}---\n" + text[m.end():]


def _replace_assessment_block(text: str, new_assessment: str) -> str:
    """Replace the content between MACHINE_DELIMITER and MACHINE_END."""
    start = text.find(MACHINE_DELIMITER)
    end = text.find(MACHINE_END)
    block = f"{MACHINE_DELIMITER}\n{new_assessment}\n{MACHINE_END}\n"
    if start == -1:
        return text.rstrip("\n") + f"\n\n{block}"
    if end == -1:
        return text[:start] + block
    return (
        text[:start]
        + block
        + text[end + len(MACHINE_END):].lstrip("\n")
    )


# ---------------------------------------------------------------------------
# Vault lookups
# ---------------------------------------------------------------------------

def _is_registered(target: str, vault_dir: Path) -> bool:
    return (vault_dir / "projects" / target).is_dir()


def _get_capability_card_path(target: str, vault_dir: Path) -> Path | None:
    cap = vault_dir / "projects" / target / "capability.md"
    return cap if cap.exists() else None


def _get_atlas_note_stems(target: str, vault_dir: Path) -> list[str]:
    """Return sorted list of atlas note stems (excluding index.md)."""
    atlas_dir = vault_dir / "projects" / target / "atlas"
    if not atlas_dir.is_dir():
        return []
    return sorted(
        f.stem for f in atlas_dir.glob("*.md") if f.name != "index.md"
    )


def _extract_freeform(text: str) -> str:
    """Return the human-written portion of an idea note (above the delimiter)."""
    body = _FM_RE.sub("", text, count=1)
    return body.split(MACHINE_DELIMITER)[0].strip()


def _rank_atlas_notes(
    idea_text: str, target: str, atlas_notes: list[str], limit: int = 3
) -> list[str]:
    """Pick the atlas notes most relevant to `idea_text`, capped at `limit`.

    Without LLM enrichment there is no way to judge relevance, so the first
    `limit` notes alphabetically are returned — the historical behaviour. With
    enrichment on, the model chooses instead, and its answer is intersected with
    the real slug list so a hallucinated note can never reach the assessment
    (DESIGN.md §9: every wikilink must resolve to a real file).
    """
    deterministic = atlas_notes[:limit]
    if len(atlas_notes) <= limit or not idea_text.strip():
        return deterministic

    prompt = (
        "An idea has been proposed for a software project. Below is the idea, "
        f"then every feature note that exists in the `{target}` atlas.\n\n"
        f"Choose at most {limit} notes that are genuinely relevant to the idea — "
        "features the idea would build on, extend, or overlap with. If fewer "
        f"than {limit} are relevant, return fewer. If none are relevant, return "
        "nothing at all.\n\n"
        "Output only the chosen slugs, one per line, copied exactly as written "
        "below. No numbering, no explanation, no other text.\n\n"
        f"IDEA:\n{idea_text[:3000]}\n\n"
        "ATLAS NOTES:\n" + "\n".join(atlas_notes) + "\n"
    )
    raw = llm.ask(prompt, fallback="", purpose=f"assessment:{target}")
    if not raw:
        return deterministic

    valid = set(atlas_notes)
    picked: list[str] = []
    for line in raw.splitlines():
        slug = line.strip().strip("-*` ").strip()
        if slug in valid and slug not in picked:
            picked.append(slug)
        if len(picked) >= limit:
            break
    return picked if picked else deterministic


# ---------------------------------------------------------------------------
# Selection logic (cap + assessed-date skip)
# ---------------------------------------------------------------------------

def _idea_needs_assessment(idea_path: Path, fm: dict) -> bool:
    """True if idea is new or was edited after its assessed date."""
    assessed = fm.get("assessed")
    if assessed is None:
        return True
    try:
        assessed_date = datetime.date.fromisoformat(str(assessed))
        # Any mtime strictly after the end of the assessed date signals a human edit
        cutoff = datetime.datetime.combine(
            assessed_date + datetime.timedelta(days=1),
            datetime.time.min,
        ).timestamp()
        return idea_path.stat().st_mtime > cutoff
    except Exception:
        return True


def select_ideas_for_assessment(
    ideas_dir: Path,
    vault_dir: Path | None = None,
    today: datetime.date | None = None,
) -> list[Path]:
    """Return up to MAX_PER_RUN idea paths that need assessment.

    Cap is enforced here — before any LLM or content-generation calls.
    """
    idea_files = sorted(f for f in ideas_dir.glob("*.md") if f.name != "index.md")
    selected: list[Path] = []
    for idea_path in idea_files:
        if len(selected) >= MAX_PER_RUN:
            break
        try:
            text = idea_path.read_text(encoding="utf-8")
        except Exception:
            continue
        fm = _parse_frontmatter(text)
        if fm is None:
            continue
        if _idea_needs_assessment(idea_path, fm):
            selected.append(idea_path)
    return selected


# ---------------------------------------------------------------------------
# Assessment generation
# ---------------------------------------------------------------------------

def build_assessment(
    idea_path: Path,
    vault_dir: Path,
    today: datetime.date | None = None,
) -> str:
    """Build an Assessment section for the given idea, grounded in vault data.

    Returns the full text of the Assessment block (to be placed between
    MACHINE_DELIMITER and MACHINE_END).  Raises ValueError if the idea note
    cannot be parsed.
    """
    if today is None:
        today = datetime.date.today()

    text = idea_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    if fm is None:
        raise ValueError(f"Cannot parse frontmatter: {idea_path}")

    targets: list[str] = fm.get("targets") or []
    idea_text = _extract_freeform(text)
    open_questions: list[str] = []
    q_counter = 0

    def next_q(question_text: str) -> str:
        nonlocal q_counter
        q_counter += 1
        q = f"Q{q_counter}: {question_text}"
        open_questions.append(q)
        return q

    already_exists_parts: list[str] = []
    must_be_built_parts: list[str] = []
    dependency_parts: list[str] = []
    first_atlas_ref: str | None = None

    for target in targets:
        if not _is_registered(target, vault_dir):
            already_exists_parts.append(
                f"`{target}` is not registered in vault/projects/"
            )
            next_q(f"Is `{target}` planned for the atlas?")
            continue

        # Target is registered — look for capability card and atlas notes
        cap_path = _get_capability_card_path(target, vault_dir)
        atlas_notes = _get_atlas_note_stems(target, vault_dir)

        if cap_path is not None:
            link = f"[[projects/{target}/capability]]"
            already_exists_parts.append(link)
            if target not in dependency_parts:
                dependency_parts.append(f"[[projects/{target}/capability]]")

        if atlas_notes:
            relevant = _rank_atlas_notes(idea_text, target, atlas_notes)
            for note_stem in relevant:
                link = f"[[projects/{target}/atlas/{note_stem}]]"
                already_exists_parts.append(link)
                if first_atlas_ref is None:
                    first_atlas_ref = link
            if target not in dependency_parts:
                dependency_parts.append(f"[[projects/{target}]]")
        elif cap_path is None:
            # Registered but no capability card and no atlas
            must_be_built_parts.append(f"capability card for `{target}`")
            next_q(
                f"What capabilities does `{target}` expose? "
                f"(registered but no capability card or atlas found)"
            )

    # Effort heuristic
    if not targets:
        effort = "S"
    elif must_be_built_parts and not already_exists_parts:
        effort = "L"
    elif must_be_built_parts:
        effort = "M"
    elif open_questions:
        effort = "M"
    else:
        effort = "S"

    already_str = (
        "; ".join(already_exists_parts) if already_exists_parts else "—"
    )
    must_str = (
        "; ".join(must_be_built_parts) if must_be_built_parts else "—"
    )
    deps_str = (
        "; ".join(dependency_parts) if dependency_parts else "—"
    )

    # Suggested first slice
    if first_atlas_ref is not None:
        first_slice = f"Verify scope against {first_atlas_ref}."
    elif targets and _is_registered(targets[0], vault_dir):
        # A registered target with no atlas note to check against. If it already
        # has a capability card, the missing piece is the atlas, not the card —
        # suggesting "add a capability card" that exists reads as a stale note.
        if _get_capability_card_path(targets[0], vault_dir) is not None:
            first_slice = (
                f"Seed the atlas for `{targets[0]}` "
                f"(`python atlas_seed.py {targets[0]}`), then re-assess."
            )
        else:
            first_slice = f"Add capability card for `{targets[0]}`."
    elif targets:
        q_text = next_q(f"What is the first testable step for `{targets[0]}`?")
        first_slice = f"({q_text})"
    else:
        q_text = next_q("What is the first independently testable step?")
        first_slice = f"({q_text})"

    lines = [
        "## Assessment\n",
        "\n",
        f"**Already exists:** {already_str}\n",
        f"**Must be built:** {must_str}\n",
        f"**Effort:** {effort}\n",
        f"**Dependencies:** {deps_str}\n",
        f"**Suggested first slice:** {first_slice}\n",
    ]
    if open_questions:
        lines.append("\n")
        for q in open_questions:
            lines.append(f"{q}\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Full pass
# ---------------------------------------------------------------------------

def run_assessment_pass(
    ideas_dir: Path,
    vault_dir: Path,
    today: datetime.date | None = None,
) -> list[Path]:
    """Select ideas, build assessments, and write results back atomically.

    Returns the list of idea paths that were successfully assessed.
    At most MAX_PER_RUN ideas are processed per call.
    """
    if today is None:
        today = datetime.date.today()

    candidates = select_ideas_for_assessment(ideas_dir, vault_dir, today)
    if not candidates:
        print(
            "Assessment pass: 0 ideas to assess. Skipping.", flush=True
        )
        return []

    assessed: list[Path] = []
    for idea_path in candidates:
        # Build assessment BEFORE touching the file (AC10)
        try:
            assessment_text = build_assessment(idea_path, vault_dir, today)
        except Exception as exc:
            print(
                f"ERROR: assessment failed for {idea_path.name}: {exc}",
                file=sys.stderr,
            )
            continue

        # Write results atomically: frontmatter update + Assessment block
        text = idea_path.read_text(encoding="utf-8")
        text = _write_frontmatter_field(text, "assessed", str(today))
        fm = _parse_frontmatter(text)
        if fm and fm.get("status") == "idea":
            text = _write_frontmatter_field(text, "status", "assessed")
        text = _replace_assessment_block(text, assessment_text)
        idea_path.write_text(text, encoding="utf-8")

        assessed.append(idea_path)
        print(f"Assessed: {idea_path.name}")

    return assessed


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Idea assessment pass — generates Assessment sections for "
        "new/edited ideas"
    )
    parser.add_argument(
        "--ideas-dir", type=Path, default=_DEFAULT_IDEAS_DIR,
        help=f"Path to vault/ideas/ (default: {_DEFAULT_IDEAS_DIR})",
    )
    parser.add_argument(
        "--vault", type=Path, default=_DEFAULT_VAULT_DIR,
        help=f"Path to vault/ root (default: {_DEFAULT_VAULT_DIR})",
    )
    args = parser.parse_args()

    ideas_dir = args.ideas_dir.resolve()
    vault_dir = args.vault.resolve()

    if not ideas_dir.is_dir():
        print(f"ERROR: ideas directory not found: {ideas_dir}", file=sys.stderr)
        return 1

    run_assessment_pass(ideas_dir, vault_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

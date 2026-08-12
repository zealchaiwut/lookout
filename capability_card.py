"""
capability_card.py — capability card generator for Lookout.

Generates a machine-readable capability.md for a given target, following
the five-section template required by the project. Reads snapshot evidence
(endpoints.json, manifest.json) from the target's latest raw snapshot.

Generated sections:
  ## What it is         — ≤2 sentences describing the target
  ## Data it owns       — datasets, files, or stores managed by the target
  ## Read surfaces      — every real GET endpoint with one example call each
  ## How to make it do things — commander slug, bulk-create path, CLI entries
  ## Constraints        — known limitations and invariants
  ## Notes for AI       — preserved verbatim across regenerations

Token budget: ≤1500 tokens (counted by count_tokens()).

Usage:
  python capability_card.py <target> [--vault <dir>]

Exit codes:
  0 — success
  1 — configuration error
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

import llm

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_NOTES_HEADER = "## Notes for AI"
_TOKEN_LIMIT = 1500

# How much of a target's README is sent when summarising it. Enough for the
# intro and feature list; short enough to keep the call cheap.
_README_PROMPT_CHARS = 6000


def count_tokens(text: str) -> int:
    """Count tokens using simple whitespace splitting (project standard tokenizer)."""
    return len(text.split())


def _load_targets(targets_yaml: Path) -> dict:
    with open(targets_yaml) as f:
        data = yaml.safe_load(f)
    return data.get("targets", {})


def _find_latest_snapshot(project_dir: Path) -> Path | None:
    raw_dir = project_dir / "raw"
    if not raw_dir.exists():
        return None
    dirs = sorted(
        d for d in raw_dir.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )
    return dirs[-1] if dirs else None


def _load_endpoints(snapshot_dir: Path) -> list:
    """Load GET endpoints from endpoints.json in the snapshot directory."""
    ep_file = snapshot_dir / "endpoints.json"
    if not ep_file.exists():
        return []
    try:
        data = json.loads(ep_file.read_text())
        return data.get("get_endpoints", [])
    except (OSError, json.JSONDecodeError):
        return []


def _load_manifest(snapshot_dir: Path) -> dict:
    manifest_file = snapshot_dir / "manifest.json"
    if not manifest_file.exists():
        return {}
    try:
        return json.loads(manifest_file.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _read_target_readme(target_config: dict) -> str:
    """Read README.md from the target's local clone, or '' if unavailable."""
    local = target_config.get("local")
    if not local:
        return ""
    readme = Path(local).expanduser() / "README.md"
    try:
        return readme.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _load_target_config(target: str, targets_yaml: Path) -> dict:
    try:
        targets = _load_targets(targets_yaml)
        return targets.get(target, {})
    except Exception:
        return {}


def extract_read_surface_paths(card_content: str) -> list:
    """Extract API paths from the Read surfaces section of a capability.md.

    Returns a list of path strings (e.g. ['/api/health', '/api/sprints']).
    Used by UAT validation to confirm every surfaced endpoint is reachable.
    """
    m = re.search(r"## Read surfaces\s+(.*?)(?=\n## |\Z)", card_content, re.DOTALL)
    if not m:
        return []
    section = m.group(1)
    paths = re.findall(r"`GET (/[^`]+)`", section)
    return paths


def _extract_notes_for_ai(existing_content: str) -> str:
    """Extract the Notes for AI section from an existing capability.md.

    Returns the section body (without the ## header line), or empty string.
    """
    if _NOTES_HEADER not in existing_content:
        return ""
    # Grab everything after the header until next ## or EOF
    m = re.search(
        r"## Notes for AI\s*(.*?)(?=\n## |\Z)",
        existing_content,
        re.DOTALL,
    )
    if not m:
        return ""
    return m.group(1).rstrip()


def _build_read_surfaces_section(endpoints: list) -> str:
    """Build the Read surfaces section from a list of endpoint dicts."""
    if not endpoints:
        return "_No read surfaces discovered in snapshot evidence._"

    lines = []
    for ep in endpoints:
        path = ep.get("path", "")
        description = ep.get("description", "")
        example = ep.get("example", f"curl http://localhost:8000{path}")
        lines.append(f"- `GET {path}` — {description}")
        lines.append(f"  - Example: `{example}`")

    return "\n".join(lines)


_GENERIC_MARKER = "is a project tracked by Lookout"


def _generic_what_it_is(target: str) -> str:
    return (
        f"`{target}` is a project tracked by Lookout via Commander. "
        f"It is monitored for health, open issues, sprint progress, and documentation drift."
    )


def _extract_what_it_is(existing_content: str) -> str:
    """Return the '## What it is' body of an existing card, or '' if generic.

    The generic sentence carries no information, so it is treated as absent —
    only a real description is worth preserving.
    """
    m = re.search(r"## What it is\s*\n+(.*?)(?=\n## |\Z)", existing_content, re.DOTALL)
    if not m:
        return ""
    body = m.group(1).strip()
    return "" if _GENERIC_MARKER in body else body


def _build_what_it_is(
    target: str, readme_text: str, endpoints: list, preserved: str = ""
) -> str:
    """Describe what the target actually does, in at most two sentences.

    The deterministic answer says only that the target is tracked by Lookout,
    which is true of every target and therefore tells a reader nothing. When LLM
    enrichment is enabled (see docs/llm-usage.md) the target's own README is
    summarised instead.

    A real description already on the card survives a run with enrichment off.
    Without that, every deterministic run — including the nightly sweep, which
    is deterministic by design — would overwrite the good description with the
    generic sentence and the next enriched run would have to buy it again.
    """
    fallback = preserved or _generic_what_it_is(target)
    if not llm.enabled() and preserved:
        return preserved
    if not readme_text.strip():
        return fallback

    paths = ", ".join(e.get("path", "") for e in endpoints[:12])
    prompt = (
        "Below is the README of a software project, followed by its documented "
        "GET endpoints. Write at most two sentences describing what the project "
        "does and who it is for. Be concrete and specific — name the actual "
        "domain and capabilities, not generic phrases like 'a software project'. "
        "Output only the sentences, with no preamble, heading, or quotation marks.\n\n"
        f"PROJECT NAME: {target}\n\n"
        f"README (truncated):\n{readme_text[:_README_PROMPT_CHARS]}\n\n"
        f"GET ENDPOINTS: {paths or '(none documented)'}\n"
    )
    return llm.ask(prompt, fallback=fallback, purpose=f"capability:{target}")


def _build_card(
    target: str,
    target_config: dict,
    manifest: dict,
    endpoints: list,
    preserved_notes: str,
    readme_text: str = "",
    preserved_what_it_is: str = "",
) -> str:
    """Build the capability card markdown content."""
    commander_slug = target_config.get("commander_slug", target)
    github = target_config.get("github", f"unknown/{target}")

    # --- What it is ---
    what_it_is = _build_what_it_is(target, readme_text, endpoints, preserved_what_it_is)

    # --- Data it owns ---
    data_it_owns = (
        f"- Snapshot artifacts under `vault/projects/{target}/raw/`\n"
        f"- Situation summary at `vault/projects/{target}/situation.md`\n"
        f"- Drift flags at `vault/projects/{target}/drift.md`\n"
        f"- Todo view at `vault/projects/{target}/todo-view.md`"
    )

    # --- Read surfaces ---
    read_surfaces = _build_read_surfaces_section(endpoints)

    # --- How to make it do things ---
    how_to = (
        f"- **Commander slug:** `{commander_slug}`\n"
        f"- **Bulk-create path:** `POST /api/briefs` with `{{\"slug\": \"{commander_slug}\"}}`\n"
        f"- **CLI:** `python gather.py {target}` (snapshot), "
        f"`python synthesize.py {target}` (situation.md)\n"
        f"- **Lookout runner:** `bin/lookout {target}`"
    )

    # --- Constraints ---
    constraints = (
        "- Snapshot data is read-only; Lookout never writes to the target repository.\n"
        "- Commander API must be reachable at `sources.commander_api` for live data.\n"
        "- Journal cross-links are populated only when `journal_entries` source is configured.\n"
        f"- GitHub repository: `{github}`"
    )

    # --- Notes for AI ---
    notes_body = preserved_notes if preserved_notes else "_Add notes here to preserve across regenerations._"

    sections = [
        f"# {target} — Capability Card\n",
        f"## What it is\n\n{what_it_is}\n",
        f"## Data it owns\n\n{data_it_owns}\n",
        f"## Read surfaces\n\n{read_surfaces}\n",
        f"## How to make it do things\n\n{how_to}\n",
        f"## Constraints\n\n{constraints}\n",
        f"{_NOTES_HEADER}\n\n{notes_body}\n",
    ]

    return "\n".join(sections)


def generate_capability_card(
    target: str,
    vault_dir: Path | None = None,
    targets_yaml: Path | None = None,
) -> Path:
    """Generate or regenerate capability.md for the given target.

    Preserves the 'Notes for AI' section from any existing capability.md.

    Returns the path to the generated file.
    """
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    if targets_yaml is None:
        targets_yaml = TARGETS_YAML

    project_dir = vault_dir / "projects" / target
    project_dir.mkdir(parents=True, exist_ok=True)

    cap_md_path = project_dir / "capability.md"

    # Preserve Notes for AI from existing file
    preserved_notes = ""
    preserved_what_it_is = ""
    if cap_md_path.exists():
        existing = cap_md_path.read_text()
        preserved_notes = _extract_notes_for_ai(existing)
        preserved_what_it_is = _extract_what_it_is(existing)

    # Load snapshot evidence
    snapshot_dir = _find_latest_snapshot(project_dir)
    endpoints = _load_endpoints(snapshot_dir) if snapshot_dir else []
    manifest = _load_manifest(snapshot_dir) if snapshot_dir else {}

    # Load target config
    target_config = _load_target_config(target, targets_yaml)
    readme_text = _read_target_readme(target_config)

    content = _build_card(
        target, target_config, manifest, endpoints, preserved_notes, readme_text,
        preserved_what_it_is,
    )

    # Enforce token limit by trimming Read surfaces if needed
    if count_tokens(content) > _TOKEN_LIMIT:
        # Trim endpoint list to fit within budget
        while endpoints and count_tokens(content) > _TOKEN_LIMIT:
            endpoints = endpoints[:-1]
            content = _build_card(
                target, target_config, manifest, endpoints, preserved_notes, readme_text,
                preserved_what_it_is,
            )

    cap_md_path.write_text(content)
    return cap_md_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate capability.md for a Lookout target"
    )
    parser.add_argument("target", help="Target name (from targets.yaml)")
    parser.add_argument(
        "--vault",
        default=str(REPO_ROOT / "vault"),
        help="Path to vault directory",
    )
    args = parser.parse_args()

    out = generate_capability_card(
        target=args.target,
        vault_dir=Path(args.vault),
    )
    print(f"Generated: {out}")


if __name__ == "__main__":
    main()

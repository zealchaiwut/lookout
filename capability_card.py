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

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_NOTES_HEADER = "## Notes for AI"
_TOKEN_LIMIT = 1500


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


def _load_target_config(target: str, targets_yaml: Path) -> dict:
    try:
        targets = _load_targets(targets_yaml)
        return targets.get(target, {})
    except Exception:
        return {}


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


def _build_card(
    target: str,
    target_config: dict,
    manifest: dict,
    endpoints: list,
    preserved_notes: str,
) -> str:
    """Build the capability card markdown content."""
    commander_slug = target_config.get("commander_slug", target)
    github = target_config.get("github", f"unknown/{target}")

    # --- What it is ---
    health_status = manifest.get("health", {}).get("status", "unknown")
    what_it_is = (
        f"`{target}` is a project tracked by Lookout via Commander. "
        f"It is monitored for health, open issues, sprint progress, and documentation drift."
    )

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
    if cap_md_path.exists():
        preserved_notes = _extract_notes_for_ai(cap_md_path.read_text())

    # Load snapshot evidence
    snapshot_dir = _find_latest_snapshot(project_dir)
    endpoints = _load_endpoints(snapshot_dir) if snapshot_dir else []
    manifest = _load_manifest(snapshot_dir) if snapshot_dir else {}

    # Load target config
    target_config = _load_target_config(target, targets_yaml)

    content = _build_card(target, target_config, manifest, endpoints, preserved_notes)

    # Enforce token limit by trimming Read surfaces if needed
    if count_tokens(content) > _TOKEN_LIMIT:
        # Trim endpoint list to fit within budget
        while endpoints and count_tokens(content) > _TOKEN_LIMIT:
            endpoints = endpoints[:-1]
            content = _build_card(target, target_config, manifest, endpoints, preserved_notes)

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

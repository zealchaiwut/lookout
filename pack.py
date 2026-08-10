"""
pack.py — pack generator for Lookout.

Bundles target situation one-liners, capacity lines, the capability map,
and agent ground rules into a single, auditable context file.

Cards:     vault/projects/<target>/situation.md
Staleness: card mtime > 7 days → ⚠ STALE warning in header
Output:    vault/packs/<YYYY-MM-DD>-<slug>.md

Usage:
  python pack.py <target...> [--vault <dir>]

Exit codes:
  0 — success
  1 — unknown target
"""
import argparse
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"
STALE_DAYS = 7


class UnknownTargetError(ValueError):
    pass


def _load_valid_targets(targets_yaml: Path) -> set:
    with open(targets_yaml) as f:
        data = yaml.safe_load(f)
    return set(data.get("targets", {}).keys())


def _card_path(vault_dir: Path, target: str) -> Path:
    return vault_dir / "projects" / target / "situation.md"


def _is_stale(card_path: Path) -> bool:
    if not card_path.exists():
        return False
    mtime = datetime.fromtimestamp(card_path.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - mtime) > timedelta(days=STALE_DAYS)


def _card_mtime_date(card_path: Path) -> str:
    mtime = datetime.fromtimestamp(card_path.stat().st_mtime, tz=timezone.utc)
    return mtime.strftime("%Y-%m-%d")


def _extract_section_first_line(content: str, section_header: str) -> str:
    """Return the first non-empty, non-source-annotation line of a section."""
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


def _extract_ground_rules(agents_content: str) -> str:
    """Extract the Read-Only Invariant section from agents.md."""
    m = re.search(
        r"(## Read-Only Invariant\s*\n.*?)(?=\n## |\Z)",
        agents_content,
        re.DOTALL,
    )
    if not m:
        return ""
    return m.group(1).strip()


def generate_pack(
    targets: list,
    vault_dir: Path,
    targets_yaml: Path = None,
    now: datetime = None,
) -> Path:
    """Generate a pack file and return its path.

    Raises UnknownTargetError if any target is not in targets_yaml.
    """
    if targets_yaml is None:
        targets_yaml = TARGETS_YAML
    if now is None:
        now = datetime.now(timezone.utc)

    valid_targets = _load_valid_targets(targets_yaml)
    unknown = [t for t in targets if t not in valid_targets]
    if unknown:
        msg = f"unknown target(s): {', '.join(unknown)}"
        print(f"Error: {msg}", file=sys.stderr)
        raise UnknownTargetError(msg)

    date_str = now.strftime("%Y-%m-%d")
    slug = "-".join(targets)
    pack_dir = vault_dir / "packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack_path = pack_dir / f"{date_str}-{slug}.md"

    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = []

    # --- Header ---
    lines.append("# Lookout Pack")
    lines.append("")
    lines.append(f"Generated: {timestamp}")
    lines.append(f"Targets: {', '.join(targets)}")

    for target in targets:
        card = _card_path(vault_dir, target)
        if _is_stale(card):
            updated = _card_mtime_date(card)
            lines.append(f"⚠ STALE: {target} (last updated {updated})")

    lines.append("")

    # --- Target blocks ---
    for target in targets:
        lines.append("---")
        lines.append("")
        lines.append(f"## {target}")
        lines.append("")
        card = _card_path(vault_dir, target)
        if card.exists():
            content = card.read_text()
            one_liner = _extract_one_liner(content)
            capacity = _extract_capacity(content)
            if one_liner:
                lines.append(one_liner)
            if capacity:
                lines.append(capacity)
        lines.append("")

    # --- Map (verbatim) ---
    lines.append("---")
    lines.append("")
    map_path = vault_dir / "map.md"
    if map_path.exists():
        lines.append(map_path.read_text().rstrip())
    lines.append("")

    # --- Footer: read-only ground-rules block from agents.md ---
    lines.append("---")
    lines.append("")
    agents_path = vault_dir / "agents.md"
    if agents_path.exists():
        ground_rules = _extract_ground_rules(agents_path.read_text())
        if ground_rules:
            lines.append(ground_rules)
    lines.append("")

    pack_path.write_text("\n".join(lines) + "\n")
    return pack_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bundle target capability cards into a context pack"
    )
    parser.add_argument("targets", nargs="+", help="Target names to include")
    parser.add_argument(
        "--vault",
        default=str(REPO_ROOT / "vault"),
        help="Path to vault directory",
    )
    args = parser.parse_args()

    try:
        pack_path = generate_pack(
            targets=args.targets,
            vault_dir=Path(args.vault),
        )
        print(f"Pack written: {pack_path}")
    except UnknownTargetError:
        sys.exit(1)


if __name__ == "__main__":
    main()

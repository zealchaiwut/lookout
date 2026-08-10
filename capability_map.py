"""
capability_map.py — Cross-project capability map generator for Lookout.

Reads all capability cards in vault/projects/*/capability.md, derives
producer→consumer relationships, and regenerates the Edges section of
vault/map.md. The Human Pipelines section is always preserved byte-for-byte.

Edge detection:
  A project is a *producer* for a surface when that surface appears in its
  ## Read surfaces section. A project is a *consumer* when its capability
  card (outside its own Read surfaces section) references that surface path.
  Only surfaces documented in a real capability card can appear in an edge.

Usage:
  python capability_map.py [--vault <dir>]

Exit codes:
  0 — success
"""
import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent
DEFAULT_VAULT = REPO_ROOT / "vault"
MAP_FILENAME = "map.md"

BEGIN_EDGES = "<!-- BEGIN MACHINE EDGES -->"
END_EDGES = "<!-- END MACHINE EDGES -->"
BEGIN_PIPELINES = "<!-- BEGIN HUMAN PIPELINES -->"
END_PIPELINES = "<!-- END HUMAN PIPELINES -->"

_EMPTY_TEMPLATE = (
    "# Capability Map\n\n"
    f"{BEGIN_EDGES}\n"
    f"{END_EDGES}\n\n"
    f"{BEGIN_PIPELINES}\n"
    f"{END_PIPELINES}\n"
)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _load_capability_cards(vault_dir: Path) -> dict[str, str]:
    """Return {target_name: card_content} for all existing capability.md files."""
    cards: dict[str, str] = {}
    projects_dir = vault_dir / "projects"
    if not projects_dir.exists():
        return cards
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        cap_file = project_dir / "capability.md"
        if cap_file.exists():
            cards[project_dir.name] = cap_file.read_text()
    return cards


def _extract_read_surfaces(card_content: str) -> list[str]:
    """Return list of GET paths from the ## Read surfaces section."""
    m = re.search(r"## Read surfaces\s+(.*?)(?=\n## |\Z)", card_content, re.DOTALL)
    if not m:
        return []
    return re.findall(r"`GET (/[^`]+)`", m.group(1))


def _text_outside_read_surfaces(card_content: str) -> str:
    """Return the card text with ## Read surfaces removed (to find consumer refs)."""
    return re.sub(
        r"## Read surfaces\s+.*?(?=\n## |\Z)",
        "",
        card_content,
        flags=re.DOTALL,
    )


# ---------------------------------------------------------------------------
# Edge generation
# ---------------------------------------------------------------------------

def generate_edges(cards: dict[str, str]) -> list[str]:
    """Derive edge lines from capability cards.

    For each surface exposed by a producer, scan every other card's
    non-Read-surfaces text. When a card mentions that surface path, emit:
      "- <producer> → <consumer> via GET <path>"

    Surfaces not present in any card's ## Read surfaces are never emitted.
    """
    # Build surface → producer mapping
    surface_to_producer: dict[str, str] = {}
    for target, content in cards.items():
        for path in _extract_read_surfaces(content):
            if path not in surface_to_producer:
                surface_to_producer[path] = target

    if not surface_to_producer:
        return []

    edges: list[str] = []
    for consumer, content in cards.items():
        consumer_text = _text_outside_read_surfaces(content)
        for path, producer in sorted(surface_to_producer.items()):
            if producer == consumer:
                continue
            pattern = re.escape(path)
            if re.search(pattern, consumer_text):
                edges.append(f"- {producer} → {consumer} via GET {path}")

    return sorted(edges)


# ---------------------------------------------------------------------------
# map.md read/write
# ---------------------------------------------------------------------------

def _read_existing_map(map_path: Path) -> str:
    if map_path.exists():
        return map_path.read_text()
    return _EMPTY_TEMPLATE


def _extract_pipelines_block(map_content: str) -> str:
    """Return the full pipelines block (sentinels inclusive), or empty block."""
    m = re.search(
        rf"({re.escape(BEGIN_PIPELINES)}.*?{re.escape(END_PIPELINES)})",
        map_content,
        re.DOTALL,
    )
    return m.group(1) if m else f"{BEGIN_PIPELINES}\n{END_PIPELINES}"


def _build_map_content(edge_lines: list[str], pipelines_block: str) -> str:
    body = "\n".join(edge_lines)
    edges_block = f"{BEGIN_EDGES}\n{body}\n{END_EDGES}" if body else f"{BEGIN_EDGES}\n{END_EDGES}"
    return f"# Capability Map\n\n{edges_block}\n\n{pipelines_block}\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_map(vault_dir: Path | None = None) -> Path:
    """Generate or update vault/map.md.

    Regenerates the Edges section from current capability cards.
    Preserves the Human Pipelines section byte-for-byte.

    Returns the path to the written file.
    """
    if vault_dir is None:
        vault_dir = DEFAULT_VAULT

    map_path = vault_dir / MAP_FILENAME

    cards = _load_capability_cards(vault_dir)
    edge_lines = generate_edges(cards)

    existing = _read_existing_map(map_path)
    pipelines_block = _extract_pipelines_block(existing)

    content = _build_map_content(edge_lines, pipelines_block)
    map_path.write_text(content)
    return map_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate vault/map.md from capability cards"
    )
    parser.add_argument(
        "--vault",
        default=str(DEFAULT_VAULT),
        help="Path to the vault directory",
    )
    args = parser.parse_args()
    out = generate_map(vault_dir=Path(args.vault))
    print(f"Generated: {out}")


if __name__ == "__main__":
    main()

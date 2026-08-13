"""
atlas_seed.py — atlas seeding bootstrap for Lookout.

Derives the initial feature list for a target from its README feature table
and/or docs/features/ headings, then writes:

  vault/projects/<target>/atlas/index.md
    A machine-managed Markdown table (feature | files | traced | stale) plus a
    clearly delimited human section where maintainers can add/remove features
    by hand.

  vault/projects/<target>/atlas/<feature-slug>.md
    A per-feature stub with YAML frontmatter (feature, files, traced, stale).

Idempotent: re-running never duplicates machine rows or overwrites human edits.
Human-section additions get a stub on the next run; human-section removals are
dropped from the machine table without deleting the stub file.

Usage
-----
    from atlas_seed import extract_features, seed
    seed(target="perf-coach", vault_dir=Path("vault"), readme_text=..., docs_features_text=...)

Or CLI:
    python atlas_seed.py <target-name> [--vault <vault_dir>]
"""
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Sentinel strings that delimit the two sections of index.md
# ---------------------------------------------------------------------------

_MACHINE_BEGIN = "<!-- BEGIN MACHINE MANAGED — do not edit below this line -->"
_MACHINE_END = "<!-- END MACHINE MANAGED -->"
_HUMAN_BEGIN = "<!-- BEGIN HUMAN SECTION — add or remove features here -->"
_HUMAN_END = "<!-- END HUMAN SECTION -->"


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

_README_FEATURE_PATTERN = re.compile(
    r"^- \*\*([^*]+)\*\*",
    re.MULTILINE,
)

# Some READMEs list each feature as a `### Name` subheading under `## Features`
# rather than as a bold bullet. asset-studio uses this form.
_README_SUBHEADING_PATTERN = re.compile(r"^###+\s+(.+?)\s*$")

# Others use a table whose first cell is the bolded feature name:
#   | **Dashboard** | Live agent event feed | [docs](…) |
# commander uses this form. The header and separator rows are skipped by the
# `**` requirement, which they never satisfy.
_README_TABLE_PATTERN = re.compile(r"^\|\s*\*\*([^*|]+)\*\*\s*\|")

# Trailing issue references on a feature heading, e.g. "Brand Settings (issue #1)".
_ISSUE_SUFFIX_PATTERN = re.compile(r"\s*\((?:issue|issues)\s*#[\d,\s#]+\)\s*$", re.IGNORECASE)

_DOCS_HEADING_PATTERN = re.compile(
    r"^## (.+)$",
    re.MULTILINE,
)

_SKIP_HEADINGS = {"features", "features index", "overview", "table of contents", "contents"}


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def extract_features(
    readme_text: str | None,
    docs_features_text: str | None,
) -> list[dict]:
    """Return a deduplicated list of feature dicts extracted from source text.

    Each dict has:
      name  — display name (as parsed from the source)
      slug  — kebab-case identifier used for stub filenames
    """
    seen_slugs: set[str] = set()
    features: list[dict] = []

    def _add(name: str, issue: int | None = None) -> None:
        slug = _slugify(name)
        if not slug or slug in seen_slugs:
            return
        seen_slugs.add(slug)
        features.append({"name": name, "slug": slug, "issue": issue})

    if readme_text:
        in_features_section = False
        for line in readme_text.splitlines():
            if re.match(r"^## Features", line, re.IGNORECASE):
                in_features_section = True
                continue
            # Only a sibling `## ` heading closes the section. Matching bare `^##`
            # here would also match `###`, ending the section at the first
            # subheading-style feature.
            if in_features_section and re.match(r"^## ", line):
                in_features_section = False
            if in_features_section:
                m = _README_FEATURE_PATTERN.match(line)
                if m:
                    _add(m.group(1).strip())
                    continue
                m = _README_TABLE_PATTERN.match(line)
                if m:
                    _add(m.group(1).strip())
                    continue
                m = _README_SUBHEADING_PATTERN.match(line)
                if m:
                    raw = m.group(1)
                    issue_m = re.search(r"#(\d+)", raw)
                    name = _ISSUE_SUFFIX_PATTERN.sub("", raw).strip()
                    if name.lower() not in _SKIP_HEADINGS:
                        _add(name, int(issue_m.group(1)) if issue_m else None)

    if docs_features_text:
        for m in _DOCS_HEADING_PATTERN.finditer(docs_features_text):
            heading = m.group(1).strip()
            if heading.lower() not in _SKIP_HEADINGS:
                _add(heading)

    return features


# ---------------------------------------------------------------------------
# Stub file creation
# ---------------------------------------------------------------------------

def _stub_text(feature_name: str, issue: int | None = None) -> str:
    issue_line = f"issue: {issue}\n" if issue is not None else "issue: null\n"
    return (
        "---\n"
        f"feature: {feature_name}\n"
        f"{issue_line}"
        "files: []\n"
        "traced: null\n"
        "stale: true\n"
        "---\n"
    )


def _ensure_stub(
    atlas_dir: Path, slug: str, feature_name: str, issue: int | None = None
) -> None:
    stub_path = atlas_dir / f"{slug}.md"
    if not stub_path.exists():
        stub_path.write_text(_stub_text(feature_name, issue))


# ---------------------------------------------------------------------------
# index.md parsing and rendering
# ---------------------------------------------------------------------------

def _parse_human_section(index_text: str) -> list[str]:
    """Return the list of feature slugs/names listed in the human section."""
    try:
        start = index_text.index(_HUMAN_BEGIN) + len(_HUMAN_BEGIN)
        end = index_text.index(_HUMAN_END, start)
    except ValueError:
        return []
    section = index_text[start:end]
    entries: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if line.startswith("- "):
            name = line[2:].strip()
            if name:
                entries.append(name)
    return entries


def _render_machine_table(features: list[dict]) -> str:
    lines = [
        _MACHINE_BEGIN,
        "",
        "## Atlas — machine-managed feature table",
        "",
        "| feature | files | traced | stale |",
        "| ------- | ----- | ------ | ----- |",
    ]
    for f in features:
        lines.append(f"| {f['name']} | pending | null | true |")
    lines.append("")
    lines.append(_MACHINE_END)
    return "\n".join(lines)


def _render_human_section(entries: list[str]) -> str:
    lines = [
        _HUMAN_BEGIN,
        "",
        "<!-- Add features below, one per line as: - feature-name -->",
        "",
    ]
    for entry in entries:
        lines.append(f"- {entry}")
    lines.append("")
    lines.append(_HUMAN_END)
    return "\n".join(lines)


def _build_index_md(machine_features: list[dict], human_entries: list[str]) -> str:
    parts = [
        "# Atlas Index",
        "",
        _render_machine_table(machine_features),
        "",
        _render_human_section(human_entries),
        "",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def seed(
    target: str,
    vault_dir: Path,
    readme_text: str | None,
    docs_features_text: str | None,
) -> None:
    """Seed or update the atlas for *target* inside *vault_dir*.

    - Creates vault/projects/<target>/atlas/ if absent.
    - Reads existing index.md to preserve human-section edits.
    - Merges README/docs features with human-section additions.
    - Drops human-section removals from the machine table (stubs stay on disk).
    - Creates per-feature stub files for any feature not yet on disk.
    - Writes an updated index.md (machine table + human section).
    """
    atlas_dir = Path(vault_dir) / "projects" / target / "atlas"
    atlas_dir.mkdir(parents=True, exist_ok=True)
    index_path = atlas_dir / "index.md"

    # Load existing index to preserve human section
    existing_human_entries: list[str] = []
    if index_path.exists():
        existing_human_entries = _parse_human_section(index_path.read_text())

    # Extract features from source text
    auto_features = extract_features(readme_text=readme_text, docs_features_text=docs_features_text)
    auto_slugs = {f["slug"] for f in auto_features}

    # Resolve human-section entries into feature dicts
    human_features: list[dict] = []
    for entry in existing_human_entries:
        slug = _slugify(entry)
        if slug and slug not in auto_slugs:
            human_features.append({"name": entry, "slug": slug})

    # The machine table = auto features + human-section additions
    all_machine_features = auto_features + human_features

    # Create stub files for any missing feature
    for f in all_machine_features:
        _ensure_stub(atlas_dir, f["slug"], f["name"], f.get("issue"))

    # Write index.md (machine table regenerated; human section preserved verbatim)
    index_text = _build_index_md(
        machine_features=all_machine_features,
        human_entries=existing_human_entries,
    )
    index_path.write_text(index_text)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _fetch_github_text(owner: str, repo: str, path: str) -> str | None:
    import base64
    import json
    import subprocess

    result = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}/contents/{path}", "--jq", ".content"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    try:
        return base64.b64decode(raw).decode("utf-8")
    except Exception:
        return None


def _load_targets(vault_dir: Path) -> dict:
    import yaml
    targets_yaml = vault_dir.parent.parent / "targets.yaml"
    if not targets_yaml.exists():
        # Try repo root
        repo_root = Path(__file__).parent
        targets_yaml = repo_root / "targets.yaml"
    if not targets_yaml.exists():
        return {}
    with open(targets_yaml) as f:
        data = yaml.safe_load(f) or {}
    return data.get("targets", {})


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Seed atlas index for a Lookout target")
    parser.add_argument("target", help="Target name (e.g. perf-coach)")
    parser.add_argument("--vault", default="vault", help="Path to vault directory")
    args = parser.parse_args()

    vault_dir = Path(args.vault)
    targets = _load_targets(vault_dir)

    if args.target not in targets:
        print(f"Error: unknown target '{args.target}'", file=sys.stderr)
        print(f"Known targets: {', '.join(targets.keys())}", file=sys.stderr)
        sys.exit(1)

    target_cfg = targets[args.target]
    github = target_cfg.get("github", "")
    if "/" not in github:
        print(f"Error: target '{args.target}' has no valid github entry", file=sys.stderr)
        sys.exit(1)
    owner, repo = github.split("/", 1)

    print(f"Fetching README for {github} …")
    readme_text = _fetch_github_text(owner, repo, "README.md")
    if readme_text is None:
        print("Warning: could not fetch README.md — features list may be empty", file=sys.stderr)

    print("Fetching docs/features/ index …")
    docs_features_text = _fetch_github_text(owner, repo, "docs/features/README.md")
    if docs_features_text is None:
        docs_features_text = _fetch_github_text(owner, repo, "docs/features/index.md")

    seed(
        target=args.target,
        vault_dir=vault_dir,
        readme_text=readme_text,
        docs_features_text=docs_features_text,
    )

    atlas_dir = vault_dir / "projects" / args.target / "atlas"
    stubs = [f for f in atlas_dir.iterdir() if f.suffix == ".md" and f.name != "index.md"]
    print(f"Atlas seeded: {len(stubs)} feature stub(s) written to {atlas_dir}")
    print(f"index.md: {atlas_dir / 'index.md'}")


if __name__ == "__main__":
    main()

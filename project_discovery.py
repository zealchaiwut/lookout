"""
project_discovery.py — per-target Discovery note (docs-first).

Writes vault/projects/<target>/discovery.md — a single "start here" page that
joins product flow, API map (with atlas joins), a shallow module map, and
atlas links. Inspired by Understand-Anything's teach-the-codebase goal, but
static markdown only: no interactive graph SPA, no live API calls, no writes
into target clones.

Usage:
    python project_discovery.py <target> [--vault <dir>]
"""
import argparse
import re
import sys
from pathlib import Path

import capability_card
import project_flow

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_MODULE_NODE_CAP = 15
_API_ROW_CAP = 80

_ENTRY_CANDIDATES = (
    "server.py", "app.py", "main.py", "api.py",
    "apps/dashboard/server.py", "apps/dashboard/app.py",
)
_CODE_TOP_DIRS = (
    "routers", "services", "apps", "src", "models", "hooks", "scripts",
)

_IMPORT_RE = re.compile(
    r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
    re.MULTILINE,
)
_KEY_PY_RE = re.compile(r"`([^`\s]+\.py)`")


def _load_target_local(target: str, targets_yaml: Path | None = None) -> Path | None:
    return project_flow._load_target_local(target, targets_yaml)


def _latest_snapshot(project_dir: Path) -> Path | None:
    return project_flow._latest_snapshot(project_dir)


def _md_cell(text: str) -> str:
    return capability_card._md_cell(text)


def _one_liner(project_dir: Path, target: str) -> str:
    cap = project_dir / "capability.md"
    if cap.exists():
        body = capability_card._extract_what_it_is(cap.read_text(encoding="utf-8"))
        if body:
            return body
    return f"`{target}` is a Lookout-tracked project."


def _product_flow_section(target: str, local: Path | None) -> list[str]:
    lines = ["## Product flow\n"]
    product_text = ""
    workflow_text = ""
    if local:
        product_path = local / "PRODUCT.md"
        if product_path.is_file():
            product_text = product_path.read_text(encoding="utf-8", errors="replace")
        workflow_path = local / "docs" / "workflow.md"
        if workflow_path.is_file():
            workflow_text = workflow_path.read_text(encoding="utf-8", errors="replace")

    steps = project_flow._extract_product_steps(product_text)
    stages = project_flow._extract_stages(workflow_text) if workflow_text else []
    commander_template = project_flow._is_commander_pipeline(workflow_text)
    is_commander = target == "commander"

    if steps:
        titles = [t for t, _ in steps]
        mermaid = project_flow._lifecycle_mermaid(titles)
        lines.append(
            f"From `{target}` `PRODUCT.md` ({len(steps)} step(s)). "
            f"Full detail: [[projects/{target}/flow]].\n"
        )
        if mermaid:
            lines.append(mermaid + "\n")
        for title, detail in steps[:8]:
            short = detail[:160] + ("…" if len(detail) > 160 else "")
            lines.append(f"- **{title}** — {short}" if short else f"- **{title}**")
        lines.append("")
    elif stages and (is_commander or not commander_template):
        mermaid = project_flow._lifecycle_mermaid(stages)
        lines.append(
            f"From `{target}` `docs/workflow.md` ({len(stages)} stage(s)). "
            f"Full detail: [[projects/{target}/flow]].\n"
        )
        if mermaid:
            lines.append(mermaid + "\n")
        for stage in stages:
            lines.append(f"- **{project_flow._short_label(stage)}**")
        lines.append("")
    elif commander_template and not is_commander:
        lines.append(
            f"_No product user-flow list in `{target}` `PRODUCT.md`. "
            f"The Commander sprint template lives under "
            f"[[projects/{target}/flow|How work ships]] on the flow page._\n"
        )
    else:
        lines.append(
            f"_No product flow extracted. See [[projects/{target}/flow]] "
            "once PRODUCT.md or docs/workflow.md has numbered steps._\n"
        )
    return lines


def _atlas_path_index(project_dir: Path, target: str) -> dict[str, dict]:
    """Map API path → {atlas_wikilink, handler} from atlas notes."""
    index: dict[str, dict] = {}
    atlas_dir = project_dir / "atlas"
    if not atlas_dir.is_dir():
        return index
    for path in sorted(atlas_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = f"projects/{target}/atlas/{path.stem}"
        handlers = _KEY_PY_RE.findall(text)
        handler = handlers[0] if handlers else ""
        found_paths: set[str] = set()
        for m in re.finditer(r"Route:\s*`(/[^`]+)`", text):
            found_paths.add(m.group(1))
        for m in re.finditer(r"`(/api/[^`\s]+)`", text):
            found_paths.add(m.group(1))
        for m in re.finditer(r"(?<![`\w])(/api/[A-Za-z0-9_{}/\-]+)", text):
            found_paths.add(m.group(1))
        for api_path in found_paths:
            # Prefer the first atlas note that cites the path; keep handler if set.
            entry = index.setdefault(api_path, {"atlas": rel, "handler": ""})
            if handler and not entry["handler"]:
                entry["handler"] = handler
    return index


def _normalize_join_path(path: str) -> str:
    """Strip trailing slash; keep {param} forms as documented."""
    return path.rstrip("/") or path


def _api_map_section(
    target: str,
    endpoints: list,
    atlas_index: dict[str, dict],
) -> list[str]:
    lines = ["## API map\n"]
    if not endpoints:
        lines.append(
            "_No GET endpoints in the latest snapshot. "
            f"See [[projects/{target}/capability]] after gather finds doc tables._\n"
        )
        return lines

    lines.append(
        "Documented GET surfaces from the latest snapshot. Atlas / Handler "
        "columns fill when an atlas note cites the path (deterministic join — "
        "no live server calls).\n"
    )
    lines.append("| API name | API | Example | Atlas | Handler |")
    lines.append("|---|---|---|---|---|")

    shown = endpoints[:_API_ROW_CAP]
    for ep in shown:
        path = ep.get("path", "")
        name = _md_cell(ep.get("description", "") or path)
        api = f"`GET {_md_cell(path)}`"
        example = capability_card._example_cell(ep, target)
        key = _normalize_join_path(path)
        join = atlas_index.get(key) or atlas_index.get(path)
        # Soft match: strip {param} segments for comparison
        if not join:
            bare = re.sub(r"\{[^}]+\}", "", path)
            for k, v in atlas_index.items():
                if re.sub(r"\{[^}]+\}", "", k) == bare:
                    join = v
                    break
        if join:
            atlas_cell = f"[[{join['atlas']}]]"
            handler_cell = f"`{join['handler']}`" if join.get("handler") else "—"
        else:
            atlas_cell = "—"
            handler_cell = "—"
        lines.append(
            f"| {name} | {api} | {example} | {atlas_cell} | {handler_cell} |"
        )
    lines.append("")
    if len(endpoints) > _API_ROW_CAP:
        lines.append(
            f"_Showing {_API_ROW_CAP} of {len(endpoints)} endpoints. "
            f"Full list: [[projects/{target}/capability]]._\n"
        )
    return lines


def _discover_entry_files(local: Path) -> list[Path]:
    found: list[Path] = []
    for rel in _ENTRY_CANDIDATES:
        p = local / rel
        if p.is_file():
            found.append(p)
    return found


def _top_level_modules(local: Path) -> dict[str, Path]:
    """Map short module label → path for entry files and top-level code packages."""
    mods: dict[str, Path] = {}
    for name in _ENTRY_CANDIDATES:
        p = local / name
        if p.is_file():
            label = str(Path(name)) if "/" in name else p.name
            mods[label] = p
    for dirname in _CODE_TOP_DIRS:
        d = local / dirname
        if not d.is_dir():
            continue
        mods[dirname + "/"] = d
        # apps/dashboard-style children only (still shallow)
        if dirname == "apps":
            for child in sorted(d.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    mods[f"apps/{child.name}/"] = child
    # Extra top-level *.py that look like packages/entry-ish (excluding entries)
    for child in sorted(local.iterdir()):
        if child.is_file() and child.suffix == ".py" and child.name not in mods:
            if child.name not in ("setup.py", "conftest.py"):
                mods[child.name] = child
    return mods


def _local_import_targets(py_file: Path, local: Path, modules: dict[str, Path]) -> list[str]:
    """Return module-map labels that this file imports."""
    try:
        text = py_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[str] = []
    for m in _IMPORT_RE.finditer(text):
        mod = (m.group(1) or m.group(2) or "").split(".")[0]
        if not mod:
            continue
        for label, path in modules.items():
            stem = label.rstrip("/").split("/")[-1].removesuffix(".py")
            if stem == mod:
                if label not in hits and path != py_file:
                    hits.append(label)
                    break
    return hits


def _module_map_section(target: str, local: Path | None) -> list[str]:
    lines = ["## Module map\n"]
    if local is None or not local.is_dir():
        lines.append(
            f"_No local clone configured for `{target}`. "
            "Register `local:` in targets.yaml to populate this map._\n"
        )
        return lines

    modules = _top_level_modules(local)
    entries = _discover_entry_files(local)
    if not modules and not entries:
        lines.append(
            f"_No entry files (`server.py` / `main.py` / …) or code packages "
            f"found under `{local}`._\n"
        )
        return lines

    # Candidate nodes: entries first, then other top-level packages.
    ordered: list[str] = []
    for entry in entries:
        label = str(entry.relative_to(local))
        if label not in ordered:
            ordered.append(label)
    for label in modules:
        if label not in ordered:
            ordered.append(label)

    overflow = max(0, len(ordered) - _MODULE_NODE_CAP)
    nodes = ordered[:_MODULE_NODE_CAP]
    allowed = set(nodes)

    edges: list[tuple[str, str]] = []
    for entry in entries:
        src = str(entry.relative_to(local))
        if src not in allowed:
            continue
        for dest in _local_import_targets(entry, local, modules):
            if dest in allowed and (src, dest) not in edges:
                edges.append((src, dest))

    lines.append(
        f"Shallow map of entry points and top-level packages under the "
        f"`{target}` clone (deterministic import skim, capped at "
        f"{_MODULE_NODE_CAP} nodes). Not a full call graph.\n"
    )

    if len(nodes) >= 2 and edges:
        used: set = set()
        ids: dict[str, str] = {}
        mermaid = ["```mermaid", "flowchart LR"]
        for label in nodes:
            nid = project_flow._node_id(label, used)
            ids[label] = nid
            short = label if len(label) <= 22 else label[:20] + "…"
            mermaid.append(f"  {nid}[{short}]")
        for a, b in edges:
            mermaid.append(f"  {ids[a]} --> {ids[b]}")
        mermaid.append("```")
        lines.append("\n".join(mermaid) + "\n")
    elif nodes:
        lines.append("Top-level modules:\n")
        for label in nodes:
            lines.append(f"- `{label}`")
        lines.append("")
    else:
        lines.append("_Module map is empty._\n")

    if overflow:
        lines.append(
            f"_{overflow} additional module(s) omitted for readability. "
            f"See the source tree and [[projects/{target}/atlas/index]]._\n"
        )
    return lines


def _atlas_coverage(project_dir: Path, target: str) -> list[str]:
    lines = ["## Feature atlas\n"]
    atlas_dir = project_dir / "atlas"
    index_path = atlas_dir / "index.md"
    if not atlas_dir.is_dir():
        lines.append(
            f"_No atlas yet. Seed with `python atlas_seed.py {target}`._\n"
        )
        return lines

    feature_notes = [
        p for p in atlas_dir.glob("*.md") if p.name != "index.md"
    ]
    total = len(feature_notes)
    traced = 0
    for p in feature_notes:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # A note is "traced" when files_read is a non-empty list or flowchart
        # has more than the empty header.
        if re.search(r"files_read:\s*\n(?:\s+-\s+\S+\n)+", text):
            traced += 1
        elif re.search(r"flowchart LR\n\s+\w+", text):
            traced += 1

    lines.append(
        f"[[projects/{target}/atlas/index|Atlas index]] — "
        f"**{traced}** traced / **{total}** features.\n"
    )
    if total:
        # Show a few feature wikilinks
        lines.append("Sample features:\n")
        for p in sorted(feature_notes, key=lambda x: x.stem)[:8]:
            lines.append(f"- [[projects/{target}/atlas/{p.stem}|{p.stem}]]")
        lines.append("")
    return lines


def _read_next(target: str) -> list[str]:
    return [
        "## Read next\n",
        f"- [[projects/{target}/situation|Situation]] — current state\n",
        f"- [[projects/{target}/capability|Capability]] — full API card\n",
        f"- [[projects/{target}/flow|Flow]] — product lifecycle + how work ships\n",
        f"- [[projects/{target}/changelog|Changelog]] — PRs and git history\n",
        f"- [[projects/{target}/todo-view|Todo view]] — open work\n",
    ]


def generate_discovery(target: str, vault_dir: Path | None = None) -> Path:
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    project_dir = vault_dir / "projects" / target
    project_dir.mkdir(parents=True, exist_ok=True)
    local = _load_target_local(target)
    snapshot = _latest_snapshot(project_dir)
    endpoints = (
        capability_card._load_endpoints(snapshot) if snapshot else []
    )
    atlas_index = _atlas_path_index(project_dir, target)

    lines = [
        f"# {target} — Discovery\n",
        "Start-here page for this project: product flow, API map, shallow "
        "module map, and atlas. Machine-generated from docs, the latest "
        "snapshot, and the local clone. Lookout does not invent edges.\n",
        "## One-liner\n",
        _one_liner(project_dir, target) + "\n",
    ]
    lines.extend(_product_flow_section(target, local))
    lines.extend(_api_map_section(target, endpoints, atlas_index))
    lines.extend(_module_map_section(target, local))
    lines.extend(_atlas_coverage(project_dir, target))
    lines.extend(_read_next(target))

    out = project_dir / "discovery.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate discovery.md for a target")
    parser.add_argument("target")
    parser.add_argument("--vault", default=str(REPO_ROOT / "vault"))
    args = parser.parse_args()
    out = generate_discovery(args.target, Path(args.vault))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

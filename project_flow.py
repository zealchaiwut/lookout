"""
project_flow.py — per-target lifecycle + sitemap note.

Writes vault/projects/<target>/flow.md from evidence that already lives in the
target repo and the vault. Nothing is invented.

Product lifecycle prefers PRODUCT.md "Core User Flows" / "Core flows" numbered
steps (create account → bind assets → carousel …). Many targets also ship a
shared Commander `docs/workflow.md` (Bulk Create → Run Sprint → Finish); that
is the *shipping* pipeline, not the product, so it lands under "How work ships"
except on commander itself — where the sprint pipeline *is* the product.

Usage:
    python project_flow.py <target> [--vault <dir>]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_STAGE_RE = re.compile(r"^## (Stage\s+\d+\s*[—–-]\s*.+)$", re.MULTILINE)
_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)
_MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")
_NUMBERED_STEP_RE = re.compile(
    r"^(\d+)\.\s+\*\*([^*]+)\*\*\s*[.—–-]?\s*(.*)$",
    re.MULTILINE,
)
_FLOW_SECTION_RE = re.compile(
    r"^#{2,3}\s+.*\b("
    r"core user flows?|core flows?|user flows?|"
    r"three jobs|primary flows?"
    r")\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_COMMANDER_MARKERS = ("Bulk Create", "Run Sprint")


def _load_target_local(target: str, targets_yaml: Path | None = None) -> Path | None:
    path = targets_yaml or TARGETS_YAML
    try:
        data = yaml.safe_load(path.read_text()) or {}
        local = (data.get("targets", {}).get(target) or {}).get("local")
        return Path(local).expanduser() if local else None
    except Exception:
        return None


def _latest_snapshot(project_dir: Path) -> Path | None:
    raw = project_dir / "raw"
    if not raw.is_dir():
        return None
    dirs = sorted(d for d in raw.iterdir() if d.is_dir())
    return dirs[-1] if dirs else None


def _node_id(label: str, used: set) -> str:
    base = _SLUG_RE.sub("", label)[:24] or "n"
    if base[0].isdigit():
        base = "s" + base
    nid = base
    i = 2
    while nid in used:
        nid = f"{base}{i}"
        i += 1
    used.add(nid)
    return nid


def _short_label(label: str) -> str:
    """Drop the 'Stage N —' prefix so diagram boxes stay readable."""
    m = re.match(r"^Stage\s+\d+\s*[—–-]\s*(.+)$", label.strip())
    if m:
        return m.group(1).strip()
    return label.strip()


def _lifecycle_mermaid(stages: list[str]) -> str:
    if len(stages) < 2:
        return ""
    used: set = set()
    ids = []
    lines = ["```mermaid", "flowchart LR"]
    for stage in stages:
        label = _short_label(stage)
        nid = _node_id(label, used)
        ids.append(nid)
        lines.append(f"  {nid}[{label}]")
    for a, b in zip(ids, ids[1:]):
        lines.append(f"  {a} --> {b}")
    lines.append("```")
    return "\n".join(lines)


def _extract_stages(workflow_text: str) -> list[str]:
    return [m.group(1).strip() for m in _STAGE_RE.finditer(workflow_text)]


def _is_commander_pipeline(workflow_text: str) -> bool:
    """True when workflow.md is the shared Commander sprint template."""
    if not workflow_text:
        return False
    if all(m in workflow_text for m in _COMMANDER_MARKERS):
        return True
    return bool(re.search(r"driven by\s+Commander", workflow_text, re.I))


def _first_paragraph_after(text: str, heading: str) -> str:
    """Return the first non-empty, non-quote paragraph after `## heading`."""
    pattern = re.compile(
        r"^## " + re.escape(heading) + r"\s*\n+(.*?)(?=\n## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return ""
    buf = []
    for line in m.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        if not stripped:
            if buf:
                break
            continue
        buf.append(stripped)
        if len(" ".join(buf)) > 280:
            break
    return " ".join(buf)


def _section_after_flow_heading(product_text: str) -> str:
    m = _FLOW_SECTION_RE.search(product_text)
    if not m:
        return ""
    start = m.end()
    rest = product_text[start:]
    stop = re.search(r"\n## [^#]", rest)
    return rest[: stop.start()] if stop else rest


def _extract_product_steps(product_text: str) -> list[tuple[str, str]]:
    """Return [(title, detail), ...] from PRODUCT.md core-flow sections."""
    if not product_text:
        return []
    section = _section_after_flow_heading(product_text)
    if not section:
        return []
    steps: list[tuple[str, str]] = []
    for m in _NUMBERED_STEP_RE.finditer(section):
        title = m.group(2).strip().rstrip(".")
        detail = m.group(3).strip()
        if title:
            steps.append((title, detail))
    return steps


def _supported_mermaid(block: str) -> bool:
    first = next((ln.strip() for ln in block.splitlines() if ln.strip()), "")
    return first.startswith("flowchart LR")


def _append_step(lines: list[str], title: str, detail: str) -> None:
    lines.append(f"### {title}\n")
    lines.append((detail or "_No summary._") + "\n")


def generate_flow(target: str, vault_dir: Path | None = None) -> Path:
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    project_dir = vault_dir / "projects" / target
    project_dir.mkdir(parents=True, exist_ok=True)
    local = _load_target_local(target)
    snapshot = _latest_snapshot(project_dir)

    lines = [
        f"# {target} — Flow\n",
        "Machine-generated from the target's own docs and atlas. "
        "Lookout does not invent features or stages. "
        "Product lifecycle comes from PRODUCT.md when present; the shared "
        "Commander sprint template in `docs/workflow.md` is listed separately "
        "as how work ships.\n",
    ]

    workflow_text = ""
    workflow_path = (local / "docs" / "workflow.md") if local else None
    if workflow_path and workflow_path.is_file():
        workflow_text = workflow_path.read_text(encoding="utf-8", errors="replace")

    product_text = ""
    product_path = (local / "PRODUCT.md") if local else None
    if product_path and product_path.is_file():
        product_text = product_path.read_text(encoding="utf-8", errors="replace")

    product_steps = _extract_product_steps(product_text)
    workflow_stages = _extract_stages(workflow_text) if workflow_text else []
    commander_template = _is_commander_pipeline(workflow_text)
    is_commander = target == "commander"

    lines.append("## Product lifecycle\n")
    if product_steps:
        titles = [t for t, _ in product_steps]
        mermaid = _lifecycle_mermaid(titles)
        lines.append(
            f"Extracted from `{target}` `PRODUCT.md` "
            f"({len(product_steps)} numbered step(s)).\n"
        )
        if mermaid:
            lines.append(mermaid + "\n")
        for title, detail in product_steps:
            _append_step(lines, title, detail)
    elif workflow_stages and (is_commander or not commander_template):
        mermaid = _lifecycle_mermaid(workflow_stages)
        lines.append(
            f"Extracted from `{target}` `docs/workflow.md` "
            f"({len(workflow_stages)} stage heading(s)).\n"
        )
        if mermaid:
            lines.append(mermaid + "\n")
        for stage in workflow_stages:
            _append_step(
                lines, stage, _first_paragraph_after(workflow_text, stage)
            )
    elif commander_template and not is_commander:
        lines.append(
            f"_No product user-flow list found in `{target}` `PRODUCT.md`. "
            "The `docs/workflow.md` file is the shared Commander sprint "
            "template (Bulk Create → Run Sprint → Finish), so it is listed "
            "under How work ships below — not as this product's lifecycle._\n"
        )
    elif not workflow_text and not product_text:
        lines.append(
            f"_No `PRODUCT.md` or `docs/workflow.md` in the {target} clone._\n"
        )
    else:
        headings = [m.group(1).strip() for m in _HEADING_RE.finditer(workflow_text)]
        lines.append(
            "_No numbered product steps found in PRODUCT.md "
            f"and no usable `## Stage N` headings in workflow.md. "
            f"Workflow sections: {', '.join(headings) or '(none)'}._\n"
        )

    if commander_template and workflow_stages and not is_commander:
        lines.append("## How work ships\n")
        lines.append(
            f"From `{target}` `docs/workflow.md` — the Commander sprint pipeline "
            f"used to build this project ({len(workflow_stages)} stage(s)). "
            "This is how tickets ship, not the end-user product flow.\n"
        )
        mermaid = _lifecycle_mermaid(workflow_stages)
        if mermaid:
            lines.append(mermaid + "\n")
        for stage in workflow_stages:
            _append_step(
                lines, stage, _first_paragraph_after(workflow_text, stage)
            )

    arch_path = (local / "docs" / "architecture.md") if local else None
    if arch_path and arch_path.is_file():
        arch_text = arch_path.read_text(encoding="utf-8", errors="replace")
        copied = False
        for block in _MERMAID_RE.findall(arch_text):
            if _supported_mermaid(block):
                lines.append("## Architecture (from the project)\n")
                lines.append("Copied from `docs/architecture.md`.\n")
                lines.append("```mermaid\n" + block.strip() + "\n```\n")
                copied = True
                break
        if not copied:
            lines.append("## Architecture (from the project)\n")
            lines.append(
                "_`docs/architecture.md` has no `flowchart LR` mermaid block "
                "to copy._\n"
            )

    lines.append("## Sitemap\n")
    atlas_index = project_dir / "atlas" / "index.md"
    if atlas_index.exists():
        lines.append(
            f"Feature inventory lives in the atlas: "
            f"[[projects/{target}/atlas/index]].\n"
        )
    else:
        lines.append("_No atlas index yet — run `atlas_seed.py` on this target._\n")

    docs_files: list[str] = []
    if snapshot and (snapshot / "docs_manifest.json").exists():
        try:
            manifest = json.loads((snapshot / "docs_manifest.json").read_text())
            docs_files = [
                e["path"] for e in manifest.get("files", [])
                if isinstance(e, dict) and e.get("path", "").endswith(".md")
            ]
        except (OSError, json.JSONDecodeError):
            docs_files = []
    if docs_files:
        lines.append("Docs recorded in the latest snapshot:\n")
        for path in docs_files:
            lines.append(f"- `{path}`")
        lines.append("")
    else:
        lines.append("_No markdown docs recorded in the latest snapshot._\n")

    out = project_dir / "flow.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate flow.md for a target")
    parser.add_argument("target")
    parser.add_argument("--vault", default=str(REPO_ROOT / "vault"))
    args = parser.parse_args()
    out = generate_flow(args.target, Path(args.vault))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

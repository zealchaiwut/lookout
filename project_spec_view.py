"""project_spec_view.py — Spec Hub (planning SoT readable view).

Writes vault/projects/<target>/spec.md: Product, Requirements, Design, and API
panes with stable heading anchors for lookup. Prefers the vault Spec
workspace over the clone.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_ABSENT = "_Absent in source._"


def _load_local(target: str) -> Path | None:
    try:
        data = yaml.safe_load(TARGETS_YAML.read_text()) or {}
        local = (data.get("targets", {}).get(target) or {}).get("local")
        return Path(local).expanduser() if local else None
    except Exception:
        return None


def _section(text: str, *title_prefixes: str) -> str:
    """Return body of the first ## section whose title starts with any prefix."""
    lines = text.splitlines()
    collecting = False
    out: list[str] = []
    for line in lines:
        if re.match(r"^##\s+", line):
            title = re.sub(r"^##\s+", "", line).strip().lower()
            if collecting:
                break
            collecting = any(title.startswith(p.lower()) for p in title_prefixes)
            continue
        if collecting:
            out.append(line)
    return "\n".join(out).strip()


def _bullet_lines(body: str, limit: int = 20) -> list[str]:
    """Collect numbered/bulleted items, joining wrapped continuation lines."""
    items: list[str] = []
    current: str | None = None
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("- ") or re.match(r"^\d+\.\s+", s):
            if current is not None:
                items.append(current)
                if len(items) >= limit:
                    return items
            current = s
        elif current is not None and s and not s.startswith("#"):
            # Continuation of a wrapped bullet
            current = current + " " + s
        elif current is not None and not s:
            items.append(current)
            current = None
            if len(items) >= limit:
                return items
    if current is not None and len(items) < limit:
        items.append(current)
    return items


def _non_goal_lines(text: str, limit: int = 8) -> list[str]:
    """Bullets or paragraphs that mention non-goal / Explicit non-goal."""
    found: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if re.search(r"non-?goal", s, re.I):
            found.append(s if s.startswith(("-", "1", "2", "3", "4", "5", "6", "7", "8", "9")) else f"- {s}")
        if len(found) >= limit:
            break
    return found


def _token_table_rows(body: str, limit: int = 16) -> list[str]:
    rows = []
    for line in body.splitlines():
        if not line.strip().startswith("|"):
            continue
        if re.search(r"\|\s*---", line):
            continue
        if re.search(r"\|\s*Token\s*\|", line, re.I) or re.search(
            r"\|\s*Role\s*\|", line, re.I
        ):
            continue
        rows.append(line.rstrip())
        if len(rows) >= limit:
            break
    return rows


def _milestone_table(body: str) -> list[str]:
    """Keep markdown table rows from a milestones section."""
    rows = [ln.rstrip() for ln in body.splitlines() if ln.strip().startswith("|")]
    return rows[:40] if rows else []


def _first_paragraph(body: str, max_lines: int = 6) -> str:
    para: list[str] = []
    for ln in body.splitlines():
        if not ln.strip():
            if para:
                break
            continue
        if ln.strip().startswith("#"):
            continue
        para.append(ln.rstrip())
        if len(para) >= max_lines:
            break
    return "\n".join(para).strip()


def _resolve_pack_file(vault_spec: Path, local: Path | None, name: str) -> Path | None:
    """Prefer vault Spec workspace copy; fall back to clone."""
    vault_path = vault_spec / name
    if vault_path.is_file():
        return vault_path
    if local is not None:
        clone_path = local / name
        if clone_path.is_file():
            return clone_path
        # SCHEMA aliases
        if name == "SCHEMA.md":
            for alt in ("schema.yaml", "schema.yml"):
                p = local / alt
                if p.is_file():
                    return p
    return None


def _read_text(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _latest_spec_json(project_dir: Path) -> dict | None:
    raw = project_dir / "raw"
    if not raw.is_dir():
        return None
    snaps = sorted(d for d in raw.iterdir() if d.is_dir())
    if not snaps:
        return None
    path = snaps[-1] / "spec.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _chrome(
    target: str,
    project_dir: Path,
    vault_spec: Path,
) -> list[str]:
    lines = [
        f"# {target} — Spec\n",
        "Planning-stage source of truth (readable). Portable files live under "
        f"`vault/projects/{target}/spec/`; promote copies them into the clone. "
        "Use the TOC below when you are confused mid-sprint.\n",
    ]

    # Completeness badge
    data = _latest_spec_json(project_dir)
    if data:
        from collectors.spec import format_badge_line
        badge = format_badge_line(data)
        if badge:
            lines.append(f"**Pack:** {badge}\n")
    else:
        lines.append(
            "**Pack:** _No `spec.json` yet — run `bin/lookout <target>`._\n"
        )

    # Lifecycle status
    status = "draft"
    updated = ""
    history: list = []
    if (vault_spec / "status.yaml").is_file():
        try:
            import spec_workspace as sw
            st = sw.read_status(vault_spec)
            status = st.get("status") or "draft"
            updated = st.get("updated") or ""
            history = list(st.get("history") or [])
        except Exception:
            raw = yaml.safe_load((vault_spec / "status.yaml").read_text()) or {}
            status = raw.get("status") or "draft"
            updated = raw.get("updated") or ""
            history = list(raw.get("history") or [])
    status_line = f"**Status:** `{status}`"
    if updated:
        status_line += f" · updated {updated}"
    lines.append(status_line + "\n")

    lines.append(
        "**CLI:** `lookout spec validate|submit|approve` · "
        "`lookout promote-spec` (when approved)\n"
    )

    # In-page TOC (anchors match ## / ### titles after site slugify)
    lines.append("## Contents\n")
    lines.extend([
        "- [Product](#product) — problem, jobs, concepts, non-goals",
        "- [Requirements](#requirements) — hard constraints",
        "- [Design](#design) — direction, signature, palette, type, layout",
        "- [API](#api) — OpenAPI pack",
        "",
    ])
    return lines, history


def _product_pane(product_text: str) -> list[str]:
    lines = ["## Product\n"]
    if not product_text.strip():
        lines.append(f"{_ABSENT.replace('source', 'PRODUCT.md')}\n")
        return lines

    problem = _section(product_text, "the problem", "problem")
    if problem:
        lines.append("### The problem\n")
        lines.append(_first_paragraph(problem, max_lines=8) or _ABSENT)
        lines.append("")
    else:
        lines.append("### The problem\n")
        lines.append("_Absent in PRODUCT.md._\n")

    jobs = _section(
        product_text, "what this tool must do", "core user flows", "core flows"
    )
    lines.append("### Jobs\n")
    if jobs:
        bullets = _bullet_lines(jobs)
        if bullets:
            lines.extend(bullets)
            lines.append("")
        else:
            lines.append(_first_paragraph(jobs) or "_No numbered jobs found._")
            lines.append("")
    else:
        lines.append("_Absent in PRODUCT.md._\n")

    concepts = _section(product_text, "core concepts")
    lines.append("### Core concepts\n")
    if concepts:
        bullets = _bullet_lines(concepts)
        lines.extend(bullets if bullets else ["_No concept bullets found._"])
        lines.append("")
    else:
        lines.append("_Absent in PRODUCT.md._\n")

    non_goals = _non_goal_lines(product_text)
    lines.append("### Non-goals\n")
    if non_goals:
        lines.extend(non_goals)
        lines.append("")
    else:
        # Also check jobs section for Explicit non-goal prose
        if jobs and re.search(r"non-?goal", jobs, re.I):
            for ln in jobs.splitlines():
                if re.search(r"non-?goal", ln, re.I):
                    lines.append(ln.strip() if ln.strip().startswith("-") else f"- {ln.strip()}")
            lines.append("")
        else:
            lines.append("_Absent in PRODUCT.md._\n")

    lines.append("_(source: PRODUCT.md)_\n")
    return lines


def _requirements_pane(product_text: str) -> list[str]:
    lines = ["## Requirements\n"]
    if not product_text.strip():
        lines.append("_Absent in PRODUCT.md._\n")
        return lines

    constraints = _section(product_text, "hard constraints", "constraints")
    lines.append("### Hard constraints\n")
    if constraints:
        bullets = _bullet_lines(constraints, limit=24)
        if bullets:
            lines.extend(bullets)
            lines.append("")
        else:
            lines.append(_first_paragraph(constraints, max_lines=12) or _ABSENT)
            lines.append("")
    else:
        lines.append("_Absent in PRODUCT.md._\n")

    # Milestones intentionally omitted: PRODUCT.md batch table drifts from
    # GitHub issues/sprints. Re-introduce when Lookout can join milestone
    # progress from the issues snapshot (separate ticket).

    lines.append("_(source: PRODUCT.md)_\n")
    return lines


def _palette_fence(rows: list[str]) -> list[str]:
    """Build a ```palette fence from markdown table rows (Token|Hex|Use)."""
    entries: list[str] = []
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 2:
            continue
        token, hex_v = cells[0], cells[1]
        use = cells[2] if len(cells) > 2 else ""
        # Split compound tokens like `--ok` / `--warn`
        if not re.search(r"#[0-9A-Fa-f]{3,8}", hex_v):
            continue
        # May contain multiple hexes separated by /
        hexes = re.findall(r"#[0-9A-Fa-f]{3,8}", hex_v)
        tokens = [t.strip() for t in re.split(r"\s*/\s*", token) if t.strip()]
        if len(tokens) == len(hexes) and len(tokens) > 1:
            for t, h in zip(tokens, hexes):
                entries.append(f"{t}|{h}|{use}")
        else:
            entries.append(f"{token}|{hexes[0]}|{use}")
    if not entries:
        return []
    out = ["```palette"]
    out.extend(entries)
    out.append("```")
    out.append("")
    return out


def _design_pane(design_text: str) -> list[str]:
    lines = ["## Design\n"]
    if not design_text.strip():
        lines.append("_Absent in DESIGN.md._\n")
        return lines

    direction = _section(design_text, "direction")
    lines.append("### Direction\n")
    if direction:
        # Include heading remainder if "## Direction: race telemetry"
        first = _first_paragraph(direction, max_lines=5)
        # Also pull subtitle from section title via a dedicated scan
        for raw in design_text.splitlines():
            m = re.match(r"^##\s+Direction\s*:\s*(.+)$", raw, re.I)
            if m:
                lines.append(f"**{m.group(1).strip()}**\n")
                break
        if first:
            lines.append(first)
            lines.append("")
    else:
        lines.append("_Absent in DESIGN.md._\n")

    signature = _section(design_text, "signature")
    lines.append("### Signature element\n")
    if signature:
        lines.append(_first_paragraph(signature, max_lines=6) or _ABSENT)
        lines.append("")
    else:
        lines.append("_Absent in DESIGN.md._\n")

    palette = _section(design_text, "palette", "tokens", "colour", "color")
    lines.append("### Palette\n")
    if palette:
        rows = _token_table_rows(palette)
        lines.extend(_palette_fence(rows))
        if rows:
            lines.append("| Token | Value | Use |")
            lines.append("|---|---|---|")
            lines.extend(rows[:12])
            lines.append("")
        else:
            lines.append(_first_paragraph(palette) or _ABSENT)
            lines.append("")
    else:
        lines.append("_Absent in DESIGN.md._\n")

    typography = _section(design_text, "typography", "type")
    lines.append("### Typography\n")
    if typography:
        bullets = _bullet_lines(typography, limit=12)
        if bullets:
            lines.extend(bullets)
            lines.append("")
        else:
            lines.append(_first_paragraph(typography, max_lines=10) or _ABSENT)
            lines.append("")
    else:
        lines.append("_Absent in DESIGN.md._\n")

    layout = _section(design_text, "layout")
    lines.append("### Layout\n")
    if layout:
        fence = re.search(r"```[\s\S]*?```", layout)
        if fence:
            lines.append(fence.group(0))
            lines.append("")
        bullets = _bullet_lines(layout, limit=8)
        if bullets:
            lines.extend(bullets)
            lines.append("")
        elif not fence:
            lines.append(_first_paragraph(layout) or _ABSENT)
            lines.append("")
    else:
        lines.append("_Absent in DESIGN.md._\n")

    motion = _section(design_text, "motion", "interaction")
    if motion:
        lines.append("### Motion and interaction\n")
        lines.append(_first_paragraph(motion, max_lines=5) or _ABSENT)
        lines.append("")

    lines.append("_(source: DESIGN.md)_\n")
    return lines


def _api_pane(target: str, vault_spec: Path, local: Path | None) -> list[str]:
    lines = ["## API\n"]
    vault_api = vault_spec / "api.yaml"
    clone_api = (local / "api.yaml") if local else None
    openapi_vault = vault_spec / "openapi.yaml"

    present = []
    if vault_api.is_file() or openapi_vault.is_file():
        present.append("vault")
    if clone_api and clone_api.is_file():
        present.append("clone")

    if not present:
        lines.append(
            "_No `api.yaml` in the Spec workspace or clone. "
            "Draft one under `spec/api.yaml`, then promote._\n"
        )
        return lines

    path_count = 0
    api_path = vault_api if vault_api.is_file() else (
        openapi_vault if openapi_vault.is_file() else clone_api
    )
    if api_path and api_path.is_file():
        try:
            data = yaml.safe_load(api_path.read_text()) or {}
            paths = data.get("paths") or {}
            if isinstance(paths, dict):
                path_count = len(paths)
        except Exception:
            pass

    if path_count:
        lines.append(f"**{path_count}** documented path(s).\n")
    if "vault" in present:
        lines.append(
            f"- Vault: [[projects/{target}/spec/api|spec/api.yaml]]\n"
        )
    if "clone" in present:
        lines.append(f"- Clone: `api.yaml` present\n")
    else:
        lines.append(
            "- Clone: absent — promote to flip Spec pack API ✓\n"
        )
    lines.append(
        f"- Path table on [[projects/{target}/discovery#api-map|Discovery → API map]]\n"
    )
    lines.append("")
    return lines


def generate_spec(target: str, vault_dir: Path | None = None) -> Path:
    """Write spec.md (Spec Hub). Does not write spec-view.md."""
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    project_dir = vault_dir / "projects" / target
    project_dir.mkdir(parents=True, exist_ok=True)
    vault_spec = project_dir / "spec"
    vault_spec.mkdir(parents=True, exist_ok=True)
    local = _load_local(target)

    chrome, _history = _chrome(target, project_dir, vault_spec)

    product_path = _resolve_pack_file(vault_spec, local, "PRODUCT.md")
    design_path = _resolve_pack_file(vault_spec, local, "DESIGN.md")
    product_text = _read_text(product_path)
    design_text = _read_text(design_path)

    lines: list[str] = []
    lines.extend(chrome)
    lines.extend(_product_pane(product_text))
    lines.extend(_requirements_pane(product_text))
    lines.extend(_design_pane(design_text))
    lines.extend(_api_pane(target, vault_spec, local))

    out = project_dir / "spec.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Drop legacy stub if present
    stub = project_dir / "spec-view.md"
    if stub.is_file():
        stub.unlink()
    return out


def generate_spec_view(target: str, vault_dir: Path | None = None) -> Path:
    """Backward-compatible alias — returns the Spec Hub path (`spec.md`)."""
    return generate_spec(target, vault_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Spec Hub (spec.md) for a target")
    parser.add_argument("target")
    parser.add_argument("--vault", default=str(REPO_ROOT / "vault"))
    args = parser.parse_args()
    out = generate_spec(args.target, Path(args.vault))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

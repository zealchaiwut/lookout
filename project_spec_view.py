"""project_spec_view.py — human-readable Spec view from PRODUCT.md + DESIGN.md.

Writes vault/projects/<target>/spec-view.md: short extracts a person can scan
in the Lookout site, without reading raw OpenAPI YAML. Machine-owned whole file.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"


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


def _bullet_lines(body: str, limit: int = 12) -> list[str]:
    items = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("- ") or re.match(r"^\d+\.\s+", s):
            items.append(s)
        if len(items) >= limit:
            break
    return items


def _token_table_rows(body: str, limit: int = 12) -> list[str]:
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


def _product_extract(text: str) -> list[str]:
    lines = ["## Product\n"]
    jobs = _section(text, "what this tool must do", "core user flows", "core flows")
    concepts = _section(text, "core concepts")
    if jobs:
        lines.append("### Jobs / flows\n")
        bullets = _bullet_lines(jobs)
        if bullets:
            lines.extend(bullets)
            lines.append("")
        else:
            lines.append("_No numbered jobs found._\n")
    if concepts:
        lines.append("### Core concepts\n")
        bullets = _bullet_lines(concepts)
        if bullets:
            lines.extend(bullets)
            lines.append("")
        else:
            lines.append("_No concept bullets found._\n")
    if not jobs and not concepts:
        # Fall back to first ~20 non-empty lines after the title
        body_lines = [
            ln for ln in text.splitlines()[1:] if ln.strip() and not ln.startswith("#")
        ][:12]
        lines.extend(body_lines)
        lines.append("")
    lines.append("_(source: PRODUCT.md)_\n")
    return lines


def _design_extract(text: str) -> list[str]:
    lines = ["## Design\n"]
    direction = _section(text, "direction")
    if direction:
        first = next((ln.strip() for ln in direction.splitlines() if ln.strip()), "")
        if first:
            lines.append(f"**Direction:** {first}\n")
    palette = _section(text, "palette", "tokens", "colour", "color")
    rows = _token_table_rows(palette) if palette else []
    if rows:
        lines.append("### Tokens\n")
        lines.append("| Token | Value | Use |")
        lines.append("|---|---|---|")
        # Keep original row shape if 3+ cells; otherwise pass through
        for row in rows[:10]:
            lines.append(row)
        lines.append("")
    layout = _section(text, "layout")
    if layout:
        lines.append("### Layout\n")
        # Prefer a fenced diagram or first short paragraph
        fence = re.search(r"```[\s\S]*?```", layout)
        if fence:
            lines.append(fence.group(0))
            lines.append("")
        else:
            para = []
            for ln in layout.splitlines():
                if ln.strip():
                    para.append(ln.rstrip())
                elif para:
                    break
            lines.extend(para[:8])
            lines.append("")
    if len(lines) == 1:
        lines.append("_No direction / palette / layout sections found._\n")
    lines.append("_(source: DESIGN.md)_\n")
    return lines


def generate_spec_view(target: str, vault_dir: Path | None = None) -> Path:
    if vault_dir is None:
        vault_dir = REPO_ROOT / "vault"
    project_dir = vault_dir / "projects" / target
    project_dir.mkdir(parents=True, exist_ok=True)
    local = _load_local(target)

    lines = [
        f"# {target} — Spec\n",
        "Human-readable extract of the Spec pack. Portable sources live in the "
        "target clone (and optionally under `spec/` in this vault). Raw "
        "`api.yaml` is linked when present — this page is for scanning.\n",
    ]

    # Completeness from latest snapshot when available
    raw = project_dir / "raw"
    if raw.is_dir():
        snaps = sorted(d for d in raw.iterdir() if d.is_dir())
        if snaps and (snaps[-1] / "spec.json").exists():
            import json
            from collectors.spec import format_badge_line
            data = json.loads((snaps[-1] / "spec.json").read_text())
            badge = format_badge_line(data)
            if badge:
                lines.append("## Completeness\n")
                lines.append(f"{badge}\n")
                lines.append("_(source: spec.json)_\n")

    if local is None or not local.is_dir():
        lines.append(
            f"_No local clone for `{target}`. Set `local:` in targets.yaml._\n"
        )
    else:
        product = local / "PRODUCT.md"
        design = local / "DESIGN.md"
        if product.is_file():
            lines.extend(_product_extract(product.read_text(encoding="utf-8", errors="replace")))
        else:
            lines.append("## Product\n\n_`PRODUCT.md` absent._\n")
        if design.is_file():
            lines.extend(_design_extract(design.read_text(encoding="utf-8", errors="replace")))
        else:
            lines.append("## Design\n\n_`DESIGN.md` absent._\n")

        vault_api = project_dir / "spec" / "api.yaml"
        clone_api = local / "api.yaml"
        if clone_api.is_file() or vault_api.is_file():
            lines.append("## API\n")
            if clone_api.is_file():
                lines.append(f"- Clone: `api.yaml` present at `{clone_api}`\n")
            if vault_api.is_file():
                lines.append(
                    "- Vault draft: [[projects/"
                    f"{target}/spec/api|spec/api.yaml]] "
                    "(promote into the clone to flip Spec pack API ✓)\n"
                )

    out = project_dir / "spec-view.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate spec-view.md for a target")
    parser.add_argument("target")
    parser.add_argument("--vault", default=str(REPO_ROOT / "vault"))
    args = parser.parse_args()
    out = generate_spec_view(args.target, Path(args.vault))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

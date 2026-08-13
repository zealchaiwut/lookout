"""
atlas_coverage.py — report which atlas features can be traced, and what blocks the rest.

The first full `--all-stale` pass traced 26 of 185 features. The other 159 are
not a lookout defect: each records an open question saying no feature-named test
or source file exists in the target repository, so tracing has no way in. That
unlock lives in the target repos, not here.

That information was spread across 159 individual notes, which made it
impossible to answer "which project is worth investing in" or "which one file
would unlock a diagram" without opening each note by hand. This turns the gaps
into a work list.

Entry-point resolution is imported from `atlas_trace` rather than reimplemented,
so the report cannot drift from what tracing actually does.

Output — `vault/atlas-coverage.md`
---------------------------------
A per-project summary (traced / blocked / total / coverage) followed by the
blocked features, each with the filename that would unlock it.

Machine-owned and regenerated whole. It carries no timestamp, so an unchanged
fleet produces no diff.

Usage
-----
    python3 atlas_coverage.py [--vault <dir>] [--targets-yaml <path>]
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

import atlas_trace

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)

TRACED = "traced"
BLOCKED = "blocked"
UNAVAILABLE = "unavailable"


def _diagram_node_count(note_text: str) -> int:
    """Number of node/edge lines inside the note's mermaid block."""
    m = _MERMAID_RE.search(note_text)
    if not m:
        return 0
    body = m.group(1)
    return sum(
        1 for line in body.splitlines()
        if line.strip() and not line.strip().startswith("flowchart")
    )


def suggested_test_filename(slug: str) -> str:
    """The file a target could add to make a feature traceable.

    Follows the `tests/test_<feature>__<criterion>.py` convention that
    `atlas_trace` keys on; the criterion suffix is optional so the plain form is
    suggested.
    """
    return f"tests/test_{slug.replace('-', '_')}.py"


def _load_targets(targets_yaml: Path) -> dict:
    with open(targets_yaml) as fh:
        return (yaml.safe_load(fh) or {}).get("targets", {})


def _atlas_notes(project_dir: Path) -> list:
    atlas = project_dir / "atlas"
    if not atlas.is_dir():
        return []
    return sorted(p for p in atlas.glob("*.md") if p.name != "index.md")


def _feature_name(note_text: str, slug: str) -> str:
    m = re.search(r"^feature:\s*(.+)$", note_text, re.MULTILINE)
    return m.group(1).strip() if m else slug


def analyse_target(target: str, local_path: Path | None, vault_dir: Path) -> dict:
    """Classify every atlas feature for one target.

    Returns {"status", "traced": [...], "blocked": [(slug, name, suggestion)], "total"}.
    A target whose local checkout is missing is reported as unavailable rather
    than counted as blocked — absence of source is not the same as absence of an
    entry point, and conflating them would overstate the work to be done.
    """
    project_dir = vault_dir / "projects" / target
    notes = _atlas_notes(project_dir)

    if local_path is None or not local_path.is_dir():
        return {"status": UNAVAILABLE, "traced": [], "blocked": [], "total": len(notes)}

    traced: list = []
    blocked: list = []
    for note in notes:
        text = note.read_text(encoding="utf-8", errors="replace")
        slug = note.stem
        if _diagram_node_count(text) > 0:
            traced.append(slug)
            continue
        name = _feature_name(text, slug)
        candidates = atlas_trace._candidate_entry_points(slug, name, local_path)
        if not candidates:
            reason = "no entry point"
            action = f"add `{suggested_test_filename(slug)}`"
        else:
            # A candidate exists but tracing it reached nothing — typically a
            # test that drives the app over HTTP and imports no local module.
            # Telling the reader to "add a test" here would be wrong advice:
            # the test exists, it just cannot be followed.
            entry = candidates[0].relative_to(local_path)
            reason = "entry imports nothing local"
            action = f"make `{entry}` import the modules it exercises"
        blocked.append((slug, name, reason, action))

    return {
        "status": "ok",
        "traced": traced,
        "blocked": blocked,
        "total": len(notes),
    }


def _pct(part: int, whole: int) -> str:
    return "—" if not whole else f"{round(100 * part / whole)}%"


def render_report(results: dict) -> str:
    """Render the coverage report. Deterministic — no timestamp, no run id."""
    lines = [
        "# Atlas Coverage",
        "",
        "Which atlas features have a traced diagram, and what blocks the rest.",
        "",
        "A feature is traceable when the target repository has a test or source "
        "file named after it — see [[agents]] for who owns what. Blocked "
        "features are not a lookout defect: the unlock is a file in the target "
        "repo, named below.",
        "",
        "## Summary",
        "",
        "| Project | Traced | Blocked | Total | Coverage |",
        "|---|---|---|---|---|",
    ]

    t_tr = t_bl = t_tot = 0
    for target in sorted(results):
        r = results[target]
        if r["status"] == UNAVAILABLE:
            lines.append(f"| {target} | — | — | {r['total']} | _local checkout unavailable_ |")
            continue
        tr, bl, tot = len(r["traced"]), len(r["blocked"]), r["total"]
        t_tr += tr
        t_bl += bl
        t_tot += tot
        lines.append(f"| {target} | {tr} | {bl} | {tot} | {_pct(tr, tot)} |")

    lines += [
        f"| **Fleet** | **{t_tr}** | **{t_bl}** | **{t_tot}** | **{_pct(t_tr, t_tot)}** |",
        "",
    ]

    any_blocked = any(
        results[t]["status"] != UNAVAILABLE and results[t]["blocked"]
        for t in results
    )
    if not any_blocked:
        lines += ["## Blocked features", "", "_None — every feature has a traceable entry point._", ""]
        return "\n".join(lines) + "\n"

    lines += [
        "## Blocked features",
        "",
        "Each row names what would give tracing a way in. Most need a "
        "feature-named test; a few already have one that imports nothing local "
        "and so cannot be followed.",
        "",
    ]
    for target in sorted(results):
        r = results[target]
        if r["status"] == UNAVAILABLE or not r["blocked"]:
            continue
        lines += [
            f"### {target}",
            "",
            "| Feature | Why | What would unlock it |",
            "|---|---|---|",
        ]
        for slug, name, reason, action in sorted(r["blocked"]):
            lines.append(f"| {name} | {reason} | {action} |")
        lines.append("")

    return "\n".join(lines) + "\n"


def generate_coverage(
    vault_dir: Path | None = None,
    targets_yaml: Path | None = None,
) -> Path:
    """Analyse every registered target and write vault/atlas-coverage.md."""
    vault_dir = vault_dir or REPO_ROOT / "vault"
    targets_yaml = targets_yaml or TARGETS_YAML

    results: dict = {}
    for target, cfg in _load_targets(targets_yaml).items():
        if not (vault_dir / "projects" / target / "atlas").is_dir():
            continue
        local = cfg.get("local")
        local_path = Path(local).expanduser() if local else None
        results[target] = analyse_target(target, local_path, vault_dir)

    out = vault_dir / "atlas-coverage.md"
    out.write_text(render_report(results), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(prog="atlas_coverage.py", description=__doc__)
    parser.add_argument("--vault", default=str(REPO_ROOT / "vault"))
    parser.add_argument("--targets-yaml", default=str(TARGETS_YAML))
    args = parser.parse_args()

    vault_dir = Path(args.vault)
    if not vault_dir.is_dir():
        print(f"atlas_coverage: vault not found: {vault_dir}", file=sys.stderr)
        sys.exit(1)

    path = generate_coverage(vault_dir, Path(args.targets_yaml))
    print(f"atlas_coverage: wrote {path}")


if __name__ == "__main__":
    main()

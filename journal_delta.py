"""
journal_delta.py — journal entry delta collector for Lookout.

Reads targets.yaml to find the journal_entries source path and registered
target names.  For each qualifying .md file, extracts:
  - frontmatter fields
  - lines containing a registered target name (case-insensitive)
  - lines under any ## Concerns or ### Concerns heading

Full entry body text is never written to the output.

Output (journal_delta.json)
---------------------------
{
    "entries": [
        {
            "date": str,           # from frontmatter or filename
            "path": str,           # relative path within journal_entries dir
            "frontmatter": dict,   # all parsed frontmatter fields
            "target_lines": list,  # body lines mentioning a target name
            "concerns_lines": list # body lines under a ## / ### Concerns heading
        },
        ...
    ]
}

Or, when the journal_entries path is absent:
    { "source": "absent" }

Snapshot (snapshot.json)
------------------------
{ "timestamp": float }   # last mtime seen; updated after each run

Exit codes
----------
0 — always (absence is not an error)
"""
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"

_MAX_FIRST_RUN = 30


def _load_config(targets_yaml: Path) -> tuple[Path | None, list[str]]:
    """Return (journal_entries_path, [target_names])."""
    with open(targets_yaml) as f:
        data = yaml.safe_load(f)

    raw_path = data.get("sources", {}).get("journal_entries", "")
    entries_path = Path(raw_path).expanduser() if raw_path else None
    target_names = list(data.get("targets", {}).keys())
    return entries_path, target_names


def _make_serializable(obj):
    """Recursively convert non-JSON-serializable objects (e.g. date) to str."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, (int, float, bool, str)) or obj is None:
        return obj
    return str(obj)


def _parse_frontmatter(text: str) -> tuple[dict, list[str]]:
    """Split YAML frontmatter from body lines.

    Returns (frontmatter_dict, body_lines).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, lines

    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break

    if end is None:
        return {}, lines

    fm_text = "\n".join(lines[1:end])
    try:
        fm = _make_serializable(yaml.safe_load(fm_text) or {})
    except Exception:
        fm = {}

    body_lines = lines[end + 1:]
    return fm, body_lines


def _extract_target_lines(body_lines: list[str], target_names: list[str]) -> list[str]:
    """Return lines that mention any registered target name (case-insensitive)."""
    lower_names = [n.lower() for n in target_names]
    result = []
    for line in body_lines:
        lower_line = line.lower()
        if any(name in lower_line for name in lower_names):
            result.append(line)
    return result


def _extract_concerns_lines(body_lines: list[str]) -> list[str]:
    """Return lines that appear under a ## Concerns or ### Concerns heading."""
    result = []
    in_concerns = False
    for line in body_lines:
        stripped = line.strip()
        # Detect start of Concerns section
        if stripped in ("## Concerns", "### Concerns"):
            in_concerns = True
            continue
        # Any other heading ends the Concerns section
        if in_concerns and stripped.startswith("#"):
            in_concerns = False
        if in_concerns and stripped:
            result.append(line)
    return result


def _process_entry(md_path: Path, entries_dir: Path, target_names: list[str]) -> dict | None:
    """Parse a .md file and return a delta entry, or None if no relevant lines."""
    try:
        text = md_path.read_text(errors="replace")
    except OSError:
        return None

    fm, body_lines = _parse_frontmatter(text)
    target_lines = _extract_target_lines(body_lines, target_names)
    concerns_lines = _extract_concerns_lines(body_lines)

    if not target_lines and not concerns_lines:
        return None

    date_val = fm.get("date", md_path.stem)
    rel_path = str(md_path.relative_to(entries_dir))

    return {
        "date": str(date_val),
        "path": rel_path,
        "frontmatter": fm,
        "target_lines": target_lines,
        "concerns_lines": concerns_lines,
    }


def collect(
    output_path: Path | None = None,
    snapshot_path: Path | None = None,
) -> None:
    """Run the journal delta collection and write output_path."""
    if output_path is None:
        output_path = REPO_ROOT / "journal_delta.json"
    if snapshot_path is None:
        snapshot_path = REPO_ROOT / "journal_delta_snapshot.json"

    entries_path, target_names = _load_config(TARGETS_YAML)

    if entries_path is None or not entries_path.exists():
        output_path.write_text(json.dumps({"source": "absent"}, indent=2))
        return

    # Load snapshot timestamp (None on first run)
    prior_ts: float | None = None
    if snapshot_path.exists():
        try:
            snap = json.loads(snapshot_path.read_text())
            prior_ts = float(snap.get("timestamp", 0)) or None
        except (json.JSONDecodeError, ValueError):
            prior_ts = None

    # Collect qualifying .md files
    all_md = [p for p in entries_path.iterdir() if p.suffix == ".md" and p.is_file()]

    if prior_ts is None:
        # First run: cap at 30 newest by mtime
        all_md.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        candidates = all_md[:_MAX_FIRST_RUN]
    else:
        # Subsequent run: only files newer than snapshot
        candidates = [p for p in all_md if p.stat().st_mtime > prior_ts]

    entries = []
    for md_path in candidates:
        entry = _process_entry(md_path, entries_path, target_names)
        if entry is not None:
            entries.append(entry)

    # Update snapshot to the newest mtime seen across all candidates
    new_ts = max((p.stat().st_mtime for p in all_md), default=prior_ts or 0.0)
    snapshot_path.write_text(json.dumps({"timestamp": new_ts}, indent=2))

    output_path.write_text(json.dumps({"entries": entries}, indent=2))


def main() -> None:
    collect()


if __name__ == "__main__":
    main()

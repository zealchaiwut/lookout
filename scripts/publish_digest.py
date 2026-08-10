"""publish_digest.py — Publish a weekly vault digest to a single Notion page.

Reads vault/index.md (project index rows, situation one-liners) and
vault/ideas/index.md (ideas ledger table), then fully overwrites one
Notion page with the combined content.

Usage:
    python scripts/publish_digest.py [--targets-yaml PATH] [--vault-index PATH]
        [--ideas-index PATH]

The Notion page ID is read from targets.yaml under sources.notion_digest_page_id.
NOTION_TOKEN env var must be set.

Exit codes:
    0 — success
    1 — configuration error or vault read failure
"""
import argparse
import os
import re
import sys
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGETS_YAML = REPO_ROOT / "targets.yaml"
VAULT_INDEX = REPO_ROOT / "vault" / "index.md"
IDEAS_INDEX = REPO_ROOT / "vault" / "ideas" / "index.md"

_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_index_rows(text: str) -> list:
    """Extract data rows from the vault index markdown table.

    Handles the header row (normalised to snake_case keys) and skips the
    separator row.  Stops at the first non-table line after the table starts.
    """
    rows = []
    in_table = False
    header = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not in_table:
            header = [
                re.sub(r"[-\s]+", "_", h.lower()).strip("_") for h in cells
            ]
            in_table = True
            continue
        # Skip separator row (cells composed only of dashes)
        if all(re.fullmatch(r"-+", c) for c in cells if c):
            continue
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return rows


def parse_ideas_ledger(text: str) -> list:
    """Extract data rows from the ideas ledger markdown table."""
    return parse_index_rows(text)


# ---------------------------------------------------------------------------
# Notion API — write helpers (single authorised write endpoint)
# ---------------------------------------------------------------------------


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": _NOTION_VERSION,
    }


def _delete_page_blocks(page_id: str, token: str) -> None:
    """Delete every child block on the page so the next write is a clean slate."""
    hdrs = _headers(token)
    cursor = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        resp = requests.get(
            f"{_NOTION_API}/blocks/{page_id}/children",
            headers=hdrs,
            params=params,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        for block in data.get("results", []):
            requests.delete(
                f"{_NOTION_API}/blocks/{block['id']}",
                headers=hdrs,
                timeout=_TIMEOUT,
            ).raise_for_status()
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")


def _write_page_blocks(page_id: str, blocks: list, token: str) -> None:
    """Append blocks to the Notion page in batches of 100 (API limit)."""
    hdrs = _headers(token)
    for i in range(0, max(len(blocks), 1), 100):
        batch = blocks[i : i + 100]
        if not batch:
            break
        requests.patch(
            f"{_NOTION_API}/blocks/{page_id}/children",
            headers=hdrs,
            json={"children": batch},
            timeout=_TIMEOUT,
        ).raise_for_status()


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------


def _h2(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _para(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _build_blocks(index_rows: list, ideas_rows: list) -> list:
    """Build the complete list of Notion blocks for the digest page."""
    blocks = []

    blocks.append(_h2("Project Index"))
    for row in index_rows:
        target = row.get("target", "")
        one_liner = row.get("one_liner", "")
        capacity = row.get("capacity", "")
        todos = row.get("todos", "")
        last_run = row.get("last_run", "")
        blocks.append(
            _para(
                f"{target} | {one_liner} | capacity: {capacity}"
                f" | todos: {todos} | last run: {last_run}"
            )
        )

    blocks.append(_divider())

    blocks.append(_h2("Situation One-Liners"))
    for row in index_rows:
        target = row.get("target", "")
        one_liner = row.get("one_liner", "")
        blocks.append(_para(f"{target}: {one_liner}"))

    blocks.append(_divider())

    blocks.append(_h2("Ideas Ledger"))
    for row in ideas_rows:
        idea = row.get("idea", "")
        status = row.get("status", "")
        effort = row.get("effort", "")
        blocked = row.get("blocked_by", "")
        age = row.get("age", "")
        blocks.append(_para(
            f"{idea} | status: {status} | effort: {effort}"
            f" | blocked-by: {blocked} | age: {age}"
        ))

    return blocks


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def publish(
    targets_yaml=None,
    vault_index=None,
    ideas_index=None,
) -> None:
    """Read vault files and overwrite the Notion digest page.

    Raises SystemExit(1) on configuration or read errors.
    """
    _targets_yaml = Path(targets_yaml) if targets_yaml else TARGETS_YAML
    _vault_index = Path(vault_index) if vault_index else VAULT_INDEX
    _ideas_index = Path(ideas_index) if ideas_index else IDEAS_INDEX

    # Read config
    try:
        with open(_targets_yaml) as fh:
            config = yaml.safe_load(fh) or {}
    except OSError as exc:
        print(f"ERROR: Cannot read targets.yaml: {exc}", file=sys.stderr)
        sys.exit(1)

    page_id = config.get("sources", {}).get("notion_digest_page_id", "")
    if not page_id or str(page_id).strip().lower() in ("", "<placeholder>", "null", "none"):
        print(
            "ERROR: targets.yaml sources.notion_digest_page_id is missing or not configured. "
            "Set it to the Notion page ID for the weekly digest.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Read vault/index.md
    try:
        vault_text = _vault_index.read_text()
    except OSError as exc:
        print(f"ERROR: Cannot read vault index ({_vault_index}): {exc}", file=sys.stderr)
        sys.exit(1)

    # Read ideas ledger
    try:
        ideas_text = _ideas_index.read_text()
    except OSError as exc:
        print(f"ERROR: Cannot read ideas index ({_ideas_index}): {exc}", file=sys.stderr)
        sys.exit(1)

    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        print("ERROR: NOTION_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    index_rows = parse_index_rows(vault_text)
    ideas_rows = parse_ideas_ledger(ideas_text)
    blocks = _build_blocks(index_rows, ideas_rows)

    print(f"Clearing Notion page {page_id}...")
    _delete_page_blocks(page_id, token)

    print(f"Writing {len(blocks)} blocks to Notion page {page_id}...")
    _write_page_blocks(page_id, blocks, token)

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish weekly vault digest to Notion.")
    parser.add_argument("--targets-yaml", type=Path, default=None,
                        help="Path to targets.yaml (default: repo root targets.yaml)")
    parser.add_argument("--vault-index", type=Path, default=None,
                        help="Path to vault/index.md (default: repo root vault/index.md)")
    parser.add_argument("--ideas-index", type=Path, default=None,
                        help="Path to vault/ideas/index.md (default: repo root)")
    args = parser.parse_args()
    publish(
        targets_yaml=args.targets_yaml,
        vault_index=args.vault_index,
        ideas_index=args.ideas_index,
    )

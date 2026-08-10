"""Notion todos collector for Lookout.

Queries a Notion database for todos filtered by target name or Global,
paginates fully, rate-limits to 3 req/s, and retries on HTTP 429.
Does NOT call page-create or page-update endpoints.
"""
import json
import time
from pathlib import Path

import requests

_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_MAX_RETRIES = 5
_NOTION_RATE_MIN_INTERVAL = 1.0 / 3  # cap at 3 requests per second
_TIMEOUT = 10


def _notion_query_once(url: str, headers: dict, payload: dict) -> tuple:
    """Single POST attempt to Notion with 429 exponential-backoff retry.

    Returns (data_dict, error_str). On success error_str is empty.
    """
    delay = 1.0
    for _ in range(_NOTION_MAX_RETRIES):
        try:
            resp = requests.post(
                url, headers=headers, json=payload, timeout=_TIMEOUT
            )
        except Exception as exc:
            return None, str(exc)

        if resp.status_code == 429:
            time.sleep(delay)
            delay *= 2
            continue

        if not resp.ok:
            try:
                msg = resp.json().get("message", f"HTTP {resp.status_code}")
            except Exception:
                msg = f"HTTP {resp.status_code}"
            return None, msg

        return resp.json(), ""

    return None, "max retries exceeded after HTTP 429"


def _normalize_notion_page(page: dict) -> dict:
    """Extract the 6 required fields from a raw Notion page object."""
    props = page.get("properties", {})

    title = ""
    for prop_val in props.values():
        if prop_val.get("type") == "title":
            parts = prop_val.get("title", [])
            title = "".join(p.get("plain_text", "") for p in parts)
            break

    status = ""
    if "Status" in props:
        p = props["Status"]
        ptype = p.get("type", "")
        if ptype == "select" and p.get("select"):
            status = p["select"].get("name", "")
        elif ptype == "status" and p.get("status"):
            status = p["status"].get("name", "")

    project = ""
    if "Project" in props:
        p = props["Project"]
        if p.get("type") == "select" and p.get("select"):
            project = p["select"].get("name", "")

    return {
        "id": page.get("id", ""),
        "title": title,
        "status": status,
        "project": project,
        "url": page.get("url", ""),
        "last_edited": page.get("last_edited_time", ""),
    }


def collect_notion_todos(
    target_name: str,
    notion_token: str,
    database_id: str,
    out_dir: Path,
) -> dict:
    """Query a Notion database for todos filtered by target_name or Global.

    Paginates fully, rate-limits to 3 req/s, retries on 429.
    Returns a sources entry dict with status and error keys.
    """
    if not notion_token:
        return {"status": "absent", "error": "NOTION_TOKEN not set"}

    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    url = f"{_NOTION_API_BASE}/databases/{database_id}/query"

    todos = []
    start_cursor = None

    while True:
        payload = {
            "filter": {
                "or": [
                    {"property": "Project", "select": {"equals": target_name}},
                    {"property": "Project", "select": {"equals": "Global"}},
                ]
            }
        }
        if start_cursor:
            payload["start_cursor"] = start_cursor

        time.sleep(_NOTION_RATE_MIN_INTERVAL)
        data, err = _notion_query_once(url, headers, payload)
        if err:
            return {"status": "absent", "error": err}

        for page in data.get("results", []):
            todos.append(_normalize_notion_page(page))

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    with open(out_dir / "notion_todos.json", "w") as fh:
        json.dump(todos, fh, indent=2)

    return {"status": "ok", "error": ""}

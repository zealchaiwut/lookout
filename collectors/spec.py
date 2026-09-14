"""collectors/spec.py — Spec pack completeness for SDD targets.

Reads the standard Spec Driven Development files from a target clone and
writes `spec.json` into the snapshot. Missing files are recorded as absent;
the run never fails because a recommended file is missing.

Recommended pack (hermes-contract):
  PRODUCT.md, DESIGN.md, SCHEMA.md|schema.yaml, api.yaml|openapi.yaml, docs/
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Display key → candidate relative paths (first existing wins).
_SPEC_FILES: list[tuple[str, tuple[str, ...]]] = [
    ("PRODUCT.md", ("PRODUCT.md",)),
    ("DESIGN.md", ("DESIGN.md",)),
    ("SCHEMA.md", ("SCHEMA.md", "schema.yaml", "schema.yml")),
    ("api.yaml", ("api.yaml", "openapi.yaml", "openapi.yml")),
]

_DOCS_DIR = "docs"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _file_entry(local_path: Path, candidates: tuple[str, ...]) -> dict:
    for rel in candidates:
        path = local_path / rel
        if path.is_file():
            return {
                "present": True,
                "path": rel,
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
    return {
        "present": False,
        "path": candidates[0],
        "sha256": None,
        "bytes": 0,
    }


def _docs_entry(local_path: Path) -> dict:
    docs = local_path / _DOCS_DIR
    if not docs.is_dir():
        return {"present": False, "path": _DOCS_DIR, "file_count": 0}
    count = sum(1 for p in docs.rglob("*") if p.is_file())
    return {"present": True, "path": _DOCS_DIR, "file_count": count}


def build_completeness(files: dict) -> dict:
    """Return present/absent lists, score, and a human badge string."""
    order = ["PRODUCT.md", "DESIGN.md", "SCHEMA.md", "api.yaml", "docs/"]
    labels = {
        "PRODUCT.md": "PRODUCT",
        "DESIGN.md": "DESIGN",
        "SCHEMA.md": "SCHEMA",
        "api.yaml": "API",
        "docs/": "docs",
    }
    present: list[str] = []
    absent: list[str] = []
    parts: list[str] = []
    for key in order:
        entry = files.get(key) or {"present": False}
        label = labels[key]
        if entry.get("present"):
            present.append(key)
            parts.append(f"{label} ✓")
        else:
            absent.append(key)
            parts.append(f"{label} ✗")
    total = len(order)
    return {
        "present": present,
        "absent": absent,
        "score": f"{len(present)}/{total}",
        "badge": " · ".join(parts),
    }


def collect_spec(local_path: Path, out_dir: Path) -> dict:
    """Write spec.json for *local_path* into *out_dir*.

    Returns a sources-style dict: {status, error, present, absent, score}.
    """
    try:
        files: dict = {}
        for key, candidates in _SPEC_FILES:
            files[key] = _file_entry(local_path, candidates)
        files["docs/"] = _docs_entry(local_path)
        completeness = build_completeness(files)
        payload = {"files": files, "completeness": completeness}
        (out_dir / "spec.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        return {
            "status": "ok",
            "error": "",
            "present": len(completeness["present"]),
            "absent": len(completeness["absent"]),
            "score": completeness["score"],
            "badge": completeness["badge"],
        }
    except Exception as exc:
        return {
            "status": "absent",
            "error": str(exc),
            "present": 0,
            "absent": 5,
            "score": "0/5",
            "badge": "PRODUCT ✗ · DESIGN ✗ · SCHEMA ✗ · API ✗ · docs ✗",
        }


def format_badge_line(spec: dict | None) -> str:
    """One-line badge for situation / discovery, or empty if no spec data."""
    if not isinstance(spec, dict):
        return ""
    completeness = spec.get("completeness") or {}
    badge = completeness.get("badge") or ""
    score = completeness.get("score") or ""
    if not badge:
        return ""
    if score:
        return f"{badge}  ({score})"
    return badge

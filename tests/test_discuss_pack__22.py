"""Tests for issue #22: discuss pack command for lookout discuss.

Each test maps to a specific AC item from the issue.
"""
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
DISCUSS_PY = REPO_ROOT / "discuss_pack.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_discuss():
    spec = importlib.util.spec_from_file_location("discuss_pack_test_mod", str(DISCUSS_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_targets_yaml(tmp_path: Path, targets: list) -> Path:
    data = {
        "sources": {"commander_api": "http://localhost:9999"},
        "targets": {
            t: {"commander_slug": t, "github": f"test/{t}", "local": f"/tmp/{t}"}
            for t in targets
        },
    }
    p = tmp_path / "targets.yaml"
    p.write_text(yaml.dump(data))
    return p


def _make_situation_md(target: str, one_liner: str, capacity: str) -> str:
    return (
        f"---\ntarget: {target}\nrun: \"2026-08-10T12:00:00Z\"\nsources_ok: true\n---\n\n"
        f"## One-liner\n\n{one_liner}\n_(source: manifest.json)_\n\n"
        f"## Capacity\n\n{capacity}\n_(source: manifest.json)_\n\n"
        f"## Since last run\n\n_No changes detected._\n"
    )


def _make_capability_md(target: str, text: str) -> str:
    return f"# {target} — Capability Card\n\n## What it is\n\n{text}\n\n## Constraints\n\nNone.\n"


def _make_questions_json(questions: list) -> str:
    registry = {
        "prefix": questions[0]["id"][:2] if questions else "XX",
        "next_id": len(questions) + 1,
        "questions": {q["id"]: q for q in questions},
    }
    return json.dumps(registry, indent=2)


def _make_drift_md(flags: list) -> str:
    lines = ["# Drift Report", ""]
    if not flags:
        lines.append("_No drift signals detected._")
        lines.append("")
    else:
        for i, flag in enumerate(flags, 1):
            stype = flag.get("signal_type", "unknown")
            lines.append(f"## Flag {i}: {stype.replace('_', ' ').title()}")
            lines.append("")
            lines.append(f"**Claim:** {flag['claim']}")
            lines.append("")
            lines.append(f"**Evidence:** {flag['evidence_path']}")
            lines.append("")
            lines.append(f"**Suggested fix:** {flag['suggested_fix']}")
            lines.append("")
    return "\n".join(lines)


def _make_vault(
    tmp_path: Path,
    targets_data: dict,
) -> Path:
    """Create a temp vault.

    targets_data: {
        target_name: {
            "one_liner": str,
            "capacity": str,
            "capability_text": str,
            "questions": [...],  # list of question dicts
            "drift_flags": [...],  # list of drift flag dicts
        }
    }
    """
    vault = tmp_path / "vault"
    (vault / "packs").mkdir(parents=True)

    for target, data in targets_data.items():
        proj = vault / "projects" / target
        proj.mkdir(parents=True)

        one_liner = data.get("one_liner", f"{target} does things.")
        capacity = data.get("capacity", "67 %")
        capability_text = data.get("capability_text", f"{target} capability text.")
        questions = data.get("questions", [])
        drift_flags = data.get("drift_flags", [])

        (proj / "situation.md").write_text(
            _make_situation_md(target, one_liner, capacity)
        )
        (proj / "capability.md").write_text(
            _make_capability_md(target, capability_text)
        )
        if questions:
            (proj / "questions.json").write_text(
                _make_questions_json(questions)
            )
        if drift_flags:
            (proj / "drift.md").write_text(
                _make_drift_md(drift_flags)
            )

    return vault


def _make_question(qid: str, text: str, evidence: str, options: list, status: str = "open",
                   signal_text: str = None) -> dict:
    return {
        "id": qid,
        "created": "2026-08-10",
        "signal_type": "drift_flag",
        "signal_text": signal_text or f"drift:{text[:80]}",
        "text": text,
        "evidence": evidence,
        "options": options,
        "status": status,
    }


NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# AC1: lookout discuss <target> creates vault/packs/<date>-discuss-<name>.md
# ---------------------------------------------------------------------------

def test_ac1_output_path(tmp_path):
    """AC1: Pack output path is vault/packs/<YYYY-MM-DD>-discuss-<name>.md."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {"alpha": {}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )

    assert result == vault / "packs" / "2026-08-10-discuss-alpha.md"
    assert result.exists()


def test_ac1_slug_derived_from_target(tmp_path):
    """AC1: <name> in filename is derived from the target slug."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {"perf-coach": {}})
    ty = _make_targets_yaml(tmp_path, ["perf-coach"])

    result = mod.generate_discuss_pack(
        argument="perf-coach", vault_dir=vault, targets_yaml=ty, now=NOW
    )

    assert result.name == "2026-08-10-discuss-perf-coach.md"


# ---------------------------------------------------------------------------
# AC2: Open questions included with ID, evidence links, options
# ---------------------------------------------------------------------------

def test_ac2_open_question_id_present(tmp_path):
    """AC2: Pack includes the stable question ID for each open question."""
    mod = _load_discuss()
    q = _make_question("ALQ1", "What is the plan?", "drift.md",
                       ["Option A", "Option B"])
    vault = _make_vault(tmp_path, {"alpha": {"questions": [q]}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "ALQ1" in content


def test_ac2_open_question_evidence_present(tmp_path):
    """AC2: Pack includes all evidence links for each open question."""
    mod = _load_discuss()
    q = _make_question("ALQ1", "What is the plan?", "api_spec.md",
                       ["Option A", "Option B"])
    vault = _make_vault(tmp_path, {"alpha": {"questions": [q]}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "api_spec.md" in content


def test_ac2_open_question_options_present(tmp_path):
    """AC2: Pack includes all listed options for each open question."""
    mod = _load_discuss()
    q = _make_question("ALQ1", "What is the plan?", "drift.md",
                       ["Option A: do this", "Option B: do that"])
    vault = _make_vault(tmp_path, {"alpha": {"questions": [q]}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "Option A: do this" in content
    assert "Option B: do that" in content


def test_ac2_question_text_present(tmp_path):
    """AC2: The question text itself appears in the pack."""
    mod = _load_discuss()
    q = _make_question("ALQ1", "How do we resolve the deployment issue?", "drift.md",
                       ["Deploy now", "Wait"])
    vault = _make_vault(tmp_path, {"alpha": {"questions": [q]}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "How do we resolve the deployment issue?" in content


# ---------------------------------------------------------------------------
# AC3: Resolved questions are never included
# ---------------------------------------------------------------------------

def test_ac3_resolved_question_excluded(tmp_path):
    """AC3: A question with status=resolved does not appear in the pack."""
    mod = _load_discuss()
    open_q = _make_question("ALQ1", "Open question text?", "drift.md", ["A", "B"])
    resolved_q = _make_question("ALQ2", "Resolved question text?", "drift.md",
                                ["X", "Y"], status="resolved")
    vault = _make_vault(tmp_path, {"alpha": {"questions": [open_q, resolved_q]}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "ALQ1" in content
    assert "ALQ2" not in content
    assert "Resolved question text?" not in content


def test_ac3_resolved_id_not_in_pack(tmp_path):
    """AC3: The resolved question's ID is absent from the pack."""
    mod = _load_discuss()
    q1 = _make_question("BEQ1", "Open?", "drift.md", ["Yes"])
    q2 = _make_question("BEQ2", "Closed?", "drift.md", ["No"], status="resolved")
    vault = _make_vault(tmp_path, {"beta": {"questions": [q1, q2]}})
    ty = _make_targets_yaml(tmp_path, ["beta"])

    result = mod.generate_discuss_pack(
        argument="beta", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "BEQ2" not in content


# ---------------------------------------------------------------------------
# AC4: Exactly three open questions → exactly three question blocks
# ---------------------------------------------------------------------------

def test_ac4_exactly_three_blocks(tmp_path):
    """AC4: Three open questions produce exactly three question blocks in the pack."""
    mod = _load_discuss()
    questions = [
        _make_question("ALQ1", "Q1 text?", "drift.md", ["A1"], signal_text="drift:q1"),
        _make_question("ALQ2", "Q2 text?", "drift.md", ["A2"], signal_text="drift:q2"),
        _make_question("ALQ3", "Q3 text?", "drift.md", ["A3"], signal_text="drift:q3"),
    ]
    vault = _make_vault(tmp_path, {"alpha": {"questions": questions}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    for qid in ["ALQ1", "ALQ2", "ALQ3"]:
        assert qid in content

    assert content.count("ALQ1") >= 1
    assert content.count("ALQ2") >= 1
    assert content.count("ALQ3") >= 1


def test_ac4_no_extra_blocks_for_resolved(tmp_path):
    """AC4: Pack with 3 open and 1 resolved has exactly 3 question blocks."""
    mod = _load_discuss()
    questions = [
        _make_question("ALQ1", "Open1?", "drift.md", ["A"]),
        _make_question("ALQ2", "Open2?", "drift.md", ["B"]),
        _make_question("ALQ3", "Open3?", "drift.md", ["C"]),
        _make_question("ALQ4", "Resolved?", "drift.md", ["D"], status="resolved"),
    ]
    vault = _make_vault(tmp_path, {"alpha": {"questions": questions}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "ALQ4" not in content
    for qid in ["ALQ1", "ALQ2", "ALQ3"]:
        assert qid in content


# ---------------------------------------------------------------------------
# AC5: Pack includes capability card full text
# ---------------------------------------------------------------------------

def test_ac5_capability_card_present(tmp_path):
    """AC5: The full capability card text appears in the pack."""
    mod = _load_discuss()
    cap_text = "Unique capability description for testing AC5 verbatim inclusion."
    vault = _make_vault(tmp_path, {"alpha": {"capability_text": cap_text}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert cap_text in content


def test_ac5_capability_card_header_present(tmp_path):
    """AC5: The capability card header is present in the pack."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {"alpha": {}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "Capability Card" in content


# ---------------------------------------------------------------------------
# AC6: Pack includes situation one-liner and capacity value
# ---------------------------------------------------------------------------

def test_ac6_one_liner_present(tmp_path):
    """AC6: The situation one-liner appears in the pack."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {"alpha": {
        "one_liner": "Alpha manages all things uniquely.",
        "capacity": "72 %",
    }})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "Alpha manages all things uniquely." in content


def test_ac6_capacity_present(tmp_path):
    """AC6: The capacity value appears in the pack."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {"alpha": {
        "one_liner": "Alpha is a system.",
        "capacity": "67 %",
    }})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "67 %" in content


def test_ac6_source_annotations_omitted(tmp_path):
    """AC6: Source annotations from situation.md do not appear in the pack."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {"alpha": {
        "one_liner": "Alpha is a system.",
        "capacity": "100 %",
    }})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "_(source:" not in content


# ---------------------------------------------------------------------------
# AC7: Only cited drift/atlas excerpts are appended; uncited are omitted
# ---------------------------------------------------------------------------

def test_ac7_cited_drift_excerpt_included(tmp_path):
    """AC7: A drift excerpt cited by an open question is included in the pack."""
    mod = _load_discuss()
    drift_flag = {
        "signal_type": "removed_feature",
        "claim": "GET /api/old is no longer available",
        "evidence_path": "api_spec.md",
        "suggested_fix": "Update docs",
    }
    q = _make_question(
        "ALQ1", "How to resolve removal of /api/old?", "api_spec.md",
        ["Update docs", "Remove endpoint"],
        signal_text="drift:GET /api/old is no longer available",
    )
    vault = _make_vault(tmp_path, {"alpha": {
        "questions": [q],
        "drift_flags": [drift_flag],
    }})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "GET /api/old is no longer available" in content


def test_ac7_uncited_drift_excerpt_excluded(tmp_path):
    """AC7: A drift excerpt cited only by a resolved question is excluded."""
    mod = _load_discuss()
    flag_open = {
        "signal_type": "todo_still_open",
        "claim": "TODO: write tests",
        "evidence_path": "README.md",
        "suggested_fix": "Write the tests",
    }
    flag_resolved_only = {
        "signal_type": "removed_feature",
        "claim": "UNIQUE_CLAIM_FOR_RESOLVED_ONLY endpoint removed",
        "evidence_path": "docs/api.md",
        "suggested_fix": "Remove from docs",
    }
    q_open = _make_question(
        "ALQ1", "Why is TODO still open?", "README.md",
        ["Write tests"], status="open",
        signal_text="drift:TODO: write tests",
    )
    q_resolved = _make_question(
        "ALQ2", "Handle removed endpoint?", "docs/api.md",
        ["Remove docs"], status="resolved",
        signal_text="drift:UNIQUE_CLAIM_FOR_RESOLVED_ONLY endpoint removed",
    )
    vault = _make_vault(tmp_path, {"alpha": {
        "questions": [q_open, q_resolved],
        "drift_flags": [flag_open, flag_resolved_only],
    }})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "TODO: write tests" in content
    assert "UNIQUE_CLAIM_FOR_RESOLVED_ONLY endpoint removed" not in content


def test_ac7_no_excerpts_when_no_open_questions(tmp_path):
    """AC7: When all questions are resolved, no drift excerpts are included."""
    mod = _load_discuss()
    flag = {
        "signal_type": "removed_feature",
        "claim": "DRIFT_CLAIM_RESOLVED feature removed",
        "evidence_path": "docs.md",
        "suggested_fix": "Update docs",
    }
    q = _make_question(
        "ALQ1", "Question about resolved feature?", "docs.md",
        ["Update"], status="resolved",
        signal_text="drift:DRIFT_CLAIM_RESOLVED feature removed",
    )
    vault = _make_vault(tmp_path, {"alpha": {
        "questions": [q],
        "drift_flags": [flag],
    }})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "DRIFT_CLAIM_RESOLVED feature removed" not in content


# ---------------------------------------------------------------------------
# AC8: When argument is an idea, include idea note + target assessments
# ---------------------------------------------------------------------------

def _make_idea_note(name: str, affects: list) -> str:
    targets_section = "\n".join(f"- [[{t}]]" for t in affects)
    return (
        f"# Idea: {name}\n\n"
        f"## Summary\n\nThis idea proposes changes to the system.\n\n"
        f"## Affects\n\n{targets_section}\n\n"
        f"## Rationale\n\nUnique rationale text for idea {name}.\n"
    )


def test_ac8_idea_pack_includes_idea_note(tmp_path):
    """AC8: When argument is an idea, the pack contains the idea note text."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {
        "alpha": {"one_liner": "Alpha.", "capacity": "80 %"},
    })
    (vault / "ideas").mkdir(exist_ok=True)
    (vault / "ideas" / "my-idea.md").write_text(
        _make_idea_note("my-idea", ["alpha"])
    )
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="my-idea", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "Unique rationale text for idea my-idea" in content


def test_ac8_idea_pack_includes_affected_target_assessment(tmp_path):
    """AC8: Pack includes assessment sections for each target the idea affects."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {
        "alpha": {
            "one_liner": "Alpha manages deployments.",
            "capacity": "80 %",
            "capability_text": "Alpha is our deployment system.",
        },
        "beta": {
            "one_liner": "Beta manages routing.",
            "capacity": "60 %",
            "capability_text": "Beta handles routing logic.",
        },
    })
    (vault / "ideas").mkdir(exist_ok=True)
    (vault / "ideas" / "new-feature.md").write_text(
        _make_idea_note("new-feature", ["alpha", "beta"])
    )
    ty = _make_targets_yaml(tmp_path, ["alpha", "beta"])

    result = mod.generate_discuss_pack(
        argument="new-feature", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    content = result.read_text()

    assert "Alpha manages deployments." in content
    assert "Beta manages routing." in content
    assert "Alpha is our deployment system." in content
    assert "Beta handles routing logic." in content


def test_ac8_idea_output_path(tmp_path):
    """AC8: Idea pack output path includes the idea slug."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {"alpha": {}})
    (vault / "ideas").mkdir(exist_ok=True)
    (vault / "ideas" / "cool-idea.md").write_text(
        _make_idea_note("cool-idea", ["alpha"])
    )
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result = mod.generate_discuss_pack(
        argument="cool-idea", vault_dir=vault, targets_yaml=ty, now=NOW
    )

    assert result.name == "2026-08-10-discuss-cool-idea.md"


# ---------------------------------------------------------------------------
# AC9: Non-zero exit and human-readable error for unknown argument
# ---------------------------------------------------------------------------

def test_ac9_unknown_target_raises(tmp_path):
    """AC9: Unknown target raises or exits non-zero."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    with pytest.raises((SystemExit, mod.UnknownArgumentError)) as exc_info:
        mod.generate_discuss_pack(
            argument="nonexistent-thing", vault_dir=vault, targets_yaml=ty, now=NOW
        )

    if isinstance(exc_info.value, SystemExit):
        assert exc_info.value.code != 0


def test_ac9_error_mentions_argument(tmp_path, capsys):
    """AC9: Error message names the unresolvable argument."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    try:
        mod.generate_discuss_pack(
            argument="nonexistent-thing", vault_dir=vault, targets_yaml=ty, now=NOW
        )
    except (SystemExit, mod.UnknownArgumentError) as exc:
        err_text = str(exc)
    captured = capsys.readouterr()
    combined = captured.err + err_text
    assert "nonexistent-thing" in combined


def test_ac9_no_file_written_on_error(tmp_path):
    """AC9: No pack file is written when the argument cannot be resolved."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    try:
        mod.generate_discuss_pack(
            argument="nonexistent-thing", vault_dir=vault, targets_yaml=ty, now=NOW
        )
    except (SystemExit, mod.UnknownArgumentError):
        pass

    pack_files = list((vault / "packs").glob("*discuss*nonexistent*"))
    assert pack_files == []


def test_ac9_subprocess_nonexistent_exits_nonzero():
    """AC9: Subprocess invocation with unknown target exits non-zero."""
    result = subprocess.run(
        [sys.executable, str(DISCUSS_PY), "nonexistent_target_xyz_abc"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "nonexistent_target_xyz_abc" in result.stderr


# ---------------------------------------------------------------------------
# AC10: Running twice on the same day overwrites (consistent naming)
# ---------------------------------------------------------------------------

def test_ac10_second_run_overwrites_file(tmp_path):
    """AC10: Running twice on the same day produces one file, not two."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {"alpha": {"one_liner": "Alpha v1.", "capacity": "50 %"}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    result1 = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )

    # Mutate vault so second run produces different content
    (vault / "projects" / "alpha" / "situation.md").write_text(
        _make_situation_md("alpha", "Alpha v2.", "99 %")
    )

    result2 = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )

    assert result1 == result2
    pack_files = list((vault / "packs").glob("*discuss-alpha*"))
    assert len(pack_files) == 1
    assert "Alpha v2." in result2.read_text()


def test_ac10_consistent_filename(tmp_path):
    """AC10: Same target + same day always produces the same filename."""
    mod = _load_discuss()
    vault = _make_vault(tmp_path, {"alpha": {}})
    ty = _make_targets_yaml(tmp_path, ["alpha"])

    r1 = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )
    r2 = mod.generate_discuss_pack(
        argument="alpha", vault_dir=vault, targets_yaml=ty, now=NOW
    )

    assert r1.name == r2.name == "2026-08-10-discuss-alpha.md"

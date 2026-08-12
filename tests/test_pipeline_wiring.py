"""Tests for the pipeline-wiring work: endpoint collection, atlas seeding from
subheading-style READMEs, the LLM gate, and the derive stage runner.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import atlas_seed  # noqa: E402
import derive  # noqa: E402
import gather  # noqa: E402
import llm  # noqa: E402
import synthesize  # noqa: E402


# ---------------------------------------------------------------------------
# atlas_seed — subheading-style README feature lists
# ---------------------------------------------------------------------------

SUBHEADING_README = """# asset-studio

## Install

Run `pip install -r requirements.txt`.

## Features

### Brand Settings (issue #1)
Configure your brand profile.

### Visual Sourcing (issue #4)
Dual-path workflow for sourcing base visuals.

### Export to Dated Folder (issue #6)
Export the active carousel as a ZIP archive.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/jobs` | List all jobs |
"""

BULLET_README = """# perf-coach

## Features

- **Readiness Score** — daily readiness.
- **Training Log** — session history.

## Install
"""


def test_subheading_features_are_extracted():
    """A `### Name` feature list under `## Features` yields one feature each."""
    features = atlas_seed.extract_features(SUBHEADING_README, None)
    slugs = [f["slug"] for f in features]
    assert "brand-settings" in slugs
    assert "visual-sourcing" in slugs
    assert "export-to-dated-folder" in slugs


def test_issue_suffix_is_stripped_from_feature_names():
    """`Brand Settings (issue #1)` becomes `Brand Settings`, not a slug with the issue."""
    features = atlas_seed.extract_features(SUBHEADING_README, None)
    names = [f["name"] for f in features]
    assert "Brand Settings" in names
    assert not any("issue" in s for s in (f["slug"] for f in features))


def test_features_section_ends_at_sibling_heading_not_subheading():
    """`###` must not terminate the Features section; only a sibling `## ` does."""
    features = atlas_seed.extract_features(SUBHEADING_README, None)
    slugs = [f["slug"] for f in features]
    # Content from the following `## API endpoints` section must not leak in.
    assert "api-endpoints" not in slugs
    assert len(features) == 3


TABLE_README = """# commander

## Features

| Feature | What it does | Docs |
|---|---|---|
| **Dashboard** | Live agent event feed | [docs](docs/features/dashboard.md) |
| **Sprint Manager** | Automates the BA loop | [docs](docs/features/sprint-manager.md) |

## Repository Layout
"""


def test_table_features_are_extracted():
    """A `| **Name** | … |` feature table yields one feature per row."""
    features = atlas_seed.extract_features(TABLE_README, None)
    assert [f["slug"] for f in features] == ["dashboard", "sprint-manager"]


def test_table_header_and_separator_rows_are_not_features():
    features = atlas_seed.extract_features(TABLE_README, None)
    slugs = [f["slug"] for f in features]
    assert "feature" not in slugs
    assert not any(set(s) <= {"-"} for s in slugs)


def test_bold_bullet_features_still_work():
    """The original bold-bullet README convention is unchanged."""
    features = atlas_seed.extract_features(BULLET_README, None)
    slugs = [f["slug"] for f in features]
    assert slugs == ["readiness-score", "training-log"]


# ---------------------------------------------------------------------------
# gather — endpoints.json collection
# ---------------------------------------------------------------------------

ENDPOINT_DOC = """# thing

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/jobs` | List all jobs |
| `POST` | `/api/run` | Submit a job |
| `GET` | `/api/profile` | Load brand profile |
| `DELETE` | `/api/jobs/{id}` | Delete a job |
"""


def test_only_get_endpoints_are_collected():
    endpoints = gather._parse_endpoint_tables(ENDPOINT_DOC)
    paths = [e["path"] for e in endpoints]
    assert paths == ["/api/jobs", "/api/profile"]


def test_endpoint_descriptions_are_captured():
    endpoints = gather._parse_endpoint_tables(ENDPOINT_DOC)
    assert endpoints[0]["description"] == "List all jobs"


def test_duplicate_paths_are_deduplicated():
    doubled = ENDPOINT_DOC + "\n| `GET` | `/api/jobs` | Again |\n"
    endpoints = gather._parse_endpoint_tables(doubled)
    assert [e["path"] for e in endpoints].count("/api/jobs") == 1


def test_collect_endpoints_writes_schema_capability_card_reads(tmp_path):
    local = tmp_path / "repo"
    local.mkdir()
    (local / "README.md").write_text(ENDPOINT_DOC)
    out = tmp_path / "snap"
    out.mkdir()

    result = gather._collect_endpoints(local, out)

    assert result["status"] == "ok"
    assert result["count"] == 2
    data = json.loads((out / "endpoints.json").read_text())
    assert "get_endpoints" in data
    first = data["get_endpoints"][0]
    assert set(("path", "description", "example")) <= set(first)
    assert first["example"].endswith("/api/jobs")
    assert data["source_files"] == ["README.md"]


def test_collect_endpoints_absent_when_no_tables(tmp_path):
    local = tmp_path / "repo"
    local.mkdir()
    (local / "README.md").write_text("# nothing here\n")
    out = tmp_path / "snap"
    out.mkdir()

    result = gather._collect_endpoints(local, out)

    assert result["status"] == "absent"
    assert result["count"] == 0
    # The file is still written, so downstream readers get an empty list not a crash.
    assert json.loads((out / "endpoints.json").read_text())["get_endpoints"] == []


# ---------------------------------------------------------------------------
# synthesize — volatile health fields excluded from the manifest diff
# ---------------------------------------------------------------------------

def test_health_telemetry_is_excluded_from_diff():
    prev = {"health": {"uptime_seconds": 10, "status": "ok"}, "sources": {"brief": "ok"}}
    curr = {"health": {"uptime_seconds": 99, "status": "degraded"}, "sources": {"brief": "ok"}}
    assert synthesize._diff_manifests(curr, prev) == []


def test_real_source_changes_still_appear_in_diff():
    prev = {"health": {"uptime_seconds": 10}, "sources": {"endpoints": {"count": 0}}}
    curr = {"health": {"uptime_seconds": 99}, "sources": {"endpoints": {"count": 17}}}
    changes = synthesize._diff_manifests(curr, prev)
    assert len(changes) == 1
    assert "sources.endpoints.count" in changes[0]


def test_issue_items_are_not_wikilinked():
    """Issue titles have no vault page, so linking them would fail lint."""
    issues = {"issues": [{"number": 7, "title": "Do a thing", "state": "open"}]}
    rendered = [
        synthesize._to_wikilink(i)
        for i in synthesize._collect_next_items({}, [], {}, issues)
    ]
    assert rendered == ["#7 — Do a thing"]
    assert not any("[[" in r for r in rendered)


def test_changed_doc_files_are_still_wikilinked():
    """Doc paths name real vault pages, so they keep their wikilink."""
    manifest = {"changed_files": ["docs/todo.md"]}
    items = synthesize._collect_next_items({}, [], manifest, None)
    assert synthesize._to_wikilink(items[0]).startswith("[[")


def test_brief_suggestion_dicts_use_their_text_key():
    """Commander suggestions are dicts keyed `text`, not `title`."""
    brief = {"suggested_next": [
        {"text": "Purge junk tickets", "type": "suggestion", "slug": "commander"}
    ]}
    rendered = [
        synthesize._to_wikilink(i)
        for i in synthesize._collect_next_items(brief, [], {}, None)
    ]
    assert rendered == ["Purge junk tickets"]


def test_sprint_lookahead_dicts_use_their_label_key():
    brief = {"up_next": [{"label": "sprint 100", "ticketcount": 2}]}
    items = synthesize._collect_next_items(brief, [], {}, None)
    assert [synthesize._to_wikilink(i) for i in items] == ["sprint 100"]


def test_unlabelled_dict_items_are_skipped_not_stringified():
    """A dict with no label key must never reach situation.md as its repr."""
    brief = {"up_next": [{"ticketcount": 2, "estimatedhours": 0.5}]}
    assert synthesize._collect_next_items(brief, [], {}, None) == []


def test_open_issues_feed_what_to_do_next():
    issues = {"issues": [
        {"number": 140, "title": "Fix the thing", "state": "open"},
        {"number": 12, "title": "Closed already", "state": "closed"},
    ]}
    items = synthesize._collect_next_items({}, [], {}, issues)
    assert [synthesize._to_wikilink(i) for i in items] == ["#140 — Fix the thing"]


def test_live_brief_keys_feed_what_to_do_next():
    """The keys the real Commander brief payload uses, not just generic ones."""
    brief = {"suggested_next": ["Ship the export"], "waiting_on_you": ["Review #3"]}
    rendered = [
        synthesize._to_wikilink(i)
        for i in synthesize._collect_next_items(brief, [], {}, None)
    ]
    assert "Ship the export" in rendered
    assert "Review #3" in rendered


# ---------------------------------------------------------------------------
# capability_card — enrichment survives a deterministic run
# ---------------------------------------------------------------------------

REAL_CARD = """# t — Capability Card

## What it is

A real description of what this thing actually does.

## Data it owns

- stuff
"""

GENERIC_CARD = """# t — Capability Card

## What it is

`t` is a project tracked by Lookout via Commander. It is monitored for health.

## Data it owns

- stuff
"""


def test_real_description_is_extracted_for_preservation():
    import capability_card
    assert capability_card._extract_what_it_is(REAL_CARD).startswith("A real description")


def test_generic_description_is_treated_as_absent():
    import capability_card
    assert capability_card._extract_what_it_is(GENERIC_CARD) == ""


def test_deterministic_run_preserves_an_existing_real_description(monkeypatch):
    """A nightly (LLM-off) run must not overwrite an enriched description."""
    import capability_card
    monkeypatch.delenv(llm.ENV_ENABLE, raising=False)
    result = capability_card._build_what_it_is(
        "t", "# readme with content", [], preserved="A real description."
    )
    assert result == "A real description."


def test_deterministic_run_with_no_prior_card_uses_generic(monkeypatch):
    import capability_card
    monkeypatch.delenv(llm.ENV_ENABLE, raising=False)
    result = capability_card._build_what_it_is("t", "# readme", [], preserved="")
    assert "is a project tracked by Lookout" in result


# ---------------------------------------------------------------------------
# llm — the subscription-only gate
# ---------------------------------------------------------------------------

def test_llm_disabled_by_default_returns_fallback(monkeypatch):
    monkeypatch.delenv(llm.ENV_ENABLE, raising=False)
    assert llm.ask("anything", fallback="FB") == "FB"


def test_llm_disabled_never_spawns_a_process(monkeypatch):
    monkeypatch.delenv(llm.ENV_ENABLE, raising=False)

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("subprocess spawned while LLM was disabled")

    monkeypatch.setattr(subprocess, "run", explode)
    assert llm.ask("anything", fallback="FB") == "FB"


def test_llm_falls_back_when_claude_missing(monkeypatch, tmp_path):
    monkeypatch.setenv(llm.ENV_ENABLE, "1")
    monkeypatch.setattr(llm, "available", lambda: False)
    assert llm.ask("p", fallback="FB", cache_dir=tmp_path) == "FB"


def test_llm_falls_back_on_nonzero_exit(monkeypatch, tmp_path):
    monkeypatch.setenv(llm.ENV_ENABLE, "1")
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="", stderr="boom"),
    )
    assert llm.ask("p", fallback="FB", cache_dir=tmp_path) == "FB"


def test_llm_caches_by_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv(llm.ENV_ENABLE, "1")
    monkeypatch.setattr(llm, "available", lambda: True)
    calls = []

    def fake_run(*a, **k):
        calls.append(a)
        return subprocess.CompletedProcess(a, 0, stdout="hello\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    first = llm.ask("same prompt", fallback="FB", cache_dir=tmp_path)
    second = llm.ask("same prompt", fallback="FB", cache_dir=tmp_path)

    assert first == second == "hello"
    assert len(calls) == 1, "second call should have been served from cache"


def test_llm_uses_claude_print_mode_not_an_sdk(monkeypatch, tmp_path):
    """The only permitted backend is `claude -p` (subscription-funded)."""
    monkeypatch.setenv(llm.ENV_ENABLE, "1")
    monkeypatch.setattr(llm, "available", lambda: True)
    captured = {}

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    llm.ask("prompt text", fallback="FB", model="haiku", cache_dir=tmp_path)

    assert captured["cmd"][:2] == ["claude", "-p"]
    assert "--model" in captured["cmd"]


def test_no_module_imports_an_llm_sdk():
    """No Python in this repo may reach a metered API directly."""
    offenders = []
    for path in REPO_ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in ("import anthropic", "from anthropic", "ANTHROPIC_API_KEY"):
            if needle in text and path.name != "llm.py":
                offenders.append(f"{path.name}: {needle}")
    assert offenders == [], f"metered-API usage found: {offenders}"


# ---------------------------------------------------------------------------
# derive — stage runner
# ---------------------------------------------------------------------------

def test_derive_target_skips_when_no_snapshot(tmp_path):
    vault = tmp_path / "vault"
    (vault / "projects" / "ghost").mkdir(parents=True)
    results = derive.derive_target("ghost", vault)
    assert len(results) == 1
    assert results[0]["status"] == derive.SKIPPED


def test_run_stage_converts_failure_into_a_record():
    def boom():
        raise RuntimeError("nope")

    result = derive._run_stage("explode", boom)
    assert result["status"] == derive.ERROR
    assert "RuntimeError" in result["detail"]


def test_any_error_detects_a_failed_stage():
    assert derive.any_error([{"stage": "a", "status": derive.ERROR, "detail": ""}])
    assert not derive.any_error([{"stage": "a", "status": derive.OK, "detail": ""}])


def test_derive_vault_skips_ideas_when_directory_absent(tmp_path):
    vault = tmp_path / "vault"
    (vault / "projects").mkdir(parents=True)
    results = derive.derive_vault(vault)
    stages = {r["stage"]: r["status"] for r in results}
    assert stages["capability_map"] == derive.OK
    assert stages["ideas"] == derive.SKIPPED


# ---------------------------------------------------------------------------
# bin/lookout — derive is actually wired into the runner
# ---------------------------------------------------------------------------

def test_bin_lookout_invokes_derive():
    text = (REPO_ROOT / "bin" / "lookout").read_text()
    assert "derive_module.derive_target" in text
    assert "derive_module.derive_vault" in text


def test_all_runner_invokes_derive():
    text = (REPO_ROOT / "all_runner.py").read_text()
    assert "derive_module.derive_target" in text
    assert "derive_module.derive_vault" in text


def test_targets_yaml_has_no_pytest_leftovers():
    """Test fixtures must not be registered targets — `--all` iterates them all."""
    import yaml
    data = yaml.safe_load((REPO_ROOT / "targets.yaml").read_text())
    for name, cfg in data["targets"].items():
        assert not name.startswith("test-"), f"pytest leftover target: {name}"
        assert "pytest-of-" not in str(cfg.get("local", "")), (
            f"target {name} points at a pytest tmp dir"
        )


# ---------------------------------------------------------------------------
# launchd — plist templates must not hardcode a machine
# ---------------------------------------------------------------------------

LAUNCHD_TEMPLATES = sorted((REPO_ROOT / "launchd").glob("*.plist.template"))


def test_launchd_templates_exist():
    assert LAUNCHD_TEMPLATES, "no plist templates found under launchd/"


@pytest.mark.parametrize("template", LAUNCHD_TEMPLATES, ids=lambda p: p.name)
def test_template_hardcodes_no_user_path(template):
    """A plist that names a specific user only runs on one machine."""
    text = template.read_text()
    assert "/Users/" not in text, (
        f"{template.name} hardcodes an absolute user path; use __REPO_ROOT__"
    )


@pytest.mark.parametrize("template", LAUNCHD_TEMPLATES, ids=lambda p: p.name)
def test_template_does_not_reference_a_worktree_slot(template):
    """Commander worktree-pool slots are transient and get recycled."""
    assert "worktree-pool" not in template.read_text()


@pytest.mark.parametrize("template", LAUNCHD_TEMPLATES, ids=lambda p: p.name)
def test_template_sets_path_for_gh_and_claude(template):
    """launchd's default PATH has no gh and no claude.

    Without an explicit PATH a run collects zero GitHub issues and silently
    skips every LLM call while still reporting success.
    """
    text = template.read_text()
    assert "<key>PATH</key>" in text
    assert "__PATH__" in text


@pytest.mark.parametrize("template", LAUNCHD_TEMPLATES, ids=lambda p: p.name)
def test_template_renders_to_valid_plist(tmp_path, template):
    """Substituting every placeholder must yield a plist macOS accepts."""
    import plistlib

    rendered = (
        template.read_text()
        .replace("__REPO_ROOT__", "/tmp/lookout")
        .replace("__PYTHON__", "/usr/bin/python3")
        .replace("__PATH__", "/usr/bin:/bin")
    )
    assert "__" not in rendered.split("-->")[-1], "placeholder left unsubstituted"

    out = tmp_path / "rendered.plist"
    out.write_text(rendered)
    parsed = plistlib.loads(out.read_bytes())
    assert parsed["Label"].startswith("com.zealchaiwut.lookout")
    assert parsed["WorkingDirectory"] == "/tmp/lookout"
    assert parsed["EnvironmentVariables"]["PATH"] == "/usr/bin:/bin"


def test_install_script_substitutes_every_placeholder():
    """Each placeholder used in a template must have a sed rule in install.sh."""
    import re

    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    used = set()
    for template in LAUNCHD_TEMPLATES:
        used |= set(re.findall(r"__[A-Z_]+__", template.read_text()))
    missing = [p for p in sorted(used) if f"s|{p}|" not in install]
    assert missing == [], f"install.sh has no substitution for: {missing}"


def test_gather_records_a_github_source_entry():
    """A gh failure must be visible in the manifest, not silent.

    It was not: gather() discarded _collect_gh's result, so a run under
    launchd (whose PATH has no gh) wrote no issues.json, recorded nothing,
    and still reported success.
    """
    text = (REPO_ROOT / "gather.py").read_text()
    assert 'sources["github"]' in text

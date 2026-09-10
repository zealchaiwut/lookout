"""Tests for issue #99: no invented wikilinks, and --all failure streaks."""
import importlib.util
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import synthesize  # noqa: E402


def _load_all_runner():
    path = REPO_ROOT / "all_runner.py"
    spec = importlib.util.spec_from_file_location("all_runner", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_targets_yaml(tmp_path, targets_dict):
    p = tmp_path / "targets.yaml"
    p.write_text(yaml.dump({
        "snapshot_branch": "develop",
        "sources": {"commander_api": "http://localhost:9999"},
        "targets": targets_dict,
    }))
    return p


def test_doc_path_next_item_is_not_a_wikilink():
    """A next-action from a target-repo path must not invent [[Readme]]."""
    known = synthesize._vault_page_index(REPO_ROOT / "vault")
    items = synthesize._collect_next_items(
        {}, [], {"changed_files": ["README.md", "docs/milestones/next-stage-bcd.md"]}, None
    )
    rendered = [synthesize._to_wikilink(i, known) for i in items]
    assert rendered == ["README.md", "docs/milestones/next-stage-bcd.md"]
    assert not any("[[" in r for r in rendered)


def test_real_vault_note_still_links(tmp_path):
    """An unmarked next-item that names a vault note still becomes a wikilink."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "decisions.md").write_text("# Decisions\n")
    known = synthesize._vault_page_index(vault)
    assert synthesize._to_wikilink("Decisions", known) == "[[decisions]]"
    assert synthesize._to_wikilink("README.md", known) == "README.md"


def test_plain_items_never_link_even_if_a_page_exists(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "decisions.md").write_text("# Decisions\n")
    known = synthesize._vault_page_index(vault)
    assert synthesize._to_wikilink(synthesize._plain("Decisions"), known) == "Decisions"


def test_notion_todo_titles_are_not_wikilinked():
    todos = [{"title": "Readme", "status": "open"}]
    items = synthesize._collect_next_items({}, todos, {}, None)
    rendered = [synthesize._to_wikilink(i) for i in items]
    assert rendered == ["Readme"]
    assert not any("[[" in r for r in rendered)


def test_unmarked_title_without_known_pages_stays_plain():
    """Without a vault index, never invent [[Page]] from a title."""
    assert synthesize._to_wikilink("README.md") == "README.md"
    assert "[[" not in synthesize._to_wikilink("docs/milestones")


def test_sweep_status_counts_consecutive_failures():
    mod = _load_all_runner()
    prev = {"updated": "", "targets": {}}
    run1 = mod._update_sweep_status(
        prev, [("viral-radar", False, "lint failed (exit 1)")], "2026-08-13T00:00:00Z"
    )
    assert run1["targets"]["viral-radar"]["consecutive_failures"] == 1
    run2 = mod._update_sweep_status(
        run1, [("viral-radar", False, "lint failed (exit 1)")], "2026-08-14T00:00:00Z"
    )
    assert run2["targets"]["viral-radar"]["consecutive_failures"] == 2
    assert run2["targets"]["viral-radar"]["last_ok"] is False


def test_sweep_status_resets_on_success():
    mod = _load_all_runner()
    failed = mod._update_sweep_status(
        {"targets": {}}, [("alpha", False, "lint failed")], "t1"
    )
    failed = mod._update_sweep_status(
        failed, [("alpha", False, "lint failed")], "t2"
    )
    ok = mod._update_sweep_status(failed, [("alpha", True, "ok")], "t3")
    assert ok["targets"]["alpha"]["consecutive_failures"] == 0
    assert ok["targets"]["alpha"]["last_ok"] is True
    assert ok["targets"]["alpha"]["last_success_at"] == "t3"


def test_run_all_writes_sweep_status_and_names_repeats(tmp_path, monkeypatch, capsys):
    """A second failure is visible in the summary and in vault/sweep-status.md."""
    mod = _load_all_runner()
    targets_yaml = _make_targets_yaml(tmp_path, {
        "alpha": {"local": str(tmp_path), "github": "t/t", "commander_slug": "t"},
        "broken": {"local": str(tmp_path / "missing"), "github": "t/t", "commander_slug": "t"},
    })
    lint_ok = tmp_path / "lint_ok.py"
    lint_ok.write_text("import sys; sys.exit(0)\n")
    monkeypatch.setattr(mod, "_commit_target", lambda *a, **kw: None)
    monkeypatch.setattr(mod, "_commit_sweep_status", lambda *a, **kw: None)

    def mock_gather(target_name):
        if target_name == "broken":
            raise SystemExit(1)
        return {}

    monkeypatch.setattr(mod.gather_module, "gather", mock_gather)

    kwargs = dict(
        targets_yaml=targets_yaml,
        lint_script=lint_ok,
        lock_path=tmp_path / "lock1",
        repo_root=tmp_path,
    )
    mod.run_all(**kwargs)
    kwargs["lock_path"] = tmp_path / "lock2"
    mod.run_all(**kwargs)

    captured = capsys.readouterr().out
    assert "repeating failures" in captured.lower()
    assert "2 consecutive" in captured

    status_md = (tmp_path / "vault" / "sweep-status.md").read_text()
    assert "`broken`" in status_md
    assert "has failed 2 runs in a row" in status_md
    data = json.loads((tmp_path / "vault" / "sweep-status.json").read_text())
    assert data["targets"]["broken"]["consecutive_failures"] == 2
    assert data["targets"]["alpha"]["consecutive_failures"] == 0


def test_lint_failure_prints_linter_output(tmp_path, monkeypatch, capsys):
    """Lint details are printed, not collapsed to one summary line."""
    mod = _load_all_runner()
    targets_yaml = _make_targets_yaml(tmp_path, {
        "viral-radar": {"local": str(tmp_path), "github": "t/t", "commander_slug": "t"},
    })
    lint_fail = tmp_path / "lint_fail.py"
    lint_fail.write_text(
        "import sys\n"
        "print('[FAIL] Wikilink check:')\n"
        "print('  projects/viral-radar/situation.md: unresolved wikilink [[Readme]]')\n"
        "sys.exit(1)\n"
    )
    monkeypatch.setattr(mod, "_commit_target", lambda *a, **kw: None)
    monkeypatch.setattr(mod, "_commit_sweep_status", lambda *a, **kw: None)
    monkeypatch.setattr(mod.gather_module, "gather", lambda t: {})

    results, any_failed = mod.run_all(
        targets_yaml=targets_yaml,
        lint_script=lint_fail,
        lock_path=tmp_path / "lock",
        repo_root=tmp_path,
    )
    assert any_failed
    assert results[0][0] == "viral-radar" and results[0][1] is False
    out = capsys.readouterr().out
    assert "unresolved wikilink [[Readme]]" in out
    assert "consecutive failures: 1" in out

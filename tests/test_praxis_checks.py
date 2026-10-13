from __future__ import annotations
from pathlib import Path
from praxis.checks import run_all, run_check, unclosable_paths
from praxis.parse import parse_roadmap
from tests.praxis_helpers import ROADMAP, make_repo


def test_passed_and_failed(tmp_path: Path):
    assert run_check("true", tmp_path, 5).result == "passed"
    r = run_check("false", tmp_path, 5)
    assert r.result == "failed" and r.returncode == 1


def test_absent_when_empty(tmp_path: Path):
    assert run_check("", tmp_path, 5).result == "absent"
    assert run_check("   ", tmp_path, 5).result == "absent"


def test_output_is_captured_not_printed(tmp_path: Path, capfd):
    r = run_check("echo hello; echo err 1>&2", tmp_path, 5)
    assert r.stdout.strip() == "hello" and r.stderr.strip() == "err"
    out, err = capfd.readouterr()
    assert out == "" and err == ""


def test_runs_from_repo_root(tmp_path: Path):
    (tmp_path / "marker").write_text("x")
    assert run_check("test -f marker", tmp_path, 5).result == "passed"


def test_pipe_works(tmp_path: Path):
    assert run_check("echo a | grep -q a", tmp_path, 5).result == "passed"


def test_timeout(tmp_path: Path):
    assert run_check("sleep 3", tmp_path, 1).result == "timeout"


def test_unclosable_paths_detects_missing_traces(tmp_path: Path):
    (tmp_path / "traces").mkdir()
    (tmp_path / "traces" / "have.log").write_text("PASS")
    cmd = "grep -q PASS traces/have.log && test -f traces/missing.log"
    assert unclosable_paths(cmd, tmp_path) == ["traces/missing.log"]


def test_unclosable_result_without_running(tmp_path: Path):
    (tmp_path / "traces").mkdir()
    r = run_check("grep -q PASS traces/none.log", tmp_path, 5)
    assert r.result == "unclosable" and r.returncode is None


def test_unclosable_glob_with_no_matching_file(tmp_path: Path):
    (tmp_path / "traces").mkdir()
    cmd = "ls traces/a6-reply-*.eml 2>/dev/null | grep -q ."
    assert unclosable_paths(cmd, tmp_path) == ["traces/a6-reply-*.eml"]
    assert run_check(cmd, tmp_path, 5).result == "unclosable"


def test_glob_check_passes_once_a_matching_file_exists(tmp_path: Path):
    (tmp_path / "traces").mkdir()
    (tmp_path / "traces" / "a6-reply-x.eml").write_text("x")
    cmd = "ls traces/a6-reply-*.eml 2>/dev/null | grep -q ."
    assert unclosable_paths(cmd, tmp_path) == []
    assert run_check(cmd, tmp_path, 5).result == "passed"


def test_run_all_keys_by_action_id(tmp_path: Path):
    root = make_repo(tmp_path)
    results = run_all(parse_roadmap(ROADMAP), root, 5)
    assert set(results) == {f"a{i}" for i in range(1, 8)}
    assert results["a1"].result == "passed"
    assert results["a2"].result == "absent"
    assert results["a3"].result == "unclosable"
    assert results["a5"].result == "passed"
    assert results["a7"].result == "failed"


def test_run_all_only_runs_the_named_actions(tmp_path):
    from praxis.checks import run_all
    from praxis.parse import parse_roadmap
    from tests.praxis_helpers import ROADMAP, make_repo
    make_repo(tmp_path)
    rm = parse_roadmap(ROADMAP, path="ROADMAP.org")
    results = run_all(rm, tmp_path, 5, only={"a1", "a7"})
    assert set(results) == {"a1", "a7"}
    assert results["a1"].result == "passed" and results["a7"].result == "failed"


def test_exit_3_is_pending_even_with_no_output(tmp_path: Path):
    from praxis.checks import run_check
    r = run_check("exit 3", tmp_path, 5)
    assert r.result == "pending" and r.returncode == 3 and r.stdout == ""


def test_exit_4_is_still_failed(tmp_path: Path):
    from praxis.checks import run_check
    assert run_check("exit 4", tmp_path, 5).result == "failed"

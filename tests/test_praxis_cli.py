from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from praxis import cli
from tests.praxis_helpers import ROADMAP, make_repo

REPO = Path(__file__).resolve().parent.parent


def test_status_json_from_repo_root(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["status", "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["branch"] == "x.y.z" and d["path"] == "ROADMAP.org" and d["format"] == 2
    assert next(a for a in d["actions"] if a["id"] == "a7")["result"] == "failed"
    assert d["summary"]["clauses"] == 3
    assert rc == 0


def test_status_human_view(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "a1   DONE    ✅" in out and "C1   ·" in out and "clauses 0/3" in out


def test_status_no_checks_spawns_nothing(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    calls = []
    real_run = subprocess.run

    def spy(*a, **kw):
        if kw.get("shell"):
            calls.append(a[0])
        return real_run(*a, **kw)

    monkeypatch.setattr(subprocess, "run", spy)
    cli.main(["status", "--json", "--no-checks"])
    d = json.loads(capsys.readouterr().out)
    assert all(a["result"] is None for a in d["actions"]) and calls == []


def test_status_exit_1_on_violation(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path, ROADMAP.replace("- check :: true", "- check :: false"))
    monkeypatch.chdir(tmp_path)
    assert cli.main(["status", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["actions"][0]["violations"] == ["done_without_passing_check"]


def test_status_exit_2_on_parse_error_with_line(tmp_path: Path, capsys, monkeypatch):
    text = ROADMAP.replace("** SIGNAL a6", "** MAYBE a6")
    make_repo(tmp_path, text)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["status"]) == 2
    err = capsys.readouterr().err
    line = next(i for i, l in enumerate(text.splitlines(), 1) if "** MAYBE a6" in l)
    assert f"ROADMAP.org:{line}:" in err and "MAYBE" in err


def test_status_exit_2_on_format1_file(tmp_path: Path, capsys, monkeypatch):
    old = "#+TITLE: x\n#+SETPOINT: y\n#+SIGNER: z\n#+OPENED: 2026-09-01\n\n* Status\n| id | step | state | source | evidence | check |\n\n* Ledger\n\n* Remains\n"
    make_repo(tmp_path, old)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["status"]) == 2
    err = capsys.readouterr().err
    assert "ROADMAP.org:2:" in err and "format 1 file" in err and "convert it" in err


def test_status_exit_2_when_missing(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["status"]) == 2
    assert "no ROADMAP.org" in capsys.readouterr().err


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores mode bits")
def test_status_exit_2_on_unreadable_roadmap(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    roadmap = tmp_path / "ROADMAP.org"
    roadmap.chmod(0)
    try:
        rc = cli.main(["status"])
    finally:
        roadmap.chmod(0o644)
    assert rc == 2 and capsys.readouterr().err.startswith("error:")


def test_status_exit_2_on_non_utf8_roadmap(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ROADMAP.org").write_bytes(b"\xff\xfe not utf8")
    assert cli.main(["status"]) == 2
    assert capsys.readouterr().err.startswith("error:")


def test_path_option_sets_root(tmp_path: Path, capsys, monkeypatch):
    sub = tmp_path / "proj"
    sub.mkdir()
    make_repo(sub)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["status", "--json", "--path", str(sub / "ROADMAP.org")]) == 0
    assert json.loads(capsys.readouterr().out)["branch"] == "x.y.z"


def test_check_single_action_prints_output(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path, ROADMAP.replace("- check :: true", "- check :: echo evidence-ok"))
    monkeypatch.chdir(tmp_path)
    assert cli.main(["check", "a1"]) == 0
    out = capsys.readouterr().out
    assert "a1: passed" in out and "evidence-ok" in out


def test_check_unknown_id(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["check", "a99"]) == 2
    assert "no action a99" in capsys.readouterr().err


def test_check_failed_exit_1(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["check", "a7"]) == 1


def test_timeout_header_is_used(tmp_path: Path, capsys, monkeypatch):
    text = ROADMAP.replace("#+OPENED: 2026-09-03", "#+OPENED: 2026-09-03\n#+CHECK_TIMEOUT: 1")
    text = text.replace("- check :: false", "- check :: sleep 3")
    make_repo(tmp_path, text)
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json"])
    assert json.loads(capsys.readouterr().out)["actions"][-1]["result"] == "timeout"


def test_bin_launcher_runs_with_system_python(tmp_path: Path):
    make_repo(tmp_path)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
    proc = subprocess.run([sys.executable, str(REPO / "bin" / "praxis"), "status", "--json"],
                          cwd=tmp_path, capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["signer"] == "Dimitri Diomaiuta"
    assert os.access(REPO / "bin" / "praxis", os.X_OK)


def test_status_color_auto_is_plain_when_not_a_tty(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NO_COLOR", raising=False)
    cli.main(["status", "--no-checks"])
    assert "\x1b[" not in capsys.readouterr().out


def test_status_color_always(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--no-checks", "--color", "always"])
    out = capsys.readouterr().out
    assert "\x1b[" in out and "DONE" in out


def test_status_color_never_and_json_unaffected(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--no-checks", "--color", "never"])
    assert "\x1b[" not in capsys.readouterr().out
    cli.main(["status", "--no-checks", "--json", "--color", "always"])
    json.loads(capsys.readouterr().out)


def test_use_color_auto_respects_tty_and_no_color(monkeypatch):
    class Tty:
        def isatty(self):
            return True

    class Pipe:
        def isatty(self):
            return False

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert cli.use_color("auto", Tty()) is True
    assert cli.use_color("auto", Pipe()) is False
    monkeypatch.setenv("NO_COLOR", "1")
    assert cli.use_color("auto", Tty()) is False
    assert cli.use_color("always", Pipe()) is True
    assert cli.use_color("never", Tty()) is False
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TERM", "dumb")
    assert cli.use_color("auto", Tty()) is False


def test_ledger_prints_all_entries_and_runs_no_checks(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("spawned")))
    assert cli.main(["ledger"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("- L1 [2026-09-03 Wed] Parser-first")
    assert "- L2 [2026-09-03 Wed 16:40 0a1b2c3d] a2 started" in out
    assert "not shown" not in out


def test_ledger_last_and_for_and_id(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["ledger", "--last", "1"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("(1 of 2 entries not shown)\n- L2 ")
    assert cli.main(["ledger", "--for", "a2"]) == 0
    assert capsys.readouterr().out.startswith("(1 of 2 entries not shown)\n- L2 ")
    assert cli.main(["ledger", "L1"]) == 0
    assert capsys.readouterr().out.startswith("(1 of 2 entries not shown)\n- L1 ")


def test_ledger_unknown_id_exit_2(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["ledger", "L9"]) == 2
    assert "no ledger entry L9" in capsys.readouterr().err


def test_ledger_color_and_path(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    assert cli.main(["ledger", "--path", str(tmp_path / "ROADMAP.org"), "--color", "always"]) == 0
    out = capsys.readouterr().out
    assert "\x1b[1mL1\x1b[0m" in out
    assert cli.main(["ledger", "--path", str(tmp_path / "ROADMAP.org")]) == 0
    assert "\x1b[" not in capsys.readouterr().out


def test_ledger_exit_2_on_parse_error(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path, ROADMAP.replace("- L2 [", "- L1 ["))
    monkeypatch.chdir(tmp_path)
    assert cli.main(["ledger"]) == 2
    assert "ROADMAP.org:" in capsys.readouterr().err


def test_status_exit_1_and_flag_on_dangling_trace(tmp_path: Path, capsys, monkeypatch):
    text = ROADMAP.replace("- source :: README release procedure\n",
                           "- source :: traces/never-captured.eml; ledger L2\n")
    make_repo(tmp_path, text)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["status", "--no-checks"]) == 1
    out = capsys.readouterr().out
    assert "a7: dangling_link (traces/never-captured.eml)" in out
    (tmp_path / "traces" / "never-captured.eml").write_text("")
    assert cli.main(["status", "--no-checks"]) == 0
    capsys.readouterr()
    assert cli.main(["status", "--no-checks", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    a7 = next(a for a in d["actions"] if a["id"] == "a7")
    assert {l["ref"]: l["resolved"] for l in a7["links"]} == {"traces/never-captured.eml": True, "L2": True}







def test_context_merges_several_ids_into_one_view(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["context", "a7", "C1", "--no-checks", "--color", "never", "--width", "80"]) == 0
    out = capsys.readouterr().out
    assert "a7   TODO    ·  release per README" in out and "C1   ·  tag vx.y.z on main.  Met by: a1 a7" in out
    assert out.count("═" * 80) == 4            # one block: clauses, actions, grounds
    assert out.count("C1   ·") == 1 and "a1   DONE    ·  cut x.y.z from main" in out
    assert all(len(l) <= 80 for l in out.splitlines())


def test_context_unknown_id_exits_2(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["context", "a42"]) == 2
    assert "no a42 in ROADMAP.org" in capsys.readouterr().err


def test_context_runs_checks_only_for_the_actions_shown(tmp_path: Path, capsys, monkeypatch):
    text = ROADMAP.replace("- source :: README release procedure\n- check :: false\n",
                           "- source :: after a1-a2\n- check :: false\n")
    make_repo(tmp_path, text)
    monkeypatch.chdir(tmp_path)
    calls = []
    real_run = subprocess.run

    def spy(*a, **kw):
        if kw.get("shell"):
            calls.append(a[0])
        return real_run(*a, **kw)

    monkeypatch.setattr(subprocess, "run", spy)
    assert cli.main(["context", "a7", "--color", "never"]) == 0
    out = capsys.readouterr().out
    assert sorted(calls) == ["false", "true"]            # a7 and a1; a2 has no check, a3-a6 are not shown
    assert "a7   TODO    ❌" in out and "a1   DONE    ✅" in out and "a2   STRT    ∅" in out
    calls.clear()
    cli.main(["context", "a7", "--no-checks"])
    assert calls == []


def test_ledger_signer_and_machine_filters(tmp_path: Path, capsys, monkeypatch):
    text = ROADMAP + "- L3 [2026-10-02 Thu 10:00 0a1b2c3d] a1 reverted to STRT: check failed. pipeline gone.\n"
    make_repo(tmp_path, text)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["ledger", "--machine"]) == 0
    out = capsys.readouterr().out
    assert "(2 of 3 entries not shown)" in out and "L3" in out and "L1" not in out
    assert cli.main(["ledger", "--signer"]) == 0
    out = capsys.readouterr().out
    assert "(1 of 3 entries not shown)" in out and "L1" in out and "L2" in out and "L3" not in out


def test_ledger_signer_and_machine_are_exclusive(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        cli.main(["ledger", "--signer", "--machine"])


def test_status_json_ledger_has_kind(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json", "--no-checks"])
    d = json.loads(capsys.readouterr().out)
    assert all(e["kind"] in ("signer", "machine") for e in d["ledger"])


def test_status_json_format_is_the_files_version(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path, ROADMAP.replace("#+PRAXIS: 2", "#+PRAXIS: 3"))
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json", "--no-checks"])
    assert json.loads(capsys.readouterr().out)["format"] == 3


def _recontact_repo(tmp_path: Path, script: str) -> Path:
    make_repo(tmp_path, ROADMAP.replace("#+PRAXIS: 2", "#+PRAXIS: 3\n#+RECONTACT: traces/recontact.sh"))
    hook = tmp_path / "traces" / "recontact.sh"
    hook.write_text(script)
    hook.chmod(0o755)
    return tmp_path


def test_status_runs_recontact_and_flags_its_lines_on_failure(tmp_path: Path, capsys, monkeypatch):
    _recontact_repo(tmp_path, "#!/bin/sh\necho 'forge: token has no read scope'\necho 'registry: name does not resolve'\nexit 1\n")
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json"])   # the hook runs only when checks run (spec Section 3)
    d = json.loads(capsys.readouterr().out)
    assert d["recontact"] == {"command": "traces/recontact.sh", "exit": 1,
                              "lines": ["forge: token has no read scope", "registry: name does not resolve"]}
    assert "recontact: forge: token has no read scope" in d["flags"]
    assert "recontact: registry: name does not resolve" in d["flags"]


def test_status_recontact_success_adds_no_flag_and_checks_still_run(tmp_path: Path, capsys, monkeypatch):
    _recontact_repo(tmp_path, "#!/bin/sh\necho fetched\nexit 0\n")
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["recontact"]["exit"] == 0 and d["recontact"]["lines"] == ["fetched"]
    assert not any(f.startswith("recontact:") for f in d["flags"])
    assert next(a for a in d["actions"] if a["id"] == "a1")["result"] == "passed"


def test_status_no_recontact_skips_the_hook(tmp_path: Path, capsys, monkeypatch):
    _recontact_repo(tmp_path, "#!/bin/sh\necho ran > hook-ran\nexit 1\n")
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json", "--no-checks", "--no-recontact"])
    d = json.loads(capsys.readouterr().out)
    assert d["recontact"] is None and not (tmp_path / "hook-ran").exists()


def test_status_without_header_has_null_recontact(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json", "--no-checks"])
    assert json.loads(capsys.readouterr().out)["recontact"] is None


def test_status_recontact_timeout_is_one_flag_and_checks_still_run(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path, ROADMAP.replace("#+PRAXIS: 2", "#+PRAXIS: 3\n#+CHECK_TIMEOUT: 1\n#+RECONTACT: sleep 5"))
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["recontact"] == {"command": "sleep 5", "exit": None, "lines": ["timeout after 1s"]}
    assert "recontact: timeout after 1s" in d["flags"]
    assert next(a for a in d["actions"] if a["id"] == "a1")["result"] == "passed"


def test_status_flags_commits_not_in_this_repo(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path, ROADMAP + "- L3 [2026-10-02 Thu] Recontact: fixture commit c0ffee1 gone.\n")
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json", "--no-checks"])
    d = json.loads(capsys.readouterr().out)
    flag = next(f for f in d["flags"] if f.startswith("commits not in this repo:"))
    assert "ab12cd3 (a2 source, L2)" in flag and "c0ffee1 (L3)" in flag   # cited by a2 and by L2


def test_no_commit_flag_outside_a_git_repo(tmp_path: Path, capsys, monkeypatch):
    (tmp_path / "ROADMAP.org").write_text(ROADMAP)
    (tmp_path / "traces").mkdir()
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json", "--no-checks"])
    d = json.loads(capsys.readouterr().out)
    assert not any(f.startswith("commits not in this repo") for f in d["flags"])


def test_status_flags_work_since_last_stamp(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    for name in ("x.py", "y.py", "z.py", "w.py"):
        p = tmp_path / name
        p.write_text(name)
        os.utime(p, (4102444800, 4102444800))   # 2100-01-01, after any stamp
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json", "--no-checks"])
    d = json.loads(capsys.readouterr().out)
    flag = next(f for f in d["flags"] if f.startswith("work since L2:"))
    # ROADMAP.org is itself untracked and newer than L2 but excluded (the caller just wrote it): four .py
    assert "4 files changed after its stamp" in flag and flag.count(", ") == 2   # three names shown


def test_no_work_flag_when_ledger_is_empty_or_nothing_is_newer(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    for p in tmp_path.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            os.utime(p, (946684800, 946684800))   # 2000-01-01
    cli.main(["status", "--json", "--no-checks"])
    d = json.loads(capsys.readouterr().out)
    assert not any(f.startswith("work since") for f in d["flags"])


def test_make_stamp_english_weekday_and_session():
    from datetime import datetime
    assert cli.make_stamp(datetime(2026, 10, 6, 19, 34), "1a2b3c4d-1234-abcd") == "[2026-10-06 Tue 19:34 1a2b3c4d]"
    assert cli.make_stamp(datetime(2026, 10, 6, 9, 5), None) == "[2026-10-06 Tue 09:05]"


def test_make_stamp_weekday_is_english_under_any_locale(monkeypatch):
    import locale
    from datetime import datetime
    try:
        locale.setlocale(locale.LC_TIME, "it_IT.UTF-8")
    except locale.Error:
        pytest.skip("it_IT locale not installed")
    try:
        assert cli.make_stamp(datetime(2026, 10, 7, 12, 0), None).split()[1] == "Wed"
    finally:
        locale.setlocale(locale.LC_TIME, "C")


def test_stamp_subcommand_prints_parseable_stamp(capsys, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "3c4d5e6f-0000")
    assert cli.main(["stamp"]) == 0
    out, err = capsys.readouterr()
    from praxis.parse import parse_stamp
    s = parse_stamp(out.strip()[1:-1], 1, "x")
    assert s.session == "3c4d5e6f" and s.time is not None and err == ""


def test_stamp_subcommand_without_session(capsys, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    assert cli.main(["stamp"]) == 0
    out, err = capsys.readouterr()
    assert out.strip().count(" ") == 2 and err.strip() == "no session"


def test_checkpoint_subcommand_runs_no_checks_by_default_flag_and_prints(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["checkpoint", "--no-checks"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("C1 ") and "a2 STRT ·" in out and "L2" in out


def test_work_since_does_not_fire_on_the_roadmap_written_in_the_stamps_minute(tmp_path: Path, capsys, monkeypatch):
    from datetime import datetime
    make_repo(tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "0a1b2c3d")
    cli.main(["stamp"])
    stamp = capsys.readouterr().out.strip()
    rp = tmp_path / "ROADMAP.org"
    rp.write_text(rp.read_text() + f"- L3 {stamp} a2 gate result: failed. not yet.\n")
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json", "--no-checks"])
    d = json.loads(capsys.readouterr().out)
    assert not any(f.startswith("work since") for f in d["flags"])


def test_recontact_failure_without_output_still_flags_the_exit(tmp_path: Path, capsys, monkeypatch):
    _recontact_repo(tmp_path, "#!/bin/sh\nexit 7\n")
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["recontact"]["lines"] == [] and "recontact: exit 7" in d["flags"]


def test_recontact_keeps_stdout_and_stderr_lines_apart(tmp_path: Path, capsys, monkeypatch):
    _recontact_repo(tmp_path, "#!/bin/sh\nprintf 'out-last'\necho err-first >&2\nexit 1\n")
    monkeypatch.chdir(tmp_path)
    cli.main(["status", "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["recontact"]["lines"] == ["out-last", "err-first"]


def _many_hashes_roadmap() -> str:
    """A roadmap whose actions and ledger cite many commit-shaped tokens, so per-hash git
    calls would show up in a process count."""
    text = ROADMAP.replace("- source :: parser branch ab12cd3", "- source :: parser branch ab12cd3, also abc1234 bcd2345 cde3456 def4567")
    for i in range(30):
        text += f"- L{3 + i} [2026-10-02 Thu 10:00 0a1b2c3d] Recontact: head at {i:07x}a; compare {i:07x}b and {i:07x}c.\n"
    return text


def _git_calls(monkeypatch) -> list:
    calls = []
    real_run = subprocess.run

    def spy(args, *a, **kw):
        if isinstance(args, list) and args and args[0] == "git":
            calls.append(args)
        return real_run(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", spy)
    return calls


def test_status_resolves_all_hashes_in_a_bounded_number_of_git_calls(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path, _many_hashes_roadmap())
    monkeypatch.chdir(tmp_path)
    calls = _git_calls(monkeypatch)
    cli.main(["status", "--json", "--no-checks"])
    d = json.loads(capsys.readouterr().out)
    flag = next(f for f in d["flags"] if f.startswith("commits not in this repo:"))
    assert "abc1234 (a2 source)" in flag and "0000001a (L4)" in flag and "000001dc (L32)" in flag
    assert len(calls) <= 6, [c[:3] for c in calls]


def test_context_resolves_only_what_it_shows_and_runs_no_status_readings(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path, _many_hashes_roadmap())
    monkeypatch.chdir(tmp_path)
    calls = _git_calls(monkeypatch)
    assert cli.main(["context", "a2", "--no-checks"]) == 0
    out = capsys.readouterr().out
    assert "abc1234" in out                      # a2's own commit grounds are still drawn
    assert len(calls) <= 5, [c[:3] for c in calls]
    assert not any("status" in c for c in calls)   # no work-since scan for a view


def test_graph_is_no_longer_a_command(tmp_path: Path, capsys, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as e:
        cli.main(["graph", "--dot"])
    assert e.value.code == 2 and "invalid choice: 'graph'" in capsys.readouterr().err

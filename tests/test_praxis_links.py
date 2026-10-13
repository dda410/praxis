from __future__ import annotations
import subprocess
from pathlib import Path
from praxis.links import Link, all_links, expand_braces, links_of, trace_exists
from praxis.parse import parse_roadmap
from tests.praxis_helpers import ROADMAP, make_repo


def _rm(text=ROADMAP):
    return parse_roadmap(text, path="ROADMAP.org")


def test_expand_braces():
    assert expand_braces("traces/x-{a,b}-1.csv") == ["traces/x-a-1.csv", "traces/x-b-1.csv"]
    assert expand_braces("traces/plain.csv") == ["traces/plain.csv"]


def test_trace_exists_plain_glob_and_braces(tmp_path: Path):
    (tmp_path / "traces").mkdir()
    for n in ("mail-2026-09-03-1.eml", "s9-a-2026.csv", "s9-b-2026.csv"):
        (tmp_path / "traces" / n).write_text("")
    assert trace_exists(tmp_path, "traces/s9-a-2026.csv")
    assert trace_exists(tmp_path, "traces/mail-2026-09-03-*.eml")
    assert trace_exists(tmp_path, "traces/s9-{a,b}-2026.csv")
    assert not trace_exists(tmp_path, "traces/s9-{a,c}-2026.csv")
    assert not trace_exists(tmp_path, "traces/missing.csv")
    assert not trace_exists(tmp_path, "traces/none-*.eml")


def test_links_ledger_trace_commit_with_trailing_punctuation(tmp_path: Path):
    make_repo(tmp_path)
    (tmp_path / "traces" / "ok.log").write_text("")
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty",
                    "-m", "x"], cwd=tmp_path, check=True)
    sha = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=tmp_path,
                         capture_output=True, text=True).stdout.strip()
    text = ROADMAP.replace(
        "- source :: README release procedure\n- check :: false\n",
        f"- source :: ledger L2; (traces/ok.log); traces/gone.csv. commit {sha}; other repo f00dfa1;"
        f" sha256 facade00; ledger L9\n- check :: false\n")
    rm = _rm(text)
    links = links_of(rm.action("a7"), rm, tmp_path)
    assert links == [
        Link("ledger", "L2", "source", True),
        Link("ledger", "L9", "source", False),
        Link("trace", "traces/ok.log", "source", True),
        Link("trace", "traces/gone.csv", "source", False),
        Link("commit", sha, "source", True),
        Link("commit", "f00dfa1", "source", False),
    ]
    dangling = [l for l in links if l.dangling]
    assert [l.ref for l in dangling] == ["L9", "traces/gone.csv"]   # unresolved commit is not dangling


def test_links_without_root_leave_traces_and_commits_unchecked():
    text = ROADMAP.replace("- source :: README release procedure\n",
                           "- source :: ledger L1; traces/x.csv; abc1234\n")
    rm = _rm(text)
    links = links_of(rm.action("a7"), rm, None)
    assert links == [Link("ledger", "L1", "source", True), Link("trace", "traces/x.csv", "source", None),
                     Link("commit", "abc1234", "source", None)]
    assert not any(l.dangling for l in links)


def test_commit_regex_needs_a_hex_letter_and_word_boundary():
    text = ROADMAP.replace("- source :: README release procedure\n",
                           "- source :: ticket 1001; pipeline #42; deadbeef1; https://x/deadbee\n")
    rm = _rm(text)
    refs = [l.ref for l in links_of(rm.action("a7"), rm, None) if l.kind == "commit"]
    assert refs == ["deadbeef1"]


def test_all_links_keyed_by_action(tmp_path: Path):
    make_repo(tmp_path)
    links = all_links(_rm(), tmp_path)
    assert set(links) == {f"a{i}" for i in range(1, 8)}
    assert links["a3"] == [] or all(isinstance(l, Link) for l in links["a3"])


def test_mentions_ids_of_three_kinds_in_order_unique():
    from praxis.links import mentions
    text = "a10 started; C3 now Met by: a3 a10. Evidence: ledger L15; overtakes L15."
    assert mentions(text) == ["a10", "C3", "a3", "L15"]


def test_mentions_expand_ranges_and_reject_reversed():
    from praxis.links import mentions
    assert mentions("ids s1-s8 renamed a1-a4; entries L28-L31; a9-a7") == \
        ["a1", "a2", "a3", "a4", "L28", "L29", "L30", "L31", "a9", "a7"]


def test_mentions_are_word_bounded():
    from praxis.links import mentions
    # hex, session ids, tickets and branch names never yield an id
    assert mentions("9a1c0de a1b2c3d4 d1e2f3a4 ABC-0000 x.y.z-abc-000 REF-100/01 XL1 xa1 L1x") == []
    assert mentions("(a5) [L2]. C7: done") == ["a5", "L2", "C7"]


def test_text_links_resolves_traces_and_commits_of_any_text(tmp_path: Path):
    from praxis.links import text_links
    make_repo(tmp_path)
    (tmp_path / "traces" / "ok.log").write_text("")
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty",
                    "-m", "x"], cwd=tmp_path, check=True)
    sha = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=tmp_path,
                         capture_output=True, text=True).stdout.strip()
    links = text_links(f"Evidence: traces/ok.log, traces/gone.csv; {sha} and f00dfa1; ledger L2 sha256 facade00.",
                       {"L2"}, tmp_path, field="text")
    assert links == [
        Link("ledger", "L2", "text", True),
        Link("trace", "traces/ok.log", "text", True),
        Link("trace", "traces/gone.csv", "text", False),
        Link("commit", sha, "text", True),
        Link("commit", "f00dfa1", "text", False),
    ]


def test_ledger_links_resolve_commits_in_entry_text(tmp_path: Path):
    import subprocess
    from praxis.links import ledger_links
    from praxis.parse import parse_roadmap
    from tests.praxis_helpers import ROADMAP, make_repo
    make_repo(tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x"], cwd=tmp_path, check=True)
    sha = subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"], cwd=tmp_path, text=True).strip()
    rm = parse_roadmap(ROADMAP + f"- L3 [2026-10-02 Thu] Recontact: head at {sha}; old hash deadbee1 gone. sha256 abcdef1234 is a digest.\n")
    out = ledger_links(rm, tmp_path)
    refs = {(l.ref, l.resolved, l.field) for l in out["L3"]}
    assert (sha, True, "L3") in refs and ("deadbee1", False, "L3") in refs
    assert not any(l.ref == "abcdef1234" for l in out["L3"])


def test_resolve_commits_batches_every_sha_into_one_git_call(tmp_path: Path, monkeypatch):
    from praxis.links import resolve_commits
    make_repo(tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x"], cwd=tmp_path, check=True)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    calls = []
    real_run = subprocess.run

    def spy(args, *a, **kw):
        if isinstance(args, list) and args and args[0] == "git":
            calls.append(args)
        return real_run(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", spy)
    out = resolve_commits(tmp_path, [sha[:7], sha, "deadbee1", "c0ffee1"])
    assert out == {sha[:7]: True, sha: True, "deadbee1": False, "c0ffee1": False}
    assert len(calls) == 1 and "--batch-check" in calls[0]


def test_resolve_commits_outside_git_is_none_for_every_sha(tmp_path: Path):
    from praxis.links import resolve_commits
    assert resolve_commits(tmp_path, ["deadbee1"]) == {"deadbee1": None}
    assert resolve_commits(tmp_path, []) == {}

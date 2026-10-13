from __future__ import annotations
from praxis.invariants import clause_met, flags, summary, uplinks, violations
from praxis.model import CheckResult
from praxis.parse import parse_roadmap
from tests.praxis_helpers import ROADMAP


def _results(**kw: str) -> dict[str, CheckResult]:
    base = {f"a{i}": CheckResult("absent") for i in range(1, 8)}
    for k, v in kw.items():
        base[k] = CheckResult(v)
    return base


def test_clean_roadmap_has_no_violations():
    v = violations(parse_roadmap(ROADMAP), _results(a1="passed"))
    assert all(codes == [] for codes in v.values())
    assert set(v) == {f"a{i}" for i in range(1, 8)}


def test_done_with_failing_check():
    v = violations(parse_roadmap(ROADMAP), _results(a1="failed"))
    assert v["a1"] == ["done_without_passing_check"]


def test_done_with_absent_check_even_when_checks_skipped():
    text = ROADMAP.replace("** STRT a2 land the new parser", "** DONE a2 land the new parser")
    v = violations(parse_roadmap(text), None)
    assert "done_without_passing_check" in v["a2"]
    assert "done_without_passing_check" not in v["a1"]  # has a check; skipped -> not judged


def test_done_without_stamp():
    text = ROADMAP.replace("- done :: [2026-09-03 Wed 10:12 0a1b2c3d]\n", "")
    v = violations(parse_roadmap(text), _results(a1="passed"))
    assert v["a1"] == ["done_without_stamp"]


def test_done_stamp_without_session_is_a_flag_not_a_violation():
    text = ROADMAP.replace("[2026-09-03 Wed 10:12 0a1b2c3d]", "[2026-09-03 Wed 10:12]")
    rm = parse_roadmap(text)
    assert violations(rm, _results(a1="passed"))["a1"] == []
    assert "a1: done stamp has no session" in flags(rm)


def test_clause_without_met_by_is_a_flag():
    rm = parse_roadmap(ROADMAP)
    assert flags(rm)[0] == "C3: no Met by"


def test_no_source_on_strt_and_done():
    text = ROADMAP.replace("- source :: parser branch ab12cd3\n", "")
    v = violations(parse_roadmap(text), _results(a1="passed"))
    assert "no_source" in v["a2"] and "phantom" in v["a2"]


def test_phantom_on_todo_without_source_but_not_signal():
    text = ROADMAP.replace("- source :: ledger 2026-09-03\n", "").replace("- source :: verbal 2026-09-03\n", "")
    v = violations(parse_roadmap(text), _results(a1="passed"))
    assert v["a3"] == ["phantom"] and v["a6"] == []


def test_skip_requires_ledger_mention_whole_word():
    text = ROADMAP.replace("** TODO a4 speed vs previous", "** SKIP a4 speed vs previous")
    assert violations(parse_roadmap(text), _results(a1="passed"))["a4"] == ["skip_without_ledger"]
    text2 = text + "- L3 [2026-09-04] a40 struck for unrelated reasons.\n"
    assert violations(parse_roadmap(text2), _results(a1="passed"))["a4"] == ["skip_without_ledger"]
    text3 = text + "- L3 [2026-09-04] a4 struck: speed claimed from the previous release instead.\n"
    assert violations(parse_roadmap(text3), _results(a1="passed"))["a4"] == []


def test_clause_met_requires_all_named_actions_done():
    rm = parse_roadmap(ROADMAP)
    c1, c2, c3 = rm.clauses
    assert clause_met(rm, c1) is False  # a7 is TODO
    assert clause_met(rm, c3) is False  # no Met by
    done = parse_roadmap(ROADMAP.replace("** TODO a7 release per README", "** DONE a7 release per README"))
    assert clause_met(done, done.clauses[0]) is True


def test_summary_counts():
    rm = parse_roadmap(ROADMAP)
    s = summary(rm, violations(rm, _results(a1="failed")))
    assert s == {"done": 1, "open": 5, "signal": 1, "clauses": 3, "clauses_met": 0, "violations": 1, "phantoms": 0}


def test_dangling_link_only_from_ledger_and_trace_links():
    from praxis.links import Link
    rm = parse_roadmap(ROADMAP)
    links = {a.id: [] for a in rm.actions}
    links["a7"] = [Link("commit", "f00dfa1", "source", False), Link("trace", "traces/x", "source", None)]
    assert violations(rm, _results(a1="passed"), links)["a7"] == []
    links["a7"] = [Link("trace", "traces/x", "source", False)]
    assert violations(rm, _results(a1="passed"), links)["a7"] == ["dangling_link"]
    assert violations(rm, _results(a1="passed"))["a7"] == []   # no links given: not checked


def test_violations_skip_check_verdict_for_actions_without_a_result():
    from praxis.invariants import violations
    from praxis.model import CheckResult
    from praxis.parse import parse_roadmap
    from tests.praxis_helpers import ROADMAP
    rm = parse_roadmap(ROADMAP.replace("- check :: true", "- check :: false"), path="ROADMAP.org")
    # a1 is DONE with a check but no result was gathered: neither confirmed nor accused
    assert violations(rm, {"a7": CheckResult("failed")})["a1"] == []
    assert violations(rm, {"a1": CheckResult("failed")})["a1"] == ["done_without_passing_check"]


# ---- up-links: every action owes a path to a clause, through Met by or through the source of an
# action it fed (manifest lines 624-627); derived, reported as flags, SIGNAL and SKIP exempt.

def test_uplink_direct_through_met_by():
    up = uplinks(parse_roadmap(ROADMAP))
    assert up["a1"] == ["a1", "C1"] and up["a4"] == ["a4", "C2"]


def test_uplink_through_source_chain_with_range():
    text = ROADMAP.replace("- source :: setpoint C2", "- source :: setpoint C2; a2-a3") \
                  .replace("- source :: parser branch ab12cd3", "- source :: parser branch ab12cd3, after a5")
    up = uplinks(parse_roadmap(text))
    assert up["a5"] == ["a5", "a2", "a4", "C2"]     # a5 fed a2 (a2's source names it), a2 fed a4 (range), a4 meets C2
    assert up["a3"] == ["a3", "a4", "C2"]


def test_uplink_ignores_evidence_ledger_and_clause_prose():
    text = ROADMAP.replace("- source :: parser branch ab12cd3\n- evidence :: staged diff",
                           "- source :: parser branch ab12cd3\n- evidence :: staged diff, a3") \
                  .replace("- C3 :: date format option settled with the reviewer", "- C3 :: a5 settled with the reviewer")
    up = uplinks(parse_roadmap(text))
    assert up["a3"] == [] and up["a5"] == []


def test_uplink_cycle_terminates():
    text = ROADMAP.replace("- source :: parser branch ab12cd3", "- source :: a3") \
                  .replace("- source :: ledger 2026-09-03", "- source :: a2")
    up = uplinks(parse_roadmap(text))
    assert up["a2"] == [] and up["a3"] == []


def test_no_uplink_flag_for_open_and_done_but_not_signal_or_skip():
    text = ROADMAP.replace("** TODO a5 date format", "** SKIP a5 date format")
    f = flags(parse_roadmap(text))
    assert "a2: no up-link" in f and "a3: no up-link" in f
    assert not any(x.startswith(("a1:", "a4:", "a5:", "a6:", "a7:")) and "up-link" in x for x in f)


def test_done_resting_on_open_action_is_a_flag():
    text = ROADMAP.replace("- source :: README release procedure\n- evidence :: branch x.y.z",
                           "- source :: README release procedure; a2\n- evidence :: branch x.y.z")
    f = flags(parse_roadmap(text))
    assert "a1: done rests on a2 STRT" in f
    assert "a2: done rests on" not in " ".join(f)


def test_unclosable_check_is_a_flag_when_results_are_given():
    rm = parse_roadmap(ROADMAP)
    assert "a3: unclosable check (grep -q PASS traces/parity.log)" in flags(rm, _results(a3="unclosable"))
    assert not any("unclosable" in x for x in flags(rm))


def test_flags_order_clauses_then_actions_in_file_order():
    f = flags(parse_roadmap(ROADMAP), _results(a1="passed", a3="unclosable"))
    assert f == ["C3: no Met by", "a1: check never seen failing", "a2: no up-link", "a3: no up-link",
                 "a3: unclosable check (grep -q PASS traces/parity.log)", "a5: no up-link"]


def test_done_with_pending_check_is_a_violation():
    from praxis.invariants import DONE_WITHOUT_PASSING_CHECK, violations
    from praxis.model import CheckResult
    from praxis.parse import parse_roadmap
    from tests.praxis_helpers import ROADMAP
    rm = parse_roadmap(ROADMAP)
    v = violations(rm, {"a1": CheckResult("pending", 3)})
    assert DONE_WITHOUT_PASSING_CHECK in v["a1"]


def _rm_with_ledger(*entries: str):
    from praxis.parse import parse_roadmap
    from tests.praxis_helpers import ROADMAP
    extra = "".join(f"- L{10 + i} [2026-10-02 Thu 10:0{i} 0a1b2c3d] {t}\n" for i, t in enumerate(entries))
    return parse_roadmap(ROADMAP + extra)


def test_done_action_with_no_failing_gate_or_revert_is_flagged():
    from praxis.invariants import flags
    assert "a1: check never seen failing" in flags(_rm_with_ledger())


def test_failed_gate_result_clears_the_flag():
    from praxis.invariants import flags
    assert "a1: check never seen failing" not in flags(_rm_with_ledger("a1 gate result: failed. not pushed yet."))


def test_revert_clears_the_flag_and_multi_id_entries_count():
    from praxis.invariants import flags
    assert "a1: check never seen failing" not in flags(_rm_with_ledger("a3 a1 reverted to STRT: check pending. running."))


def test_seen_failing_on_clears_the_flag_even_when_passed():
    from praxis.invariants import flags
    assert "a1: check never seen failing" not in flags(
        _rm_with_ledger("a1 gate result: passed. ok. Check seen failing on: the pre-change source."))


def test_passed_gate_without_seen_failing_keeps_the_flag():
    from praxis.invariants import flags
    assert "a1: check never seen failing" in flags(_rm_with_ledger("a1 gate result: passed. ok."))


def test_flag_only_on_done_actions():
    from praxis.invariants import flags
    out = flags(_rm_with_ledger())
    assert not any(f.startswith("a2:") and "never seen failing" in f for f in out)


def test_commits_not_in_repo_flag_lists_each_sha_with_its_places():
    from praxis.invariants import flags
    from praxis.links import Link
    rm = _rm_with_ledger("Recontact: old head deadbee1 gone.")
    action_links = {a.id: [] for a in rm.actions}
    action_links["a2"] = [Link("commit", "deadbee1", "source", False), Link("commit", "ab12cd3", "source", True)]
    entry_links = {"L10": [Link("commit", "deadbee1", "L10", False)]}
    out = flags(rm, None, links=action_links, ledger_links=entry_links)
    assert "commits not in this repo: deadbee1 (a2 source, L10)" in out


def test_no_commit_flag_when_nothing_unresolved_or_unchecked():
    from praxis.invariants import flags
    from praxis.links import Link
    rm = _rm_with_ledger()
    links = {a.id: [] for a in rm.actions}
    links["a2"] = [Link("commit", "ab12cd3", "source", None)]   # not a git repo: unchecked, not flagged
    assert not any(f.startswith("commits not in this repo") for f in flags(rm, None, links=links, ledger_links={}))

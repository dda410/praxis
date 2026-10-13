from __future__ import annotations
import json
from praxis.invariants import violations
from praxis.model import CheckResult
from praxis.parse import parse_roadmap
from praxis.render import table_view, to_dict
from tests.praxis_helpers import ROADMAP


def _results():
    r = {f"a{i}": CheckResult("absent") for i in range(1, 8)}
    r["a1"] = CheckResult("passed", 0, "", "")
    r["a3"] = CheckResult("unclosable")
    r["a7"] = CheckResult("failed", 1, "", "")
    return r


def _doc(text=ROADMAP, results="default", branch="x.y.z"):
    rm = parse_roadmap(text, path="ROADMAP.org")
    res = _results() if results == "default" else results
    return to_dict(rm, res, violations(rm, res), branch=branch)


def test_to_dict_matches_schema():
    d = _doc()
    assert set(d) == {"path", "branch", "format", "title", "signer", "opened", "closed",
                      "setpoint", "actions", "ledger", "recontact", "flags", "summary"}
    assert d["format"] == 2 and d["branch"] == "x.y.z" and d["closed"] is None
    assert d["title"] == "orrery x.y.z — roadmap"
    c1 = d["setpoint"][0]
    assert c1 == {"id": "C1", "text": "tag vx.y.z on main.", "met_by": ["a1", "a7"], "met": False}
    a1 = d["actions"][0]
    assert set(a1) == {"id", "title", "state", "source", "evidence", "check", "done", "result", "violations",
                       "clauses", "reaches", "links"}
    assert a1["links"] == []
    assert a1["done"] == {"date": "2026-09-03", "time": "10:12", "session": "0a1b2c3d"}
    assert a1["clauses"] == ["C1"] and a1["result"] == "passed"
    a3 = d["actions"][2]
    assert a3["done"] is None and a3["result"] == "unclosable" and a3["clauses"] == []
    assert d["ledger"][0] == {"id": "L1", "date": "2026-09-03", "time": None, "session": None, "kind": "signer",
                              "text": "Parser-first replaces benchmark-first; benchmark attempt archived. Evidence: 1234567, 2b3c4d5."}
    assert d["ledger"][1]["session"] == "0a1b2c3d" and d["ledger"][1]["time"] == "16:40" and d["ledger"][1]["id"] == "L2"
    assert d["summary"] == {"done": 1, "open": 5, "signal": 1, "clauses": 3, "clauses_met": 0,
                            "violations": 0, "phantoms": 0}
    json.dumps(d)


def test_to_dict_null_results_when_checks_skipped():
    d = _doc(results=None)
    assert all(a["result"] is None for a in d["actions"])


def test_clause_met_in_dict():
    text = ROADMAP.replace("** TODO a7 release per README", "** DONE a7 release per README")
    text = text.replace("- check :: false", "- check :: true\n- done :: [2026-09-04 Thu 09:00 4e5f6a7b]")
    res = _results()
    res["a7"] = CheckResult("passed", 0)
    d = _doc(text, res)
    assert d["setpoint"][0]["met"] is True and d["summary"]["clauses_met"] == 1


def test_table_view_lists_clauses_actions_flags_summary():
    out = table_view(_doc())
    assert out.splitlines()[0] == "orrery x.y.z — roadmap"
    assert "branch: x.y.z   signer: Dimitri Diomaiuta   opened: 2026-09-03" in out
    assert "C1   ·  tag vx.y.z on main.  (a1 a7)" in out
    assert "C3   ·  date format option settled with the reviewer" in out
    assert "a1   DONE    ✅  cut x.y.z from main" in out
    assert "a3   TODO    ⛔  parity gate" in out
    assert "a7   TODO    ❌  release per README" in out
    assert "flags:" in out and "a3: unclosable check" in out and "C3: no Met by" in out
    assert "remains:" not in out
    assert out.rstrip().endswith("done 1  open 5  signal 1  clauses 0/3  violations 0  phantoms 0")


def test_table_view_shows_met_clause_and_violations():
    text = ROADMAP.replace("** TODO a7 release per README", "** DONE a7 release per README")
    text = text.replace("- check :: false", "- check :: true\n- done :: [2026-09-04 Thu 09:00 4e5f6a7b]")
    res = _results()
    res["a1"] = CheckResult("failed", 1)
    res["a7"] = CheckResult("passed", 0)
    out = table_view(_doc(text, res, branch=None))
    assert "C1   ✅  tag vx.y.z on main.  (a1 a7)" in out
    assert "a1: done_without_passing_check" in out
    assert "branch: ?" in out


def test_view_flags_agree_with_invariants_flags():
    from praxis.invariants import flags
    rm = parse_roadmap(ROADMAP)
    out = table_view(_doc())
    for f in flags(rm, _results()):
        assert f"  {f}" in out


def test_doc_carries_flags_and_each_action_its_uplink_path():
    from praxis.invariants import flags
    d = _doc()
    assert d["flags"] == flags(parse_roadmap(ROADMAP), _results())
    by_id = {a["id"]: a for a in d["actions"]}
    assert by_id["a1"]["reaches"] == ["a1", "C1"] and by_id["a2"]["reaches"] == []
    assert "a2: no up-link" in d["flags"] and "a3: unclosable check (grep -q PASS traces/parity.log)" in d["flags"]


def test_table_view_prints_flags_from_the_document_in_order():
    d = _doc()
    d["flags"] = ["C9: made up", "a1: also made up"]
    out = table_view(d)
    assert "flags:\n  C9: made up\n  a1: also made up" in out


def test_id_column_width_aligns_two_digit_ids():
    text = ROADMAP.replace(
        "** TODO a7 release per README\n- source :: README release procedure\n- check :: false\n",
        "** TODO a7 release per README\n- source :: README release procedure\n- check :: false\n"
        "** TODO a10 tenth action\n- source :: test\n")
    text = text.replace(
        "- C3 :: date format option settled with the reviewer\n",
        "- C3 :: date format option settled with the reviewer\n- C10 :: tenth clause\n")
    out = table_view(_doc(text, results=None))
    assert "a10  TODO" in out
    assert "C10  ·" in out


def test_table_view_default_has_no_ansi():
    assert "\x1b[" not in table_view(_doc())


def test_table_view_color_matches_plain_when_stripped():
    from praxis.render import strip_ansi
    plain = table_view(_doc())
    colored = table_view(_doc(), color=True)
    assert colored != plain
    assert strip_ansi(colored) == plain


def test_table_view_colors_states_results_flags_and_summary():
    from praxis.render import BOLD, DIM, GREEN, MAGENTA, RED, RESET, YELLOW
    text = ROADMAP.replace("** TODO a7 release per README", "** STRT a7 release per README")
    out = table_view(_doc(text), color=True)
    assert out.splitlines()[0] == f"{BOLD}orrery x.y.z — roadmap{RESET}"
    assert f"{GREEN}DONE{RESET}" in out and f"{GREEN}✅{RESET}" in out      # a1 passed
    assert f"{YELLOW}STRT{RESET}" in out and f"{RED}❌{RESET}" in out       # a7 failed
    assert f"{MAGENTA}SIGNAL{RESET}" in out
    assert f"{RED}⛔{RESET}" in out                                          # a3 unclosable
    assert f"{DIM}∅{RESET}" in out                                           # absent
    assert f"{YELLOW}a3: unclosable check" in out
    assert f"{YELLOW}C3: no Met by{RESET}" in out
    assert f"violations {GREEN}0{RESET}" in out and f"phantoms {GREEN}0{RESET}" in out


def test_table_view_colors_violations_red():
    from praxis.render import DIM, GREEN, RED, RESET
    text = ROADMAP.replace("** TODO a7 release per README", "** DONE a7 release per README")
    text = text.replace("- check :: false", "- check :: true\n- done :: [2026-09-04 Thu 09:00 4e5f6a7b]")
    res = _results()
    res["a1"] = CheckResult("failed", 1)
    res["a7"] = CheckResult("passed", 0)
    out = table_view(_doc(text, res), color=True)
    assert f"{RED}a1: done_without_passing_check{RESET}" in out
    assert f"violations {RED}1{RESET}" in out
    assert f"C1   {GREEN}✅{RESET}" in out
    assert f"C2   {DIM}·{RESET}" in out


def test_table_view_no_flags_dim_none():
    from praxis.render import DIM, RESET
    text = ROADMAP.replace("- C3 :: date format option settled with the reviewer\n",
                           "- C3 :: date format option settled with the reviewer. Met by: a5\n") \
                  .replace("** TODO a7 release per README\n- source :: README release procedure",
                           "** TODO a7 release per README\n- source :: README release procedure; a2 a3")   # a2, a3 fed a7
    text += "- L3 [2026-09-03 Wed 17:00 0a1b2c3d] a1 gate result: failed. branch not cut yet.\n"   # a1 seen failing
    res = _results()
    res["a3"] = CheckResult("absent")
    out = table_view(_doc(text, res), color=True)
    assert f"flags: {DIM}none{RESET}" in out


def _ledger(text=ROADMAP):
    return parse_roadmap(text, path="ROADMAP.org").ledger


def test_ledger_view_prints_entries_verbatim_one_per_line():
    from praxis.render import ledger_view
    out = ledger_view(_ledger())
    assert out.splitlines() == [
        "- L1 [2026-09-03 Wed] Parser-first replaces benchmark-first; benchmark attempt archived. Evidence: 1234567, 2b3c4d5.",
        "- L2 [2026-09-03 Wed 16:40 0a1b2c3d] a2 started: commit the staged parser. Prior: fast tests green."
        " Regulates against: ab12cd3. Tacit: none.",
    ]
    assert "\x1b[" not in out


def test_ledger_view_color_bold_id_dim_stamp():
    from praxis.render import BOLD, DIM, RESET, ledger_view, strip_ansi
    out = ledger_view(_ledger(), color=True)
    assert out.splitlines()[0].startswith(f"- {BOLD}L1{RESET} {DIM}[2026-09-03 Wed]{RESET} Parser-first")
    assert strip_ansi(out) == ledger_view(_ledger())


def test_ledger_view_reports_hidden_entries():
    from praxis.render import DIM, RESET, ledger_view
    entries = _ledger()
    out = ledger_view(entries[-1:], hidden=1)
    assert out.splitlines()[0] == "(1 of 2 entries not shown)"
    assert out.splitlines()[1].startswith("- L2 ")
    assert ledger_view(entries[-1:], hidden=1, color=True).splitlines()[0] == f"{DIM}(1 of 2 entries not shown){RESET}"
    assert ledger_view([], hidden=2) == "(2 of 2 entries not shown)"
    assert ledger_view([]) == "(ledger is empty)"


def test_ledger_select_last_id_and_for():
    from praxis.render import select_ledger
    entries = _ledger()
    assert select_ledger(entries) == (entries, 0)
    assert select_ledger(entries, last=1) == (entries[1:], 1)
    assert select_ledger(entries, last=5) == (entries, 0)
    assert select_ledger(entries, entry_id="L1") == (entries[:1], 1)
    assert select_ledger(entries, entry_id="L9") == ([], 2)
    assert select_ledger(entries, for_action="a2") == (entries[1:], 1)
    assert select_ledger(entries, for_action="a20") == ([], 2)   # whole-word match only
    assert select_ledger(entries, for_action="a2", last=1) == (entries[1:], 1)


def test_dangling_link_in_dict_and_table():
    from praxis.links import Link
    text = ROADMAP.replace("- source :: README release procedure\n",
                           "- source :: ledger L9; traces/gone.csv; ledger L1\n")
    rm = parse_roadmap(text, path="ROADMAP.org")
    links = {a.id: [] for a in rm.actions}
    links["a7"] = [Link("ledger", "L9", "source", False), Link("trace", "traces/gone.csv", "source", False),
                   Link("ledger", "L1", "source", True)]
    res = _results()
    viol = violations(rm, res, links)
    d = to_dict(rm, res, viol, "x.y.z", links)
    a7 = next(a for a in d["actions"] if a["id"] == "a7")
    assert a7["violations"] == ["dangling_link"]
    assert a7["links"][0] == {"kind": "ledger", "ref": "L9", "field": "source", "resolved": False}
    out = table_view(d)
    assert "a7: dangling_link (L9 traces/gone.csv)" in out
    assert d["summary"]["violations"] == 1


def test_to_dict_result_is_null_for_actions_without_a_result():
    from praxis.invariants import violations
    from praxis.model import CheckResult
    from praxis.parse import parse_roadmap
    from praxis.render import to_dict
    from tests.praxis_helpers import ROADMAP
    rm = parse_roadmap(ROADMAP, path="ROADMAP.org")
    results = {"a7": CheckResult("failed")}
    doc = to_dict(rm, results, violations(rm, results), "x.y.z")
    by = {a["id"]: a["result"] for a in doc["actions"]}
    assert by["a7"] == "failed" and by["a1"] is None


def test_to_dict_ledger_entries_carry_kind():
    from praxis.render import to_dict
    from praxis.parse import parse_roadmap
    from tests.praxis_helpers import ROADMAP
    rm = parse_roadmap(ROADMAP)
    d = to_dict(rm, None, {a.id: [] for a in rm.actions}, None)
    kinds = {e["id"]: e["kind"] for e in d["ledger"]}
    assert kinds == {"L1": "signer", "L2": "signer"}


def test_ledger_select_by_kind():
    from praxis.model import LedgerEntry, Stamp
    from praxis.render import select_ledger
    entries = [
        LedgerEntry("L1", Stamp("2026-10-01"), "Registered prior at init: x", 1),
        LedgerEntry("L2", Stamp("2026-10-01"), "Recontact: head moved.", 2),
        LedgerEntry("L3", Stamp("2026-10-01"), "a1 reverted to STRT: check failed. reason", 3),
        LedgerEntry("L4", Stamp("2026-10-01"), "Signer decided to add a2.", 4),
    ]
    kept, hidden = select_ledger(entries, kind="signer")
    assert [e.id for e in kept] == ["L1", "L4"] and hidden == 2
    kept, hidden = select_ledger(entries, kind="machine")
    assert [e.id for e in kept] == ["L2", "L3"] and hidden == 2
    kept, hidden = select_ledger(entries, kind="machine", last=1)
    assert [e.id for e in kept] == ["L3"] and hidden == 3


def test_table_view_pending_glyph():
    from praxis.render import GLYPHS, RESULT_COLORS, table_view, to_dict
    from praxis.model import CheckResult
    from praxis.parse import parse_roadmap
    from tests.praxis_helpers import ROADMAP
    assert GLYPHS["pending"] == "⏳" and "pending" in RESULT_COLORS
    rm = parse_roadmap(ROADMAP)
    results = {a.id: CheckResult("pending", 3) for a in rm.actions}
    d = to_dict(rm, results, {a.id: [] for a in rm.actions}, None)
    assert "a1   DONE    ⏳" in table_view(d)

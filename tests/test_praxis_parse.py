from __future__ import annotations
import pytest
from praxis.model import ParseError
from praxis.parse import parse_roadmap, parse_stamp
from tests.praxis_helpers import ROADMAP, line_of


def test_header_fields():
    rm = parse_roadmap(ROADMAP)
    assert rm.header.title == "orrery x.y.z — roadmap"
    assert rm.header.signer == "Dimitri Diomaiuta"
    assert rm.header.opened == "2026-09-03"
    assert rm.header.closed is None
    assert rm.header.check_timeout == 30
    assert not hasattr(rm.header, "setpoint")


def test_check_timeout_and_closed_headers():
    text = ROADMAP.replace("#+OPENED: 2026-09-03", "#+OPENED: 2026-09-03\n#+CLOSED: 2026-09-20\n#+CHECK_TIMEOUT: 5")
    rm = parse_roadmap(text)
    assert rm.header.check_timeout == 5
    assert rm.header.closed == "2026-09-20"


@pytest.mark.parametrize("key", ["TITLE", "SIGNER", "OPENED", "PRAXIS", "TODO"])
def test_missing_required_header_is_error(key):
    line = next(l for l in ROADMAP.splitlines() if l.startswith(f"#+{key}:"))
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace(line + "\n", ""))
    assert key in e.value.msg


def test_unknown_praxis_version_is_error():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("#+PRAXIS: 2", "#+PRAXIS: 4"))
    assert "PRAXIS" in e.value.msg and "4" in e.value.msg and "reads formats 2 and 3" in e.value.msg


def test_format_2_and_3_both_parse_and_report_their_version():
    assert parse_roadmap(ROADMAP).header.format == 2
    assert parse_roadmap(ROADMAP.replace("#+PRAXIS: 2", "#+PRAXIS: 3")).header.format == 3


def test_recontact_header_read_at_format_3():
    text = ROADMAP.replace("#+PRAXIS: 2", "#+PRAXIS: 3\n#+RECONTACT: traces/recontact.sh --quick")
    h = parse_roadmap(text).header
    assert h.recontact == "traces/recontact.sh --quick"
    assert parse_roadmap(ROADMAP).header.recontact is None


def test_recontact_header_refused_at_format_2_naming_the_line():
    text = ROADMAP.replace("#+TODO:", "#+RECONTACT: traces/recontact.sh\n#+TODO:")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "#+RECONTACT: needs #+PRAXIS: 3" in str(e.value) and e.value.line == 5


def test_wrong_todo_line_is_error():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("#+TODO: TODO STRT SIGNAL | DONE SKIP", "#+TODO: TODO | DONE"))
    assert "TODO STRT SIGNAL | DONE SKIP" in e.value.msg


def test_format1_setpoint_header_is_refused_with_line():
    text = ROADMAP.replace("#+OPENED: 2026-09-03", "#+OPENED: 2026-09-03\n#+SETPOINT: old style")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text, path="R.org")
    assert e.value.line == line_of(text, "#+SETPOINT:")
    assert "format 1 file" in e.value.msg and "convert it" in e.value.msg
    assert str(e.value).startswith(f"R.org:{e.value.line}:")


@pytest.mark.parametrize("old", ["* Status", "* Remains"])
def test_format1_sections_are_refused(old):
    text = ROADMAP.replace("* Ledger", old)
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "format 1 file" in e.value.msg and old in e.value.msg


def test_unknown_section_is_error():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("* Ledger", "* Later"))
    assert "Later" in e.value.msg


def test_missing_section_is_error():
    text = ROADMAP[:ROADMAP.index("* Ledger")]
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "Ledger" in e.value.msg


def test_sections_out_of_order_is_error():
    head = ROADMAP[:ROADMAP.index("* Setpoint")]
    setpoint = ROADMAP[ROADMAP.index("* Setpoint"):ROADMAP.index("* Actions")]
    actions = ROADMAP[ROADMAP.index("* Actions"):ROADMAP.index("* Ledger")]
    ledger = ROADMAP[ROADMAP.index("* Ledger"):]
    with pytest.raises(ParseError) as e:
        parse_roadmap(head + actions + setpoint + ledger)
    assert "order" in e.value.msg


def test_duplicate_section_is_error():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP + "\n* Ledger\n")
    assert "duplicate" in e.value.msg


def test_comment_lines_are_ignored():
    text = ROADMAP.replace("* Actions\n", "* Actions\n# one heading per action\n")
    assert len(parse_roadmap(text).actions) == 7


def test_header_keyword_after_ledger_section_is_error():
    text = ROADMAP + "#+CLOSED: 2026-09-30\n"
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "CLOSED" in e.value.msg
    assert e.value.line == line_of(text, "#+CLOSED: 2026-09-30")


def test_setpoint_header_after_setpoint_section_is_format1_error():
    text = ROADMAP.replace("* Setpoint\n", "* Setpoint\n#+SETPOINT: old\n")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "format 1 file" in e.value.msg
    assert e.value.line == line_of(text, "#+SETPOINT: old")


@pytest.mark.parametrize("inner,expected", [
    ("2026-09-08", ("2026-09-08", None, None, None)),
    ("2026-09-08 Mon", ("2026-09-08", "Mon", None, None)),
    ("2026-09-08 19:55", ("2026-09-08", None, "19:55", None)),
    ("2026-09-08 Mon 19:55 5d6e7f8a", ("2026-09-08", "Mon", "19:55", "5d6e7f8a")),
    ("2026-09-08 5d6e7f8a", ("2026-09-08", None, None, "5d6e7f8a")),
])
def test_parse_stamp_grammar(inner, expected):
    s = parse_stamp(inner, 1, "R.org")
    assert (s.date, s.weekday, s.time, s.session) == expected


@pytest.mark.parametrize("bad", ["8 Sep 2026", "2026-09-08 19:55 Mon", "2026-09-08 4e5f6a7b-ecd5", "2026-09-08 Monday"])
def test_parse_stamp_rejects_malformed(bad):
    with pytest.raises(ParseError) as e:
        parse_stamp(bad, 7, "R.org")
    assert e.value.line == 7 and "stamp" in e.value.msg


def test_clauses_parsed_with_met_by():
    rm = parse_roadmap(ROADMAP)
    assert [c.id for c in rm.clauses] == ["C1", "C2", "C3"]
    c1, c2, c3 = rm.clauses
    assert c1.text == "tag vx.y.z on main." and c1.met_by == ["a1", "a7"]
    assert c2.met_by == ["a4"]
    assert c3.text == "date format option settled with the reviewer" and c3.met_by == []
    assert c1.line == line_of(ROADMAP, "- C1 ::")
    assert rm.clauses_of("a1") == ["C1"] and rm.clauses_of("a6") == []


def test_clause_continuation_line_joins():
    text = ROADMAP.replace("- C3 :: date format option settled with the reviewer",
                           "- C3 :: date format option\n  settled with the reviewer. Met by: a5")
    c3 = parse_roadmap(text).clauses[2]
    assert c3.text == "date format option settled with the reviewer." and c3.met_by == ["a5"]


@pytest.mark.parametrize("bad", ["Met by: a1, a7", "Met by: a1 and a7", "Met by:", "met by: a1"])
def test_malformed_met_by_is_parse_error(bad):
    text = ROADMAP.replace("Met by: a1 a7", bad)
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "C1" in e.value.msg and "Met by" in e.value.msg
    assert e.value.line == line_of(text, "- C1 ::")


def test_clause_naming_unknown_action_is_error():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("Met by: a4", "Met by: a4 a99"))
    assert "a99" in e.value.msg and "C2" in e.value.msg


def test_duplicate_clause_id_is_error():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("- C3 ::", "- C1 ::"))
    assert "duplicate clause id C1" in e.value.msg


def test_empty_setpoint_is_error():
    text = ROADMAP[:ROADMAP.index("- C1 ::")] + ROADMAP[ROADMAP.index("* Actions"):]
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "Setpoint" in e.value.msg


def test_bad_setpoint_line_is_error():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("* Setpoint\n", "* Setpoint\nnot a clause\n"))
    assert "setpoint line" in e.value.msg.lower()


def test_actions_parsed_in_order_with_fields_and_lines():
    rm = parse_roadmap(ROADMAP)
    assert [a.id for a in rm.actions] == ["a1", "a2", "a3", "a4", "a5", "a6", "a7"]
    a1 = rm.action("a1")
    assert (a1.state, a1.title, a1.source, a1.evidence, a1.check) == (
        "DONE", "cut x.y.z from main", "README release procedure", "branch x.y.z", "true")
    assert (a1.done.date, a1.done.weekday, a1.done.time, a1.done.session) == ("2026-09-03", "Wed", "10:12", "0a1b2c3d")
    assert a1.line == line_of(ROADMAP, "** DONE a1")
    a3 = rm.action("a3")
    assert a3.evidence == "" and a3.done is None
    assert a3.check == "grep -q PASS traces/parity.log"
    assert rm.action("a2").check == ""


def test_pipe_in_check_is_literal_and_vert_is_not_an_escape():
    rm = parse_roadmap(ROADMAP)
    assert rm.action("a5").check == "echo a | grep -q a"
    text = ROADMAP.replace("echo a | grep -q a", "echo a \\vert grep -q a")
    assert parse_roadmap(text).action("a5").check == "echo a \\vert grep -q a"


def test_field_continuation_joins_with_space():
    text = ROADMAP.replace("- source :: parser branch ab12cd3", "- source :: parser branch\n  ab12cd3")
    assert parse_roadmap(text).action("a2").source == "parser branch ab12cd3"


def test_empty_field_value_allowed():
    text = ROADMAP.replace("- evidence :: staged diff", "- evidence ::")
    assert parse_roadmap(text).action("a2").evidence == ""


def test_heading_without_state_is_error():
    text = ROADMAP.replace("** TODO a3 parity gate", "** a3 parity gate")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert e.value.line == line_of(text, "** a3") and "STATE" in e.value.msg


def test_unknown_state_is_error():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("** SIGNAL a6", "** MAYBE a6"))
    assert "MAYBE" in e.value.msg


def test_bad_action_id_and_duplicate_id_are_errors():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("** TODO a7", "** TODO s7"))
    assert "a<digits>" in e.value.msg
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("** TODO a7", "** TODO a1"))
    assert "duplicate action id a1" in e.value.msg


def test_heading_without_title_is_error():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("** TODO a7 release per README", "** TODO a7"))
    assert "title" in e.value.msg.lower()


def test_unknown_field_key_is_error():
    text = ROADMAP.replace("- evidence :: staged diff", "- evidence :: staged diff\n- owner :: the reviewer")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "owner" in e.value.msg and e.value.line == line_of(text, "- owner ::")


def test_repeated_field_is_error():
    text = ROADMAP.replace("- evidence :: staged diff", "- evidence :: staged diff\n- source :: twice")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "repeated" in e.value.msg and "a2" in e.value.msg


def test_stray_text_under_action_is_error():
    text = ROADMAP.replace("- evidence :: staged diff", "- evidence :: staged diff\nsome prose here")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert e.value.line == line_of(text, "some prose here") and "a2" in e.value.msg


def test_level3_heading_under_action_is_error():
    text = ROADMAP.replace("- evidence :: staged diff", "- evidence :: staged diff\n*** sub")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "a2" in e.value.msg


def test_text_before_first_action_heading_is_error():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("* Actions\n", "* Actions\n- source :: orphan\n"))
    assert "before the first" in e.value.msg


def test_done_must_be_a_bracketed_stamp():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("- done :: [2026-09-03 Wed 10:12 0a1b2c3d]", "- done :: yesterday"))
    assert "done" in e.value.msg
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("- done :: [2026-09-03 Wed 10:12 0a1b2c3d]", "- done :: [2026-09-03 10:12 Wed]"))
    assert "stamp" in e.value.msg


def test_ledger_entries_with_stamps_and_continuation():
    rm = parse_roadmap(ROADMAP)
    assert len(rm.ledger) == 2
    first, second = rm.ledger
    assert (first.stamp.date, first.stamp.weekday, first.stamp.time, first.stamp.session) == ("2026-09-03", "Wed", None, None)
    assert first.text.endswith("Evidence: 1234567, 2b3c4d5.")
    assert (second.stamp.time, second.stamp.session) == ("16:40", "0a1b2c3d")
    assert second.text.startswith("a2 started:")
    assert (first.id, second.id) == ("L1", "L2")
    assert first.line == line_of(ROADMAP, "- L1 [2026-09-03 Wed] Parser-first")


def test_ledger_tags_have_no_meaning():
    text = ROADMAP + "- L3 [2026-09-04] OPEN: still a plain sentence.\n- L4 [2026-09-04] SUPERSEDES [2026-09-03]: also plain.\n"
    rm = parse_roadmap(text)
    assert rm.ledger[2].text == "OPEN: still a plain sentence."
    assert rm.ledger[3].text == "SUPERSEDES [2026-09-03]: also plain."
    assert not hasattr(rm.ledger[2], "open")


def test_indented_ledger_entry_is_a_new_entry_not_a_continuation():
    text = ROADMAP.replace("- L2 [2026-09-03 Wed 16:40 0a1b2c3d] a2 started", "  - L2 [2026-09-03 Wed 16:40 0a1b2c3d] a2 started")
    assert len(parse_roadmap(text).ledger) == 2


def test_bad_ledger_line_and_bad_ledger_stamp_are_errors():
    with pytest.raises(ParseError) as e:
        parse_roadmap(ROADMAP.replace("* Ledger\n", "* Ledger\nnot an entry\n"))
    assert "ledger" in e.value.msg.lower()
    text = ROADMAP.replace("- L1 [2026-09-03 Wed] Parser-first", "- L1 [3 Sep] Parser-first")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert e.value.line == line_of(text, "- L1 [3 Sep]") and "stamp" in e.value.msg


def test_ledger_entry_without_id_is_error():
    text = ROADMAP.replace("- L1 [2026-09-03 Wed] Parser-first", "- [2026-09-03 Wed] Parser-first")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert e.value.line == line_of(text, "- [2026-09-03 Wed] Parser-first") and "L<n>" in e.value.msg


@pytest.mark.parametrize("bad_id", ["L2", "L1"])
def test_ledger_ids_must_strictly_increase(bad_id):
    text = ROADMAP.replace("- L2 [2026-09-03 Wed 16:40 0a1b2c3d] a2 started", f"- L3 [2026-09-03 Wed 16:40 0a1b2c3d] a2 started")
    text = text + f"- {bad_id} [2026-09-04] out of order.\n"
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert e.value.line == line_of(text, f"- {bad_id} [2026-09-04] out of order") and "append-only" in e.value.msg


def test_ledger_ids_may_skip_numbers_but_not_go_back():
    text = ROADMAP + "- L9 [2026-09-04] later entry.\n"
    assert [e.id for e in parse_roadmap(text).ledger] == ["L1", "L2", "L9"]


def test_ledger_id_lowercase_is_error():
    text = ROADMAP.replace("- L1 [2026-09-03 Wed] Parser-first", "- l1 [2026-09-03 Wed] Parser-first")
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "L<n>" in e.value.msg


@pytest.mark.parametrize("bad", ["2026-02-30", "2026-13-05", "2026-10-07 Wed 25:99"])
def test_stamp_with_impossible_date_or_time_is_a_parse_error_naming_the_line(bad):
    text = ROADMAP + f"- L3 [{bad}] hand-written.\n"
    with pytest.raises(ParseError) as e:
        parse_roadmap(text)
    assert "bad stamp" in e.value.msg and e.value.line == len(text.splitlines())

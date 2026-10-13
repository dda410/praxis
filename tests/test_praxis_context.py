"""praxis context: one id's neighbourhood, layered clauses / actions / ledger / grounds."""
from __future__ import annotations
from pathlib import Path
import pytest
from praxis.checks import run_all
from praxis.context import build_context
from praxis.invariants import violations
from praxis.links import all_links
from praxis.parse import parse_roadmap
from praxis.render import to_dict
from tests.praxis_helpers import ROADMAP, make_repo

# a7 cites L2 and the missing L9, names a1-a3 and C2, points at a missing trace;
# L3 names a7, C1 and L1; a4 names C2 in its source.
TEXT = ROADMAP.replace(
    "- source :: README release procedure\n- check :: false\n",
    "- source :: ledger L2; a1-a3 first; setpoint C2; ledger L9; traces/gone.csv\n"
    "- evidence :: verbal 2026-09-03; a99\n- check :: false\n",
).rstrip("\n") + "\n- L3 [2026-09-04 Thu] a7 blocked; C1 at risk; see L1.\n"


def _doc(tmp_path: Path, checks: bool = False) -> dict:
    make_repo(tmp_path, TEXT)
    rm = parse_roadmap(TEXT, path="ROADMAP.org")
    results = run_all(rm, tmp_path, 5) if checks else None
    links = all_links(rm, tmp_path)
    return to_dict(rm, results, violations(rm, results, links), "x.y.z", links)


def _rows(lines):
    return [(l.id, l.status, l.relations) for l in lines]


def test_action_focus_layers_clauses_actions_ledger_grounds(tmp_path: Path):
    ctx = build_context(_doc(tmp_path), "a7", tmp_path)
    assert ctx.focuses == ["a7"]
    assert _rows(ctx.clauses) == [("C1", "ok", ["met by a7, with a1"]), ("C2", "ok", ["named in a7 source"])]
    assert _rows(ctx.actions) == [("a7", "focus", []), ("a1", "ok", ["named in a7 source"]),
                                  ("a2", "ok", ["named in a7 source"]), ("a3", "ok", ["named in a7 source"]),
                                  ("a99", "missing", ["named in a7 evidence"])]
    assert _rows(ctx.ledger) == [("L2", "ok", ["cited by a7"]), ("L3", "ok", ["names a7"]),
                                 ("L9", "missing", ["cited by a7"])]
    assert [(g.id, g.kind, g.status) for g in ctx.grounds] == \
        [("traces/gone.csv", "trace", "missing"), ("text:a7", "text", "unresolved")]
    assert "verbal 2026-09-03" in ctx.grounds[1].body and "a99" not in ctx.grounds[1].body


def test_clause_focus_lists_meeting_and_naming_actions(tmp_path: Path):
    ctx = build_context(_doc(tmp_path), "C2", tmp_path)
    assert _rows(ctx.clauses) == [("C2", "focus", [])]
    assert _rows(ctx.actions) == [("a4", "ok", ["meets C2", "names C2"]), ("a7", "ok", ["names C2"])]
    assert ctx.ledger == [] and ctx.grounds == []


def test_clause_focus_sees_ledger_entries_naming_it(tmp_path: Path):
    ctx = build_context(_doc(tmp_path), "C1", tmp_path)
    assert _rows(ctx.actions) == [("a1", "ok", ["meets C1"]), ("a7", "ok", ["meets C1"])]
    assert _rows(ctx.ledger) == [("L3", "ok", ["names C1"])]


def test_ledger_focus_actions_ledger_and_commit_grounds(tmp_path: Path):
    ctx = build_context(_doc(tmp_path), "L2", tmp_path)
    assert _rows(ctx.actions) == [("a2", "ok", ["named by L2"]), ("a7", "ok", ["cites L2"])]
    assert _rows(ctx.ledger) == [("L2", "focus", [])]
    assert [(g.id, g.kind, g.status) for g in ctx.grounds] == [("ab12cd3", "commit", "unresolved")]


def test_ledger_focus_names_clauses_and_other_entries(tmp_path: Path):
    ctx = build_context(_doc(tmp_path), "L3", tmp_path)
    assert _rows(ctx.clauses) == [("C1", "ok", ["named by L3"])]
    assert _rows(ctx.actions) == [("a7", "ok", ["named by L3"])]
    assert _rows(ctx.ledger) == [("L3", "focus", []), ("L1", "ok", ["named by L3"])]


def test_focus_line_carries_the_document_entry(tmp_path: Path):
    ctx = build_context(_doc(tmp_path, checks=True), "a7", tmp_path)
    a7 = ctx.actions[0]
    assert a7.data["state"] == "TODO" and a7.data["result"] == "failed"
    assert "dangling_link" in a7.data["violations"]


@pytest.mark.parametrize("bad", ["a42", "C9", "L77", "x1", "7"])
def test_unknown_focus_raises(tmp_path: Path, bad: str):
    with pytest.raises(KeyError):
        build_context(_doc(tmp_path), bad, tmp_path)


def test_several_ids_merge_into_one_union_with_shared_lines_once(tmp_path: Path):
    ctx = build_context(_doc(tmp_path), ["a7", "a1"], tmp_path)
    assert ctx.focuses == ["a7", "a1"]
    # C1 is met by both foci: one line, one folded word; C2 only by a7's mention
    assert _rows(ctx.clauses) == [("C1", "ok", ["met by a1, a7"]), ("C2", "ok", ["named in a7 source"])]
    # both foci in the actions band, file order; each focus line carries what the other gives it
    assert _rows(ctx.actions)[:2] == [("a1", "focus", ["named in a7 source"]), ("a7", "focus", ["names a1"])]
    assert [l.id for l in ctx.actions] == ["a1", "a7", "a2", "a3", "a99"]
    assert _rows(ctx.ledger) == [("L2", "ok", ["cited by a7"]), ("L3", "ok", ["names a7"]),
                                 ("L9", "missing", ["cited by a7"])]
    assert [g.id for g in ctx.grounds] == ["traces/gone.csv", "text:a7", "text:a1"]


def test_mixed_kinds_merge_and_a_focus_ledger_entry_is_still_cited(tmp_path: Path):
    ctx = build_context(_doc(tmp_path), ["C1", "L3", "a7"], tmp_path)
    assert _rows(ctx.clauses) == [("C1", "focus", ["met by a7, with a1", "named by L3"]),
                                  ("C2", "ok", ["named in a7 source"])]
    assert ("L3", "focus", ["names C1", "names a7"]) in _rows(ctx.ledger)
    assert ("a1", "ok", ["meets C1", "named in a7 source"]) in _rows(ctx.actions)
    assert ("a7", "focus", ["meets C1", "named by L3"]) in _rows(ctx.actions)


# ---- the terminal view ----
from praxis.context import context_view          # noqa: E402
from praxis.render import strip_ansi             # noqa: E402


def _view(tmp_path: Path, focus: str, **kw) -> str:
    return context_view(build_context(_doc(tmp_path, checks=True), focus, tmp_path), **kw)


def test_view_bands_are_separated_by_rules_and_empty_bands_are_dropped(tmp_path: Path):
    out = _view(tmp_path, "a7", width=100)
    lines = out.splitlines()
    rules = [i for i, l in enumerate(lines) if l == "═" * 100]
    assert lines[0] == lines[-1] == "═" * 100
    assert len(rules) == 5                      # top, clauses|actions, actions|ledger, ledger|grounds, bottom
    out_c2 = _view(tmp_path, "C2", width=100)
    assert out_c2.count("═" * 100) == 3         # clauses, actions: two bands, three rules


def test_view_focus_action_head_and_fields(tmp_path: Path):
    out = _view(tmp_path, "a7", width=100)
    assert "a7   TODO    ❌  release per README" in out
    assert "     source    ledger L2; a1-a3 first; setpoint C2; ledger L9; traces/gone.csv" in out
    assert "     evidence  verbal 2026-09-03; a99" in out
    assert "     check     false" in out
    assert "     done      (none)" in out
    assert "     reaches   a7 → C1" in out
    assert "     flags     dangling_link" in out


def test_view_focus_action_with_no_uplink_says_so(tmp_path: Path):
    out = _view(tmp_path, "a5", width=100)          # nothing under a clause names a5 in its source
    assert "     reaches   no clause" in out
    assert "     reaches   a2 → a7 → C1" in _view(tmp_path, "a2", width=100)


def test_view_relation_words_are_right_aligned_on_the_first_line(tmp_path: Path):
    out = _view(tmp_path, "a7", width=100)
    c1 = next(l for l in out.splitlines() if l.startswith("C1 "))
    assert c1.endswith("met by a7, with a1") and len(c1) == 100
    l3 = next(l for l in out.splitlines() if l.startswith("L3 "))
    assert l3.endswith("names a7") and "[2026-09-04]" in l3   # the JSON stamp carries no weekday


def test_view_missing_and_grounds(tmp_path: Path):
    out = _view(tmp_path, "a7", width=100)
    assert "L9   MISSING" in out and "a99  MISSING" in out
    trace = next(l for l in out.splitlines() if l.startswith("traces/gone.csv"))
    assert trace.endswith("MISSING")
    assert '"first; setpoint; verbal 2026-09-03"' in out and "text the CLI cannot resolve" in out
    out_l2 = _view(tmp_path, "L2", width=100)
    assert "ab12cd3" in out_l2 and "not in this repo" in out_l2


def test_view_wraps_to_width_and_indents_continuations(tmp_path: Path):
    out = _view(tmp_path, "L2", width=60)
    lines = out.splitlines()
    assert all(len(l) <= 60 for l in lines)
    l2 = [l for l in lines if l.startswith("L2 ") or l.startswith("     ")]
    assert len(l2) >= 2 and "Regulates" in out


def test_view_color_paints_missing_red_and_focus_bold(tmp_path: Path):
    plain = _view(tmp_path, "a7", width=100)
    colored = _view(tmp_path, "a7", width=100, color=True)
    assert strip_ansi(colored) == plain
    assert "\x1b[31mMISSING\x1b[0m" in colored and "\x1b[1ma7\x1b[0m" in colored
    assert "\x1b" not in plain


def test_view_of_two_ids_is_one_block_with_two_focus_heads(tmp_path: Path):
    out = context_view(build_context(_doc(tmp_path), ["a7", "a1"], tmp_path), width=100)
    assert out.count("═" * 100) == 5
    assert out.count("     source    ") == 2 and out.count("C1   ·") == 1
    c1 = next(l for l in out.splitlines() if l.startswith("C1 "))
    assert c1.endswith("met by a1, a7")


def test_view_phantom_is_said_on_the_focus_head(tmp_path: Path):
    text = TEXT.replace("- source :: ledger L2; a1-a3 first; setpoint C2; ledger L9; traces/gone.csv\n", "- source ::\n")
    make_repo(tmp_path, text)
    rm = parse_roadmap(text, path="ROADMAP.org")
    links = all_links(rm, tmp_path)
    doc = to_dict(rm, None, violations(rm, None, links), "x.y.z", links)
    out = context_view(build_context(doc, "a7", tmp_path), width=100)
    assert "a7   TODO    ·  release per README" in out and "no down-link" in out


def test_view_field_continuations_align_under_the_value(tmp_path: Path):
    out = _view(tmp_path, "a7", width=60)
    lines = out.splitlines()
    i = next(i for i, l in enumerate(lines) if l.startswith("     source    "))
    assert lines[i + 1].startswith(" " * 15) and not lines[i + 1].startswith(" " * 16)


def test_view_groups_resolved_commits_after_traces(tmp_path: Path):
    import subprocess
    make_repo(tmp_path, TEXT)
    shas = []
    while len(shas) < 2:   # a short sha of digits only is not a commit to COMMIT_RE; draw again
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty",
                        "-m", str(len(shas))], cwd=tmp_path, check=True)
        sha = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=tmp_path,
                             capture_output=True, text=True).stdout.strip()
        if any(c.isalpha() for c in sha):
            shas.append(sha)
    (tmp_path / "traces" / "ok.log").write_text("")
    text = TEXT.replace("- evidence :: verbal 2026-09-03; a99\n",
                        f"- evidence :: {shas[0]} then traces/ok.log then {shas[1]}; other repo f00dfa1\n")
    (tmp_path / "ROADMAP.org").write_text(text)
    rm = parse_roadmap(text, path="ROADMAP.org")
    links = all_links(rm, tmp_path)
    doc = to_dict(rm, None, violations(rm, None, links), "x.y.z", links)
    out = context_view(build_context(doc, "a7", tmp_path), width=100)
    grounds = out.split("═" * 100)[4].strip().splitlines()
    assert grounds[0].startswith("traces/gone.csv") and grounds[0].endswith("MISSING")
    assert grounds[1].startswith("traces/ok.log") and grounds[1].endswith("exists")
    assert grounds[2].startswith(f"{shas[0]}  {shas[1]}") and grounds[2].endswith("commits in this repo")
    assert grounds[3].startswith("f00dfa1") and grounds[3].endswith("not in this repo")
    assert grounds[4].startswith('"') and grounds[4].endswith("text the CLI cannot resolve")


def test_same_commit_cited_short_and_long_is_one_ground(tmp_path: Path):
    import subprocess
    make_repo(tmp_path, TEXT)
    full = "0000000"
    while not any(c.isalpha() for c in full[:7]):   # digits-only short form is no commit to COMMIT_RE
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty",
                        "-m", "x"], cwd=tmp_path, check=True)
        full = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()
    text = TEXT.replace("- evidence :: verbal 2026-09-03; a99\n", f"- evidence :: {full[:7]} then {full}\n")
    rm = parse_roadmap(text, path="ROADMAP.org")
    links = all_links(rm, tmp_path)
    doc = to_dict(rm, None, violations(rm, None, links), "x.y.z", links)
    commits = [g for g in build_context(doc, "a7", tmp_path).grounds if g.kind == "commit"]
    assert [g.id for g in commits] == [full[:7]]

from __future__ import annotations
from praxis.checkpoint import build_checkpoint, checkpoint_view
from praxis.model import CheckResult
from praxis.parse import parse_roadmap
from praxis.render import to_dict
from tests.praxis_helpers import ROADMAP

LEDGER = """\
- L3 [2026-10-02 Thu 10:00 0a1b2c3d] Signer decided a3 is stepwise: parse; configure; overlay.
- L4 [2026-10-02 Thu 10:05 0a1b2c3d] a3 started: fit. Stepwise: parse; configure; overlay. Prior: x. Regulates against: y. Tacit: none.
- L5 [2026-10-02 Thu 10:30 0a1b2c3d] Recontact: head moved; a3 unchanged.
- L6 [2026-10-02 Thu 11:00 0a1b2c3d] Signer's decision: C1 reworded. Supersedes the entry of 2026-09-03 on C1 (L1).
- L7 [2026-10-02 Thu 11:10 0a1b2c3d] A rule for the whole delivery: never push.
"""


def _doc():
    rm = parse_roadmap(ROADMAP + LEDGER)
    results = {a.id: CheckResult("passed", 0) for a in rm.actions}
    return to_dict(rm, results, {a.id: [] for a in rm.actions}, "x.y.z")


def test_blocks_in_file_order_clauses_then_actions_then_unmentioned():
    ids = [b.id for b in build_checkpoint(_doc())]
    assert ids[:3] == ["C1", "C2", "C3"] and ids[3:10] == ["a1", "a2", "a3", "a4", "a5", "a6", "a7"]
    assert ids[-1] == "unmentioned"


def test_a3_block_latest_first_signer_before_machine_with_markers():
    b = next(b for b in build_checkpoint(_doc()) if b.id == "a3")
    assert [e["id"] for e in b.entries] == ["L4", "L3", "L5"]
    assert "stepwise" in b.entries[0]["markers"] and "stepwise" in b.entries[1]["markers"]
    assert b.entries[2]["markers"] == []


def test_c1_block_has_supersedes_marker():
    b = next(b for b in build_checkpoint(_doc()) if b.id == "C1")
    assert [e["id"] for e in b.entries] == ["L6"]   # L1 cites only commits, so it names no clause
    assert "supersedes" in b.entries[0]["markers"]


def test_unmentioned_block_holds_entries_naming_nothing_latest_first():
    b = build_checkpoint(_doc())[-1]
    assert [e["id"] for e in b.entries] == ["L7", "L1"]


def test_head_shows_state_and_result():
    blocks = build_checkpoint(_doc())
    assert next(b.head for b in blocks if b.id == "a1").startswith("a1 DONE ✅")
    assert next(b.head for b in blocks if b.id == "C1").startswith("C1 ")


def test_view_prints_markers_and_folds_entries():
    out = checkpoint_view(build_checkpoint(_doc()))
    assert "⟂ supersedes" in out and "⟂ stepwise" in out and "L7" in out
    assert "\n  " not in out.split("L7")[1].split("\n")[0]   # one line per entry

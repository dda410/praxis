from praxis.phrases import Phrase, entry_kind, parse_phrase


def test_started_single_id_with_stepwise_and_prior():
    p = parse_phrase("a3 started: fit the curve. Stepwise: parse the data; choose the scale; overlay. Prior: defaults miss. Regulates against: x. Tacit: none.")
    assert p.kind == "started" and p.ids == ("a3",)
    assert p.stepwise == ("parse the data", "choose the scale", "overlay")
    assert p.result is None and p.under is None


def test_started_without_stepwise():
    p = parse_phrase("a9 started: bump pyproject. Prior: green. Regulates against: y. Tacit: none.")
    assert p.kind == "started" and p.stepwise is None


def test_started_under_names_entry():
    p = parse_phrase("a1 started under L6: bump the runtime. Prior: lock resolves. Regulates against: z. Tacit: L6.")
    assert p.kind == "started_under" and p.ids == ("a1",) and p.under == "L6"


def test_gate_result_several_ids_and_result():
    p = parse_phrase("a1 a2 a10 a5 gate result: failed. Merges committed locally; nothing pushed.")
    assert p.kind == "gate" and p.ids == ("a1", "a2", "a10", "a5") and p.result == "failed"
    assert p.seen_failing is False


def test_gate_result_seen_failing():
    p = parse_phrase("a8 gate result: passed. Suite passed. Check seen failing on: the pre-change source.")
    assert p.kind == "gate" and p.result == "passed" and p.seen_failing is True


def test_revert_several_ids_pending():
    p = parse_phrase("a1 a2 a5 a6 a7 a10 reverted to STRT: check pending, CI run still going.")
    assert p.kind == "revert" and len(p.ids) == 6 and p.result == "pending"


def test_revert_old_single_form_still_parses():
    p = parse_phrase("a3 reverted to STRT: check failed.")
    assert p.kind == "revert" and p.ids == ("a3",) and p.result == "failed"


def test_recontact_plain_and_for():
    assert parse_phrase("Recontact: origin/x.y.z moved.").kind == "recontact"
    p = parse_phrase("Recontact for a16: CI run on x.y.z.")
    assert p.kind == "recontact" and p.ids == ("a16",)


def test_chain_stop_and_auth():
    p = parse_phrase("Chain stopped under L6 at a6: check failed after 1 of 5 gate runs.")
    assert p.kind == "chain_stop" and p.under == "L6" and p.ids == ("a6",)
    q = parse_phrase("Chained act authorized: a1 a2 a4. a1: intent; prior: x. Cap: 12 turns.")
    assert q.kind == "chain_auth" and q.ids == ("a1", "a2", "a4")


def test_correction_orient_inside_prior_case_closed():
    assert parse_phrase("Correction to L5: the hash reads abc1234.").kind == "correction"
    assert parse_phrase("Orient inside act a14: a5 set DONE.").kind == "orient_inside"
    assert parse_phrase("Registered prior at init: upgrade the runtime.").kind == "prior"
    assert parse_phrase("Case against the prior given: no comparison test. Signer: revised.").kind == "case"
    assert parse_phrase("Closed: setpoint met. Evidence: a1.").kind == "closed"


def test_decide_entry_is_other():
    p = parse_phrase("Signer's decision in these words: \"keep the current format\". Supersedes L5.")
    assert p.kind == "other" and p.ids == ()


def test_entry_kind_partition():
    machine = ["Recontact: x", "Recontact for a2: x", "a1 a2 reverted to STRT: check failed. y",
               "a4 gate result: passed. z", "Chain stopped under L3 at a2: cap.", "Correction to L5: x",
               "Orient inside act a1: y"]
    signer = ["Registered prior at init: x", "Case against the prior given: x. Signer: kept.",
              "a1 started: x. Prior: y. Regulates against: z. Tacit: none.",
              "a1 started under L2: x. Prior: y.", "Chained act authorized: a1 a2",
              "Closed: setpoint met.", "Signer decided to add C7.", "Decisione del signer: rinviare."]
    assert all(entry_kind(t) == "machine" for t in machine)
    assert all(entry_kind(t) == "signer" for t in signer)


def test_malformed_started_with_several_ids_is_signer_and_does_not_crash():
    p = parse_phrase("a1 a2 started: two at once. Prior: none.")
    assert p.kind == "started" and p.ids == ("a1", "a2")
    assert entry_kind("a1 a2 started: two at once.") == "signer"


def test_stepwise_separator_is_semicolon_and_trailing_period_dropped():
    p = parse_phrase("a4 started: merge. Stepwise: rename; other changes; new modules; commit. Prior: smooth.")
    assert p.stepwise == ("rename", "other changes", "new modules", "commit")

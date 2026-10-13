"""The fixed phrases the skill writes into the ledger, as a grammar the CLI can read.

docs/praxis-spec.md, section 2. The content after a phrase is prose in the project's language;
only the phrase, the ids it names, the check result it carries and the `Stepwise:` /
`Check seen failing on:` markers are read here. An entry's kind (signer or machine) is
decided by the phrase alone, never by the content.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

RESULT_WORDS = "passed|failed|absent|unclosable|timeout|pending"
_IDS = r"(?P<ids>a\d+(?: a\d+)*)"
_STARTED_RE = re.compile(rf"^{_IDS} started(?: under (?P<under>L\d+))?:")
_GATE_RE = re.compile(rf"^{_IDS} gate result: (?P<result>{RESULT_WORDS})\b")
_REVERT_RE = re.compile(rf"^{_IDS} reverted to STRT: check (?P<result>{RESULT_WORDS})\b")
_RECONTACT_RE = re.compile(rf"^Recontact(?: for {_IDS})?:")
_CHAIN_STOP_RE = re.compile(r"^Chain stopped under (?P<under>L\d+) at (?P<ids>a\d+):")
_CHAIN_AUTH_RE = re.compile(rf"^Chained act authorized: {_IDS}")
_CORRECTION_RE = re.compile(r"^Correction to L\d+:")
_ORIENT_INSIDE_RE = re.compile(rf"^Orient inside act(?: {_IDS})?:")
_PRIOR_RE = re.compile(r"^Registered prior at init:")
_CASE_RE = re.compile(r"^Case against the prior given:")
_CLOSED_RE = re.compile(r"^Closed: setpoint met\.")
_STEPWISE_RE = re.compile(r"\bStepwise: (?P<steps>.*?)\.?\s+Prior:")
_SEEN_FAILING_RE = re.compile(r"\bCheck seen failing on:")

MACHINE_KINDS = frozenset({"recontact", "revert", "gate", "chain_stop", "correction", "orient_inside"})


@dataclass(frozen=True)
class Phrase:
    kind: str
    ids: tuple[str, ...] = ()
    result: str | None = None
    seen_failing: bool = False
    stepwise: tuple[str, ...] | None = None
    under: str | None = None


def _ids(m: re.Match) -> tuple[str, ...]:
    raw = m.groupdict().get("ids")
    return tuple(raw.split()) if raw else ()


def parse_phrase(text: str) -> Phrase:
    t = text.strip()
    if m := _STARTED_RE.match(t):
        steps = None
        if sm := _STEPWISE_RE.search(t):
            steps = tuple(s.strip().rstrip(".") for s in sm.group("steps").split(";") if s.strip())
        kind = "started_under" if m.group("under") else "started"
        return Phrase(kind, _ids(m), stepwise=steps, under=m.group("under"))
    if m := _GATE_RE.match(t):
        return Phrase("gate", _ids(m), m.group("result"), bool(_SEEN_FAILING_RE.search(t)))
    if m := _REVERT_RE.match(t):
        return Phrase("revert", _ids(m), m.group("result"))
    if m := _RECONTACT_RE.match(t):
        return Phrase("recontact", _ids(m))
    if m := _CHAIN_STOP_RE.match(t):
        return Phrase("chain_stop", _ids(m), under=m.group("under"))
    if m := _CHAIN_AUTH_RE.match(t):
        return Phrase("chain_auth", _ids(m))
    if _CORRECTION_RE.match(t):
        return Phrase("correction")
    if m := _ORIENT_INSIDE_RE.match(t):
        return Phrase("orient_inside", _ids(m))
    if _PRIOR_RE.match(t):
        return Phrase("prior")
    if _CASE_RE.match(t):
        return Phrase("case")
    if _CLOSED_RE.match(t):
        return Phrase("closed")
    return Phrase("other")


def entry_kind(text: str) -> str:
    """`machine` for the phrases orient, act's gate and a chain write about what they saw;
    `signer` for everything else, decide entries included (they have no fixed prefix)."""
    return "machine" if parse_phrase(text).kind in MACHINE_KINDS else "signer"

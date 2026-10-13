"""Spec invariants, reported per action so the skill can quote them; clause state; flags."""
from __future__ import annotations
import re
from collections import deque
from .links import Link, mentions
from .phrases import parse_phrase
from .model import CheckResult, Clause, Roadmap

DONE_WITHOUT_PASSING_CHECK = "done_without_passing_check"
DONE_WITHOUT_STAMP = "done_without_stamp"
NO_SOURCE = "no_source"
SKIP_WITHOUT_LEDGER = "skip_without_ledger"
PHANTOM = "phantom"
DANGLING_LINK = "dangling_link"


def violations(roadmap: Roadmap, results: dict[str, CheckResult] | None,
               links: dict[str, list[Link]] | None = None) -> dict[str, list[str]]:
    """Per-action violation codes. `links` (from links.all_links) adds dangling_link when a
    `ledger L<n>` or `traces/` down-link resolves to nothing. An action absent from `results`
    (checks run for a subset) gets no verdict on its check either way."""
    ledger_text = "\n".join(e.text for e in roadmap.ledger)
    out: dict[str, list[str]] = {}
    for a in roadmap.actions:
        codes: list[str] = []
        if a.state == "DONE":
            if not a.check.strip():
                codes.append(DONE_WITHOUT_PASSING_CHECK)
            elif results is not None and a.id in results and results[a.id].result != "passed":
                codes.append(DONE_WITHOUT_PASSING_CHECK)
            if a.done is None:
                codes.append(DONE_WITHOUT_STAMP)
        if a.state in ("DONE", "STRT") and not a.source.strip():
            codes.append(NO_SOURCE)
        if a.state == "SKIP" and not re.search(rf"\b{re.escape(a.id)}\b", ledger_text):
            codes.append(SKIP_WITHOUT_LEDGER)
        if a.state != "SIGNAL" and not a.source.strip():
            codes.append(PHANTOM)
        if links is not None and any(l.dangling for l in links.get(a.id, [])):
            codes.append(DANGLING_LINK)
        out[a.id] = codes
    return out


def clause_met(roadmap: Roadmap, clause: Clause) -> bool:
    return bool(clause.met_by) and all(roadmap.action(i).state == "DONE" for i in clause.met_by)


def fed_by(roadmap: Roadmap) -> dict[str, list[str]]:
    """Per action, the actions its `source` names: what it rests on. A mention in `source` is a
    down-link of this action and so an up-link of the named one (manifest lines 624-627). Only
    `source` counts; `evidence`, ledger text and clause prose are narrative, not structure."""
    ids = {a.id for a in roadmap.actions}
    return {a.id: [m for m in mentions(a.source) if m in ids and m != a.id] for a in roadmap.actions}


def uplinks(roadmap: Roadmap) -> dict[str, list[str]]:
    """Per action, the shortest path to a clause: `[a1, a4, a5, C1]` reads a1 fed a4, a4 fed a5,
    a5 meets C1 (`Met by:`). Empty when no path exists. Derived on every call, never written."""
    rests_on = fed_by(roadmap)
    feeds: dict[str, list[str]] = {a.id: [] for a in roadmap.actions}
    for aid, deps in rests_on.items():
        for d in deps:
            feeds[d].append(aid)
    out: dict[str, list[str]] = {}
    for a in roadmap.actions:
        parent: dict[str, str | None] = {a.id: None}
        queue, path = deque([a.id]), []
        while queue:
            x = queue.popleft()
            clauses = roadmap.clauses_of(x)
            if clauses:
                path = [clauses[0]]
                while x is not None:
                    path.insert(0, x)
                    x = parent[x]
                break
            for y in feeds[x]:
                if y not in parent:
                    parent[y] = x
                    queue.append(y)
        out[a.id] = path
    return out


def seen_failing(roadmap: Roadmap) -> set[str]:
    """Actions some ledger entry has seen fail: a gate result or revert with a result other than
    passed, or a gate result carrying `Check seen failing on:` (docs/praxis-spec.md, section 1, Flags)."""
    out: set[str] = set()
    for e in roadmap.ledger:
        p = parse_phrase(e.text)
        if p.kind == "revert" or (p.kind == "gate" and (p.result != "passed" or p.seen_failing)):
            out.update(p.ids)
    return out


def flags(roadmap: Roadmap, results: dict[str, CheckResult] | None = None,
          recontact: dict | None = None, links: dict[str, list[Link]] | None = None,
          ledger_links: dict[str, list[Link]] | None = None, work: list[str] | None = None) -> list[str]:
    """Reported, not violations. Clauses first, then actions in file order: no up-link (TODO, STRT,
    DONE only; a SIGNAL has formed no intent yet, a SKIP is retired), a DONE action resting on an
    action that is not DONE, an unclosable check (when results are given), a stamp with no session."""
    out = [f"{c.id}: no Met by" for c in roadmap.clauses if not c.met_by]
    up, rests_on, seen = uplinks(roadmap), fed_by(roadmap), seen_failing(roadmap)
    for a in roadmap.actions:
        if a.state in ("TODO", "STRT", "DONE") and not up[a.id]:
            out.append(f"{a.id}: no up-link")
        if a.state == "DONE":
            out += [f"{a.id}: done rests on {d} {roadmap.action(d).state}"
                    for d in rests_on[a.id] if roadmap.action(d).state != "DONE"]
        if a.state == "DONE" and a.id not in seen:
            out.append(f"{a.id}: check never seen failing")
        if results is not None and a.id in results and results[a.id].result == "unclosable":
            out.append(f"{a.id}: unclosable check ({a.check})")
        if a.done is not None and a.done.session is None:
            out.append(f"{a.id}: done stamp has no session")
    places: dict[str, list[str]] = {}
    for a in roadmap.actions:
        for l in (links or {}).get(a.id, []):
            if l.kind == "commit" and l.resolved is False:
                places.setdefault(l.ref, []).append(f"{a.id} {l.field}")
    for e in roadmap.ledger:
        for l in (ledger_links or {}).get(e.id, []):
            if l.kind == "commit" and l.resolved is False:
                places.setdefault(l.ref, []).append(e.id)
    if places:
        out.append("commits not in this repo: " + ", ".join(f"{sha} ({', '.join(where)})" for sha, where in places.items()))
    if work and roadmap.ledger:
        last = roadmap.ledger[-1]
        out.append(f"work since {last.id}: {len(work)} files changed after its stamp ({', '.join(work[:3])})")
    if recontact is not None and recontact["exit"] != 0:
        out += [f"recontact: {line}" for line in recontact["lines"]] or [f"recontact: exit {recontact['exit']}"]
    return out


def summary(roadmap: Roadmap, viol: dict[str, list[str]]) -> dict:
    states = [a.state for a in roadmap.actions]
    return {
        "done": states.count("DONE"),
        "open": states.count("TODO") + states.count("STRT"),
        "signal": states.count("SIGNAL"),
        "clauses": len(roadmap.clauses),
        "clauses_met": sum(1 for c in roadmap.clauses if clause_met(roadmap, c)),
        "violations": sum(len(c) for c in viol.values()),
        "phantoms": sum(1 for c in viol.values() if PHANTOM in c),
    }

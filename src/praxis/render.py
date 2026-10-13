"""Roadmap + results -> JSON document (spec schema, format 2) and a human table view."""
from __future__ import annotations
import re
from .invariants import clause_met, flags, summary, uplinks
from .links import Link
from .model import CheckResult, LedgerEntry, Roadmap, Stamp
from .phrases import entry_kind

GLYPHS = {"passed": "✅", "failed": "❌", "absent": "∅", "unclosable": "⛔", "timeout": "⏱", "pending": "⏳", None: "·"}

# ANSI SGR codes for the colored table view (stdlib only; off unless asked).
RESET, BOLD, DIM = "\x1b[0m", "\x1b[1m", "\x1b[2m"
RED, GREEN, YELLOW, MAGENTA = "\x1b[31m", "\x1b[32m", "\x1b[33m", "\x1b[35m"
STATE_COLORS = {"DONE": GREEN, "STRT": YELLOW, "SIGNAL": MAGENTA, "SKIP": DIM}
RESULT_COLORS = {"passed": GREEN, "failed": RED, "unclosable": RED, "timeout": YELLOW, "absent": DIM, "pending": YELLOW, None: DIM}
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(s: str) -> str:
    return _ANSI.sub("", s)


def _stamp(s: Stamp | None) -> dict | None:
    if s is None:
        return None
    return {"date": s.date, "time": s.time, "session": s.session}


def to_dict(roadmap: Roadmap, results: dict[str, CheckResult] | None,
            viol: dict[str, list[str]], branch: str | None,
            links: dict[str, list[Link]] | None = None, recontact: dict | None = None,
            ledger_links: dict[str, list[Link]] | None = None, work: list[str] | None = None) -> dict:
    setpoint = [{"id": c.id, "text": c.text, "met_by": list(c.met_by), "met": clause_met(roadmap, c)}
                for c in roadmap.clauses]
    actions, reaches = [], uplinks(roadmap)
    for a in roadmap.actions:
        actions.append({
            "id": a.id, "title": a.title, "state": a.state, "source": a.source,
            "evidence": a.evidence, "check": a.check, "done": _stamp(a.done),
            "result": None if results is None or a.id not in results else results[a.id].result,
            "violations": list(viol[a.id]),
            "clauses": roadmap.clauses_of(a.id),
            "reaches": reaches[a.id],
            "links": [{"kind": l.kind, "ref": l.ref, "field": l.field, "resolved": l.resolved}
                      for l in (links or {}).get(a.id, [])],
        })
    ledger = [{"id": e.id, **_stamp(e.stamp), "kind": entry_kind(e.text), "text": e.text} for e in roadmap.ledger]
    h = roadmap.header
    return {
        "path": roadmap.path, "branch": branch, "format": roadmap.header.format,
        "title": h.title, "signer": h.signer, "opened": h.opened, "closed": h.closed,
        "setpoint": setpoint, "actions": actions, "ledger": ledger,
        "recontact": recontact,
        "flags": flags(roadmap, results, recontact=recontact, links=links, ledger_links=ledger_links, work=work),
        "summary": summary(roadmap, viol),
    }


def table_view(doc: dict, color: bool = False) -> str:
    def paint(text: str, code: str | None) -> str:
        return f"{code}{text}{RESET}" if color and code else text

    lines = [paint(doc["title"], BOLD),
             f"branch: {doc['branch'] or '?'}   signer: {doc['signer']}   opened: {doc['opened']}"
             + (f"   closed: {doc['closed']}" if doc["closed"] else ""), ""]
    for c in doc["setpoint"]:
        mark = paint("✅", GREEN) if c["met"] else paint("·", DIM)
        met_by = f"  ({' '.join(c['met_by'])})" if c["met_by"] else ""
        lines.append(f"{c['id']:<4} {mark}  {c['text']}{met_by}")
    lines.append("")
    for a in doc["actions"]:
        state = paint(a["state"], STATE_COLORS.get(a["state"])) + " " * (7 - len(a["state"]))
        glyph = paint(GLYPHS[a["result"]], RESULT_COLORS[a["result"]])
        lines.append(f"{a['id']:<4} {state} {glyph}  {a['title']}")
    flag_lines = []
    for a in doc["actions"]:
        for code in a["violations"]:
            detail = ""
            if code == "dangling_link":
                refs = [l["ref"] for l in a["links"] if l["kind"] in ("ledger", "trace") and l["resolved"] is False]
                detail = f" ({' '.join(refs)})"
            flag_lines.append(paint(f"{a['id']}: {code}{detail}", RED))
    flag_lines += [paint(f, YELLOW) for f in doc["flags"]]   # computed once, in invariants.flags
    lines.append("")
    lines.append("flags:" + ("" if flag_lines else " " + paint("none", DIM)))
    lines.extend(f"  {f}" for f in flag_lines)
    s = doc["summary"]

    def count(n: int) -> str:
        return paint(str(n), RED if n else GREEN)

    lines.append("")
    lines.append(f"done {s['done']}  open {s['open']}  signal {s['signal']}  clauses {s['clauses_met']}/{s['clauses']}"
                 f"  violations {count(s['violations'])}  phantoms {count(s['phantoms'])}")
    return "\n".join(lines)


def format_stamp(s: Stamp) -> str:
    return "[" + " ".join(p for p in (s.date, s.weekday, s.time, s.session) if p) + "]"


def select_ledger(entries: list[LedgerEntry], last: int | None = None, entry_id: str | None = None,
                  for_action: str | None = None, kind: str | None = None) -> tuple[list[LedgerEntry], int]:
    """Filter the ledger; returns (kept entries, how many of the whole were hidden).
    `kind` is "signer" or "machine" (docs/praxis-spec.md, section 2: decided by the fixed phrase alone)."""
    kept = entries
    if entry_id is not None:
        kept = [e for e in kept if e.id == entry_id]
    if for_action is not None:
        word = re.compile(rf"(?<![A-Za-z0-9]){re.escape(for_action)}(?![A-Za-z0-9])")
        kept = [e for e in kept if word.search(e.text)]
    if kind is not None:
        kept = [e for e in kept if entry_kind(e.text) == kind]
    if last is not None and last < len(kept):
        kept = kept[len(kept) - last:]
    return kept, len(entries) - len(kept)


def ledger_view(entries: list[LedgerEntry], color: bool = False, hidden: int = 0) -> str:
    """The ledger as written in the file, one entry per line, continuation lines folded."""
    def paint(text: str, code: str) -> str:
        return f"{code}{text}{RESET}" if color else text

    lines = []
    if hidden:
        lines.append(paint(f"({hidden} of {hidden + len(entries)} entries not shown)", DIM))
    elif not entries:
        return "(ledger is empty)"
    for e in entries:
        lines.append(f"- {paint(e.id, BOLD)} {paint(format_stamp(e.stamp), DIM)} {e.text}")
    return "\n".join(lines)

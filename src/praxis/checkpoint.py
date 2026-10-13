"""The mechanical half of the manifest's checkpoint document (docs/praxis-spec.md, section 3):
ledger entries grouped under the clause or action they mention, latest first, signer entries
before machine entries, with markers where the text claims a supersession or a stepwise act.
The supersession relation itself is prose and is left to the chronicler. Printed, never written."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from .links import mentions
from .model import Stamp
from .phrases import entry_kind, parse_phrase
from .render import BOLD, DIM, GLYPHS, RESET, format_stamp

_SUPERSEDES_RE = re.compile(r"supersedes the entry|overtakes", re.IGNORECASE)
_STEPWISE_RE = re.compile(r"\bis stepwise:")


@dataclass
class Block:
    id: str
    head: str
    entries: list[dict] = field(default_factory=list)


def _markers(e: dict) -> list[str]:
    out = []
    if _SUPERSEDES_RE.search(e["text"]):
        out.append("supersedes")
    if _STEPWISE_RE.search(e["text"]) or parse_phrase(e["text"]).stepwise:
        out.append("stepwise")
    return out


def _order(entries: list[dict]) -> list[dict]:
    """Latest first within kind; signer entries before machine entries."""
    latest = list(reversed(entries))
    return [e for e in latest if e["kind"] == "signer"] + [e for e in latest if e["kind"] == "machine"]


def build_checkpoint(doc: dict) -> list[Block]:
    ledger = [{**e, "kind": e.get("kind") or entry_kind(e["text"]), "markers": _markers(e)} for e in doc["ledger"]]
    by_id: dict[str, list[dict]] = {}
    unmentioned: list[dict] = []
    known = {c["id"] for c in doc["setpoint"]} | {a["id"] for a in doc["actions"]}
    for e in ledger:
        named = [m for m in mentions(e["text"]) if m in known]
        if not named:
            unmentioned.append(e)
        for m in named:
            by_id.setdefault(m, []).append(e)
    blocks = []
    for c in doc["setpoint"]:
        mark = "✅" if c["met"] else "·"
        blocks.append(Block(c["id"], f"{c['id']} {mark} {c['text']}", _order(by_id.get(c["id"], []))))
    for a in doc["actions"]:
        glyph = GLYPHS[a["result"]]
        blocks.append(Block(a["id"], f"{a['id']} {a['state']} {glyph} {a['title']}", _order(by_id.get(a["id"], []))))
    blocks.append(Block("unmentioned", "entries naming no clause or action", _order(unmentioned)))
    return blocks


def checkpoint_view(blocks: list[Block], color: bool = False) -> str:
    def paint(text: str, code: str | None) -> str:
        return f"{code}{text}{RESET}" if color and code else text

    lines: list[str] = []
    for b in blocks:
        if lines:
            lines.append("")
        lines.append(paint(b.head, BOLD))
        if not b.entries:
            lines.append(paint("  (no entry)", DIM))
        for e in b.entries:
            stamp = format_stamp(Stamp(e["date"], None, e["time"], e["session"]))
            marks = "".join(f" ⟂ {m}" for m in e["markers"])
            lines.append(f"  {paint(e['id'], BOLD)} {paint(stamp, DIM)}{marks} {e['text']}")
    return "\n".join(lines)

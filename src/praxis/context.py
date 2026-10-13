"""One id's neighbourhood, one hop out, laid in the manifest's chain order: clauses on top,
then actions, then ledger, then grounds (traces, commits, text). Position carries direction:
what sits above the focus rests on it, what sits below is what the focus rests on. Where a band
mixes directions (a ledger entry the action cites and one that names it) the relation word on
the line says which. Derived from the status document on every call; nothing is written.

Connections read, all one hop: `Met by:` on a clause; `ledger L<n>`, `traces/` and commit
down-links in an action's source/evidence (links.py); and mentions — any bare `a<n>`, `C<n>`
or `L<n>` in a clause's text, an action's source/evidence, or a ledger entry's text, ranges
expanded (links.mentions). A mention that names nothing is shown MISSING; it is not a status
violation. A focus action also shows `reaches`, its up-link path to a clause from the document
(invariants.uplinks), or `no clause`.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

from .links import mentions, text_ground, text_links

ID_RE = re.compile(r"^(a|C|L)\d+$")
KIND = {"a": "action", "C": "clause", "L": "ledger"}


@dataclass
class Line:
    id: str
    kind: str                 # clause | action | ledger | trace | commit | text
    status: str               # focus | ok | missing | unresolved
    relations: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)   # the document entry (clause / action / ledger)
    body: str = ""            # grounds only: the text to show


@dataclass
class Context:
    focuses: list[str]
    clauses: list[Line] = field(default_factory=list)
    actions: list[Line] = field(default_factory=list)
    ledger: list[Line] = field(default_factory=list)
    grounds: list[Line] = field(default_factory=list)


def _action_text(a: dict) -> str:
    return f"{a.get('source') or ''}\n{a.get('evidence') or ''}"


def _fields_naming(a: dict, target: str) -> list[str]:
    return [f for f in ("source", "evidence") if target in mentions(a.get(f) or "")]


class _Band:
    """Collects lines for one kind, keeping file order, missing ids after, one line per id."""

    def __init__(self, kind: str, entries: list[dict]):
        self.kind = kind
        self.order = {e["id"]: i for i, e in enumerate(entries)}
        self.by_id = {e["id"]: e for e in entries}
        self.lines: dict[str, Line] = {}

    def add(self, id: str, relation: str) -> None:
        line = self.lines.get(id)
        if line is None:
            status = "ok" if id in self.by_id else "missing"
            line = self.lines[id] = Line(id, self.kind, status, [], self.by_id.get(id, {"id": id}))
        if relation not in line.relations:
            line.relations.append(relation)

    def focus(self, id: str) -> None:
        self.lines[id] = Line(id, self.kind, "focus", [], self.by_id[id])   # marked before any relation lands

    def sorted(self) -> list[Line]:
        def key(l: Line):
            return (0 if l.status == "focus" else 1 if l.status == "ok" else 2, self.order.get(l.id, 0))
        return sorted(self.lines.values(), key=key)


def _ground(kind: str, ref: str, resolved: bool | None) -> Line:
    if kind == "trace":
        status = "missing" if resolved is False else "unresolved" if resolved is None else "ok"
    else:  # commit: unresolved when git cannot find it (other repositories are legitimate)
        status = "ok" if resolved else "unresolved"
    return Line(ref, kind, status, body=ref)


def build_context(doc: dict, focuses: str | list[str], root: Path | None = None) -> Context:
    """The union of the neighbourhoods of one or more ids; a line shared by several foci appears
    once with every relation word. Raises KeyError when an id is not in the document."""
    ids = [focuses] if isinstance(focuses, str) else list(dict.fromkeys(focuses))
    clauses = _Band("clause", doc["setpoint"])
    actions = _Band("action", doc["actions"])
    ledger = _Band("ledger", doc["ledger"])
    bands = {"a": actions, "C": clauses, "L": ledger}
    for f in ids:
        if not ID_RE.match(f) or f not in bands[f[0]].by_id:
            raise KeyError(f)
        bands[f[0]].focus(f)
    foci = set(ids)
    ctx = Context(ids)
    seen_grounds: set[tuple[str, str]] = set()

    def ground(kind: str, ref: str, resolved: bool | None) -> None:
        if kind == "ledger" or (kind, ref) in seen_grounds:
            return
        if kind == "commit" and any(k == "commit" and (r.startswith(ref) or ref.startswith(r))
                                    for k, r in seen_grounds):
            return   # the same commit cited short and long
        seen_grounds.add((kind, ref))
        ctx.grounds.append(_ground(kind, ref, resolved))

    # Met by, folded over every action focus: "met by a1, a7, with a3"
    for c in doc["setpoint"]:
        hits = [x for x in c["met_by"] if x in foci]
        if hits:
            others = [x for x in c["met_by"] if x not in foci]
            clauses.add(c["id"], f"met by {', '.join(hits)}" + (f", with {' '.join(others)}" if others else ""))

    for focus in ids:
        if focus[0] == "a":
            a = actions.by_id[focus]
            for f in ("source", "evidence"):
                for m in mentions(a.get(f) or ""):
                    if m == focus:
                        continue
                    if m[0] == "L":
                        ledger.add(m, f"cited by {focus}")
                    else:
                        bands[m[0]].add(m, f"named in {focus} {f}")
            for c in doc["setpoint"]:
                if focus in mentions(c["text"]):
                    clauses.add(c["id"], f"names {focus}")
            for o in doc["actions"]:
                if o["id"] != focus and _fields_naming(o, focus):
                    actions.add(o["id"], f"names {focus}")
            for e in doc["ledger"]:
                if focus in mentions(e["text"]):
                    ledger.add(e["id"], f"names {focus}")
            for l in a["links"]:
                ground(l["kind"], l["ref"], l["resolved"])
            text = text_ground(a, strip_mentions=True)
            if text:
                ctx.grounds.append(Line(f"text:{focus}", "text", "unresolved", body=text))

        elif focus[0] == "C":
            for aid in clauses.by_id[focus]["met_by"]:
                actions.add(aid, f"meets {focus}")
            for o in doc["setpoint"]:
                if o["id"] != focus and focus in mentions(o["text"]):
                    clauses.add(o["id"], f"names {focus}")
            for o in doc["actions"]:
                if _fields_naming(o, focus):
                    actions.add(o["id"], f"names {focus}")
            for e in doc["ledger"]:
                if focus in mentions(e["text"]):
                    ledger.add(e["id"], f"names {focus}")

        else:  # ledger
            e = ledger.by_id[focus]
            for m in mentions(e["text"]):
                if m != focus:
                    bands[m[0]].add(m, f"named by {focus}")
            for o in doc["actions"]:
                if focus in mentions(_action_text(o)):
                    actions.add(o["id"], f"cites {focus}")
            for o in doc["ledger"]:
                if o["id"] != focus and focus in mentions(o["text"]):
                    ledger.add(o["id"], f"names {focus}")
            for l in text_links(e["text"], set(ledger.by_id), root):
                ground(l.kind, l.ref, l.resolved)

    ctx.clauses, ctx.actions, ctx.ledger = clauses.sorted(), actions.sorted(), ledger.sorted()
    return ctx


# ---- terminal view ----
import textwrap  # noqa: E402
from .render import BOLD, DIM, GLYPHS, GREEN, RED, RESET, RESULT_COLORS, STATE_COLORS  # noqa: E402

RULE = "═"
INDENT = 5                     # continuation lines sit under the text, past the id column
GROUND_WORDS = {("trace", "ok"): "exists", ("trace", "missing"): "MISSING", ("trace", "unresolved"): "unchecked",
                ("commit", "unresolved"): "not in this repo",
                ("text", "unresolved"): "text the CLI cannot resolve"}


def _stamp(d: dict | None) -> str:
    if d is None:
        return "(none)"
    return "[" + " ".join(p for p in (d.get("date"), d.get("weekday"), d.get("time"), d.get("session")) if p) + "]"


class _Out:
    """Lines as (text, ansi) segments; width is measured on the text, color painted at the end."""

    def __init__(self, color: bool, width: int):
        self.color, self.width, self.lines = color, width, []

    def paint(self, text: str, code: str | None) -> str:
        return f"{code}{text}{RESET}" if self.color and code else text

    def rule(self) -> None:
        self.lines.append(self.paint(RULE * self.width, DIM))

    def entry(self, prefix: list[tuple[str, str | None]], body: str, right: str = "", right_code: str | None = DIM,
              indent: int = INDENT) -> None:
        """prefix segments, then body wrapped; `right` sits right-aligned on the first line;
        continuation lines start at `indent`."""
        plain_prefix = "".join(t for t, _ in prefix)
        first_width = max(self.width - len(plain_prefix) - (len(right) + 2 if right else 0), 10)
        rest_width = max(self.width - indent, 10)
        words = textwrap.wrap(body, first_width, break_on_hyphens=False) or [""]
        first, rest = words[0], " ".join(words[1:])
        line = "".join(self.paint(t, c) for t, c in prefix) + first
        if right:
            pad = self.width - len(plain_prefix) - len(first) - len(right)
            line += " " * max(pad, 2) + self.paint(right, right_code)
        self.lines.append(line)
        for w in textwrap.wrap(rest, rest_width, break_on_hyphens=False) if rest else []:
            self.lines.append(" " * indent + w)

    def field(self, label: str, value: str, code: str | None = None) -> None:
        prefix = " " * INDENT + f"{label:<10}"
        if code is None:
            self.entry([(prefix, None)], value, indent=len(prefix))
        else:
            self.lines.append(prefix + self.paint(value, code))


def _id(l: Line) -> list[tuple[str, str | None]]:
    return [(l.id, BOLD if l.status == "focus" else None), (" " * (5 - len(l.id)), None)]


def _missing(o: _Out, l: Line) -> None:
    o.entry(_id(l) + [("MISSING", RED)], "", " · ".join(l.relations))


def _clause_line(o: _Out, l: Line) -> None:
    if l.status == "missing":
        return _missing(o, l)
    c = l.data
    mark = ("✅", GREEN) if c["met"] else ("·", DIM)
    body = c["text"] + (f"  Met by: {' '.join(c['met_by'])}" if l.status == "focus" and c["met_by"] else "")
    o.entry(_id(l) + [mark, ("  ", None)], body, " · ".join(l.relations))


def _action_line(o: _Out, l: Line) -> None:
    if l.status == "missing":
        return _missing(o, l)
    a = l.data
    prefix = _id(l) + [(f"{a['state']:<7}", STATE_COLORS.get(a["state"])), (" ", None),
                       (GLYPHS[a["result"]], RESULT_COLORS[a["result"]]), ("  ", None)]
    if l.status == "focus" and "phantom" in a["violations"]:
        o.entry(prefix, a["title"], "no down-link", RED)
    else:
        o.entry(prefix, a["title"], " · ".join(l.relations))
    if l.status == "focus":
        o.field("source", a["source"] or "(empty)")
        o.field("evidence", a["evidence"] or "(empty)")
        o.field("check", a["check"] or "(none)")
        o.field("done", _stamp(a["done"]))
        o.field("reaches", " → ".join(a["reaches"]) if a["reaches"] else "no clause")
        if a["violations"]:
            o.field("flags", " ".join(a["violations"]), RED)


def _ledger_line(o: _Out, l: Line) -> None:
    if l.status == "missing":
        return _missing(o, l)
    o.entry(_id(l) + [(_stamp(l.data) + " ", DIM)], l.data["text"], " · ".join(l.relations))


def _ground_lines(o: _Out, grounds: list[Line]) -> None:
    """Traces one per line, resolved commits folded onto one line, the rest one per line, text last."""
    def one(l: Line) -> None:
        word = GROUND_WORDS.get((l.kind, l.status), l.status)
        body = f'"{l.body}"' if l.kind == "text" else l.body
        o.entry([], body, word, RED if l.status == "missing" else DIM)

    for l in grounds:
        if l.kind == "trace":
            one(l)
    ok = [l.body for l in grounds if l.kind == "commit" and l.status == "ok"]
    if ok:
        o.entry([], "  ".join(ok), "commits in this repo" if len(ok) > 1 else "commit in this repo")
    for l in grounds:
        if l.kind == "commit" and l.status != "ok":
            one(l)
    for l in grounds:
        if l.kind == "text":
            one(l)


def context_view(ctx: Context, color: bool = False, width: int = 100) -> str:
    """Layout A: bands in the chain's order, separated by rules, empty bands dropped."""
    o = _Out(color, width)
    o.rule()
    for lines, draw in ((ctx.clauses, _clause_line), (ctx.actions, _action_line), (ctx.ledger, _ledger_line)):
        if lines:
            for l in lines:
                draw(o, l)
            o.rule()
    if ctx.grounds:
        _ground_lines(o, ctx.grounds)
        o.rule()
    return "\n".join(o.lines)

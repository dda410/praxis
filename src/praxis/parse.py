"""Org text (format 2) -> Roadmap. Loud on every irregularity; never drops a line."""
from __future__ import annotations
import re
from datetime import datetime
from .model import (ACCEPTED_FORMATS, DEFAULT_TIMEOUT, FIELD_KEYS, STATES, TODO_LINE, Action, Clause,
                    Header, LedgerEntry, ParseError, Roadmap, Stamp)

SECTIONS = ("Setpoint", "Actions", "Ledger")
FORMAT1_SECTIONS = ("Status", "Remains")
REQUIRED_HEADERS = ("TITLE", "SIGNER", "OPENED", "PRAXIS", "TODO")
FORMAT1_MSG = "format 1 file ({what}); praxis reads formats 2 and 3, convert it"
_HEADER_RE = re.compile(r"^#\+([A-Z_]+):\s*(.*?)\s*$")
_SECTION_RE = re.compile(r"^\*\s+(.+?)\s*$")
_ACTION_RE = re.compile(r"^\*\*\s+(.*?)\s*$")
_FIELD_RE = re.compile(r"^- (\w+) ::(?:\s(.*))?$")
_CLAUSE_RE = re.compile(r"^- (C\d+) ::\s*(.*)$")
_MET_BY_RE = re.compile(r"\s*Met by:\s*((?:a\d+\s*)+)$")
_LEDGER_RE = re.compile(r"^- (L\d+) \[([^\]]*)\]\s*(.*)$")
_STAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?: ([A-Z][a-z]{2}))?(?: (\d{2}:\d{2}))?(?: ([0-9a-f]{8}))?$")
_ACTION_ID_RE = re.compile(r"^a\d+$")


def parse_stamp(inner: str, line: int, path: str) -> Stamp:
    m = _STAMP_RE.match(inner.strip())
    if not m:
        raise ParseError(line, f"bad stamp [{inner}] (expected YYYY-MM-DD, optional weekday Www, HH:MM, 8-hex session, in that order)", path)
    date, _weekday, hhmm, _session = m.groups()
    try:
        datetime.strptime(f"{date} {hhmm or '00:00'}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise ParseError(line, f"bad stamp [{inner}] (date or time does not exist)", path)
    return Stamp(*m.groups())


def parse_roadmap(text: str, path: str = "ROADMAP.org") -> Roadmap:
    lines = text.splitlines()
    headers: dict[str, str] = {}
    header_lines: dict[str, int] = {}
    sections: dict[str, list[tuple[int, str]]] = {}
    order: list[str] = []
    current: str | None = None

    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        if current is None and (m := _HEADER_RE.match(line)):
            if m.group(1) == "SETPOINT":
                raise ParseError(i, FORMAT1_MSG.format(what="#+SETPOINT: header"), path)
            headers[m.group(1)] = m.group(2)
            header_lines[m.group(1)] = i
            continue
        if m := _SECTION_RE.match(line):
            name = m.group(1)
            if name in FORMAT1_SECTIONS:
                raise ParseError(i, FORMAT1_MSG.format(what=f"'* {name}' section"), path)
            if name not in SECTIONS:
                raise ParseError(i, f"unknown section '* {name}' (expected one of {', '.join(SECTIONS)})", path)
            if name in sections:
                raise ParseError(i, f"duplicate section '* {name}'", path)
            current = name
            sections[name] = []
            order.append(name)
            continue
        if current is not None and (m := _HEADER_RE.match(line)):
            key = m.group(1)
            if key == "SETPOINT":
                raise ParseError(i, FORMAT1_MSG.format(what="#+SETPOINT: header"), path)
            raise ParseError(i, f"header keyword #+{key}: must appear before '* Setpoint'", path)
        if line.startswith("#"):
            continue  # comments are ignored
        if current is not None:
            sections[current].append((i, line))

    for key in REQUIRED_HEADERS:
        if not headers.get(key):
            raise ParseError(1, f"missing required header #+{key}:", path)
    accepted = tuple(str(v) for v in ACCEPTED_FORMATS)
    if headers["PRAXIS"] not in accepted:
        raise ParseError(1, f"unsupported #+PRAXIS: {headers['PRAXIS']} (this praxis reads formats {' and '.join(accepted)})", path)
    version = int(headers["PRAXIS"])
    recontact = headers.get("RECONTACT") or None
    if recontact and version < 3:
        raise ParseError(header_lines["RECONTACT"], "#+RECONTACT: needs #+PRAXIS: 3", path)
    if headers["TODO"] != TODO_LINE:
        raise ParseError(1, f"#+TODO: must be exactly '{TODO_LINE}', got {headers['TODO']!r}", path)
    for name in SECTIONS:
        if name not in sections:
            raise ParseError(len(lines), f"missing section '* {name}'", path)
    if order != list(SECTIONS):
        raise ParseError(1, f"sections out of order: got {order}, expected {list(SECTIONS)}", path)

    timeout = DEFAULT_TIMEOUT
    if "CHECK_TIMEOUT" in headers:
        try:
            timeout = int(headers["CHECK_TIMEOUT"])
        except ValueError:
            raise ParseError(1, f"#+CHECK_TIMEOUT must be an integer, got {headers['CHECK_TIMEOUT']!r}", path)

    header = Header(title=headers["TITLE"], signer=headers["SIGNER"], opened=headers["OPENED"],
                    closed=headers.get("CLOSED") or None, check_timeout=timeout,
                    format=version, recontact=recontact)
    rm = Roadmap(path=path, header=header)
    rm.clauses = _parse_setpoint(sections["Setpoint"], path)
    rm.actions = _parse_actions(sections["Actions"], path)
    rm.ledger = _parse_ledger(sections["Ledger"], path)
    known = {a.id for a in rm.actions}
    for c in rm.clauses:
        for aid in c.met_by:
            if aid not in known:
                raise ParseError(c.line, f"clause {c.id} names unknown action {aid}", path)
    return rm


def _parse_setpoint(body: list[tuple[int, str]], path: str) -> list[Clause]:
    clauses: list[Clause] = []
    seen: set[str] = set()
    for i, line in body:
        if not line.strip():
            continue
        if m := _CLAUSE_RE.match(line):
            cid = m.group(1)
            if cid in seen:
                raise ParseError(i, f"duplicate clause id {cid}", path)
            seen.add(cid)
            clauses.append(Clause(cid, m.group(2).strip(), [], i))
        elif line.startswith((" ", "\t")) and clauses:
            clauses[-1].text = (clauses[-1].text + " " + line.strip()).strip()
        else:
            raise ParseError(i, "setpoint line must be '- C<n> :: text[. Met by: a1 a2]' or an indented continuation", path)
    if not clauses:
        raise ParseError(body[0][0] if body else 1, "Setpoint has no clauses", path)
    for c in clauses:
        if m := _MET_BY_RE.search(c.text):
            c.met_by = m.group(1).split()
            c.text = c.text[:m.start()].rstrip()
        elif re.search(r"met by", c.text, re.IGNORECASE):
            raise ParseError(c.line, f"clause {c.id}: 'Met by:' must end the line as a space-separated list of action ids (Met by: a1 a2)", path)
    return clauses


def _parse_actions(body: list[tuple[int, str]], path: str) -> list[Action]:
    actions: list[Action] = []
    seen: set[str] = set()
    head: tuple[int, str, str, str] | None = None  # (line, state, id, title)
    fields: dict[str, str] = {}
    field_lines: dict[str, int] = {}
    last_key: str | None = None

    def flush() -> None:
        if head is None:
            return
        line, state, id_, title = head
        done: Stamp | None = None
        if "done" in fields:
            raw = fields["done"].strip()
            if not (raw.startswith("[") and raw.endswith("]")):
                raise ParseError(field_lines["done"], f"done must be a stamp in brackets, got {raw!r}", path)
            done = parse_stamp(raw[1:-1], field_lines["done"], path)
        actions.append(Action(id_, title, state, fields.get("source", "").strip(),
                              fields.get("evidence", "").strip(), fields.get("check", "").strip(),
                              done, line))

    for i, line in body:
        if not line.strip():
            continue
        if m := _ACTION_RE.match(line):
            flush()
            parts = m.group(1).split(None, 2)
            if not parts or parts[0] not in STATES:
                raise ParseError(i, f"action heading must be '** <STATE> a<n> <title>' with STATE one of {', '.join(STATES)}, got {m.group(1)!r}", path)
            if len(parts) < 2 or not _ACTION_ID_RE.match(parts[1]):
                raise ParseError(i, f"action id must look like a<digits>, got {parts[1] if len(parts) > 1 else ''!r}", path)
            if len(parts) < 3 or not parts[2].strip():
                raise ParseError(i, f"action {parts[1]} has no title", path)
            state, id_, title = parts[0], parts[1], parts[2].strip()
            if id_ in seen:
                raise ParseError(i, f"duplicate action id {id_}", path)
            seen.add(id_)
            head = (i, state, id_, title)
            fields, field_lines, last_key = {}, {}, None
            continue
        if head is None:
            raise ParseError(i, "unexpected text in Actions before the first '** ' heading", path)
        if m := _FIELD_RE.match(line):
            key, value = m.group(1), m.group(2) or ""
            if key not in FIELD_KEYS:
                raise ParseError(i, f"unknown field '{key}' in {head[2]} (allowed: {', '.join(FIELD_KEYS)})", path)
            if key in fields:
                raise ParseError(i, f"field '{key}' repeated in {head[2]}", path)
            fields[key] = value
            field_lines[key] = i
            last_key = key
            continue
        if line.startswith((" ", "\t")) and last_key is not None:
            fields[last_key] = (fields[last_key] + " " + line.strip()).strip()
            continue
        raise ParseError(i, f"unexpected line under {head[2]} (expected '- <key> :: value' or an indented continuation)", path)
    flush()
    return actions


def _parse_ledger(body: list[tuple[int, str]], path: str) -> list[LedgerEntry]:
    entries: list[LedgerEntry] = []
    last_n = 0
    for i, line in body:
        if not line.strip():
            continue
        s = line.strip()
        if m := _LEDGER_RE.match(s):
            n = int(m.group(1)[1:])
            if n <= last_n:
                raise ParseError(i, f"ledger id {m.group(1)} must be greater than L{last_n}: the ledger is append-only, ids strictly increase", path)
            last_n = n
            entries.append(LedgerEntry(m.group(1), parse_stamp(m.group(2), i, path), m.group(3), i))
        elif line.startswith((" ", "\t")) and entries:
            entries[-1].text = (entries[-1].text + " " + s).strip()
        else:
            raise ParseError(i, "ledger line must be '- L<n> [stamp] text' or an indented continuation", path)
    return entries

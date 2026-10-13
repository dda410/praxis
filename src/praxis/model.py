from __future__ import annotations
from dataclasses import dataclass, field

STATES = ("TODO", "STRT", "DONE", "SIGNAL", "SKIP")
RESULTS = ("passed", "failed", "absent", "unclosable", "timeout", "pending")
PENDING_EXIT = 3
FIELD_KEYS = ("source", "evidence", "check", "done")
FORMAT = 3                     # the version init writes
ACCEPTED_FORMATS = (2, 3)      # docs/praxis-spec.md, section 1: 2 is read until every live roadmap has moved
TODO_LINE = "TODO STRT SIGNAL | DONE SKIP"
DEFAULT_TIMEOUT = 30


class ParseError(Exception):
    def __init__(self, line: int, msg: str, path: str = "ROADMAP.org"):
        self.line = line
        self.msg = msg
        self.path = path
        super().__init__(f"{path}:{line}: {msg}")


@dataclass
class Stamp:
    date: str
    weekday: str | None = None
    time: str | None = None
    session: str | None = None


@dataclass
class Header:
    title: str
    signer: str
    opened: str
    closed: str | None = None
    check_timeout: int = DEFAULT_TIMEOUT
    format: int = FORMAT
    recontact: str | None = None


@dataclass
class Clause:
    id: str
    text: str
    met_by: list[str]
    line: int


@dataclass
class Action:
    id: str
    title: str
    state: str
    source: str
    evidence: str
    check: str
    done: Stamp | None
    line: int


@dataclass
class LedgerEntry:
    id: str
    stamp: Stamp
    text: str
    line: int


@dataclass
class Roadmap:
    path: str
    header: Header
    clauses: list[Clause] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    ledger: list[LedgerEntry] = field(default_factory=list)

    def action(self, id: str) -> Action:
        for a in self.actions:
            if a.id == id:
                return a
        raise KeyError(id)

    def clauses_of(self, action_id: str) -> list[str]:
        return [c.id for c in self.clauses if action_id in c.met_by]


@dataclass
class CheckResult:
    result: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""

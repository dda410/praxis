"""praxis — read ROADMAP.org, run checks, report. Never writes the file.

Usage:
    praxis status [--json] [--no-checks] [--no-recontact] [--color auto|always|never] [--path FILE]
    praxis check <action id> [--path FILE]
    praxis ledger [L<n>] [--last N] [--for a<n>] [--signer | --machine] [--color auto|always|never] [--path FILE]
    praxis context <id>... [--no-checks] [--width N] [--color auto|always|never] [--path FILE]
    praxis stamp
    praxis checkpoint [--no-checks] [--color auto|always|never] [--path FILE]

Exit codes: 0 ok, 1 any violation (or a failed single check), 2 parse error / missing file.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from .checkpoint import build_checkpoint, checkpoint_view
from .checks import run_all, run_check
from .context import ID_RE, build_context, context_view
from .invariants import violations
from .links import all_links, ledger_links
from .model import ParseError
from .parse import parse_roadmap
from .recontact import run_recontact
from .render import ledger_view, select_ledger, table_view, to_dict
from .worktree import changed_since, stamp_datetime


def find_roadmap(start: Path, explicit: str | None) -> tuple[Path, Path]:
    if explicit:
        p = Path(explicit).expanduser().resolve()
    else:
        p = (start / "ROADMAP.org").resolve()
    if not p.is_file():
        raise FileNotFoundError(f"no ROADMAP.org at {p}")
    return p, p.parent


def current_branch(root: Path) -> str | None:
    try:
        proc = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=str(root),
                              capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def use_color(mode: str, stream) -> bool:
    """auto: color only on a terminal, unless NO_COLOR is set or TERM is dumb."""
    if mode == "always":
        return True
    if mode == "never":
        return False
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def _load(args) -> tuple:
    path, root = find_roadmap(Path.cwd(), args.path)
    text = path.read_text(encoding="utf-8")
    rm = parse_roadmap(text, path=path.name)
    return rm, root


def cmd_status(args) -> int:
    rm, root = _load(args)
    doc = _status_doc(args, rm, root)
    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
    else:
        print(table_view(doc, color=use_color(args.color, sys.stdout)))
    return 1 if doc["summary"]["violations"] else 0


def cmd_check(args) -> int:
    rm, root = _load(args)
    try:
        action = rm.action(args.id)
    except KeyError:
        print(f"error: no action {args.id} in {rm.path}", file=sys.stderr)
        return 2
    res = run_check(action.check, root, rm.header.check_timeout)
    print(f"{action.id}: {res.result}" + (f" (exit {res.returncode})" if res.returncode is not None else ""))
    if res.stdout:
        print(res.stdout.rstrip())
    if res.stderr:
        print(res.stderr.rstrip(), file=sys.stderr)
    return 0 if res.result == "passed" else 1


WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def make_stamp(now: datetime, session: str | None) -> str:
    """`[YYYY-MM-DD Www HH:MM xxxxxxxx]`, weekday in English whatever the locale (docs/praxis-spec.md, section 3:
    the stamp comes from the clock at the moment of the write, never from the model's memory)."""
    parts = [now.strftime("%Y-%m-%d"), WEEKDAYS[now.weekday()], now.strftime("%H:%M")]
    if session:
        parts.append(session[:8])
    return "[" + " ".join(parts) + "]"


def cmd_stamp(args) -> int:
    session = os.environ.get("CLAUDE_CODE_SESSION_ID") or None
    print(make_stamp(datetime.now(), session))
    if not session:
        print("no session", file=sys.stderr)
    return 0


def cmd_ledger(args) -> int:
    rm, _root = _load(args)
    if args.id is not None and all(e.id != args.id for e in rm.ledger):
        print(f"error: no ledger entry {args.id} in {rm.path}", file=sys.stderr)
        return 2
    kind = "signer" if args.signer else "machine" if args.machine else None
    kept, hidden = select_ledger(rm.ledger, last=args.last, entry_id=args.id, for_action=args.for_action, kind=kind)
    print(ledger_view(kept, color=use_color(args.color, sys.stdout), hidden=hidden))
    return 0


def _status_doc(args, rm, root, only: set[str] | None = None, scope: str = "full") -> dict:
    """The status document. `scope="full"` (status, checkpoint) computes every reading the flags
    need: the hook, every action's links, the ledger's commit links, the work-since scan.
    `scope="view"` (context, graph) resolves only the links of the actions in `only` (all when
    None) and runs none of the flag readings: a view draws no flag, so it pays for none."""
    full = scope == "full"
    recontact = None
    if full and rm.header.recontact and not getattr(args, "no_checks", False) and not getattr(args, "no_recontact", False):
        recontact = run_recontact(rm.header.recontact, root, rm.header.check_timeout)
    results = None if args.no_checks else run_all(rm, root, rm.header.check_timeout, only)
    links = all_links(rm, root, only=None if full else only)
    entry_links = ledger_links(rm, root) if full else None
    work = changed_since(root, stamp_datetime(rm.ledger[-1].stamp), exclude=root / rm.path) if full and rm.ledger else None
    return to_dict(rm, results, violations(rm, results, links), current_branch(root), links,
                   recontact=recontact, ledger_links=entry_links, work=work)


def cmd_context(args) -> int:
    """The union of the given ids' neighbourhoods, one hop out, as layered text (clauses / actions /
    ledger / grounds). Checks run only for the actions the view shows."""
    rm, root = _load(args)
    known = {c.id for c in rm.clauses} | {a.id for a in rm.actions} | {e.id for e in rm.ledger}
    for fid in args.ids:
        if fid not in known:
            print(f"error: no {fid} in {rm.path}", file=sys.stderr)
            return 2
    color = use_color(args.color, sys.stdout)
    width = args.width or (shutil.get_terminal_size().columns if sys.stdout.isatty() else 100)
    doc = _status_doc(argparse.Namespace(no_checks=True), rm, root, only=set(), scope="view")
    shown = {l.id for l in build_context(doc, args.ids, root).actions if l.status != "missing"}
    doc = _status_doc(args, rm, root, only=shown, scope="view")
    print(context_view(build_context(doc, args.ids, root), color=color, width=width))
    return 0


def cmd_checkpoint(args) -> int:
    """Ledger entries grouped by the clause or action they mention, latest first (docs/praxis-spec.md, section 3)."""
    rm, root = _load(args)
    doc = _status_doc(args, rm, root)
    print(checkpoint_view(build_checkpoint(doc), color=use_color(args.color, sys.stdout)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="praxis", description="read ROADMAP.org, run checks, report")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status", help="parse, run every check, print table or JSON")
    s.add_argument("--json", action="store_true")
    s.add_argument("--no-checks", action="store_true", help="skip running checks (result: null)")
    s.add_argument("--no-recontact", action="store_true", help="skip the #+RECONTACT: hook; checks still run")
    s.add_argument("--color", choices=["auto", "always", "never"], default="auto",
                   help="color the table view (auto: only on a terminal, honors NO_COLOR)")
    s.add_argument("--path", help="explicit ROADMAP.org path (root = its directory)")
    s.set_defaults(func=cmd_status)
    c = sub.add_parser("check", help="run one action's check and show its output")
    c.add_argument("id")
    c.add_argument("--path")
    c.set_defaults(func=cmd_check)
    ld = sub.add_parser("ledger", help="print the ledger as written; runs no checks")
    ld.add_argument("id", nargs="?", help="one entry, L<n>")
    ld.add_argument("--last", type=int, metavar="N", help="only the last N entries")
    ld.add_argument("--for", dest="for_action", metavar="a<n>", help="only entries that name this action")
    who = ld.add_mutually_exclusive_group()
    who.add_argument("--signer", action="store_true", help="only entries the signer triggered (decide, prior, started, chain authorized, closed)")
    who.add_argument("--machine", action="store_true", help="only entries orient, gates and chains wrote (recontact, reverted, gate result, chain stopped, correction)")
    ld.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    ld.add_argument("--path")
    ld.set_defaults(func=cmd_ledger)
    cx = sub.add_parser("context", help="the neighbourhood of one or more ids as layered text: clauses, actions, ledger, grounds")
    cx.add_argument("ids", nargs="+", metavar="id", help="a<n>, C<n> or L<n>; several ids merge into one view")
    cx.add_argument("--no-checks", action="store_true", help="skip running the shown actions' checks (glyph: ·)")
    cx.add_argument("--width", type=int, metavar="N", help="wrap at N columns (default: the terminal's, else 100)")
    cx.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    cx.add_argument("--path")
    cx.set_defaults(func=cmd_context)
    st = sub.add_parser("stamp", help="print the stamp of this instant from the clock and $CLAUDE_CODE_SESSION_ID")
    st.set_defaults(func=cmd_stamp)
    cp = sub.add_parser("checkpoint", help="ledger entries grouped under the clause or action they name, latest first; printed, never written")
    cp.add_argument("--no-checks", action="store_true", help="skip running checks (glyph: ·)")
    cp.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    cp.add_argument("--path")
    cp.set_defaults(func=cmd_checkpoint)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, UnicodeDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ParseError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

"""Files touched after the last ledger stamp: a manual reading of the work tree made mechanical
(docs/praxis-spec.md, section 1, flag `work since L<n>`). Read-only; names files, says nothing about them."""
from __future__ import annotations
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from .model import Stamp


def stamp_datetime(s: Stamp) -> datetime:
    """The end of the stamp's minute, so a file written in that same minute does not count as
    later; a date-only stamp (hand-written) counts as the end of its day. The parser has
    already refused a date or time that does not exist."""
    hhmm = s.time or "23:59"
    return datetime.strptime(f"{s.date} {hhmm}", "%Y-%m-%d %H:%M") + timedelta(seconds=59)


def _git(root: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def changed_since(root: Path, since: datetime, exclude: Path | None = None) -> list[str] | None:
    """Paths `git status --porcelain` lists (modified, added, untracked) whose mtime is after
    `since`, relative to the repository top level; `exclude` (the roadmap file itself, which
    the caller has just written) is left out. None when `root` is not inside a git repository."""
    top = _git(root, "rev-parse", "--show-toplevel")
    status = _git(root, "status", "--porcelain", "--untracked-files=all", "-z")
    if top is None or status is None:
        return None
    toplevel = Path(top.strip())
    skip = exclude.resolve() if exclude else None
    out: list[str] = []
    for record in status.split("\0"):
        if len(record) < 4:
            continue
        path = record[3:]
        p = toplevel / path
        if skip is not None and p.resolve() == skip:
            continue
        if p.is_file() and datetime.fromtimestamp(p.stat().st_mtime) > since:
            out.append(path)
    return out

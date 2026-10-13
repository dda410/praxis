from __future__ import annotations
import os
import time
from datetime import datetime
from pathlib import Path
from tests.praxis_helpers import make_repo


def test_stamp_datetime_date_only_is_end_of_day():
    from praxis.model import Stamp
    from praxis.worktree import stamp_datetime
    assert stamp_datetime(Stamp("2026-10-06")) == datetime(2026, 10, 6, 23, 59, 59)
    assert stamp_datetime(Stamp("2026-10-06", "Tue", "19:34", "1a2b3c4d")) == datetime(2026, 10, 6, 19, 34, 59)


def test_changed_since_lists_untracked_and_modified_files_newer_than_the_stamp(tmp_path: Path):
    from praxis.worktree import changed_since
    make_repo(tmp_path)
    old = tmp_path / "old.txt"
    old.write_text("x")
    past = time.time() - 3600
    os.utime(old, (past, past))
    new = tmp_path / "new.txt"
    new.write_text("y")
    since = datetime.now().replace(second=0, microsecond=0)
    os.utime(new, (time.time() + 120, time.time() + 120))
    out = changed_since(tmp_path, since)
    assert "new.txt" in out and "old.txt" not in out


def test_changed_since_is_none_outside_git(tmp_path: Path):
    from praxis.worktree import changed_since
    assert changed_since(tmp_path, datetime(2026, 1, 1)) is None


def test_stamp_datetime_is_the_end_of_the_stamps_minute():
    from praxis.model import Stamp
    from praxis.worktree import stamp_datetime
    assert stamp_datetime(Stamp("2026-10-06", "Tue", "19:34", "1a2b3c4d")) == datetime(2026, 10, 6, 19, 34, 59)
    assert stamp_datetime(Stamp("2026-10-06")) == datetime(2026, 10, 6, 23, 59, 59)


def test_changed_since_excludes_the_roadmap_itself_and_resolves_from_a_subdirectory(tmp_path: Path):
    import subprocess
    from praxis.worktree import changed_since
    make_repo(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "ROADMAP.org").write_text("x")
    (sub / "work.py").write_text("y")
    (sub / "café note.txt").write_text("z")
    future = time.time() + 120
    for p in (sub / "ROADMAP.org", sub / "work.py", sub / "café note.txt"):
        os.utime(p, (future, future))
    out = changed_since(sub, datetime(2000, 1, 1), exclude=sub / "ROADMAP.org")
    assert "sub/work.py" in out and "sub/café note.txt" in out and "sub/ROADMAP.org" not in out

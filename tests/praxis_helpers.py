"""Shared fixture text and repo builder for praxis tests (format 2)."""
from __future__ import annotations
import subprocess
from pathlib import Path

ROADMAP = """\
#+TITLE: orrery x.y.z — roadmap
#+SIGNER: Dimitri Diomaiuta
#+OPENED: 2026-09-03
#+PRAXIS: 2
#+TODO: TODO STRT SIGNAL | DONE SKIP

* Setpoint
- C1 :: tag vx.y.z on main. Met by: a1 a7
- C2 :: speed vs previous measured in traces/. Met by: a4
- C3 :: date format option settled with the reviewer

* Actions
** DONE a1 cut x.y.z from main
- source :: README release procedure
- evidence :: branch x.y.z
- check :: true
- done :: [2026-09-03 Wed 10:12 0a1b2c3d]
** STRT a2 land the new parser
- source :: parser branch ab12cd3
- evidence :: staged diff
** TODO a3 parity gate
- source :: ledger 2026-09-03
- check :: grep -q PASS traces/parity.log
** TODO a4 speed vs previous
- source :: setpoint C2
- check :: test -f traces/timing.log
** TODO a5 date format
- source :: T-1; the reviewer 9e8d7c6
- check :: echo a | grep -q a
** SIGNAL a6 icon set (the designer)
- source :: verbal 2026-09-03
- evidence :: no branch yet
** TODO a7 release per README
- source :: README release procedure
- check :: false

* Ledger
- L1 [2026-09-03 Wed] Parser-first replaces benchmark-first; benchmark attempt archived.
  Evidence: 1234567, 2b3c4d5.
- L2 [2026-09-03 Wed 16:40 0a1b2c3d] a2 started: commit the staged parser. Prior: fast tests green. Regulates against: ab12cd3. Tacit: none.
"""


def line_of(text: str, needle: str) -> int:
    """1-based line number of the first line containing needle."""
    for i, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return i
    raise ValueError(needle)


def make_repo(tmp_path: Path, text: str = ROADMAP, branch: str = "x.y.z") -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "symbolic-ref", "HEAD", f"refs/heads/{branch}"],
                   cwd=tmp_path, check=True)
    (tmp_path / "ROADMAP.org").write_text(text, encoding="utf-8")
    (tmp_path / "traces").mkdir(exist_ok=True)
    return tmp_path

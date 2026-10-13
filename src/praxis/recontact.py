"""Run the signer's `#+RECONTACT:` command before any check (docs/praxis-spec.md, section 1, Recontact).

The hook verifies that the paths to reality the checks depend on are open and refreshes the
local mirrors. Exit 0: every path open. Otherwise one line per closed path; each becomes a
flag. Read-only on the world; never prints."""
from __future__ import annotations
import subprocess
from pathlib import Path


def run_recontact(cmd: str, root: Path, timeout: int) -> dict:
    try:
        proc = subprocess.run(cmd, shell=True, cwd=str(root), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"command": cmd, "exit": None, "lines": [f"timeout after {timeout}s"]}
    lines = [l for l in proc.stdout.splitlines() + proc.stderr.splitlines() if l.strip()]
    return {"command": cmd, "exit": proc.returncode, "lines": lines}

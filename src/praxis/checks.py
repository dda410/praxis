"""Run check-column commands. Read-only on the world; never prints.
Exit 0 passed, exit 3 pending (the trace is being produced, docs/praxis-spec.md, section 1, Check results), anything else failed."""
from __future__ import annotations
import glob
import re
import subprocess
from pathlib import Path
from .model import PENDING_EXIT, CheckResult, Roadmap

_TRACES_RE = re.compile(r"(?<![\w/.-])(traces/[\w./*?\[\]-]+)")


def unclosable_paths(cmd: str, root: Path) -> list[str]:
    out = []
    for p in _TRACES_RE.findall(cmd):
        if any(ch in p for ch in "*?["):
            if not glob.glob(str(root / p)):
                out.append(p)
        elif not (root / p).exists():
            out.append(p)
    return out


def run_check(cmd: str, root: Path, timeout: int) -> CheckResult:
    cmd = cmd.strip()
    if not cmd:
        return CheckResult("absent")
    if unclosable_paths(cmd, root):
        return CheckResult("unclosable")
    try:
        proc = subprocess.run(cmd, shell=True, cwd=str(root), capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return CheckResult("timeout", None, (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""),
                           (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or ""))
    result = "passed" if proc.returncode == 0 else "pending" if proc.returncode == PENDING_EXIT else "failed"
    return CheckResult(result, proc.returncode, proc.stdout, proc.stderr)


def run_all(roadmap: Roadmap, root: Path, timeout: int, only: set[str] | None = None) -> dict[str, CheckResult]:
    """Every action's check, or with `only` just those ids (the others get no result at all)."""
    return {a.id: run_check(a.check, root, timeout) for a in roadmap.actions if only is None or a.id in only}

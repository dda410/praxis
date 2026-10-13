"""Down-links an action's source/evidence make to things the CLI can resolve.

Three kinds are exact enough to check: `ledger L<n>` (an entry id), `traces/<path>`
(a captured file; `*`, `?` and `{a,b}` patterns allowed), and a repo-local commit
hash. Everything else in a source (verbal grounds, URLs, pipeline numbers, other
repos' commits) is a reference the CLI cannot reach and is left as text.

Commits are resolved in one `git cat-file --batch-check` per document (docs/praxis-spec.md, section 1, Flags: a
per-hash process makes `context` on a long ledger spawn hundreds of them).

A ledger or trace link that does not resolve is *dangling*: the manifest's phantom
in miniature (a down-link that reaches nothing). A commit that git cannot find is
not dangling, only unresolved: roadmaps legitimately cite other repositories.
"""
from __future__ import annotations
import glob
import itertools
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from .model import Action, Roadmap

LEDGER_RE = re.compile(r"ledger (L\d+)")
TRACE_RE = re.compile(r"traces/\S+")
COMMIT_RE = re.compile(r"(?<![0-9a-zA-Z/])(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}(?![0-9a-zA-Z])")
TRAILING = ".,;:)]}…'\""
MENTION_RE = re.compile(r"(?<![A-Za-z0-9])([aCL])(\d+)(?:-\1(\d+))?(?![A-Za-z0-9])")


@dataclass(frozen=True)
class Link:
    kind: str          # ledger | trace | commit
    ref: str           # L5 | traces/x.csv | abc1234
    field: str         # source | evidence
    resolved: bool | None   # None: not checkable here (no root, not a git repo)

    @property
    def dangling(self) -> bool:
        return self.kind in ("ledger", "trace") and self.resolved is False


def mentions(text: str) -> list[str]:
    """Ids the text names, in order of first appearance: `a<n>`, `C<n>`, `L<n>`, word-bounded,
    with ranges like `a1-a4` or `L28-L31` expanded (a reversed range yields its two ends).
    Wider than the `ledger L<n>` down-link: any bare id counts as a mention."""
    out: list[str] = []
    for kind, lo, hi in MENTION_RE.findall(text):
        lo_n, hi_n = int(lo), int(hi) if hi else int(lo)
        ids = [f"{kind}{n}" for n in range(lo_n, hi_n + 1)] if hi_n >= lo_n else [f"{kind}{lo_n}", f"{kind}{hi_n}"]
        out += [i for i in ids if i not in out]
    return out


def expand_braces(pattern: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    out = []
    for alt in m.group(1).split(","):
        out += expand_braces(pattern[:m.start()] + alt + pattern[m.end():])
    return out


def trace_exists(root: Path, ref: str) -> bool:
    for p in expand_braces(ref):
        if glob.has_magic(p):
            if not glob.glob(str(root / p)):
                return False
        elif not (root / p).exists():
            return False
    return True


def resolve_commits(root: Path, shas: list[str]) -> dict[str, bool | None]:
    """Whether each sha names a commit in the repository at `root`, in ONE git process
    (`cat-file --batch-check`, one input line per sha, one answer line per input, in order).
    Every value is None when `root` is not inside a git repository. An ambiguous short
    sha is False, as `cat-file -e` read it before."""
    shas = list(dict.fromkeys(shas))
    if not shas:
        return {}
    try:
        proc = subprocess.run(["git", "cat-file", "--batch-check"], cwd=str(root), input="".join(f"{s}^{{commit}}\n" for s in shas),
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return {s: None for s in shas}
    if proc.returncode != 0:
        return {s: None for s in shas}
    answers = proc.stdout.splitlines()
    if len(answers) != len(shas):
        return {s: None for s in shas}
    return {s: not (a.endswith(" missing") or a.endswith(" ambiguous")) for s, a in zip(shas, answers)}


def _tokens(text: str, rx: re.Pattern) -> list[str]:
    seen: list[str] = []
    for m in rx.finditer(text):
        tok = m.group(0).rstrip(TRAILING)
        if tok and tok not in seen:
            seen.append(tok)
    return seen


def commit_tokens(text: str) -> list[str]:
    """Commit-shaped tokens of a text, sha256 digests excluded."""
    return [ref for ref in _tokens(text, COMMIT_RE) if not re.search(rf"sha256\s*{re.escape(ref)}", text)]


def text_links(text: str, ledger_ids: set[str], root: Path | None, field: str = "text",
               check_commits: bool = True, resolved: dict[str, bool | None] | None = None) -> list[Link]:
    """The down-links one piece of text makes; `field` is recorded on each link. Commits are
    looked up in `resolved` (a map from resolve_commits) when given, else resolved here in one
    git call for this text, else left None."""
    out: list[Link] = []
    for ref in LEDGER_RE.findall(text):
        out.append(Link("ledger", ref, field, ref in ledger_ids))
    for ref in _tokens(text, TRACE_RE):
        out.append(Link("trace", ref, field, None if root is None else trace_exists(root, ref)))
    commits = commit_tokens(text)
    if resolved is None:
        resolved = resolve_commits(root, commits) if root is not None and check_commits else {}
    for ref in commits:
        out.append(Link("commit", ref, field, resolved.get(ref)))
    return out


def _action_texts(action: Action) -> list[tuple[str, str]]:
    return [(field, getattr(action, field) or "") for field in ("source", "evidence")]


def links_of(action: Action, roadmap: Roadmap, root: Path | None,
             check_commits: bool = True, resolved: dict[str, bool | None] | None = None) -> list[Link]:
    ledger_ids = {e.id for e in roadmap.ledger}
    out: list[Link] = []
    for field, text in _action_texts(action):
        out += text_links(text, ledger_ids, root, field, check_commits, resolved)
    return out


def _resolve_for(texts: list[str], root: Path | None, check_commits: bool) -> dict[str, bool | None]:
    """One batch for every commit token of `texts`; an empty map when nothing can be checked
    (then every commit link reads None, as before)."""
    tokens = [t for text in texts for t in commit_tokens(text)]
    if root is None or not check_commits or not tokens:
        return {t: None for t in tokens}
    return resolve_commits(root, tokens)


def all_links(roadmap: Roadmap, root: Path | None, check_commits: bool = True,
              only: set[str] | None = None) -> dict[str, list[Link]]:
    """Links of every action, or with `only` just those ids (the others get an empty list),
    all commits of the scope resolved in one git call."""
    scope = [a for a in roadmap.actions if only is None or a.id in only]
    resolved = _resolve_for([t for a in scope for _f, t in _action_texts(a)], root, check_commits)
    return {a.id: links_of(a, roadmap, root, check_commits, resolved) if a in scope else [] for a in roadmap.actions}


def ledger_links(roadmap: Roadmap, root: Path | None, check_commits: bool = True) -> dict[str, list[Link]]:
    """Commit, trace and ledger down-links found in each ledger entry's text, keyed by entry id;
    `field` is the entry id. docs/praxis-spec.md, section 1, Flags: the commit flag reads these beside the actions'."""
    ledger_ids = {e.id for e in roadmap.ledger}
    resolved = _resolve_for([e.text for e in roadmap.ledger], root, check_commits)
    return {e.id: text_links(e.text, ledger_ids, root, e.id, check_commits, resolved) for e in roadmap.ledger}


def text_ground(action: dict, strip_mentions: bool = False) -> str:
    """What is left of source+evidence once the resolvable references are removed:
    segments split on ';', each stripped of references and separators, empty ones dropped.
    `strip_mentions` also removes bare `a<n>`/`C<n>`/`L<n>` ids (the context view resolves those)."""
    kept: list[str] = []
    for fld in ("source", "evidence"):
        for seg in (action.get(fld) or "").split(";"):
            t = LEDGER_RE.sub(" ", seg)
            t = TRACE_RE.sub(" ", t)
            t = COMMIT_RE.sub(" ", t)
            if strip_mentions:
                t = MENTION_RE.sub(" ", t)
            t = re.sub(r"sha256\b", " ", t)
            t = re.sub(r"\s+", " ", t).strip(" " + TRAILING + "(")
            if re.search(r"[A-Za-z0-9]", t):
                kept.append(t)
    return "; ".join(kept)

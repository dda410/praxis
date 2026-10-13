# praxis — the contract

This file is the source of truth for what the `praxis` CLI reads and
writes and for the words the skill must keep exact. The skill
(`.claude/skills/praxis/SKILL.md`) says how the loop is run; this file
says what the loop runs on. When the two disagree, this file wins and
the skill is fixed. The practice both implement is the manifesto beside
them, `manifesto/reality-first.org`.

## 1. The file: `ROADMAP.org`

One file per repository, at its root, in the repository the work lives
in. The CLI never writes it. Format version is `#+PRAXIS: 3`; the parser
also accepts `2`, which differs only by the absence of `#+RECONTACT:`.

### Header

```org
#+TITLE: <repo> <slug> — roadmap
#+SIGNER: <name>
#+OPENED: <YYYY-MM-DD>
#+CLOSED: <YYYY-MM-DD>              ; absent while open
#+PRAXIS: 3                         ; required; 2 accepted
#+TODO: TODO STRT SIGNAL | DONE SKIP ; required, exactly this
#+CHECK_TIMEOUT: <seconds>          ; optional, default 30; an integer
#+RECONTACT: <command>              ; optional; needs #+PRAXIS: 3
```

A file carrying `#+SETPOINT:` or a `* Status` section is a format-1
file and is refused with an error naming the line. A file at `2`
carrying `#+RECONTACT:` is a parse error naming the line.

### Sections, fixed names, in this order

**`* Setpoint`**, one clause per line:

```org
- C1 :: <clause text>. Met by: a5
- C2 :: <clause text>. Met by: a7 a8
- C3 :: <clause text>
```

- `C<n>` ids are assigned once and never reused.
- The clause text states what will be true at close, named by the trace
  that will exist: a commit, tag, branch, CI run, ticket state, or a
  file captured into `traces/`.
- `Met by:` is optional and, when present, ends the line with a
  space-separated list of action ids. Every id named must exist in
  Actions, otherwise a parse error. A clause with no `Met by:` is legal
  and flagged.
- Continuation lines are indented two spaces.

**`* Actions`**, one level-2 heading per action:

```org
** DONE a5 <title>
- source :: <down-link: what this action starts from>
- evidence :: <up-link: what it produced>
- check :: <shell command, run from the repo root; exit 0 = passed>
- done :: [<stamp>]
** SIGNAL a6 <title or the question that waits for a trace>
- source :: verbal <YYYY-MM-DD>
```

- Heading: `** <STATE> a<n> <title>`. State is one of `TODO STRT SIGNAL
  DONE SKIP`; a heading without one is a parse error. Ids are assigned
  once, never reused, never renumbered.
- Fields are description-list items `- <key> :: <value>` with keys
  `source`, `evidence`, `check`, `done`. An unknown key, or a key
  repeated, is a parse error. A missing field is an empty field.
  Continuation lines are indented two spaces and joined with a space.
- Pipes in `check` are literal. A `check` may use a shell glob under
  `traces/`; a glob counts as existing when it matches at least one
  file.
- Any other line under an action heading is a parse error: a line the
  parser silently lost would be a line the loop has lost.
- Action order is the signer's hand and carries no meaning. There is no
  dependency field.

**`* Ledger`**, an append-only list:

```org
- L1 [<stamp>] Registered prior at init: …
- L2 [<stamp>] a4 started: …
  continuation line
```

- Entry: `- L<n> [<stamp>] <text>`. `L<n>` is assigned once at append
  time; ids strictly increase down the file and the parser refuses a
  repeated or lower id. That is the append-only rule made checkable.
- No tags. `OPEN:` and `SUPERSEDES` have no meaning to the parser. A
  supersession is written in the text ("supersedes the entry of <date>
  on …"); an open question is a `SIGNAL` action.
- Entries are never edited and never reordered.

### States

`TODO`, `STRT` (started), `SIGNAL`, `DONE`, `SKIP`.

- `SIGNAL`: no world-trace yet, or an open question waiting for one. It
  may never become `DONE`.
- `SKIP`: struck. It must be named in at least one ledger entry.

### The stamp

```
[YYYY-MM-DD( Www)?( HH:MM)?( [0-9a-f]{8})?]
```

Date required; English three-letter weekday, time, and session optional,
in that order. The session is the first eight characters of
`$CLAUDE_CODE_SESSION_ID`, which names the transcript file of the
conversation that wrote the entry; the stamp is a pointer to a local
trace, not a label. The skill writes full stamps on every entry and
every `done` field, taken from `praxis stamp` at the moment of the
write. The signer may write a bare date by hand.

### `traces/`

A directory beside the file for captured evidence: things ephemeral or
external to the repository (a test log, a mail, a screenshot, a pasted
excerpt). Each capture names the action it grounds and its capture date
in the file name or a first line. Durable, addressable traces (commits,
tags, branches, CI runs, tickets) are referenced from `check` and
`evidence` directly, never copied. A verbal commitment can appear only
in `source` or in the ledger, and an action grounded only on one cannot
be `DONE`.

### Gates and checks

A **check** reads evidence that already exists: cheap, read-only,
idempotent, run on every `status`. A **gate** produces that evidence: a
test suite, a comparison, a release procedure. It lives as a script in
`traces/` or in the repository's own test tree, or as a documented
procedure; when the machine cannot run it, the signer runs it and the
output is captured. An action turns `DONE` only when its check passes
against the gate's output.

Design rule for a check: it reads committed objects (`git cat-file -e`,
`git merge-base --is-ancestor`, `git ls-files`, `git show <ref>:<file>`),
files captured under `traces/`, or pins in versioned files. It does not
read an environment (`.venv`, installed packages, bytecode) nor a ref
that can move or vanish, unless the check is about that ref. Checks are
shell commands taken from the file and run with `shell=True`: `praxis
status` on an untrusted clone executes whatever its checks say. Run it
only on roadmaps you signed.

### Check results

`passed`, `failed`, `absent` (empty check), `unclosable` (the check names
a `traces/` path that does not exist yet), `timeout`, `pending` (the
check exited **3**: the trace is being produced and is not readable yet).
`null` when checks were not run. `pending` and `unclosable` are results,
not violations; a `DONE` action carrying either is in violation like one
carrying `failed`.

### Invariants

Violations, reported by `status` and counted in its exit code:

| code | rule |
|---|---|
| `done_without_passing_check` | a `DONE` action must have a check and it must pass |
| `done_without_stamp` | a `DONE` action must have a `done` field |
| `no_source` | a `DONE` or `STRT` action must have a non-empty `source` |
| `skip_without_ledger` | a `SKIP` action must be named in at least one ledger entry |
| `phantom` | a non-`SIGNAL` action with an empty `source`: an item whose provenance reaches no trace |
| `dangling_link` | a `ledger L<n>` or `traces/<path>` named in `source` or `evidence` resolves to nothing; `traces/` accepts `*`, `?`, `{a,b}`; a commit that does not resolve is not a violation, since roadmaps cite other repositories |

### Flags

Readings of the file, reported beside the table and in the JSON, never
violations, and free to change without a version bump:

| flag | reading |
|---|---|
| `C<n>: no Met by` | nothing drives toward the clause |
| `a<n>: no up-link` | a `TODO`, `STRT` or `DONE` action with no path to a clause (see Up-link); `SIGNAL` and `SKIP` are exempt |
| `a<n>: done rests on a<m> <state>` | a `DONE` action whose `source` names an action that is not `DONE` |
| `a<n>: unclosable check (<command>)` | the check names a `traces/` path that does not exist yet |
| `a<n>: done stamp has no session` | the `done` stamp carries no session |
| `a<n>: check never seen failing` | a `DONE` action no `gate result:` or `reverted to STRT:` entry names with a result other than `passed`, and no gate result names with `Check seen failing on:`. Weak by design: it catches a check never exercised to failure, not one that fails for the wrong reason |
| `commits not in this repo: <sha> (<where>), …` | every commit-shaped token in `source`, `evidence` or ledger text that `git cat-file -e` cannot find here; `<where>` is `a<n> source`, `a<n> evidence` or `L<n>`; tokens after `sha256` are skipped. Permanent for a roadmap that cites another repository, which is the honest reading |
| `work since L<n>: <k> files changed after its stamp (<names>)` | files `git status --porcelain` lists whose modification time is later than the last ledger entry's stamp; a date-only stamp counts as its end of day; silent outside a git repository |
| `recontact: <line>` | one per output line of the `#+RECONTACT:` command when it exits non-zero |

### Up-link

Every artifact owes a down-link to its origin and an up-link to what it
fed. The down-link is enforced by `no_source` and `dangling_link`; the
up-link is derived and reported. An action's up-link path is the
shortest path to a clause through two edges that already exist in the
file: `Met by:` on a clause, and an action id named in another action's
`source` (ranges like `a1-a4` expand). Only `source` counts; `evidence`,
ledger text and clause prose are narrative. The path is computed on
every call and never written. `reaches` in the JSON carries it.

### Clause state

A clause is `met` when its `Met by:` list is non-empty and every listed
action is `DONE`. Computed, never written.

### Recontact

`#+RECONTACT: <command>` names a command the signer owns, run from the
repository root before any check unless `--no-checks` or
`--no-recontact` is given. It verifies that the paths to reality the
checks depend on are open (network, a registry, a token and its scope, a
ticket system) and refreshes local mirrors (a fetch in this clone or in
another the checks read). Exit 0 means every path open; otherwise one
line per closed path, each becoming a `recontact:` flag. Read-only on
the world. Its timeout is `#+CHECK_TIMEOUT`. Simple projects need none:
`traces/` reachability is already the `unclosable` result.

### Language

The skeleton is English and stays English: section names, state
keywords, field keys, `Met by:`, and the fixed ledger phrases below. The
content, titles, clause text, sources, ledger prose, is in the language
of the project or the practitioner, and a line that mixes the two is
correct. The parser reads only the skeleton and the stamp.

### Change policy

`#+PRAXIS:` is the version. A change to this section bumps it, and the
parser refuses a version it does not know.

## 2. The ledger's fixed phrases

The fixed phrases the skill writes are the only structure the ledger
has. The content after a phrase is prose in the project's language.

```
<ids> := a<n>( a<n>)*          one or more action ids, in file order

a<n> started: <intent>. [Stepwise: <step>; <step>; …. ]Prior: <…>. Regulates against: <…>. Tacit: <…>.
a<n> started under L<n>: <intent>. Prior: <…>. Regulates against: <…>. Tacit: <…>.
<ids> gate result: <result>. <what was seen>[ Check seen failing on: <known-bad state>.]
<ids> reverted to STRT: check <result>. <reason>
Recontact: <…>                 or   Recontact for <ids>: <…>
Correction to L<n>: <…>
Chain stopped under L<m> at a<N>: <reason>.
Chained act authorized: <ids> …
a<N> is stepwise: <step>; <step>; …
Registered prior at init: <…>
Case against the prior given: <…>. Signer: <kept | revised: "…">
Closed: setpoint met. Evidence: <…>
```

- A `started:` line names exactly one id. `gate result:` and `reverted to
  STRT:` may name several: one entry per event, with the reason in it. A
  bare `check failed.` and nothing else is never written.
- `Stepwise:` lists the steps the signer named, semicolon-separated. A
  `decide` entry may state `a<N> is stepwise: <steps>` ahead of the act;
  the `started:` line then copies them.
- `Check seen failing on:` names the known-bad state on which the check
  was observed to fail: the seeded error in its cheapest form.

### Entry kinds

Every entry has a derived `kind`, never written in the file, read from
its opening phrase and nothing else:

| kind | entries whose text starts with |
|---|---|
| `machine` | `Recontact:`, `Recontact for`, `<ids> reverted to STRT:`, `<ids> gate result:`, `Chain stopped under`, `Correction to L`, `Orient inside act` |
| `signer` | everything else, including `started:` and `started under` (they record the signer's intent and prior), `Chained act authorized:`, `Closed:`, and every `decide` entry |

A phrase misspelled is an entry misclassified.

## 3. The CLI

`praxis` is Python 3.9 or later, standard library only. It never writes
the roadmap. Every subcommand takes `--path FILE` to name the roadmap
explicitly; the root is that file's directory. Exit codes: 0; 1 when at
least one violation stands (`status` only); 2 for a missing file, a
parse error (the message carries `file:line: message`), or an unknown
id.

```
praxis status [--json] [--no-checks] [--no-recontact] [--color auto|always|never]
praxis check <a<n>>
praxis ledger [L<n>] [--last N] [--for a<n>] [--signer | --machine] [--color …]
praxis context <id>... [--no-checks] [--width N] [--color …]
praxis stamp
praxis checkpoint [--no-checks] [--color …]
```

**`status`** parses the file, runs the recontact hook if any, runs every
check, and prints the table view or, with `--json`, the document below.
`--no-checks` runs nothing and reports `result: null`. Colour only on a
terminal by default, honouring `NO_COLOR`; JSON is never coloured.

**`check a<n>`** runs one action's check and prints its result and
output.

**`ledger`** prints the ledger as written, one entry per line with
continuation lines folded, and runs no checks. Any filter prints first
how many entries of the whole it hid, `(k of n entries not shown)`, so a
subset is never mistaken for the record. `--signer` and `--machine`
filter by kind.

**`context`** prints the neighbourhood of one or more ids (`a<n>`,
`C<n>`, `L<n>`) one hop out, as one merged view in four bands separated
by rules: clauses; actions, the focus first with its fields, its
`reaches` path or `no clause`, and any violation codes; ledger entries;
grounds (traces, commits, text the CLI cannot resolve). Position carries
direction: what sits above the focus rests on it, what sits below is
what it rests on; where a band mixes directions a relation word sits
right-aligned (`met by a10`, `cited by L3`, `names a10`). Connections
are `Met by:`, the down-links, and mentions: any bare `a<n>`, `C<n>` or
`L<n>` in a clause's text, an action's `source` or `evidence`, or a
ledger entry's text, ranges expanded. A mention that names nothing
prints `MISSING`; it is not a violation. Checks run only for the actions
shown.

**`stamp`** prints the stamp of this instant from the clock and
`$CLAUDE_CODE_SESSION_ID`, never from a model. With the variable unset
it prints a stamp without a session and `no session` on stderr, exit 0.
It reads no file. One event, one stamp: a gate result entry and the
`done` field it justifies carry the same stamp; two writes at different
moments carry different ones.

**`checkpoint`** prints, never writes, the mechanical half of a
checkpoint document: for each clause in file order, then each action in
file order, then the entries that mention neither, the ledger entries
that mention the id, latest first, folded to one line each, signer
entries before machine entries, with `⟂ supersedes` on entries whose
text contains "supersedes the entry" or "overtakes" and `⟂ stepwise` on
entries carrying `is stepwise:`. Each block opens with the id's current
state and check result. The supersession relation itself is free text
and is not resolved by the CLI.

### JSON document

```json
{
  "path": "ROADMAP.org", "branch": "main", "format": 3,
  "title": "…", "signer": "…", "opened": "YYYY-MM-DD", "closed": null,
  "setpoint": [
    {"id": "C1", "text": "…", "met_by": ["a5"], "met": true}
  ],
  "actions": [
    {"id": "a5", "title": "…", "state": "DONE",
     "source": "…", "evidence": "…", "check": "test -f …",
     "done": {"date": "YYYY-MM-DD", "time": "HH:MM", "session": "0123abcd"},
     "result": "passed", "violations": [], "clauses": ["C1"],
     "reaches": ["a5", "C1"],
     "links": [
       {"kind": "commit", "ref": "0123abc", "field": "source", "resolved": true},
       {"kind": "trace", "ref": "traces/a5-….log", "field": "evidence", "resolved": true},
       {"kind": "ledger", "ref": "L3", "field": "source", "resolved": true}
     ]}
  ],
  "ledger": [
    {"id": "L2", "date": "YYYY-MM-DD", "time": "HH:MM", "session": "0123abcd",
     "kind": "signer", "text": "…"}
  ],
  "recontact": null,
  "flags": ["C3: no Met by", "a2: no up-link"],
  "summary": {"done": 1, "open": 2, "signal": 3, "clauses": 3, "clauses_met": 1,
              "violations": 0, "phantoms": 0}
}
```

- `done` is `null` when the field is absent; `time` and `session` are
  `null` when absent from a stamp.
- `result` is one of the check results above, or `null` when checks did
  not run.
- `links` lists the down-links found in `source` and `evidence`
  (`commit`, `trace`, `ledger`), each with `resolved` true, false, or
  null when not checkable here.
- `recontact` is `null` when the header has no hook, otherwise
  `{"command": "…", "exit": 0, "lines": []}`.
- `flags` is the list the table prints, computed once so that the skill
  and any other reader take it from here instead of re-deriving it.

### Table view

```
<title>
branch: main   signer: …   opened: YYYY-MM-DD

C1   ✅  <clause text>  (a5)
C2   ·   <clause text>  (a6)

a5   DONE    ✅  <title>
a6   SIGNAL  ⛔  <title>

flags:
  …
done 1  open 2  signal 3  clauses 1/3  violations 0  phantoms 0
```

Glyphs: `✅` passed, `❌` failed, `⛔` unclosable, `⏳` pending, `∅`
absent, `·` not run.

## 4. Chained act

`/praxis act a<n> a<n> …` with two or more ids is a chain: several
turns of the loop without the signer present, allowed only by a
`Chained act authorized:` entry that names those ids in that order, with
an intent and a prior per action, any retry cap, and a turn cap. The
entry alone never starts a chain; a sub-sequence of its ids is valid,
which is how a stopped chain resumes.

`decide` writes the entry only if every id exists and is `TODO`, `STRT`
or `DONE`; a `SIGNAL` or `SKIP` id, or one with a standing `is
stepwise:` entry, is refused and nothing is written. The entry names no
how; the how lives outside praxis and the entry may point to it.

A chain turn is an ordinary act turn with three substitutions: the offer
is skipped, the entry has chosen; the started line reads `a<N> started
under L<n>:` with the entry's intent and prior, taking nothing from the
signer; a gate that must run elsewhere ends the chain. A retry is the
agent working further inside the action and running the gate again,
counted once per gate run.

Stops, a closed list; the chain ends at the first that holds:

- the check is not `passed` and the retry cap is spent (none named: one
  attempt);
- orient reverted an action, or quoted a trace that contradicts a state
  or a ledger entry;
- a violation stands that was not standing at the start;
- the next id is `SIGNAL` or `SKIP`;
- the gate must run elsewhere;
- the check reads `pending`;
- the next id has a standing `is stepwise:` entry;
- the turn cap is reached (none named: the number of ids given);
- the ids are exhausted, or every clause is `met`.

Every stop appends `Chain stopped under L<m> at a<N>: <reason>.` and
prints the table. A chain never adds, strikes or reorders an action,
never continues past a stop, never writes a decision, never touches a
`SIGNAL`, and takes intent and prior from the entry alone.

## 5. Converting a format-1 file

Older roadmaps carried `#+SETPOINT:` clauses in the header, a `* Status`
table with `s<n>` rows, and a ledger without ids. The CLI refuses them.
To convert one, write the new file beside the old and let the signer
review before it replaces anything:

- `s<n>` becomes `a<n>` with the same number, in headings and in ledger
  text; capture file names keep their old prefix, a path is a path.
- `#+SETPOINT:` clauses become the Setpoint section, one line each, with
  `Met by:` filled from the rows that plainly satisfy each clause; the
  signer corrects at review.
- Each table row becomes an action heading with `source`, `evidence`,
  `check`; `\vert` becomes `|`. `DONE` rows get a `done` field with the
  date of the ledger entry that recorded the gate result, and the
  session where it can be identified, else date only.
- Ledger entries keep their text verbatim and their date-only stamps,
  and receive ids `L1, L2, …` in file order. `OPEN:` and `SUPERSEDES`
  prefixes stay as text.
- Open questions and leftover items with no other home become `SIGNAL`
  actions with `source :: ledger L<n>`.
- The result must pass `praxis status --path` with no parse error; the
  flags it raises are reported to the signer, not silenced.
- A final ledger entry records the conversion and the id map.

# praxis

**A reality-first loop for work that must be answered for.**

This repository holds three things that belong together:

- **A manifesto**, [*Reality First*](manifesto/reality-first.org) (also as a [PDF](manifesto/reality-first.pdf)), which states a working practice: organise any work that accumulates against a reality as a self-correcting loop, let the traces the work leaves behind outrank every plan written about it, let a machine absorb the friction of keeping those traces honest, and keep exactly one act human: the judgment that turns what reality shows into a committed, signed choice.
- **A practice**, praxis, which is that loop applied to one bounded delivery with one roadmap and one signer.
- **A tool**: a dependency-free command-line program that re-derives the roadmap from the traces, and a Claude Code skill that runs the loop with you in conversation.

You can use the tool without reading the manifesto. You will want to read the manifesto once the tool has surprised you.

## The problem it answers

Plans drift from the work they describe. A roadmap written on Monday is a belief by Friday, and keeping it honest by hand costs so much articulation that most people stop. Language models make a second failure cheap: hand the whole thing over, plan and judgment together, and get back a tidy map of work that never touched reality.

praxis takes the opposite bet. The machine does everything around the loop. It records, checks, re-derives, narrates. It never decides what to do next, never declares something done without evidence, and never edits history.

## Two principles

1. **Representations are answerable to traces.** A commit, a test log, a tag, a captured mail: those are what happened. The roadmap is re-derived from them and is disposable. Where the two disagree, the traces win.
2. **One node is non-delegable.** The person who signs the roadmap reads what the traces show, chooses, and answers for the choice. Everything else can be handed to a machine.

Neither principle works alone. A map answerable to traces with nobody judging it is a dashboard. A judge with no traces is a planner guessing.

## How the loop runs

One file, `ROADMAP.org`, in the repository the work lives in.

- A **setpoint**: a few clauses stating what will be true at close, each naming the trace that will exist when it is met, and the actions that meet it.
- **Actions**, each with a **source** (the trace it starts from), a **check** (a shell command that reads committed objects or captured files and exits 0 only when the trace exists), and, once done, **evidence** and a stamped **done** line.
- A **ledger**: append-only, stamped entries. Your prior before you start an action, the case against it, what you decided and on what evidence, what the machine saw when a check failed.

The command `praxis status` parses the file, runs every check, and prints what the traces support. An action you believe done but whose check fails is reverted to started. An action whose check passes is marked done with its evidence. A clause nobody imposed, an action no clause needs, a done that rests on something undone: each is flagged. The map is never trusted over the world.

The Claude Code skill drives the same loop as a conversation: `init` asks for your prior before it looks at anything and gives the case against it; `orient` re-contacts reality and corrects the map; `act` takes one action from your intent to its gate; `decide` records a decision; `contradict` attacks your current reading with traces; `checkpoint` prints the decisions that still bind; `close` refuses unless every clause is met.

## What praxis refuses to do

- Choose or recommend the next action unasked.
- Mark an action done without a passing check.
- Edit or reorder a ledger entry.
- Author an action with no trace behind it.
- Write how it would run an action before your own intent and prior are on record.

These refusals are the point. They keep the one human node human.

## Install

The CLI is Python 3.9 or later, standard library only. Checks run through your shell and usually call `git`.

```sh
uv tool install git+https://github.com/dda410/praxis
# or
pipx install git+https://github.com/dda410/praxis
# or
pip install git+https://github.com/dda410/praxis
```

The skill is a single file for [Claude Code](https://claude.com/claude-code). Clone the repository and link or copy the skill folder into your skills directory:

```sh
git clone https://github.com/dda410/praxis
ln -s "$PWD/praxis/.claude/skills/praxis" ~/.claude/skills/praxis
```

The CLI works without Claude Code. The stamp on ledger entries carries a session id when one is available and says so when it is not.

## Quick start

In the repository where the work happens:

```sh
praxis status            # table of clauses, actions, check results, flags
praxis status --json     # the same as data
praxis check a3          # run one action's check and show what it saw
praxis ledger --last 5   # the ledger as written
praxis context a3        # the neighbourhood of one action: clauses, entries, grounds
praxis checkpoint        # the decisions that still bind, grouped, never saved
praxis stamp             # the stamp of this instant
```

In Claude Code, from the same repository:

```
/praxis init        # one bounded delivery: setpoint as clauses, actions seeded from existing traces
/praxis orient      # re-derive the map from the traces
/praxis act a1      # one turn of the loop on one action
/praxis decide      # record a decision, with its evidence or as tacit
/praxis contradict  # hear what the traces hold against your current reading
/praxis close       # only when every clause is met
```

## The file, in brief

```org
#+TITLE: my-service 2.0 — roadmap
#+SIGNER: Your Name
#+PRAXIS: 3
#+TODO: TODO STRT SIGNAL | DONE SKIP

* Setpoint
- C1 :: The service runs on the new runtime, shown by a green CI run on main. Met by: a1 a2

* Actions
** DONE a1 Retarget the runtime
- source :: pyproject.toml at abc1234
- evidence :: commit def5678
- check :: grep -q 'requires-python = ">=3.13"' pyproject.toml
- done :: [stamp]
** TODO a2 Run the suite on the new runtime
- source :: README procedure
- evidence ::
- check :: f=$(ls traces/a2-pytest-*.log | tail -1) && grep -qE '[0-9]+ passed' "$f"

* Ledger
- L1 [stamp] Registered prior at init: "…"
- L2 [stamp] Case against the prior given: …. Signer: kept.
```

A `SIGNAL` is an open question with no trace yet; it can never become `DONE`. A `SKIP` needs a ledger entry naming it. The full contract lives in the skill file and is what the CLI enforces.

## Who this is for

The manifesto was extracted from several working systems that converged on the same design: a personal log kept across years, a data-science methodology, a compiler project, a bounded delivery against a brief agreed in writing with its recipient. The tool was built in daily use and tested on package migrations, on work whose evidence came from outside the repository, and on the publication of itself.

Nothing in the loop is specific to software. It needs a reality that leaves traces, a delivery that can be bounded, and one person willing to sign. If your work has those three, praxis may apply. If it has them and praxis does not fit, that is the most useful thing you could tell us.

## Participate

- **Issues** for anything that is wrong or missing in the tool or the skill: a check that misreads, a flag that fires falsely, a command you expected.
- **Discussions** for how the practice applies to your work, where it does not, what a reality-first loop would need in your field, and what you tried. Open one even if you have no code to show.

Pull requests are welcome for the tool. Changes to the manifesto are discussed first; it is a signed text and its revisions are dated strikethroughs, not rewrites.

## Read further

- The manifesto: `manifesto/reality-first.org`, also rendered as `manifesto/reality-first.pdf`.
- The skill: `.claude/skills/praxis/SKILL.md`, the complete behaviour the CLI and the conversation follow.
- `praxis --help` and `praxis <command> --help`.

## Status and limits

One roadmap per repository, one signer, one bounded delivery at a time. The roadmap is org text; no other format is read. There is no graph view and no server. The CLI reads your repository and nothing else. The practice is young; the manifesto's own falsifiability section says what would prove it wrong.

## Licence

The CLI, its launcher, the tests and the Claude Code skill are released under the MIT License; see `LICENSE`. The manifesto, *Reality First*, and its rendered PDF are released under the Creative Commons Attribution 4.0 International licence (CC BY 4.0); see `manifesto/LICENSE`. Both keep the author's name on the work and let you adapt it, as long as changes are marked and not presented as the author's.

# clay-skill-creator

Turn what you already built in Clay — a table, a workflow, or just an idea in your head — into a
**portable Clay skill** you can submit to the Marketplace.

A skill is a single Markdown file (`SKILL.md`) plus optional supporting files. It describes a
repeatable job in enough detail that someone else's agent can run it in *their* workspace, with
their own data and their own credentials. That last part is the whole design constraint: a skill
that only works in your workspace is not a skill, it is a note to yourself.

## Four ways in

| | Start from | Use when |
|---|---|---|
| **I just have an idea** | a conversation | nothing is built yet, or what you built holds little recoverable logic |
| **From a Clay table** | a table you already built | you built the thing and want it packaged |
| **From a Clay workflow** | a workflow you already built | same, for a workflow — read from its configuration, never from a run |
| **I have an existing `SKILL.md`** | a file you already have | it is written; you want it validated and submitted |

The idea route and the existing-`SKILL.md` route touch Clay at no point — no sign-in, no CLI. The
table and workflow routes read configuration only, and the workflow route needs `clay login`.

All four end the same way: a finished `SKILL.md` **you review**, and then you choose how it goes —
upload it at [`marketplace.clay.com/submit`](https://marketplace.clay.com/submit), or have the agent
send it with `tools/submit_skill.py`. **Nothing is submitted without your explicit yes**,
which is enforced rather than promised: the send command refuses without a token only the preview
mints, and the token stops matching if the file changed after you saw it.

See [`SUBMITTING.md`](SUBMITTING.md) for both routes in full, what a submission carries, and what is
not built yet.

## Start here

**[`START-HERE.md`](START-HERE.md)** — install, sign in, then create the skill. If you are pasting a link to
someone, paste that one.

The rest is reference, in the order you will want it:

1. [`PREREQUISITES.md`](PREREQUISITES.md) — install and authenticate, on **Claude Code, Codex or
   Cursor**. It does not restate Clay's procedure; it links
   [Clay's own](https://github.com/clay-run/agent-plugins/blob/main/GETTING_STARTED.md) and hands you
   to the plugin's `setup` skill. One `clay login` covers both the `clay` command and the Clay MCP
   server. It adds only the two steps that are ours: confirm your workspace, and **preflight** whether
   the table path is open to you — one free call, before you spend anything on setup.
2. Your route: [`workflows/table-to-skill.md`](workflows/table-to-skill.md),
   [`workflows/workflow-to-skill.md`](workflows/workflow-to-skill.md), or
   [`workflows/interview-to-skill.md`](workflows/interview-to-skill.md).
3. [`DETERMINISM.md`](DETERMINISM.md) — **read this before writing any step that spends credits.** The
   four things such a step has to name, the name-it-confirm-it-fail-loudly rule, the waterfall shape,
   and the traps that have cost real debugging: a column named for revenue holding a headcount, size
   bands arriving as strings, a plural action name that accepts one item, a dead company enriching
   perfectly well.
4. [`NO-FUNCTION-EXISTS.md`](NO-FUNCTION-EXISTS.md) — **read this while you are still talking, not
   after drafting.** The jobs the platform has no function for: scoring, dedupe and CRM merge
   execution, batch email validation, question-answering, identified website visitors. If someone
   says "and then score them", that has to surface in the conversation rather than in a draft that
   names something imaginary.
5. [`references/functions/`](references/functions/README.md) — **the observed surface, so you can name
   a function instead of writing "enrich the company".** Read its index, then
   `platform-surfaces.md`, then **exactly one** job leaf — identity, company enrichment, contacts,
   email validators, jobs, funding and news, scraping, or search. Each leaf carries the arms that
   answered, the fields they really return, which of them disagree with each other and by how much,
   and its own date range. They are evidence for traps, not a price list: read the actual charge from
   the response, never a figure remembered from a file.
6. [`SKILL-TEMPLATE.md`](SKILL-TEMPLATE.md) — the body section by section, and the one section every
   submission is required to have.
7. [`PACKAGE-LAYOUT.md`](PACKAGE-LAYOUT.md) — what a package may and may not contain.
8. [`VALIDATION.md`](VALIDATION.md) — check it locally before you submit.
9. [`SUBMITTING.md`](SUBMITTING.md) — the form, and the send-it-from-here path.

**This repo is an installable plugin.** Two commands, and nothing needs to be fetched at runtime:

```
codex plugin marketplace add sungwanjo-clay/clay-skill-creator      # or /plugin marketplace add … in Claude Code
```

then install **`clay-skill-author`**. The skill lives at
[`plugin/skills/clay-skill-author/`](plugin/skills/clay-skill-author/) — the whole flow, its own
validator, the worked examples. Reading it is the fastest way to see exactly what the flow does.

## Where to read finished skills

**[`examples/`](examples/) is a curated teaching set** — finished skills picked for the quality of the
reasoning rather than to cover package shapes, plus one that exists nowhere else: a **low-yield** case,
showing what an honest skill looks like when the source table did not hold enough to convert. That
fourth one is the reason this directory exists at all.

If you want to see how a declared-inputs table is written, or how a skill states what it does *not*
claim, read these.

**`skills/` is different: it is other people's skills, and it is not part of this kit.** Every
directory under it is `skills/<author>/<skill>/`, written by whoever wrote that skill. Nothing in
this repository's tooling generates or removes anything there — that tree has one writer, and it is not
the kit. Read those to see the range of what the marketplace holds; read `examples/` to see the format.

**Not all of them are published, so do not read this tree as the marketplace catalogue.** Of 59
directories, 25 arrived by a publication and match their listing byte for byte; 34 were imported by
hand, and 30 of those had **no matched active publication** in the audit of 2026-09-25. The 30 under
`skills/clay/` are library skills, installable from this repository. Whether they were ever submitted
is not established — an unmatched path is not proof of that, only of what this audit could match — so
read them as skills you can install from here rather than as listings. This paragraph replaces a
sentence that called the whole tree "published skills": that was wrong about 34 of 59, and it is where
the "59 published skills" figure quoted elsewhere came from.

Internal evaluation records (`EVAL.md`) are excluded from everything published here.

## If your agent cannot read this repository

The one-liner in [`START-HERE.md`](START-HERE.md) hands your agent a GitHub link, and some sandboxes cannot fetch one — no outbound
network, or a blob page it cannot parse. **Then tell it to fetch the raw file instead:**

```
curl -fsSL https://raw.githubusercontent.com/sungwanjo-clay/clay-skill-creator/main/START-HERE.md
```

That is a different mechanism from a `git clone` or a web search, and it is the one that works when
those fail. If it also returns nothing, the sandbox has no egress at all — then **install the skill
instead of fetching the docs**: `clay-skill-author` carries this whole procedure, its own validator
and the worked examples, and loads from disk with no network. See `SUBMITTING.md`.

**The tell that your agent gave up and improvised**: it names no files from this repository. Ask it
which files it read. If the answer is a confident plan with no filenames, it fell back to a generic
skill-creation workflow and whatever it produces will look right and be unrelated to any of this.

## Three things that will save you a rejected submission

**Your table's handles do not travel.** Column ids, table ids, saved-view names and auth-account
handles exist only in your workspace. Every one of them has to become a *declared input* the
installer supplies. The converter does this for you; the local validator catches what it missed.

**Numbers get checked against your formulas.** Any threshold the skill states is compared against
the formula it came from, and a mismatch stops generation. This exists because a transcription error
is invisible to the person best placed to catch it — your table ran in production, so a skill that
misquotes it still looks like it works.

**"Verified" is narrow, on purpose.** A generated skill says, in its body under **What this skill
does not claim**, exactly what was and was not checked. A table-derived skill is always
`partial`: the comparison runs on your machine at generation time, the source formula does not
travel with the package, so nobody downstream can re-run it. That is a limit of the method, and the
skill says so rather than implying more.

## What this reads, and what it never touches

Table → skill reads **column configuration only**, scoped to tables you own:

```
clay whoami                              your identity
clay tables list --filter owner.id=<me>  your tables, never a bare list
clay tables columns list <tableId>       column ids, names, types
clay tables columns get  <tableId>       the recipe: formulas, prompts, input wiring
```

Those four commands are the entire surface. It never reads a row, never runs a column, never writes
anything, and never executes a Clay action. The list command is owner-scoped because a shared
workspace lists everyone's tables and table *names* alone can disclose customers and deals.

**Three of those four are served by Clay's public observability API, which the CLI's help states is
enabled per workspace.** An earlier version of this paragraph added "and available on Enterprise
plans" — that came from Clay's own docs rather than a test, and a test refuted it: all four commands
returned exit `0`, recipes included, on a brand-new non-onboarded workspace at the bottom of the range.
Exit `3` is real but **we cannot say what enables it**, so this file no longer names a tier. If you hit
it the table path is closed to you — the interview path is unaffected and reaches the same finished
skill. `PREREQUISITES.md` step 1b checks this in one call, before you install
anything you would not be able to use.

## Licence

**MIT** — see `LICENSE`. Copy a skill, change it, ship it, sell it; keep the notice.

That applies to everything here, `examples/` included. They exist to be taken apart
and reused, and a corpus published as "read these" that grants no right to copy them would be an
invitation that is not one.

Nothing about the licence changes what you owe your own installers: a skill you write from these
still has to name what it runs, what it costs, and what it does not claim. That is a quality bar,
not a legal one.

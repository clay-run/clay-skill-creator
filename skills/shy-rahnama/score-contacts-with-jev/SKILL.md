---
name: score-contacts-with-jev
description: |
  Build a contact lead-scoring workflow in Clay that uses Jev, TypeSafe's decision model, to
  judge each person (their likely role in the purchase, their seniority, whether they are a
  prospect at all) and plain code for everything numeric, including the company's own fit tier.
  The agent starts from what it already knows about your buyers (memory, notes, persona docs in
  your folder), interviews you only for the gaps, and turns that into a rubric of rules and Jev
  questions: yes/no Nouls, categories and scales. It previews the rubric on ten of your real
  contacts, then builds a callable Clay workflow that takes a person's context from a Clay
  table, a saved Audiences audience or any webhook and returns a 0 to 100 score, a tier, the
  reasons, and the answers worth a second look. It can carry in the account's tier from your
  account scoring, so a VP at a poor-fit company does not outrank a manager at your best one.
  Works with a TypeSafe key or an OpenRouter key, kept in a local .env and in a Clay connection,
  reusing either if you already have one. A few cents per thousand contacts. Use whenever
  someone asks: score my contacts or leads, persona fit score, rank the people on my list, which
  of my contacts is the decision maker, lead scoring for people in Clay, qualify contacts with
  Jev, or set up Jev or TypeSafe in Clay for contacts. Do NOT use it to score companies
  (score-accounts-with-jev does that), to find or enrich people, to route or assign leads, to
  push scores into a CRM or sequencer, or to train a model on won and lost deals.
category: score-and-qualify
personas: [revops, sales-development]
mechanism: workflow
touches: writes-records
keywords: [lead-scoring]
---

# Score contacts with Jev (Jev judges the person, code counts the rest)

**The insight: a contact score is two different kinds of fact, and only one of them is about the
person.** "Would this title own the budget?", "is this a recruiter?", "how senior is 'Head of Fleet
Ops'?" are judgments about the person, and titles are messy enough that only a model reads them
well. "Is their company an A?", "did they start this role in the last four months?", "how many
points is that?" are lookups and arithmetic. Ask a model for "a lead score from 0 to 100" and it
blends both into a number nobody can decompose, and quietly lets a VP at a poor-fit company outrank
a manager at your best account.

The evidence is Jev's own documentation. TypeSafe publishes what Jev 1.13 is bad at, and the top of
the list is numbers, counting and comparing dates; it reads literally; it degrades when the record
carries fields the question does not need. Its recommended pattern for scoring is to break the
judgment into atomic questions and **combine them with weights in code**. And Jev returns a
probability for every option, so a score can use how sure it was.

What follows is the whole design:

- **Rules** (account tier, time in role, lists) are worked out in the workflow's code step. Free,
  exact. The account's tier from account scoring is one of them.
- **Questions** (Jev's Noul, Choice and Score) are sent in **one request per contact**, with only
  the fields they read. About $0.042 per million input tokens and output is free: a few cents per
  thousand contacts.
- **Points are expected values over Jev's probabilities.** A 30-point "decision maker" Jev is 60%
  sure of adds 18. An unsure answer moves the score less than a sure one, in either direction; it
  never flips a verdict outright.
- **Missing data never poses as a verdict.** A contact without a title is `not_scored`; one the data
  cannot judge is `insufficient_data`, not a D; above that bar, every criterion with no data earns
  nothing and is named. A recruiter comes back `disqualified`.
- **The preview is the workflow.** The ten-contact preview runs the identical code the Clay step
  runs, so what the installer approves is what they get.

> **Measured.** Run live against Jev (TypeSafe) and a Clay workspace: a VP of Operations at an
> A-tier account scored 96 A in Clay and in the local preview alike, and a recruiter was
> disqualified. The build caught Clay attaching an unrelated connection to the Jev step and refused
> to publish. The live checks, and what was not run, are in `references/live-checks.md`.

> **This skill is not finished when the rubric is agreed.** It is finished when the workflow is
> published, one contact has gone through it in Clay and matched the local preview, and the
> installer has been shown how to call it. If you stop early, say which step you stopped at and the
> command that resumes it.

## How to talk to the installer

- **Every question is a choice they click**, asked with the host's question tool (`AskUserQuestion`
  in Claude Code), one decision at a time, likely answer first, free text only as "Other". Never a
  paragraph of questions.
- **Never ask what you already know or can look up.** Your memory, this conversation, and files in
  the working folder come first (Step 2). Table columns, audience fields and whether a key exists
  are commands.
- **Before any question, apply the test: does the answer change the rubric or the build?** If not,
  do not ask it, and do not defer it to a later step either.
- **Run every command yourself**, in the background when it waits on the installer. The installer
  only does what needs a person: pasting a key into a box, creating a connection in Clay's UI, and
  deciding.
- Show names, never ids, in anything the installer reads.

## Declared inputs

**Nothing here ships with a value.** Where a default is offered it is named, and accepting it is
recorded as borrowed (`"origin": "default"`) and said at delivery.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Where contacts come from** | a Clay table, a saved Audiences audience of people, or "another system" (webhook). Picked from a list the agent reads | no default. It decides which fields exist, so which criteria are possible |
| **What they sell** | a line or two, **found in the agent's context first**; asked only if not | stop: no rubric can be written without it |
| **The buying roles** | who signs, who champions, who is consulted, described by function and title | stop at Step 2. Never invented |
| **Seniority that matters** | whether senior is better, or a level is the sweet spot | a 0-to-top seniority scale is offered, recorded as borrowed if accepted |
| **People who are never prospects** | recruiters, students, consultants, competitors' staff, or "none" | "none" is a real answer; ask, never assume |
| **The account's fit** | a column or field carrying the company's tier or score, usually from the account skill | the criterion is left out, and the card says a poor-fit company's VP can outscore a best-fit manager |
| **Signals worth points** | only those the data carries (new in role, recent job change) | left out |
| **Tier cut-offs** | what an A must reach | A≥70, B≥45, C≥25 offered, recorded as borrowed if accepted |
| **A Jev key** | TypeSafe or OpenRouter. Found in the environment, `./.env` or `~/.config/jev-lead-score/.env` (shared with the account skill); otherwise saved there through a password box | stop at Step 4: nothing can be previewed |
| **The same key in a Clay connection** | an existing HTTP API connection named by the installer (the account skill's, if built), or a new one they create in Clay's UI | stop at Step 6: the workflow cannot call Jev |

**Not asked, ever:** column or field names (read and shown as a mapping to correct), which fields
the score writes (fixed), a callback URL (the caller's own), whether to preview (always), the
provider when only one key exists, point values for every option (proposed in the draft and
corrected there), and any key in the chat.

### The workflow's interface: prescribed by the rubric

Inputs are the rubric's `inputs`, one flat field each, plus `source_ref` (echoed back for joining).
A typical contact rubric reads `full_name` and `title` (required), `headline`, `company_name`,
`account_tier` and `started_role_on`. Output, every key always present:

| Key | |
|---|---|
| `lead_score` | 0 to 100 integer |
| `lead_tier` | the rubric's tiers (A, B, C, D by default), or the status when not `scored` |
| `score_status` | `scored` · `disqualified` · `insufficient_data` · `not_scored` · `failed`. Five, no sixth |
| `score_reasons` | what counted for the record "(+25)", what counted against it "(2 of 25)", and what had no data |
| `needs_review` | answers under the confidence floor, with Jev's split; `none` otherwise |
| `coverage_pct` | how much of the rubric the data let Jev and the rules judge |
| `criteria_json` | every criterion: answer, confidence, points, status |
| `rubric`, `jev_model`, `jev_cost_usd`, `error`, `source_ref`, `scored_at` | provenance |
| `record_id`, `isTerminal` | plumbing: the audience record written to, and the flag a run is settled on |

## What this skill touches

- **Reads**: the agent's own context (memory, this conversation, files in the working folder) for
  what the installer sells and who buys it; a saved account rubric under
  `~/.local/state/score-accounts-with-jev/`, if one exists; the column list and up to ten rows of
  the table, or the field list and up to ten records of the audience, the installer picks (Step 1,
  Step 5); Clay's action catalogue; the workspace name.
- **Writes**: a rubric, preview results and build state under
  `~/.local/state/score-contacts-with-jev/`; the Jev key into a `.env` file only through the
  password box, at mode 0600, by default `~/.config/jev-lead-score/.env`, never into a file git
  would commit. In Clay: one workflow "Jev lead score: contacts · <rubric>" (Step 7); with an
  audience, a second workflow and seven "Jev …" fields on people records, adopted if they already
  exist. That audience workflow then **writes those seven fields onto each person record** it
  scores, and never writes on a failed Jev call. The table workflow writes onto the rows of any
  table later bound to it. Only when a wrong connection is fixed through Clay's default (Step 7),
  the installer changes which connection is the workspace default, then changes it back.
- **Sends**: for each scored contact, the fields the rubric's questions read (typically job title
  and profile headline) to Jev at TypeSafe, directly or through OpenRouter. Names, emails and phone
  numbers are not sent unless a question reads them, and a rubric should not need them.
- **Never**: asks for, prints or stores a key in the chat or in a workflow step; writes a key into a
  file git would commit; clears or blanks a field; overwrites a score when Jev failed; edits a
  table's columns; contacts anyone; writes to a CRM or a sequencer; deletes anything outside its own
  nodes.
- **Halts**: Step 1 `other`, Step 2 `other`, Step 3 `other`, Step 4 `other`, Step 5 `sample-review`,
  Step 6 `other`, Step 7 `write-approval`, Step 7 `spend-approval`.
- **Vendor-specific**: Jev, from TypeSafe, reached with a TypeSafe or an OpenRouter key. Without one
  of the two there is nothing to call, so the skill stops at Step 4.

## Representative output

The people, companies and numbers are invented.

### The rubric card (Step 3, what the installer corrects)

What `rubric_tool.py check` prints for `scripts/rubric.example.json`, saved under the installer's
own name with the seniority scale and cut-offs accepted as defaults.

```
Rubric: Route-planning buyer fit (v1) — scores contacts, 0 to 100

Worked out in code (free, no Jev call):
  Account fit                from Account tier (account scoring): A → +30; B → +20; C → +8; anything
                             else → +0
  New in role                from Started current role: under 120 days ago → +10;
                             120–364 days ago → +5; 365+ days ago → +0

Asked of Jev (one request per contact, all questions together):
  Buying role                Choice on Job title, Profile headline or summary: decision_maker +30;
                             champion +25; influencer +10; not_involved +0;
                             not_enough_information +0
  Seniority                  Score (5 levels) on Job title: 0 to +15
  Not a prospect             Noul (yes/no) on Job title, Profile headline or summary: yes at
                             80%+ DISQUALIFIES

Most points possible: 85. Tiers: A ≥ 70, B ≥ 45, C ≥ 25, D ≥ 0.
Below 50% coverage (too little data to judge) a contact is 'insufficient_data', not a low tier.
Answers under 60% confidence are listed in needs_review.
Borrowed defaults you accepted rather than chose: Seniority, tier cut-offs.
Jev cost through TypeSafe: about 659 input tokens per contact (output is free),
so roughly $0.028 per 1,000 contacts.
```

### The preview (Step 5)

Scores and tiers are from a live run of the example rubric against Jev; the reasons are shortened
(the tool writes "Buying role: likely decision maker (+30) | …"), and the people are invented. A
reason counts for the person as "(+30)" and against them as "(0 of 30)", so a low score names what
pulled it down.

| Contact | Score | Tier | Why |
|---|---|---|---|
| Dana Ruiz, VP Operations, Northwind Supply | 96 | A | at an A-tier account (+30) · likely decision maker (+30) · Vice president (+11) · started this role in the last 4 months (+10) |
| Sam Okafor, Fleet Manager, Northwind Supply | 69 | B | at an A-tier account (+30) · likely champion (+25) · against: Manager or team lead (4 of 15), in this role over a year (0 of 10) |
| Priya Shah, Head of Fleet Ops, Adventure Works | 69 | B | likely champion (+26) · at a B-tier account (+20) · Director or head of a function (+8) |
| Lee Park, VP Marketing, Tailspin Toys | 13 | D | Vice president (+11) · against: at a low-fit or unscored account (0 of 30), not involved in this purchase (0 of 30) |
| Jo Brandt, Talent Partner, Contoso | 25 | disqualified | Disqualified: not a prospect (recruiter, student or outsider) |
| Ari Moss (no title on record) | 0 | not_scored | Not scored: missing title |

Lee Park is senior and still a D: the title says marketing and the company is a poor fit, which is
the case a single "fit score" column gets wrong. Six contacts cost $0.00013.

### The delivery card and how to call it

````
Contact scoring is live: "Jev lead score: contacts · Route-planning buyer fit" (published)

  Rubric       Route-planning buyer fit v2 · 2 rules, 3 Jev questions · tiers A/B/C/D (cut-offs borrowed)
  Jev          TypeSafe, jev-1.13.0 · key in Clay connection "Jev (TypeSafe)"
               and locally in ~/.config/jev-lead-score/.env
  Account fit  read from each contact's "Account tier" column (your account scoring's lead_tier)
  Smoke test   Dana Ruiz: local 96 A · Clay 96 A · answers match ✓
  Preview      10 contacts: A 2, B 3, C 1, D 2, disqualified 1, not_scored 1 · $0.0002

From a Clay table: add this workflow to the table, starting node "1 Intake", and map full_name,
title, headline, company_name, account_tier, started_role_on onto your columns (names need not
match). The score comes back onto the row.

From anywhere else:
curl -X POST 'https://api.clay.com/v3/sources/webhook/…' -H 'Content-Type: application/json' \
  -d '{"full_name":"Dana Ruiz","title":"VP Operations","company_name":"Northwind Supply",
       "account_tier":"A","started_role_on":"2026-07-01","source_ref":"row-2210"}'
````

## Files in this skill

| File | What it is for |
|---|---|
| `scripts/jev_lib.py` | the rubric check, the scoring code the Clay steps run, key discovery, state paths, the `clay` wrapper |
| `scripts/rubric_tool.py` | check, save (with version bumps), show and export a rubric |
| `scripts/rubric.example.json` | a complete, invented contact rubric to start from |
| `scripts/jev_key.py` | find an existing key, guide, save one through a password box into a `.env`, test it |
| `scripts/score_local.py` | the preview: score up to 50 real contacts on this machine with the exact workflow code |
| `scripts/build_scorer.py` | build, check the connection on, and publish the workflow(s); backfill an audience |
| `scripts/smoke_test.py` | one contact through the published workflow, compared with the local score |
| `scripts/test_offline.py` | every generated step, the arithmetic and the builder, with no Clay, network or key |
| `references/jev-api.md` | Jev's two routes, request and answer shapes, price, limits, what it is bad at |
| `references/rubric-format.md` | the rubric file, how a score is worked out, writing questions Jev answers well |
| `references/graph-shape.md` | both workflows node by node, and the traps each avoids |
| `references/live-checks.md` | what was run live against Jev and Clay, and what was not |

Run every script with `python3 -B`. They need only the standard library and the `clay` CLI.

**Do not start a step before the steps above it have their answers.** If a declared input is
missing, ask for it; never assume one and continue.

## Step 0: Say what this builds, what it costs, and check the platform

Three short paragraphs:

1. **What it builds.** A scoring rubric for contacts, previewed on their own records, then a Clay
   workflow that scores any person sent to it and says why.
2. **Where the work runs and what it costs.** Lookups and arithmetic are worked out in the
   workflow's code step, free. Judgments about the person go to Jev, one request per contact: about
   $0.04 per million input tokens, a few cents per thousand contacts, billed by TypeSafe or
   OpenRouter. Each run also counts toward Clay's workflow usage; no Clay data credits are spent.
3. **What leaves their systems.** The fields the questions read, typically title and headline, go to
   Jev (TypeSafe, directly or via OpenRouter). The key never passes through the chat.

Then, without asking: `clay --version && clay whoami` (say the workspace name back),
`python3 -B scripts/test_offline.py`, `python3 -B scripts/rubric_tool.py list` and
`python3 -B scripts/jev_key.py find`. A key the account skill saved is found here too. A saved
rubric or a found key means those steps are offered as done. If the platform check fails, say which
part and the one command that fixes it, and stop.

## Step 1: Where the contacts come from

Ask **"Where will the contacts you want scored come from?"** (A Clay table / A Clay audience of
people / Another system, by webhook). Then look, never ask:

- **Table:** list the installer's own tables
  (`clay tables list --filter owner.id=<id from clay whoami>`) and ask **"Which table?"** with up to
  four names as options. Read its columns (`clay tables columns list`).
- **Audience:** `clay audiences list --entity-type people`, ask **"Which audience?"** the same way,
  read the people fields (`clay audiences fields list --entity-type people`).
- **Webhook:** no fields to read; the rubric's inputs will be the interface.

**Audiences people records do not carry their company's fields.** For an audience, the account tier
counts only if it is already a field on the person record. If it is not, say so plainly: a table
(where a lookup can bring the company's tier onto each row) is the source that includes account fit,
and an audience without it scores people alone.

Note whether a column or field carries the **company's tier or score** (for example the account
skill's `lead_tier` written back to a table, or a tier field someone copied onto the person). The
fields that exist decide which criteria are possible; carry the list into Step 2.

## Step 2: Build the buyer brief from what you already know, then ask only the gaps

**Before asking anything, write the brief from your own context.** Look in: your memory files and
the project instructions loaded in this session; this conversation; a saved account rubric (the
account skill keeps them under `~/.local/state/score-accounts-with-jev/<workspace id>/rubrics/`, and
a rubric's `about` says what they sell); and documents in the working folder a person would keep
about who buys (a persona doc, an ICP or positioning doc, a strategy or "anchor context" document,
win notes). Read, do not guess.

The brief has six parts:

| Part | Becomes |
|---|---|
| What they sell | the frame for every question's wording |
| Buying roles: who signs, who champions, who is consulted, who is irrelevant | a Choice with described options |
| Seniority that matters | a Score over the title, or a Choice when a middle level is the sweet spot |
| People who are never prospects | a disqualifying Noul (and a match rule for known domains) |
| The account's fit | a lookup rule over the account tier column |
| Signals worth points | rules (time in role) or Nouls (the headline says they are hiring for a team) |

Show the brief as a short table: each part, what you found, and **where it came from**, or
*missing*. Then ask only for the missing parts that change the rubric, one click at a time, with
options drawn from what you found. For example **"Who usually signs off on buying this?"** (options
from their persona doc, plus Other) and **"Anyone who should never count as a prospect?"**
(Recruiters and students / Consultants and agencies / Competitors' staff / None). If no account tier
exists in their data, say plainly what that costs (a senior person at a poor-fit company scores
high) and ask **"Score people without their company's fit, or set up account scoring first?"**
(Without it for now / Account scoring first). If the brief is complete from context, ask one
question instead: **"I built this from <sources>. Anything wrong or missing?"**

Never invent a buying role, a disqualifier or a signal the installer did not state or a source did
not say. If what they sell cannot be found or answered, stop.

## Step 3: Draft the rubric, and have it corrected

Write the rubric JSON following `references/rubric-format.md`, from the brief and the fields Step 1
found:

- **The account's fit is a `lookup` rule**, tier letter to points, never a question.
- **Time in role is a `days_since` rule.** Never ask Jev about a date.
- **Every judgment about the person is a Jev question** reading the title (and headline when there
  is one), stating one condition, describing every option. Three to eight questions is typical.
- A Choice gets `not_enough_information` automatically. Level 0 of a Score is the most junior.
- Keep names, emails and phone numbers out of every question's `reads`: they add nothing to a
  judgment and send personal data for no reason.
- Mark anything accepted rather than chosen with `"origin": "default"`; put what they sell and the
  sources in `about`.

Run `python3 -B scripts/rubric_tool.py check draft.json --provider <provider if known>` and show the
card. Ask **"Does this match how you would judge a contact?"** (Looks right / Change the points or
cut-offs / Change a criterion / Other). Edit and re-check until it does, then
`rubric_tool.py save draft.json`.

## Step 4: The Jev key, on this machine

`jev_key.py find` already ran. Then:

- **A key sits in a project `.env` in the working folder** (not the shared file, not the
  environment): it may belong to another project or client. Ask **"Use the <provider> key in <that
  file> for this?"** (Yes / No, save a separate key). Never bill one project's key silently.
- **One provider has a key** in the shared file or the environment: use it, and say where it was
  found (never the value).
- **Both have keys:** ask **"Which should scoring use?"** (OpenRouter / TypeSafe).
- **Neither:** ask **"Which will you use for Jev?"** (OpenRouter: any OpenRouter key works, no
  TypeSafe account / TypeSafe: a key from TypeSafe's console). Run `jev_key.py guide <provider>` and
  relay it, then run **in the background** `python3 -B scripts/jev_key.py save <provider>`: a
  password box opens and the key goes to `~/.config/jev-lead-score/.env` at 0600
  (`--env-file <path>` for a project `.env`; refused if git would commit it). A key pasted into the
  chat is exposed: do not use it, ask them to revoke it, and open the box again.

Prove it: `python3 -B scripts/jev_key.py check <provider>`.

## Step 5: Preview on ten real contacts

Run `python3 -B scripts/score_local.py --provider <p> --table <id>` (or `--audience <id>`, or
`--file`) with **`--show-map` first**, show the mapping, take corrections as `--map key=Column`,
then run it for real and show the table.

**Stop here.** Ask **"Do these scores look right for people you know?"** (Yes, build it / Some are
off: adjust the rubric / Try ten different contacts). "Some are off" goes back to Step 3 with the
specific people in hand: which criterion moved them, and whether the fix is points, an option's
description (titles are where literal reading bites: say "Head of Fleet counts as a champion" in the
option), or a missing criterion. Rescore after every change.

## Step 6: The key in Clay

If the account skill already built a workflow in this workspace, its connection holds the same key:
offer it by name first. Otherwise ask **"Do you already have a Clay connection holding this
<provider> key?"** (No, I'll create one now / Yes, I'll tell you its name).

- **No:** Settings → Connections → Create → search "http" → **HTTP API (Headers)** → name it exactly
  `Jev (OpenRouter)` (or `Jev (TypeSafe)`) → one header, `Authorization`, value `Bearer ` followed
  by the key → Save. Wait for "done".
- **Yes:** take its exact name for `--connection "<name>"`.

Clay's CLI cannot create or list connections, which is why this one step is theirs.

## Step 7: Build and publish, after one gate

**Build it; never score in the conversation instead.** It has to be a workflow because it runs
unattended: every row of a bound table, every person who joins an audience, every POST from another
system, long after this session ends.

First confirm the node and trigger commands on the installed CLI: `clay workflows nodes --help` and
`clay workflows triggers --help`. `build_scorer.py` creates the workflow (`clay workflows create`),
its trigger (`clay workflows triggers create`) and its nodes (`clay workflows nodes create`, then
`update` with every pin and edge, then read back), in dependency order:

- **Jev lead score: contacts · <rubric>**: webhook trigger → `1 Intake` (code: rules, which
  questions have data, the one Jev request) → `2 Anything to ask Jev?` (conditional) → either
  `2b Score without Jev` (code, terminal) or `3 Ask Jev` (HTTP, key from the Clay connection) →
  `4 Score` (code, terminal).
- **… (audience)**, only with an audience: an audience trigger → the same four steps →
  `2c Save to Audiences` after 2b; after 4, `5 Save it?` → `6 Save to Audiences`, or
  `5b Not saved (Jev failed)`.

The traps it guards against are in `references/graph-shape.md`.

Run `python3 -B scripts/build_scorer.py --provider <p> --plan` (add `--audience <id>` and
`--show-audience-map` for an audience). Then one message with everything, and the word *write*:

> This **writes** to your Clay workspace: one workflow, "Jev lead score: contacts · Route-planning
> buyer fit", published, calling Jev through your connection "Jev (TypeSafe)". [With an audience: a
> second workflow triggered by members of "Ops leaders", and seven "Jev …" fields on your people
> records, which it **writes onto every contact it scores** from then on.] Each contact costs about
> $0.00003 in Jev. Nothing is scored until you call it or bind a table [or: until people join;
> scoring the 3,400 already there is a separate run, about $0.10].

Ask **"Go ahead?"** (Yes, build it / Build it, but don't score existing audience members yet /
Change something first). On yes:

```bash
python3 -B scripts/build_scorer.py --provider typesafe [--connection "<name>"] [--audience <id>]
```

**Exit 6 means the Jev step is on the wrong connection, and its workflow was not published.** Clay
binds a connection to a step by id, its CLI lists no connection ids, and a step written without one
gets whatever connection Clay treats as the workspace default (in testing, the first build landed on
an unrelated connection). Never publish around it: that connection's key would go to Jev. Fix it in
this order, then the same build checks every step again and publishes:

1. **The id, when someone can read it:** re-run with `--connection-id <connection id>`. Verified in
   testing: binds on the first write.
2. **Through Clay's default:** have them open Settings → Connections, find the Jev connection and
   choose **Set as default** from its … menu. Re-run with `--reattach`, which rewrites the Jev step
   so Clay attaches its default (verified in testing). Then have them set the connection the report
   named back as default, so HTTP steps added elsewhere do not pick up the Jev key.
3. Picking the connection on the step itself, in the workflow's draft, and saving. That choice did
   not persist in testing (`references/live-checks.md`, check 7), so treat it as the last resort and
   let the re-run's check say whether it held.

If they approved scoring existing members:
`python3 -B scripts/build_scorer.py backfill --audience <id>`. It submits, in batches of 50, every
member whose "Jev score rubric" field does not already read this rubric's name and version, so a
re-run after any interruption or Jev outage submits only what is left.

## Step 8: Prove it with one contact

`python3 -B scripts/smoke_test.py --from-preview` sends the first preview contact through the
published workflow and scores it locally again. **Match** proves the wiring, the connection's key
and the published rubric. A 401 in Clay's result means the connection holds the wrong key; if the
run fails, the script names the step and Clay's error. With an audience, also run
`smoke_test.py --audience`, which reads the member's "Jev …" fields back from Audiences. Do not call
either workflow live until it matches.

## Step 9: Deliver, ending with how to call it

The delivery card from "Representative output", with the real numbers, then **end with how to call
it**, all three ways:

1. **From a Clay table:** add the workflow to the table, starting node **1 Intake**, map the columns
   onto the inputs. If the table also runs account scoring, map `account_tier` to that column so the
   account's verdict flows into the person's.
2. **From an audience** (if built): new people are scored as they join; "A-tier contacts at A-tier
   accounts" is then a saved audience.
3. **From anything that can POST:** the webhook URL and a `curl` with a real-shaped body.

Say what was borrowed rather than chosen, and what was not tested. When asked later: **"change the
rubric"** is Steps 3, 5, 7 and 8; **"score the companies too"** is the sibling account skill.

## What this skill does not claim

- The rubric is the installer's judgment written down, not a model trained on won and lost deals.
  Nothing here measures whether A-tier contacts reply or convert more.
- Jev reads titles literally. Unusual titles ("Chief Moving Officer") land where the option
  descriptions send them; the preview is the only accuracy check, and it is by eye.
- Without an account-fit input, company quality does not enter the score at all.
- Jev's probabilities move slightly between calls, so a re-run can differ by a point or two and a
  tier can flip at a cut-off.
- The OpenRouter route is on a path OpenRouter labels `alpha`, and was not run live: the live runs
  used a TypeSafe key. The two take the same request and return the same answers, per both docs.
- The Jev step does not retry: Clay's own retry options made it fail before calling Jev on every
  live run, so they are off. A Jev 429 or 529 comes back `failed`; re-run those contacts.
- The audience workflow was run live for accounts, not for people; the contact skill shares its
  code. Picking a connection on a step in Clay's UI did not persist in testing. What was run live is
  in `references/live-checks.md`.
- A profile written to argue for its own classification can move Jev's answer; TypeSafe says so.
- `insufficient_data` means the record lacked fields, not that the person is a poor lead. The skill
  does not enrich.

## What good looks like

A good run ends with **one contact scored identically in Clay and locally**, a published workflow
whose **3 Ask Jev** step is on the installer's named connection, and a preview the installer read
and agreed with, in which a senior person at a poor-fit company scores below a hands-on champion at
a best-fit one. Every score names the criteria that moved it with their points; a person with no
title is `not_scored`; a recruiter is `disqualified`.

A thin run looks finished and is not:
- The account's fit is missing from the rubric and nobody said so.
- A question asks Jev a date or a number ("in the role under six months?"). That is a rule.
- Every contact lands in one tier; the points were never checked against the preview.
- The workflow is published but the smoke test never ran.
- A question's `reads` includes email or phone, sending personal data for nothing.
- A key appeared in the chat, or sits in a project `.env` git will commit.

## Rules

- **Jev judges the person; code counts the rest.** Account tier, dates and numbers are rules.
- **Context before questions.** Memory, conversation, a saved account rubric and folder docs first;
  ask only gaps that change the rubric.
- **Never invent** a buying role, disqualifier, signal or cut-off. Accepted proposals are marked
  borrowed.
- **Send Jev the least personal data that decides the question.** Titles and headlines, not contact
  details.
- **Always preview on real contacts before building**, and rescore after every rubric change.
- **Missing data is `insufficient_data` or `not_scored`, never a low tier.** Five statuses.
- **Never ask for, accept, print or log a key in the chat.** Never write one where git would commit
  it.
- **Never publish a workflow whose Jev step is on the wrong connection.**
- **One write gate (Step 7).** Say it is a write, name every workflow and field, price it.
- **Never blank a field; never overwrite a score because Jev failed.**
- **Do not call it live until the smoke test matches.**

## Worked example

The workspace, people and company are invented; the steps and outputs are the real shapes.

**Ask:** "We scored our accounts with Jev last week. Now I want the people in our Ops leaders
audience scored too."

**Step 0.** Workspace *Northwind GTM*. `jev_key.py find`: "TypeSafe key: found (TYPESAFE_API_KEY in
~/.config/jev-lead-score/.env)", saved by the account skill. No contact rubric yet.

**Step 1.** Audience, named in the ask; *Ops leaders* picked from the list. Its people fields
include Job title, Headline, Company name, Started role, and *Account tier*, a copy of each
company's "Jev lead tier" that the team keeps on its people.

**Step 2.** The brief, from context: *what they sell* from the saved account rubric's `about`;
*buying roles* from `personas.md` in the folder (the COO signs, fleet and dispatch managers
champion). Missing: who is never a prospect. "Anyone who should never count as a prospect?" →
Recruiters and students. Seniority scale and cut-offs: the defaults, accepted, so borrowed.

**Step 3.** Two rules, three questions (the card above). "Does this match how you would judge a
contact?" → Looks right. Saved as v1.

**Step 4.** TypeSafe key found and used. `check typesafe` → "key works".

**Step 5.** `--show-map`: `account_tier` ← *Account tier*, `started_role_on` ← *Started role*, all
matched. Ten contacts for $0.0002. "Some are off": a *Head of Fleet Ops* came out `influencer`. The
champion option's description gains "Head of Fleet"; rescored, now champion. Saved as v2, the
version the delivery card shows.

**Step 6.** The account skill's connection `Jev (TypeSafe)` exists: offered by name and taken.

**Step 7.** The gate names both workflows, the seven "Jev …" people fields, $0.00003 a contact, and
the 3,400 existing members as a separate run of about $0.10. "Build it, but don't score existing
members yet." Built and published on the first try: Clay's default HTTP connection was already
`Jev (TypeSafe)`, and the read-back confirmed it before anything was published.

**Step 8.** Smoke test: Dana Ruiz, local 96 A, Clay 96 A, answers match; `--audience` reads a
member's "Jev …" fields back and they match too.

**Step 9.** The card, then: new members of *Ops leaders* are scored as they join; to score the 3,400
already there, `build_scorer.py backfill --audience <id>`; or bind any table to **1 Intake** and map
`account_tier`. Borrowed: the seniority scale and the cut-offs.

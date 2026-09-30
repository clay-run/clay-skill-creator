---
name: check-employment-with-jev
description: |
  Build an always-on Clay workflow, "Person Active At Company (Jev)", that answers whether a person
  still works at a given company, and in what capacity: their main job, a side job (fractional,
  contract, a second role), a passive tie (advisor, board seat, investor, honorary title), a former
  role, or nothing at all. It reads a Clay-enriched LinkedIn profile with its work history, or buys
  one from a LinkedIn URL when that is all you have, and judges each role on the profile with Jev,
  TypeSafe's decision model, while plain code does every date and match. People hold several
  current roles at once and leave jobs without adding an end date, so "is_current" alone is not the
  answer. Jev costs under ten cents per thousand people, which is what makes running it on every
  row sensible. Works from a Clay table, a webhook, or an Audiences segment of people (checked as
  they join, or re-checked on a schedule) with the verdict written onto each record. Use whenever
  someone asks: is this contact still at the company, detect job changes, check if people have left
  their company, flag contacts who moved on, is this person an advisor or an employee, clean up
  stale contacts, verify current employer, or set up Jev or TypeSafe in Clay for people. Do NOT use
  it to find new contacts at a company, to find where someone went next, to find emails or phones,
  to score leads, or to update a CRM or a sequencer.
category: verify-and-clean
personas: [revops, sales-development]
mechanism: workflow
touches: writes-records
keywords: [job-change, crm-hygiene]
---

# Check employment with Jev: judge each role, then let code decide

**The insight: a LinkedIn profile does not have "a current job", so "is this person still at the
company?" cannot be read off one field.** Clay's own Enrich person returns `current_experience` as
a *list*, and the profiles it returns show why. Measured on real profiles: a CEO who is also a
university trustee; a CTO who also holds an adjunct university post; a founder whose co-founder
title at an earlier company still has no end date beside two newer roles. And a role nobody closed
stays "current" forever: a person who left in 2025 without editing the profile still reads as
employed. A single `is_current` flag, or a model asked "does this person work at X?", answers
these wrong in both directions.

The evidence for the fix is Jev's own documentation. TypeSafe publishes what Jev 1.13 is bad at:
comparing dates, counting items in a list, and reading loosely. Its advice for a list is to ask one
question per item and combine the answers in code. So:

- **Code finds the roles** that could be at the company: same website, same LinkedIn company page,
  or a name that matches once "Inc" and "LLC" are dropped. It works out every date.
- **Jev answers small questions about one role at a time**: is this the same company, what kind of
  role is it (a job, a contract, an advisory seat, an investment, an honorary title), is it still
  held given the jobs started after it, is it the main job. The person's other current roles are
  classified too, so a trustee seat never makes a CEO look like they left (it did, at 64%, before
  this was added).
- **Code combines the answers into one verdict** from a fixed set, with a confidence and the
  evidence in a sentence.
- **Jev is cheap enough to leave on**: $0.042 per million input tokens, measured at 800 to 2,500
  tokens a person, so four to ten cents per thousand people. The only real cost is buying a profile
  (Clay's Enrich person, 0.5 credits) for a person sent with a LinkedIn URL and no profile.

> **This skill is not finished when the workflow is built.** It is finished when the workflow is
> published, invented and real people have gone through it in Clay with the same verdicts as the
> local check, and the installer has been shown how to call it. If you stop early, say which step
> you stopped at and the command that resumes it.

## How to talk to the installer

- **Every question is a choice they click**, asked with the host's question tool
  (`AskUserQuestion` in Claude Code), likely answer first, free text only as "Other". Batch the
  questions of one step into one ask.
- **Before any question, apply the test: does the answer change what gets built or what it costs?**
  If not, do not ask it, and do not defer it to a later step either.
- **Never ask what a command can answer.** Table columns, audience fields, member counts, whether a
  key exists: look, then show what you found.
- **Run every command yourself.** The installer only pastes a key into a box and decides.
- Show names, never ids, in anything the installer reads.

## Declared inputs

**Nothing here ships with a value.** Every input is the installer's, read from their workspace or
asked; where a default is used it is named, and using it is said at delivery.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Where people come from** | a Clay table, a saved Audiences audience of people, or "another system" (webhook). Picked from a list the agent reads | no default: it decides whether an Audiences workflow is built and where the preview comes from |
| **The audience, and when to check** (Audiences only) | which audience, and whether to check people when they join or re-check everyone weekly, monthly or quarterly | no default; the cadence is the cost, because each re-check buys every member's profile again (0.5 credits a person) unless a people field already holds one |
| **A Jev key** | TypeSafe or OpenRouter. Found in the environment, `./.env`, `~/.config/jev/.env` or `~/.config/jev-lead-score/.env` (a shared location other Jev tools may use); otherwise saved to `~/.config/jev/.env` through a password box | stop at Step 2: nothing can be checked |

Read and shown, never asked: which table columns (or people fields) hold the profile, the LinkedIn
URL, the person's name and the company. The profile is found by what the cells hold. A table with
no company column is said plainly and does not block anything: the preview uses the invented
people instead, and the mapping is only the installer's to set when they call the workflow.

**Not asked, ever:** which fields the verdict writes (fixed), what counts as "active" (the verdict
keeps a job, a side job and a passive tie apart; the installer filters on it), the 60% and 40%
cut-offs (fixed in code and stated), a callback URL (the caller's own), a Clay connection (none
is used), whether to preview (always), the provider when only one key exists, real people's
records in the chat, and any key in the chat.

### The workflow's interface, prescribed

Inputs, one flat field each; at least one company field, and a profile or a LinkedIn URL:

| Input | |
|---|---|
| `company_name`, `company_domain`, `company_linkedin_url` | the company to check against. A website or LinkedIn page makes matching exact |
| `profile` | an enriched profile with a work history: the value of a Clay Enrich person column is ideal; object or JSON text |
| `linkedin_url` | the person's LinkedIn URL, used to buy a profile when `profile` is empty |
| `full_name` | optional; any profile, supplied or bought, whose name shares no word with it is flagged and capped at 50% |
| `skip_enrichment` | `true` never buys a profile (the person comes back `not_checked`) |
| `max_profile_age_days` | re-buy a supplied profile last refreshed longer ago than this; blank never does |
| `source_ref` | echoed back, for joining |

Outputs, every key always present:

| Key | |
|---|---|
| `active_at_company` | `yes` · `passive` · `no` · `unsure` · `not_checked`. Five, no sixth |
| `relationship` | `primary_job` · `side_job` · `advisor_or_board` · `investor` · `honorary` · `former` · `no_record` · `unknown` |
| `verdict_confidence` | 0 to 100, the probability behind the verdict |
| `check_status` | `checked` · `no_profile` · `blocked_missing_input` · `failed` |
| `evidence`, `needs_review`, `check_note` | the verdict in a sentence; the answers worth a second look (`none` otherwise); why a person was not checked (`none` otherwise) |
| `role_title`, `role_company`, `role_started`, `role_ended`, `months_in_role` | the role the verdict rests on |
| `other_current_roles`, `main_employer` | what else they hold now, and where their main job is when it is not here |
| `company_checked`, `profile_source`, `profile_age_days`, `roles_json`, `jev_model`, `jev_cost_usd`, `error`, `source_ref`, `checked_at` | provenance |

The terminal step also carries `isTerminal: true`, Clay's marker for the step that ends a run. How
each verdict is reached, rule by rule, is in `references/how-it-decides.md`.

## What this skill touches

- **Reads**: the installer's table list, and the column list and 10 rows (up to 50 with `--limit`)
  of the table they pick; the audience list, member counts, the people field list, and up to ten
  members' fields to find a profile field by content; after the build, the "Active …" fields of the
  members this skill sent; Clay's action catalogue; the workspace name; the Jev key from a local
  `.env`.
- **Writes**: in Clay, one workflow "Person Active At Company (Jev)" (Step 5), with the Jev key
  written into its first step; with an audience, a second workflow "Person Active At Company (Jev)
  · Audiences" and nine "Active …" fields on people records, adopted if they already exist. That
  audience workflow then **writes those fields onto every person it checks**: all nine for a
  verdict; for a person it could not check, only "Active last attempt" and "Active last attempt
  note" (the verdict fields keep the last real check); nothing when Jev failed. The table workflow
  writes nothing itself: it returns the verdict to whatever called it (a table that invokes it
  gets the verdict as that action's result; not yet observed on a live table). Locally: the key into a `.env` file only
  through the password box, at mode 0600, never into a file git would commit; preview results,
  build state and the backfill ledger under `~/.local/state/check-employment-with-jev/`.
- **Sends**: to Jev (TypeSafe, directly or through OpenRouter), for each person checked, the
  profile's headline and, per role, the company, title, start and end, description (first 300
  characters), work type and company website, plus the company being checked. Name, email and
  phone fields are never sent, though a headline or a company name can contain a name.
- **Spends**: 0.5 Clay credits for each person sent with a LinkedIn URL and no profile (Clay's
  Enrich person), whether or not the profile it returns is the right person; Jev at four to ten
  cents per thousand people, billed by TypeSafe or OpenRouter; one or two workflow action
  executions per person (measured: the Jev call, plus the purchase when there is one; the
  Audiences lookup and writes counted none).
- **Never**: prints or stores a key in the chat; writes a key into a file git would commit;
  clears or blanks a field; overwrites a verdict because Jev failed or a person could not be
  checked; edits a table's columns; contacts anyone; writes to a CRM or a sequencer; deletes
  anything outside its own steps.
- **Halts**: Step 1 `other`, Step 2 `other`, Step 3 `sample-review`, Step 3 `spend-approval`,
  Step 4 `write-approval`, Step 4 `spend-approval`, Step 5 `other`, Step 6 `sample-review`,
  Step 7 `spend-approval`.
- **Vendor-specific**: Jev, from TypeSafe, reached with a TypeSafe or an OpenRouter key. Without
  one of the two there is nothing to judge the roles with, so the skill stops at Step 2.

## Representative output

The people, companies and numbers are invented; the shapes are what the workflow returns.

### Verdicts, one row per person

| Person | Checked against | Active | Relationship | Confidence | Evidence |
|---|---|---|---|---|---|
| Dana Ruiz | Northwind Supply | yes | primary_job | 100 | VP Operations at Northwind Supply since April 2021 (works there; main job). Also current: Contoso Robotics: Advisor; Tailspin Toys: Angel Investor |
| Pat Quinn | Northwind Supply | yes | side_job | 79 | Fractional CFO at Northwind Supply since March 2024 (works there as a contractor or consultant; not the main job). Also current: Quinn Finance Partners: Founder & Principal; Contoso Robotics: Fractional CFO |
| Lee Park | Northwind Supply | passive | advisor_or_board | 99 | Board Member at Northwind Supply since May 2022 (advisor or board member). Also current: Adatum: Chief Executive Officer |
| Sam Okafor | Fabrikam Freight | no | former | 84 | Software Engineer at Fabrikam Freight since February 2019, still listed as current, but replaced by a later full-time job at Litware |
| Kim Lau | Acme Corp | no | no_record | 89 | No role at Acme Corp on this profile (Acme Analytics: a different company, 11% same) |
| Ari Moss | Northwind Supply | not_checked | unknown | 0 | Not checked: no profile and no LinkedIn profile URL to enrich |

Sam's profile still lists Fabrikam as current; that is the case a "current employer" field gets
wrong. Ari was sent with nothing to read, and comes back `not_checked` rather than `no`.

### The Audiences fields on a person record

| Field | Value |
|---|---|
| Active at company | passive |
| Active relationship | advisor_or_board |
| Active company checked | Northwind Supply |
| Active evidence | Board Member at Northwind Supply since May 2022 (advisor or board member). Also current: Adatum: Chief Executive Officer |
| Active confidence | 99 |
| Active needs review | none |
| Active last attempt | checked |
| Active last attempt note | none |
| Active checked at | 2026-09-29T06:35:20Z |

If a later check cannot run (the LinkedIn URL was removed, say), only the two "last attempt"
fields change, to `blocked_missing_input` and the reason; the verdict above and its date stay.

### The delivery card

````
"Person Active At Company (Jev)" is live (published) in Northwind GTM

  Jev          TypeSafe, jev-1.13.0 · key written into step "1 Intake" (visible to your workspace)
  Profiles     read from your "Enrich person" column; bought only when a row has just a LinkedIn URL (0.5 credits)
  Preview      10 of your people: yes 7, passive 1, no 1, unsure 1 · Jev $0.0009
  Smoke test   11 invented people through the published workflow: 11 match the local check

From a Clay table: add an action that invokes the workflow "Person Active At Company (Jev)", map your
columns onto company_domain, profile, linkedin_url, full_name (names need not match); the verdict
comes back as that action's result.

From anywhere else (a LinkedIn URL with no profile buys one, 0.5 credits):
curl -X POST '<the webhook URL>' -H 'Content-Type: application/json' \
  -d '{"company_domain":"northwind.example","linkedin_url":"<their LinkedIn URL>",
       "full_name":"Dana Ruiz","source_ref":"crm-4411"}'
````

## Files in this skill

| File | What it is for |
|---|---|
| `scripts/active_lib.py` | the code every Clay step runs, key discovery, state paths, the `clay` wrapper |
| `scripts/jev_key.py` | find a key, save one through a password box into a `.env`, test it |
| `scripts/check_local.py` | the preview: check 10 (up to 50) of the installer's people on this machine with the workflow's own code |
| `scripts/build_workflow.py` | build, check and publish both workflows; check an audience's existing members; read their fields back |
| `scripts/smoke_test.py` | send people through the published workflow and compare each verdict with the local check |
| `scripts/test_offline.py` | every generated step, the verdict rules and the builder, with no Clay, network or key |
| `scripts/fixtures.json` | eleven invented people, each with the verdict a correct run gives |
| `scripts/jev_answers.json` | Jev's recorded answers for those people, replayed by the offline test |
| `references/how-it-decides.md` | how roles are matched, the questions, how the answers combine, what was measured |
| `references/graph-shape.md` | both workflows step by step, and the traps each avoids |
| `references/jev-api.md` | Jev's two routes, request and answer shapes, price, and what it is bad at |

Run every script with `python3 -B`. They need only the standard library and the `clay` CLI.

**Do not start a step before the steps above it have their answers.** If a declared input is
missing, ask for it; never assume one and continue.

## Step 0: Say what this builds, what it costs, and check the platform

Three short paragraphs:

1. **What it builds.** A Clay workflow that takes a person and a company and says whether the
   person works there now, as their main job or a side job, holds only an advisory, board,
   investor or honorary tie, used to, or never did, with the evidence. Optionally a second one that
   does this for everyone in an Audiences segment and writes the answer onto each person.
2. **Where the work runs and what it costs.** Matching and dates run in the workflow's code, free.
   Judging each role goes to Jev: four to ten cents per thousand people, billed by TypeSafe or
   OpenRouter. A person sent with only a LinkedIn URL costs 0.5 Clay credits for the profile.
3. **What leaves their systems, and where the key goes.** For each role on the profile, its
   company, title, dates, a short description and the company's website, plus the headline, go to
   Jev; name, email and phone fields never do. The key goes into the workflow's first step in
   Clay, readable by anyone in their workspace who opens it, because Clay's CLI cannot yet create
   or attach a connection. It never passes through the chat.

Then, without asking: `clay --version && clay whoami` (say the workspace name back), `python3 -B
scripts/test_offline.py`, and `python3 -B scripts/jev_key.py find`. If a check fails, say which part
and the one command that fixes it, and stop.

## Step 1: Where the people come from

Look first, then ask once. List the installer's own tables (`clay tables list --filter
owner.id=<id from clay whoami>`) and their people audiences (`clay audiences list --entity-type
people`, with each one's member count from `clay audiences records search-count --audience-id <id>
--entity-type people`). Then ask **"Where are the people you want checked?"** with what you found
as the options: the likeliest audiences and tables by name (with member counts), and "Another
system, by webhook"; up to four options, the host's Other covers the rest. If the ask already named
one, skip the question.

- **An audience:** ask, in the same batch, **"When should people be checked?"** (When they join
  (Recommended): 0.5 credits once per new person / Re-check everyone monthly / weekly / quarterly:
  0.5 credits per person per re-check, with the audience's figure in the option text).
- **A table:** nothing more to ask; Step 3 reads it.
- **A webhook:** nothing to read; the interface above is the contract.

One Audiences workflow serves one audience. Pointing it at another later is Steps 4 and 5 again
with `--audience <other id>`: the build moves the trigger. There is no second trigger to add by hand.

## Step 2: The Jev key, on this machine

`jev_key.py find` already ran.

- **One provider has a key:** use it; say where it was found, never the value.
- **Both:** ask **"Which should the checks use?"** (TypeSafe / OpenRouter).
- **Neither:** ask **"Which will you use for Jev?"** (OpenRouter: any OpenRouter key works /
  TypeSafe: a key from TypeSafe's console). Run `jev_key.py guide <provider>` and relay it, then
  run **in the background** `python3 -B scripts/jev_key.py save <provider>`: a password box opens
  and the key goes to `~/.config/jev/.env` at 0600. A key pasted into the chat is exposed: do not
  use it, ask them to revoke it, and open the box again.

Prove it: `python3 -B scripts/jev_key.py check <provider>`.

## Step 3: Preview

- **Table:** `python3 -B scripts/check_local.py --provider <p> --table <id> --show-map`. Show the
  mapping (the profile column is found by what its cells hold, the rest by name) and take
  corrections as `--map input=Column`. If no column holds the company, say so and preview with
  `--fixtures` instead; nothing else changes. Otherwise run it without `--show-map`. If rows have
  only a LinkedIn URL, the output says how many and what buying them costs: ask **"Buy those N
  profiles for the preview? X credits."** (No, preview the rest / Yes) and add `--enrich` only on
  yes.
- **Webhook:** `python3 -B scripts/check_local.py --provider <p> --fixtures`, without asking. Show
  the table as how verdicts look; it proves nothing about their people, so do not ask the review
  question below about it.
- **Audience:** there is no local preview (Clay's CLI cannot read which company a person is linked
  to). Say so: ten members, run after the build in Step 6, are the preview.

**Stop here for a table preview of their own people.** Show the verdicts and ask **"Do these look
right for people you know?"** (Yes, build it / One is wrong: show me why / Try ten other rows:
the same command with `--skip 10`). "One is wrong" means reading that person's `roles_json`
together: which role was matched, what Jev called it, what code did with it. The fix is a column
mapping, a missing company website, or a profile that is simply out of date; the rules themselves
do not change per installer.

## Step 4: One gate: the writes and the spend

Run `python3 -B scripts/build_workflow.py --provider <p> --plan` (add `--audience <id>` and
`--schedule <cadence>` if chosen, and `--show-audience-map` to see which people fields are the
LinkedIn URL, the name and, if one is found, the profile). Then one message with all of it, and the
word *write*:

> This **writes** to your Clay workspace: one workflow, "Person Active At Company (Jev)", published,
> with your TypeSafe key in its first step (anyone in the workspace can read it there). [With an
> audience: a second workflow for "Customer contacts", and nine "Active …" fields on your people
> records, which it **writes onto every person it checks** from then on. Right after the build, ten
> members are checked as the preview: up to 5 credits.] Each person costs well under a tenth of a
> cent in Jev, and 0.5 Clay credits when their profile has to be bought [Audiences stores no work
> history unless a field holds one, so that is every new member: 0.5 credits each]. [With a
> schedule: **the first re-check runs tomorrow at 09:00 UTC and checks all 1,200 members, up to
> 600 credits, then again every month.**] Otherwise nothing runs until you invoke it, a table calls
> it, or people join the audience.

Ask **"Go ahead?"** (Yes, build it / Change something first).

## Step 5: Build and publish

**Build it; never check people in the conversation instead.** It has to be a workflow because it
runs unattended: every row of a table that calls it, every person who joins an audience, every
POST from another system.

First confirm the commands on the installed CLI: `clay workflows nodes --help` and `clay workflows
triggers --help`. Then:

```bash
python3 -B scripts/build_workflow.py --provider typesafe [--audience <id> [--schedule monthly]]
```

It creates each workflow, its trigger and steps in dependency order, reads every step back, and
publishes both together or neither. **Exit 6 means a step came back with a Clay connection
attached, and this build published neither workflow** (a version published earlier stays live).
Relay the report (open the named step in Clay, clear its connection, save), wait for "done", then
re-run the same command. Never publish around it. The steps and the traps they avoid are in
`references/graph-shape.md`.

## Step 6: Prove it

- `python3 -B scripts/smoke_test.py --provider <p> --fixtures`: the eleven invented people through
  the published webhook, free apart from Jev; every verdict must match the local check and the
  expected answer.
- **Table installs:** `python3 -B scripts/smoke_test.py --provider <p> --from-preview`: the first
  person of the Step 3 preview, through Clay. It buys a profile (0.5 credits) only if that person
  had just a LinkedIn URL.
- **Audience:** `python3 -B scripts/build_workflow.py backfill --audience <id> --limit 10` (the
  preview Step 4 priced), wait a minute, then `python3 -B scripts/build_workflow.py readback
  --audience <id>` and show that table. A member shown as `(pending)` has not finished; read back
  again. If most come back `(not checked)`, say why first, from their "Active last attempt note"
  (usually: no LinkedIn URL on the record), before asking anything. Then ask **"Do these look right
  for people you know?"** (Yes / One is wrong: show me why), and go on to Step 7 either way: the
  workflow is live, and the card says what the audience lacks.

A 401 in a verdict's `error` means the key in the first step is wrong: fix it locally and rebuild.
Do not call the workflow live until the smoke test matches.

## Step 7: Deliver, ending with how to call it

The delivery card from "Representative output", with the real numbers, then **how to call it**:

1. **From a Clay table:** add an action that invokes "Person Active At Company (Jev)" and map the
   columns (the Step 3 mapping). Tell them what was not tested: whether a table passes an Enrich
   person column as the whole profile. If the first rows come back with `profile_source` =
   `enriched` although the row had a profile, the table passed only its display text, and each
   row is buying a profile it already had: map the column's JSON instead.
2. **From an audience** (if built): members are checked as they join (or on the schedule);
   "`Active at company` is `no`" is then a saved audience of people who have left. Unless a
   schedule was chosen (it re-checks everyone anyway), run `python3 -B scripts/build_workflow.py
   backfill --audience <id> --plan` and ask **"Check the N people already in <audience> now? Up to
   X credits."** (Not now / Yes, check them). On yes, run it without `--plan`. What is left is
   worked out from what Clay holds, so it can be re-run after any interruption, and a person whose
   check failed is sent again.
3. **From anything that can POST:** the webhook URL and a `curl` with a real-shaped body.

Say what was borrowed or not tested. When asked later: **"re-check everyone monthly"** is Steps
1, 4 and 5 with `--schedule` (after deleting the audience workflow's trigger in Clay, since a
trigger's type cannot change in place); **"use another audience"** is Steps 4 and 5 with
`--audience <id>`; a new key is Step 2 then Step 5.

## What this skill does not claim

- A LinkedIn profile is self-reported. A person who left without adding an end date, and has not
  listed a new job, still reads as active; nothing here can see past the profile.
- A bought profile can be the wrong person. A made-up LinkedIn URL returned a stranger's profile
  and was billed; `full_name` catches a mismatch only when it is sent.
- Accuracy is measured on eleven invented people and thirteen real profiles, by eye. It is not a
  benchmark, and Jev's probabilities move a point or two between calls, so a person near a cut-off
  can flip between runs.
- Recognising a renamed company, or a brand of a parent, relies on what Jev knows; Facebook and Meta
  matched, a small company's rename may not.
- The Audiences workflow checks only the person's first linked company.
- Whether a Clay table passes an Enrich person column to the workflow as the whole profile has not
  been observed.
- The Jev key sits in the workflow's first step, readable by the whole workspace, until Clay's CLI
  can create and attach connections.
- A failing step fails the whole run (Clay has no continue-on-error); no enrichment failure was
  observed, but one would leave that person unchecked.

## What good looks like

A good run ends with the workflow published, the eleven invented people matching in Clay and
locally, and a preview the installer read in which the hard cases come out right: a person with
an advisory seat elsewhere is still `primary_job`, a board member is `passive` and not `yes`, and a
person whose old job was never closed but who has a newer full-time job is `former`. Every verdict
names the role it rests on and the other roles they hold; a person with nothing to read is
`not_checked`, never `no`.

A thin run looks finished and is not:
- Every row came back `not_checked` because no company column was mapped.
- Every row bought a profile although the table already had one (`profile_source` = `enriched`).
- The workflow is published but the smoke test never ran.
- A schedule was built and nobody was told it spends the whole audience's credits the next morning.
- A verdict of `no` is being used to delete contacts; `no` is a reason to look, not proof.
- A key appeared in the chat, or sits in a project `.env` git will commit.

## Rules

- **Jev judges one role at a time; code finds the roles, does the dates, and decides.**
- **Keep a job, a side job and a passive tie apart.** Never collapse `passive` into `yes` or `no`.
- **Missing data is `not_checked`, never `no`.** Five verdict values.
- **Send Jev the least that decides the question.** Roles and headline, never contact fields.
- **Always preview before building**, and prove the published workflow against the local check.
- **Never ask for, accept, print or log a key in the chat.** Never write one where git would commit it.
- **Never publish a workflow whose Jev step came back on a Clay connection.**
- **One write gate (Step 4).** Say it is a write, name every workflow and field, price the profiles
  and any schedule's first run.
- **Never blank a field; never overwrite a verdict because Jev failed or a person was not checked.**

## Worked example

The workspace, people and companies are invented; the steps and outputs are the real shapes.

**Ask:** "Can you set up something that flags when our customer contacts have left their company?"

**Step 0.** Workspace *Northwind GTM*. Offline test passes. `jev_key.py find`: "TypeSafe key: found
(TYPESAFE_API_KEY in ~/.config/jev/.env)", saved there on an earlier run.

**Step 1.** Tables and audiences listed first. "Where are the people you want checked?"
(Customer contacts, 1,200 people / Ops leaders, 340 people / Contacts table / Another system, by
webhook) → *Customer contacts*; "When should people be checked?" → When they join.

**Step 2.** TypeSafe key found; `check typesafe` → "key works".

**Step 3.** No local preview for an audience; said so.

**Step 4.** `--show-audience-map`: LinkedIn URL ← *LinkedIn URL*, name ← *Name*, no field holds a
profile. The gate names both workflows, the nine fields, the key in the first step, ten members
checked right after the build (up to 5 credits), and 0.5 credits per new member after that.
"Yes, build it."

**Step 5.** Built and published on the first run; no step came back on a connection.

**Step 6.** Smoke test: 11 of 11 match. `backfill --limit 10`, then `readback`: yes 7, passive 1 (a
board member), no 1 (an old role never closed, a newer full-time job elsewhere), unsure 1 (a
co-founder title beside a newer company). "Do these look right?" → Yes.

**Step 7.** The card, then: a saved audience "Active at company is no" lists people who have left.
`backfill --plan`: 1,190 left, up to 595 credits. "Check the 1,190 people already in Customer
contacts now?" → Not now; the command for later is `build_workflow.py backfill --audience <id>`.

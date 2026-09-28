---
name: find-recent-company-developments
description: |
  Summarize what changed at a company inside a lookback window you choose — new leadership who
  started in that window, merger, acquisition and divestiture events, technology transformation
  programs, procurement notices and contract awards, and verified news items — each dated, sourced
  and standardized, by building (once) and running a Clay workflow that resolves the company from a
  LinkedIn URL or domain, finds new joiners, and runs the author's four Claygent research prompts
  verbatim. Use whenever someone asks: what's new at this account, brief me on this company before
  the call, recent developments at these companies, who joined their leadership recently, has this
  company done any M&A lately, any news on this account in the last quarter, or build me an account
  research brief. Do NOT use it for firmographics or headcount (enrich the company instead), for
  finding a contact's email or phone, for funding-round history as a number, for tracking a named
  person's job change, or for writing the outreach itself — it ends at a dated, sourced summary per
  company that a person reads.
category: research
personas: [account-executive, sales-development]
mechanism: workflow
touches: writes-own-output
keywords: []
---

# Find recent company developments (fix the window first, then research inside it)

The insight, in the author's prompts: **an account development is only useful if it is dated and
sourced, and only real if it falls inside the window you asked about.** Every prompt says the same
thing three ways — *"only include results dated on or after"* the start date, *"every item must be
traceable to a real, accessible source with a direct URL"*, and *"do not pad with low-confidence or
speculative entries"*. So the skill computes the window before anything runs, hands the same start
date to every research pass, and drops any event that arrives undated or before it. The new-leadership
list is scoped the same way: people whose current role started inside the window.

The judgment lives in four Claygent prompts, carried **verbatim** in `references/prompts.md` with
their output schemas and the author's combine-and-format rules. This skill's job is to stand them up
as a Clay workflow in your workspace, run it per company, and hand back the standardized summary —
not to reword them.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The companies** | one company LinkedIn URL or domain per company — pasted, or **a CSV file** with a column holding either (name the column if there are several). A name column is optional and never used to identify a company | no default — a company name alone is refused, because it cannot be resolved to one organization |
| **Leadership seniority** | the title words that count as leadership for the new-joiner search, comma-separated | **the author's default is `Chief, CEO, CFO, CTO, COO, CRO, CMO, CIO, President, VP, Vice President, Director, Head`** — confirm it with the installer before the first run and say it was used |
| **Lookback** | how many months back to look | no default — ask. The window decides what counts as "recent" for every event type, and the author's function required it |
| **Event types** | which of the four research passes to run: M&A, news, procurement, technology transformation | **all four is the default**, matching the author's function; say so, and offer to drop passes the installer does not need, since each is a paid research run |
| **Where the summary goes** | the conversation, a Markdown file per company, or **a CSV** with one row per company (and one per event, if asked) | the conversation |
| **Spend cap** | the most Clay credits they will spend on this list | asked after the one-company test (Step 4), in credits, with the measured per-company cost beside it. No cap, no full run |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — the companies and lookback you supply, and each workflow run's node outputs (the resolved company, its recent joiners, and the four research passes' results, which read public web pages during the run).
- **Writes** — one Clay workflow of its own in your workspace (created once, reused after), its runs, one provenance line in that workflow's description, and the summary, to the conversation or the files you name.
- **Never** — edits a workflow, table or record it did not create, writes to a CRM, contacts anyone, or reports an event without a date and a source URL.
- **Halts** — Step 2 write-approval, Step 2 spend-approval, Step 4 sample-review, Step 4 spend-approval

## Step 0 — Verify Clay is working, and say what this does

Say this first, as two sentences: *this builds one Clay workflow in your workspace (or reuses it if
it is already there) and runs it once per company to resolve the company, list who joined inside your
window, and research four kinds of developments; it hands back a dated, sourced summary and never
writes anywhere else.*

Run `clay whoami; echo "exit_code=$?"`. If it fails, name what is wrong — the CLI missing, below the
version the Clay plugin requires, or signed out — give the one fix (`clay login`, or install the Clay
plugin and run its `setup` skill), and **stop**. Do not install, upgrade or fetch anything to repair
it. Tell the user which workspace you are in.

This skill builds and runs its workflow **through the Clay plugin's `workflows` and
`workflows-claygent` skills** — read both before Step 2 and follow them for every CLI shape (trigger
creation, node JSON, wiring, validate, test runs). If they are not installed, say the Clay plugin is
required and stop.

## Step 1 — Collect the inputs (interview; do not guess)

1. **Companies** — LinkedIn URLs or domains, pasted or from a CSV the installer points you at (read
   the column they name, or the one column that holds URLs or domains). Normalize: lowercase, strip
   `www.`, query strings and trailing slashes; dedupe. Refuse a row that has only a name, and say why.
   Keep the other CSV columns so the output CSV can carry them through unchanged.
2. **Lookback** in months. Compute `lookback_start_date` yourself: today's date minus that many
   months, as `YYYY-MM-DD`, and carry today's date as `run_date`. Both go into every run and into
   the output, permanently.
3. **Event types** — confirm all four, or drop some.
4. **Leadership seniority** — show the author's default title list and ask the installer to confirm or
   edit it; it is the whole definition of "leadership" for the joiner search.
5. **Where the summary goes** — conversation, Markdown files, or CSV.

The spend cap is asked in Step 4, once there is a measured cost to set it against.

## Step 2 — Find or build the workflow (one gate first)

**Look before building.** `clay workflows list` and look for **Recent company developments**. If it
exists, read it with `clay workflows get` and `clay workflows graph get --mode full` and check it has
the nodes below with the prompts and model in `references/prompts.md`; if so, reuse it and skip to
Step 3. If it exists but differs, say how, and ask whether to use it as-is or build a fresh one
alongside — never edit it.

**Before creating anything, one message:** the workflow name and workspace, the node list below, that
a provenance line will be written into the new workflow's description so it can be traced back to
this listing, and that the next step runs it on **one** company — whose cost cannot be stated exactly
beforehand, because four Claygent research passes bill by what they do on the open web. Give the
declared figures for the two data steps, read from the catalogue on this machine; the author's own
test (2026-09-28, one large company, 12-month window) reported **5 data credits and 6 action
executions in 80 seconds**. **Wait for an
explicit yes.**

Identify every action by the pair **`(packageId, actionKey)`** read from `clay workflows actions list`,
and pull each one's real inputs with `clay workflows actions schema <packageId> <actionKey>` before
wiring — parameter names below were read on 2026-09-28 and can drift. Both data actions live in Clay's
own package (display name *Companies, People, Jobs*).

The graph, in order:

| # | Node | Type | What it does |
|---|---|---|---|
| 1 | **Manual trigger** | trigger | inputs `company_identifier` (required; LinkedIn URL or domain), `lookback_months` (number), `lookback_start_date` (`YYYY-MM-DD`, computed in Step 1), `leadership_titles` (the confirmed list) — one company per run |
| 2 | **Enrich company** | tool — action `cpj-enrich-company-v2` | `company_identifier` ← the trigger input. Read `$.result.name`, `$.result.domain` and **`$.result.url`** (the company LinkedIn URL — the field is named `url`, not `linkedin_url`; confirmed on the author's test run 2026-09-28). This is how a domain or a LinkedIn URL becomes the name, domain and URL the prompts need; a missing `name` ends the run for that company as *not resolved*. Catalogue price on 2026-09-28: **0.5 credits** |
| 3 | **Find new leadership** | tool — action `cpj-find-lists-of-people-v2` | `company_identifier` ← node 2 `$.result.url` (pinned on the node's `inputSchema`, then mapped by `reference`); `current_role_max_months_since_start_date` ← trigger `lookback_months`; `job_title_keywords` ← trigger `leadership_titles` (the confirmed seniority list); `job_title_exclude_keywords` ← `Office of, Assistant`; `limit` ← `10`. Read `$.result.people[]` (`name`, `title`, `location_name`, `url`, `experience[0].start_date`) and `$.result.peopleCount`. **The action returns at most 10 people while `peopleCount` is the true total** (469 at a large company on the author's test), so the output always says "N shown of M" and never presents the 10 as the whole list. The author's function carried only the two exclusions; the title filter is the author's later correction, made when this skill was written, so "leadership" means the confirmed list and nothing else. Catalogue price on 2026-09-28: **0.5 credits per call** |
| 4 | **M&A events** | Claygent | prompt 1 in `references/prompts.md`, model `gpt-4.1-mini`, output `events_json`; inputs `company_name`, `company_domain` ← node 2, `lookback_start_date` ← trigger |
| 5 | **News events** | Claygent | prompt 2, same model, output `events_json`; inputs as above plus `company_linkedin_url` ← node 2 `$.result.url` |
| 6 | **Procurement events** | Claygent | prompt 3, same model, output `events_json`; inputs as node 4 |
| 7 | **Transformation events** | Claygent | prompt 4, same model, output `events_json`; inputs as node 4 |

Nodes 4 to 7 all follow node 3 and run in parallel; when the installer dropped an event type in Step 1,
do not build that node. Wire every `{{variable}}` in each prompt as a top-level input on its node
from the node named in `references/prompts.md`, give every output field a description (the write is
rejected without one), and send `agentName`, `agentPrompt` and `agentModel` together in the create
call — separate calls can persist a blank prompt. After creating each Claygent node, `nodes get` it
and confirm the prompt is not blank and the model is `gpt-4.1-mini`; if that model is unavailable in
the installer's workspace, **say so and ask which to use** — never substitute one silently.

**Write the provenance line:** read the workflow's description with `clay workflows get`; if it is
`null` write the skill's one-line description, a newline, then
`Sourced from marketplace skill: <slug>@<revision>` using the `marketplace_slug` and
`marketplace_revision` this file's frontmatter carries when installed from the Marketplace; if those
fields are absent, say *"Marketplace attribution is unavailable for this skill"* and write no marker.
If a marker is already there, write nothing and say so; if a different marker is there, stop and
report the conflict. Read the description back and confirm both halves. Validate the graph. A manual
test run uses the draft, so no publish is needed to run this skill.

## Step 3 — Test on one company

Take one company from the list and start one run with `clay workflows runs test <wf> --inputs`
carrying the four trigger inputs; wait with `clay workflows runs get <wf> <run> --wait`, then read
`clay workflows runs get <wf> <run> --verbose`:

- **cost** — the top-level `dataCreditsUsed` and `actionCreditsUsed` are this run's actual spend. Use
  them, **never the workspace balance**, which moves with everyone else's work.
- **values** — each node is in `.nodes[]` by `nodeName`; the tool nodes' payloads are at
  `.outputs.result`, each Claygent's `events_json` at `.outputs.structuredOutputs.events_json` — a JSON string that
  may be the bare array or an object holding it under the prompt's array key; parse both. Check
  values, not status: a Claygent that completed with `[]` found nothing, which is a real answer; one
  that completed with prose instead of JSON is a build error to fix (schema, wiring), never a prompt
  to reword.

Then run Step 5 on this one company so the sample in Step 4 is the finished summary.

## Step 4 — Show the sample, set the cap, then run the rest

**One message:** the company's full summary in the output shape below, the measured cost for one
company, that cost × the remaining companies, and one question: *what is the most you want to spend
on this list?* Say plainly that research depth varies by company, so later ones can cost more or less
than the first. **Wait** — this is the look at what the passes actually found that no estimate
reveals, and the spend decision in the same breath.

Then start one run per remaining company, a few at a time. Keep a running total of each finished
run's `dataCreditsUsed`; **stop before the next batch would pass the cap** and say how many companies
remain.

## Step 5 — Combine, window-check and format, in code

Parse each `events_json`. Then apply the author's rules from `references/prompts.md` exactly, in
code and never by judgment: concatenate the four arrays in the stated order, keep only events whose
`eventDate` is on or after `lookback_start_date`, drop any whose `eventDate` contains `@`, sort newest
first, and render the *Events summary* and *New leadership* blocks in both the plain and Markdown
shapes given there. An event with an empty `eventDate` fails the window test and is dropped; count
how many were dropped for that reason and say so. Build the leadership block from *Find new
leadership* only, and every event field from the Claygent that produced it.

## Step 6 — Deliver

Per company: the resolved name, domain and LinkedIn URL; run date and lookback start date; the
leadership block headed "N shown of M who joined in the window with a leadership title"; the events block; and a count line — joiners found, events kept, events dropped as
undated or out of window, passes that returned nothing. Then the list-level summary: companies in,
resolved, with at least one event, with at least one joiner, failed runs, and credits spent (the sum
of each run's reported `dataCreditsUsed`) against the cap. Then the answer-sheet offer from
*Declared inputs*.

## Representative output

### Company brief

**Northwind** · northwind.example · linkedin.com/company/northwind
Run date 2026-09-28 · window from 2026-06-28 (3 months)

New leadership (2 shown of 2 who joined in the window with a leadership title)
- **Dana Whitfield** — Chief Revenue Officer, Austin, TX
  [LinkedIn](…) | Started: 2026-08-01
- **Sam Ortiz** — VP Engineering, Remote
  [LinkedIn](…) | Started: 2026-07-15

Developments (4 kept · 1 dropped as undated)
- **Acquisition — 2026-09-12** Northwind acquires Fabrikam Analytics for $40M [Source](…)
- **Company Announcement — 2026-09-03** Northwind launches Northwind Cloud 3.0 [Source](…)
- **Transformation Program — 2026-08-20** Northwind selects SAP S/4HANA for global ERP replacement [Source](…)
- **Contract Award — 2026-07-02** Northwind awarded 5-year logistics contract by Contoso [Source](…)

Passes with nothing in the window: none. Procurement returned 1, news 2, M&A 1, transformation 1.

### List summary

| Companies in | Resolved | With events | With new joiners | Failed runs | Credits spent / cap |
|---|---|---|---|---|---|
| 25 | 24 | 17 | 11 | 0 | 61.2 / 80 |

## What this skill does not claim

- The leadership title list is a keyword match on current titles, so "Director of Photography" counts and a founder titled only by name does not; no seniority taxonomy was used because the platform's own values could not be read at authoring time.
- How complete the four research passes are was never measured — each returns what its searches found, and a quiet pass is not proof that nothing happened.
- Event dates come from the sources the passes found; a source that misdates an event misdates it here.
- The graph has been run end to end once, on one large company over a 12-month window: 5 data credits, 6 action executions, 80 seconds, 11 events found of which 2 fell before the start date and were dropped. Nothing has measured a list, a small company, or a short window.
- The joiner list is capped at 10 by the action; the total is reported beside it, but who the other joiners are is not.
- Whether an event the passes report is true is only as good as the source they cite; the author did not verify the test run's events against the sources.
- Whether `gpt-4.1-mini` is the right model for these prompts was never tested against another; it is what the author ran.

## What good looks like

- Every event carries a date on or after the start date and a source URL; nothing undated survives.
- Every joiner carries a start date inside the window and a profile URL.
- A company with no events says so, per pass, rather than vanishing or being padded.
- The same company run twice with the same window returns the same joiners; the events may differ only by what the web now says.
- The common mistake: rewording the prompts "to fit the skill". They are the product; the skill is the wiring.

## Rules

- MUST use the four prompts in `references/prompts.md` verbatim, on the model listed there; NEVER reword, merge or substitute a model silently.
- MUST compute `lookback_start_date` before the first run and pass the same value to every pass; NEVER let a pass run without a window.
- MUST drop any event that is undated or dated before the start date, and say how many were dropped.
- MUST look for an existing **Recent company developments** workflow before building, and NEVER edit a workflow, table or record this skill did not create.
- MUST get explicit approval (Step 2) before creating the workflow or running it, and a spend cap (Step 4) before running more than one company.
- MUST resolve each company from a LinkedIn URL or domain through Enrich company; NEVER accept a name alone as the identifier.
- MUST confirm the leadership title list with the installer before the first run, and pass it to the joiner search on every run.
- MUST combine, filter, sort and format in code, from the node that produced each value.
- NEVER contact anyone or write to a CRM — this ends at the summary.

## Worked example

Ask: "Brief me on these 25 accounts — what's changed in the last 3 months?" Step 0: signed in, Clay
plugin present. Step 1: a CSV of 25 domains → 24 unique; lookback 3 months, start date computed; all four
passes; the default leadership list confirmed; summary to the conversation and a CSV. Step 2: no existing workflow; the seven-node graph and the
one-company test are approved; built, validated, attribution written and read back. Step 3: test on
one company — resolved, 2 joiners of 2, 5 events across the passes; run reports 5 data credits. Step 4:
the brief is shown with "this one cost N credits, about 23 × N for the rest — what's the most you
want to spend?"; cap set. Step 5: 23 runs in batches, totalling reported credits between batches;
combined, windowed, formatted. Step 6: 24 in · 24 resolved · 17 with events · 11 with joiners · 0
failed · credits spent against the cap.

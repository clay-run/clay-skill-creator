---
name: paid-alumni-job-changer-enrollment
description: |
  Build an unattended Clay workflow for the paid-alumni job changer play: when someone leaves one of
  your paying customers and joins a company you would like to win, check the move against your CRM
  gate by gate, draft persona- and usage-aware outreach that is honest about what the person actually
  did with your product, and enroll them the same day in the account rep's sequence — an automatic
  email flow, or a manual multi-touch flow of calls, emails and LinkedIn touches — then log the
  enrollment to a CRM campaign and the rep's task queue. Use whenever someone asks: reach out when a
  customer's champion changes jobs, build a paid alumni job changer play, follow former customers'
  leaders to their new company, turn job-change signals into same-day outreach, sell to people who
  just left our customers, or route job changers to the right rep with drafted copy. Do NOT use it to
  send a congratulations email to everyone with the right title, to detect job changes in the first
  place, to score or tier accounts, to create or clean CRM contacts, or to report on who changed jobs.
category: route-and-automate
personas: [revops, gtm-engineer]
mechanism: workflow
touches: writes-records
keywords: [job-change, sequencer]
---

# Paid-alumni job changer enrollment (paid-prior is the signal; timing beats persona)

The insight, in its author's words: **when someone leaves a paying customer, pair the departure with
where they go next, and a churn risk becomes a buying signal.** The person has landed somewhere new,
with a goal to fulfil and often an incomplete stack, and they remember what the old one did for them.
Three things make the play work, also in the author's words:

- **Paid-prior is the signal.** The old company paid for the product, which says the system was
  valuable enough to keep paying for. Whether the person personally used it matters much less.
- **Timing beats persona.** Outreach that arrives in a leader's first months, while they are deciding
  what their team will run on, matters more than a perfect ICP match whose stack is already settled.
- **Power plus context.** Director-level and above can install a stack, and they arrive knowing what a
  working one looks like.

What follows from it is the shape of this skill: **a long chain of free checks, each able to stop a
record with a named reason, so that the only records that reach a rep are ones the CRM can vouch for.**
The author's workflow fails closed throughout — a CRM lookup that errors is never read as "not found",
a person with no contact on the new account is skipped because the play never creates contacts, an
account with no assigned rep is skipped rather than given an invented owner, and an enrollment is not
believed until the sequencer is read back. The author's own figures, from their write-up: the filters
are strict, so only a handful of moves qualify — roughly one enrollment a day for sales personas, and 62
people meeting every criterion across 60 days of job changes.

**Why a workflow and not an agent loop:** a signal starts this, not a person. Job changes are detected
daily and the window to reach the person shrinks each day, so the sequence has to be waiting the same
day — nobody is in a conversation when the signal fires. This skill's job is to **build** that workflow
in the installer's workspace, prove it on test records, and set it live.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and if an answer does not exist say which step becomes unavailable
rather than guessing. Where the author used a value it is named, and using it means saying so in the
output.

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
Say which values came from the sheet before using them. If there is no sheet, say nothing about sheets.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Your product** | what you sell, in one line, and what "already ran on it" means for a team | no default — the copy cannot be written. Stop at Step 1 |
| **Job-change signal** | the feed that detects career moves for contacts tied to your accounts and POSTs each one to the workflow's webhook: a unique event id, person, persona, old account, new account, the new account's tier, and a usage subtype — regular (no product history), product user (had a seat), power user (hands-on) | no default — there is nothing to trigger on. Stop at Step 1 |
| **Audience rules** | the filters applied to the signal before it reaches the workflow: how you know the old account paid, which titles are senior enough, which functions are out, which new-account tiers and types are in | the author kept paid-prior accounts only (trials and free never count); VP, Head of, Director and above, CRO, Chief Revenue, Chief Sales or tagged decision-maker; excluded customer success, partnerships, enablement, SDR and BDR management and fractional roles; kept sales tiers 1–3 and excluded enterprise, agencies, VC and PE firms, and education. Ask; borrow only if they have no view, and say so |
| **Excluded tier** | the new-account tier the workflow itself rejects, as a second check | the author's workflow rejected the enterprise product tier |
| **Persona filter** | whether the workflow drops records outside a persona list, and the list | the author's write-up names sales, ops, marketing and executive; the author's workflow is currently configured to let every persona through. Ask — turning the filter on can remove a large share of records whose persona is unknown or outside the list |
| **CRM** | which CRM they run, that a lookup action for it exists in their Clay action catalogue, and the contact, account, user and campaign-member fields the checks read | stop at Step 0. Read their schema and show the mapping; ask only about what does not match. The author used Salesforce |
| **Required contact fields** | fields that must be populated before a contact can be enrolled | the author's workflow required first name, last name, email, LinkedIn URL and title; phone is read but optional |
| **Sender** | the account field naming the rep who owns the sequence, and that rep's user fields: email, active flag, booking link | no default, and no fallback to the account owner. Without it the record skips |
| **Qualification and routing step** | their own step returning: qualified or disqualified, the resolved contact and account, whether the person belongs to another team's motion, which booking link to use, and the sequence type — `automatic`, `manual` or blank | no default and no stand-in — this is the installer's rules of engagement. Step 2 cannot be built without it |
| **Sequencer** | which sequencer they run, that its add-to-sequence and read-assigned-sequences actions exist in their catalogue, and the connected account that owns each | stop at Step 0. The author used Gong Engage |
| **Sequences** | the automatic sequence and the manual sequence, each with its step layout | no default. The author's two layouts are in `references/node-graph.md` as an illustration only. With only one sequence, every record routes to it |
| **Copy step** | either their existing copy generator, or their copy rules for the skill's own copy node (see Step 5) | if neither: stop at Step 1. Outreach with no rules is the "congrats!" email this play exists to replace |
| **Campaigns** | the CRM campaign each sequence's enrollments are logged against, and their create-or-update step for campaign members | no default. Without a campaign the cooldown cannot run either — say so |
| **Task queue** (optional) | the queue that tells the rep a new enrollment is waiting, and what it needs | skipped, and runs end `enrolled` without it |
| **Cooldown** | whether an account already touched by this play is skipped, and for how many days | the author's write-up describes 30 days; the author's workflow currently runs with the cooldown off. Ask: on or off, and how many days |
| **Alert channel** | where soft failures go, and who owns them | no default. The author's rule: growth owns anything the play misses, sales owns everything it sends |
| **Off switch** | the single obvious way to stop the play | the author pauses the data feed. Name it in Step 7 |
| **Verify delay** | seconds to wait before reading an enrollment back from the sequencer | the author used 60. Defensible; state it |

## What this skill touches

- **Reads** — the installer's CRM contact, account, user and campaign-member records; their sequencer's
  assigned sequences for a contact; their Clay action catalogue; the job-change records the signal
  sends.
- **Writes** — a new workflow in the installer's Clay workspace (nodes, a webhook trigger, and one
  provenance line in its description); once live, one sequence enrollment per qualifying record in their
  sequencer, owned by the account's rep — and the automatic sequence sends email from that rep's account
  with nobody reviewing it; one campaign member per enrollment in their CRM; one task-queue entry where
  configured; and alert messages to the channel they name.
- **Never** — creates a CRM contact, invents a sender, claims product usage the record does not support,
  deletes or clears any record or field, sends anyone's data to a destination the installer did not
  name, or enrolls a record whose lookup errored.
- **Halts** — Step 2 write-approval, Step 4 sample-review, Step 6 spend-approval, Step 6 send-approval, Step 6 write-approval

## Step 0 — Check the platform, and say where the work runs

Say this before anything else: *"This builds a workflow in your Clay workspace. Building it writes
nodes there; once it is live, it enrolls qualifying people into your rep's sequences — one of which
sends email automatically — and logs each one to a CRM campaign. It never creates contacts, never
deletes anything, and never enrolls anyone a check could not confirm."*

Then check, and stop on the first failure:

1. `clay whoami` returns a user and a workspace. Name the workspace out loud.
2. `clay workflows nodes --help` lists `create`. **Confirm node syntax here, on the installed CLI —
   never from a form written in this file.**
3. `clay workflows actions list` contains a lookup action for their CRM, an add-to-sequence action and
   a read-assigned-sequences action for their sequencer, and a send-message action for their alert
   channel. Read each one's real inputs with `clay workflows actions schema <packageId> <actionKey>`.

**Step 0 is a gate, not a repair shop.** If any check fails, say which component is wrong, what is
required, and the one command that fixes it — then stop. Do not install, upgrade or fetch anything.

**Where the work runs:** every check is a code node or a read on the installer's own connected CRM. The
steps that bill Clay credits are the routing step, the copy step, the sequencer and campaign writes and
the task queue; their prices are read in Step 6, never assumed.

## Step 1 — Define the audience (interview; do not guess)

Do not start a step before the steps above it have their answers. If a declared input is missing, ask
for it — never assume a default and continue.

**Most job changes are never worth a rep's time, so the audience does most of the work.** Collect the
audience rules one at a time, then confirm the signal applies all of them **before** a record reaches
the workflow, plus two rules about the data itself:

- **Trigger on the date the change was detected, never the job start date.** Start dates come from
  LinkedIn at month granularity and pile up on the first of the month; detection dates spread out
  because detection runs daily.
- **One record per person per new account.** The same move can be detected more than once — keep the
  most recent and discard the rest.

Then ask the persona filter and cooldown questions — both change who gets contacted — and collect the
copy rules (Step 5). Read their CRM schema through the lookup action, **show the mapping you found for
the fields this play needs, including what did not match**, and ask only about the unmatched rows. Ask
for one sample record from their signal and map it onto the intake fields in `references/node-graph.md`.

## Step 2 — Build the workflow (write-approval)

Say: *"I'm about to create a workflow in your workspace — around sixty-five nodes, a webhook trigger,
and one line in its description so it can be traced back to this skill. Nothing runs until you set it
live. Go ahead?"* Then stop and wait.

On a yes:

1. Create an empty workflow (`clay workflows create`) and hold the id it returns. **On any retry, reuse
   that id** — never create a second workflow.
2. Write the description with `clay workflows update <id> --description`, ending with the provenance
   line on its own line. Read the description first: a fresh workflow returns `null`; keep any existing
   text; write nothing if this marker is already there; **report a conflict and write nothing** if a
   different marker is there. The marker is
   `Sourced from marketplace skill: <marketplace_slug>@<marketplace_revision>`, from the identity fields
   the Marketplace put in this file's frontmatter. If those fields are absent, skip the marker and say
   *"Marketplace attribution is unavailable for this skill."* Read the description back and check both
   halves landed.
3. Add a webhook trigger (`clay workflows triggers create`, reading an existing trigger's shape first).
4. Create the nodes **in dependency order**, exactly as `references/node-graph.md` lists them — each
   node's type, what feeds it, and its outgoing edges. Read one node back with `clay workflows nodes get`
   before creating the first of each new type, so the shape you write is the shape this workspace
   accepts.
5. Validate with `clay workflows graph validate`. An error stops the build; report the node it names.

**Node rules that decide whether the build works:**

- **Every decision lives in a code node or a rules conditional. Never in an LLM node.** If the copy step
  is an LLM node, it writes prose and nothing else; which usage claim and persona angle apply are decided
  in code first and handed to it.
- **The chain is serial, as the author built it.** Do not parallelise the CRM reads: parallel branches
  converge, a convergence needs a merge node, and an asymmetric merge node stays pending forever.
- **The one fork is deliberate:** the automatic and manual enrollment nodes both feed one normalize
  node, and only one of them runs. That node reads both inputs and keeps the one that ran — do not
  replace it with a merge node.
- **A tool node does not echo its inputs**, so trigger fields cannot ride through it — pin them from the
  intake node directly. **A pin two hops back resolves to null**, so pin each value from the node that
  produced it. **Tool-node pins read `$.result`; code-node pins read `$`.**
- **Never require a pin on a field an empty lookup does not return.** A lookup that finds nothing comes
  back with no `foundAtLeastOne` at all, and a node that requires that path fails the whole run — and
  skips the alert path on the way out. Read the lookup's whole result object and decide in code, the way
  every gate in `references/node-graph.md` does.
- **Blank strings become `-` before any pin**, so an empty field cannot fail the run.
- **Every terminal node returns `status`, `reason` and `detail`** — that is the run log Step 7 reads.

## Step 3 — The checks, in a fixed order

Each record passes these in order and either exits with a named reason or continues. **If any check
errors or cannot find its data, the record skips or alerts — it is never sent.** All of these are free.

1. **Sanity** — no event id or new account → `invalid_payload`; same company on either side by id, name
   or domain → `same_company`; a placeholder employer → `placeholder_new_account`; malformed identity →
   `unusable_identity`; the pause switch on → `workflow_paused`.
2. **Excluded tier** — the new account is in the excluded tier → `new_account_enterprise`.
3. **Persona** — if the installer turned the filter on, a persona outside the list → `persona_not_live`.
4. **Contact** — the person must already exist as a contact, with every required field populated. The
   lookup ignores blank emails so an empty value cannot match a random record. **The workflow never
   creates a CRM record** → `would_create_contact`, or `incomplete_contact` naming the missing fields. A
   lookup error alerts; it is never read as "not found".
5. **Route and qualify** — the installer's routing step runs here. Disqualified → `disqualified`; a
   different contact than the lookup found → `ids_mismatch`; a suppressed account → `account_suppressed`
   with the CRM's reasons; no rep → `no_rep`; belongs to another team, an inactive
   rep, or no usable booking link → `not_enrolled`. A link containing a template token or an
   inbound-routing path is not usable.
6. **Cooldowns** — the contact is already in an active sequence → `in_flight`; if the installer turned
   cooldown on, the account has a campaign member on this play's campaigns inside the window →
   `account_cooldown`.

## Step 4 — Dry run on test records, then show the outcomes (sample-review)

**This is a dry run because the live step cannot be taken back.** A ten-record live test is ten real
people enrolled, and on the automatic sequence that is ten real emails sent. So the build carries a
`DRY_RUN` switch, read by one conditional placed **directly before the copy step**: when on, the run ends
`would_enroll` with the persona, usage subtype, contact, rep, sequence type and campaign it would have
used — no copy, no enrollment, no CRM write.

1. Load **ten test records built from the installer's sample** with `clay workflows test-data` against
   the webhook trigger, including at least one each that should stop at: same company, excluded tier, no
   contact, suppressed account, no rep, already in a sequence — and an unknown persona or a cooldown hit
   if those are on. A skip path that has never fired is not a safeguard, it is a paragraph.
2. Run the draft against them with the switch on.
3. Show one line per record: outcome, reason, detail. **Point out any record that stopped at a different
   check than expected** — which check stopped it is the question, not whether it stopped. And **no run
   may end `failed`**: a failed run is a node that could not resolve its inputs, which is a build defect,
   not an outcome.

Then stop and wait for the installer to read it.

## Step 5 — Copy and handoff (built into the graph)

These run only on live records that cleared Step 3. They are described here because they hold the
play's judgment; their nodes are in `references/node-graph.md`.

**Copy rules — the installer's, collected in Step 1, in the author's shape.** Whether the copy comes
from the installer's own generator or from this skill's copy node, it must follow these.

The usage subtype decides **what the copy may claim** — the honesty rule, and the most important one:

| Subtype | What the copy may say |
|---|---|
| regular | what the old company's teams ran on the product. **Never** that the recipient used it |
| product user | that they had a seat at the old company, without overstating how much they used it |
| power user | skip the introductory pitch; talk about getting set up again at the new company |

The persona decides **the opening angle**. The author's four, for a product the old company's GTM org
ran on:

| Persona | Opening angle |
|---|---|
| sales | at the old company, it is what ops and growth were using |
| ops | at the old company, your function ran it |
| marketing | at the old company, growth used it for lists, targeting and personalisation |
| executive | at the old company, the GTM org already ran on it |

**Every message, always:** never criticise either company, never invent details about the old company's
stack, close with the rep's booking link, and if no lookalike use cases exist for the new account — what
similar companies do with the product — drop that section rather than invent one. The author's account
records carried three lookalike use-case fields.

**The copy step returns** four emails (insight, use case, value nugget, final), three LinkedIn messages
(insight, use case, value nugget), call notes, and a status. A status other than `generated` →
`copy_not_generated`.

**Pick the sequence.** From the routing step's sequence type: `automatic` → the automatic sequence;
`manual` with a phone on the contact → the manual sequence; `manual` without a phone → the automatic
sequence; blank → `blank_guidelines`.

**Enroll, verify, log.** Enroll the contact owned by the account's rep, with the drafted copy mapped to
each step. If the response does not return the expected sequence id and an instance id, wait the verify
delay and read the contact's assigned sequences back; not found → `enroll_failed`, alerted. Then write
the campaign member against that sequence's campaign, then the task-queue entry. A missing campaign
member → `campaign_member_failed`; a missing queue record → `queue_failed`; both alerted.

## Step 6 — One gate: the result, the cost, the sends, the writes, the ask

One message, carrying all of it:

- the dry-run outcome table from Step 4;
- **the cost per enrolled person**: read the routing step's, the copy step's and each write's price from
  the installer's workspace and add them. Expect most of it to be routing and copy, and **never quote a
  figure you did not read from their workspace**;
- **the sends, named as sends**: *"Once live, every job change that clears these checks is enrolled the
  same day. Records routed to the automatic sequence get email from your rep's account with nobody
  reviewing it first; records routed to the manual sequence wait for your rep."*
- **the writes, named as writes**: one campaign member per enrollment, on the campaign for its sequence;
  one task-queue entry where configured;
- the ask: *"Set it live?"*

Then stop. Only on a yes: turn the dry-run switch off, publish (`clay workflows publish`), and give the
installer the webhook URL to point their signal at. Stop a second time only if the dry run showed
something nobody named — a check stopping every record, a mapping that resolved nothing.

## Step 7 — Deliver, and read what each run decided

Every run ends at exactly one terminal node, so every run has exactly one outcome. **These four, no
fifth:**

| Outcome | Means |
|---|---|
| `enrolled` | in the rep's sequence, confirmed by the sequencer, logged to the campaign and the queue |
| `would_enroll` | dry run only |
| `skipped` | stopped at a named check — the reason says which |
| `error` | a lookup, the enrollment, the campaign write or the queue failed — an alert was posted |

**An enrollment is `enrolled` only when the sequencer says so.** Never infer it from a completed call.
**A run that ends `failed` instead of one of these is a build defect** — fix the node that failed rather
than reading it as an outcome.

Report, in one message: the workflow id and URL and whether it is live; the webhook URL; whether the
provenance line was written, already present, or unavailable; the dry-run outcome table; the off switch,
named; and any declared input they skipped with the step it disabled.

Then offer, in these words or close to them: *"Want me to save your answers to a file alongside this? It
isn't part of the skill — it's a short note of what you told me: your audience rules, your CRM fields,
your two sequences, your copy rules. You'd never answer these again if you rebuild it, and a teammate
handed the file and the skill gets asked only what it doesn't cover. It stays with you — never submitted
or published, and it holds no passwords or API keys."*

## Representative output

### Dry-run outcomes

| Record | Outcome | Reason | Detail |
|---|---|---|---|
| Ada Moreno, VP Sales → Northwind | `would_enroll` | — | sales persona · product user · automatic sequence · rep active · booking link usable |
| Ben Okafor, Head of Ops → Contoso | `skipped` | `account_suppressed` | Contoso is suppressed in the CRM: "marked do-not-contact" |
| Cara Lin, CMO → Fabrikam | `skipped` | `would_create_contact` | no CRM contact for this email at Fabrikam; this play never creates contacts |
| Dev Shah, Director RevOps → Tailspin | `skipped` | `in_flight` | already in an active sequence |
| Eli Park, CEO → Litware | `error` | `lookup_error` | the account lookup returned no record set; alert posted, not treated as not found |

Five records, one would enroll. The verdicts are `would_enroll`, `skipped` and `error`; `enrolled`
appears only on live runs.

### First email, drafted for a regular-subtype sales leader

**Subject:** what Contoso's ops team ran

Hi Ada — congrats on the move to Northwind. At Contoso, our product is what your ops and growth teams were
using to build target lists and route inbound. Teams Northwind's size usually start with two things:
enriching inbound leads before a rep sees them, and keeping account research current without a weekly
scramble. If either is on your list for the first quarter, here's a time that works:
calendar.example.com/rep.

## What this skill does not claim

- The insight and the copy rules are the author's, from their write-up of the play; the workflow
  configuration itself carries no prompt stating either.
- The author's workflow is currently configured with every persona allowed and the cooldown off, while
  the write-up describes both as on; this skill makes each one an installer decision.
- The enrollment figures are the author's, in their own market; nobody has measured what this play
  yields elsewhere, and there is no measured cost per enrollment.
- The author's routing step, copy generator, campaign-member step and task queue are separate pieces of
  their workspace that were not read; this skill declares what each must return, not how each works.
- The skill's own copy node is written from the author's stated copy rules and has not been compared
  against the author's generator's output.
- The identity check confirms routing resolved the same contact; also requiring the same account is left
  to the installer.
- The author's two sequence layouts are reproduced as an illustration; nothing established that they suit
  anyone else's sequences.
- The 80-character identity limit, the placeholder employer names and the 60-second verify delay are the
  author's workflow values; nobody established why those numbers.

## What good looks like

A good build ends with a live workflow whose dry run stopped each deliberately bad record at the check it
was written for, let the clean ones through as `would_enroll`, and ended no run `failed`. Once live, every
run has one outcome and one reason, every `error` has a matching alert, the count of `enrolled` runs
matches the count of new campaign members, and each email names the right old company, makes only the
usage claim its subtype allows, and closes with a working booking link. A bad build looks finished and
fails quietly: runs end `failed` at a gate reading an empty lookup (and post no alert), every record ends
at the same check (a field mapped wrong), a regular-subtype email says *"you used"*, lookup errors end as
`skipped` instead of `error`, or dozens enroll on the first of the month (the trigger is on the start
date).

## Rules

- **MUST** build the workflow; never process job changes in the conversation.
- **MUST** fail closed: a check that errors or cannot find its data skips the record or alerts.
- **MUST** decide every route and every copy rule in code; any LLM node writes prose only.
- **MUST** trigger on the detection date and keep one record per person per new account.
- **MUST** dry-run before going live, show which check stopped each test record, and end no run `failed`.
- **MUST** confirm enrollment by reading the sequencer back before recording it.
- **MUST** name the automatic sequence as a send at the Step 6 gate.
- **NEVER** create a CRM contact, invent a sender, or fall back to the account owner.
- **NEVER** let the copy claim a person used the product when their subtype is regular, criticise either
  company, or invent the old company's stack.
- **NEVER** delete, clear or blank a field; the campaign write sets only the fields named in
  `references/node-graph.md`.
- **NEVER** hardcode the author's tiers, titles, sequences, campaigns, channel or people — read each from a
  declared input.
- **NEVER** publish without the single Step 6 yes.

## Worked example

A Head of RevOps at a paying customer, Contoso, is detected starting at Northwind, a 50-person fintech in
sales tier 2. The signal's audience rules let her through. In the workflow, the old and new domains
differ, Northwind is not in the excluded tier, and the persona reads as ops. The CRM has a contact for her
at Northwind with every required field and a phone number. Routing returns qualified, the same contact,
Northwind's rep, the rep's booking link and sequence type `manual`; Northwind is not suppressed; the rep is
active; she is in no sequence; cooldown is on and Northwind has no campaign member on this play in the
last 30 days. The copy step, given her subtype — power user — and the ops angle, drafts four emails, three
LinkedIn messages and call notes. Because routing said manual and a phone exists, she goes to the manual
sequence. The add call returns the manual sequence id and an instance id, the campaign member is written
against the manual sequence's campaign, the queue entry is written, and the run ends `enrolled`. The rep
starts with the LinkedIn connection request that afternoon. The same move detected again the next day ends
`in_flight`.

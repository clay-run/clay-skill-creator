---
name: find-work-email
description: |
  Find and verify a person's work email address using Clay — from their name and company,
  or their social URL. Use whenever someone asks: find someone's email, what is this
  person's work email, get a verified email for this contact, find the email address of a
  person at a company, or turn a short list of names into verified work emails. It screens
  the domain free first (MX check, disposable/trap-domain screen — dead domains cost
  nothing), runs Clay's provider waterfall (cascading sources, stopping at the first valid
  hit, so you only pay for what it finds) plus deliverability verification, switches to a
  recovery track on catch-all domains where validators lie, and ships only addresses that
  plausibly belong to the person — role addresses (info@, sales@) are rejected, catch-all
  and risky results are flagged, and every address names the source that produced it. Do
  NOT use it to check an address you already have (verify-email-deliverability), to
  bulk-clean an existing list or CRM (clean-email-list), to identify who a person is from
  an email you already have (reverse enrichment), or to source net-new prospects by
  persona (people search). It never guesses email patterns.
category: find-contact-data
personas: [sales-development]
mechanism: functions
touches: read-only
keywords: [waterfall]
---

# Find a work email

The insight that separates this from typing `first.last@company.example` and hoping: **found is
not the same as sendable.** A pattern-guessed or unverified address burns sender reputation
when it bounces. So verification is part of the find, not an afterthought — and an honest
"not found" beats a fabricated address every time. And the deeper version of the trap: on a
catch-all domain, *verification itself lies* — the domain answers "deliverable" for every
address, real or invented, so a validator can neither confirm nor deny the mailbox. Those
domains need a different find, not a stronger validator.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **What they have per row** | a profile URL plus name, a name plus domain, or a name plus company name only | no default. Quality descends in that order, and the third route resolves the domain first — a wrong domain poisons every lookup, silently |
| **A known personal email** | if they have one | optional, and it raises the waterfall's hit rate. Pass it through when present |
| **Cost ceiling** | credits, and whether misses are acceptable | state per-row cost before running, and say plainly that a waterfall bills for attempts, not only for hits |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — what each row already carries, and the provider waterfall plus deliverability checks it runs.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, sends to an address, or guesses an email pattern.
- **Halts** — Step 3 spend-approval.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run the Clay
plugin's `setup` skill (or follow
https://raw.githubusercontent.com/clay-run/agent-plugins/main/GETTING_STARTED.md), restart
the agent if setup says to, and re-run this skill. Tell the user which workspace you're in.

## Step 1 — Collect what identifies the person

Best → worst input quality:
1. **LinkedIn URL** (plus name/company) — highest match accuracy.
2. **Full name + company domain** — the standard case.
3. **Full name + company name only** — resolve the domain FIRST (a company-domain function
   exists for exactly this) and sanity-check it; a wrong domain poisons every downstream
   lookup and the failure is silent.

A personal email, if known, improves the waterfall's hit rate — pass it through.

## Step 2 — Free domain pre-gates (zero credits)

Screen the domain before the first paid lookup — a domain that fails here costs nothing
and poisons nothing downstream:

1. **MX check** (any DNS tool — never hardcode a DoH URL; some networks block them). Three
   shapes: **NXDOMAIN or no MX records** → the domain can't receive mail — report
   `not found (dead domain)` free, skip every paid step. **Null MX** (a single record
   `0 .`) → the domain *declares* it takes no mail — same verdict, even though a record
   "exists". **Real MX** → proceed.
2. **Trap/disposable screen.** Known disposable and spamtrap domains (mailinator,
   guerrillamail, yopmail, …) → `blocked: trap domain` — never find, never email. These
   are honeypots; one send can burn the sender's whole domain reputation.

## Step 3 — Run the managed function

Use the workspace's managed **Work Email** function (confirm it exists with
`clay routines list` / `get` — never promise a function you haven't confirmed). It cascades
providers and stops at the first valid result. Check its `estimatedCreditCost` and the
workspace balance (`clay credits`); for anything beyond a handful of lookups, state the
total cost and get explicit approval first.

- **1–20 people:** run the function directly (CLI `clay routines runs start`, or the Clay
  MCP). The CLI input envelope is `{"items":[{"id":"<your-key>","inputs":{...}}]}` piped via
  `--input -`; discovery note — `clay routines list` paginates and can omit managed
  functions, but `clay routines get function:<id>` fetches any of them directly.
- **Hundreds, or recurring:** this stops being a lookup and becomes a pipeline — put the
  list in an Audience and run it through a workflow or table instead, and say so.

Set time expectations: a hit returns in seconds (the waterfall stops early), but a
not-found takes minutes — the cascade exhausts every provider before giving up. A batch
containing bad rows finishes at the speed of its misses.

## Step 4 — The catch-all branch (where validation lies)

Detect it cheaply: run a validator (~0.1 credits, catalog action) on the found address —
ZeroBounce `status: valid` + `sub_status: catch_all`, or Enrichley `result: catch_all`,
marks the **domain**, not just the address. (A deliberately-invalid probe like
`test1234@` + domain validating as deliverable is the same diagnostic — the one place this
skill ever constructs an address, and it never ships: probes diagnose domains, only found
addresses ship.) One trap verified live: catch-all is a *per-validator verdict*, not a
domain fact — one validator resolved a specific mailbox as not-found on the very domain
another graded catch-all. Stay inside one validator's vocabulary end to end: detect with
the same validator whose mailbox probe you'll use for recovery, and never read one
validator's catch-all verdict into another's fields.

On a catch-all domain the normal machinery breaks in both directions: validator-interleaved
find arms *discard real addresses* (every candidate comes back "unconfirmable"), and naive
acceptance *blesses bounces*. The production answer is a dual track, not a caveat:

- **Valid-domain track** (the default above): validator-interleaved waterfall; accept only
  verified-deliverable.
- **Catch-all track**: a second, WIDER find pass with **no validator interleave** — first
  found address wins, because per-arm validation on these domains only destroys candidates.
  On the agent surface, run the catalog's find actions directly without validation gating.
  Gate this track on employment confirmed current — an unverifiable address for a possible
  job-changer is a double risk.
- **Mailbox-level recovery**: Enrichley probes the specific mailbox on a catch-all domain —
  `result: catch_all_validated` means confirmed live (ship as valid, probe-confirmed);
  plain `catch_all` stays unconfirmable. This recovers a meaningful share (production
  builds see 20–40%) of addresses the interleaved track would have thrown away.
- **Coalesce with provenance**: prefer the valid track; the status distinguishes
  `valid` / `valid, catch-all (probe-confirmed)` / `catch-all (found, unprobed — risky)`
  so the send side can throttle instead of treating all addresses alike.

Checking a single address you already have is `verify-email-deliverability`'s job — this
branch exists because on catch-all domains the *find itself* changes shape.

## Step 5 — The email-matches-contact check (anti-info@)

Before shipping, check that the local-part plausibly belongs to the person — a provider
that returns `info@company.example` for "Jordan Lee" found the *company*, not the person:

- Local-part carries a name token — `jordan.lee`, `jlee`, `jordanl`, `jordan` — → pass.
- Role/functional local-parts (info, contact, support, sales, admin, hello, office, team,
  billing, hr, press, marketing, careers, jobs, noreply, postmaster, abuse, webmaster, …)
  → **reject as this person's email**: report `rejected: role address`, never ship it in
  the email column.
- Ambiguous (handle-like, digit-mixed, no recognizable name correspondence) → precision
  over recall: flag for review rather than blessing — a wrong match sends someone's pitch
  to a stranger; a not-found costs nothing.

## What good looks like

- **Only verified-deliverable addresses ship as "valid"** — and on catch-all domains, only
  probe-confirmed ones. A found-but-unverifiable address is a flag, not a result.
- **Every shipped address names its source** — which track and which provider (or "managed
  waterfall") produced it. Provenance is what makes a fill rate auditable and a bad
  provider findable; production builds carry it as a twin column on every waterfall.
- **Not-found stays empty.** Never backfill with a pattern guess (`first.last@domain`) —
  that's fabrication with a bounce risk attached. And know the shape: a no-hit run returns
  `status: complete` with an empty result object — completion is not data; gate on the
  presence of an actual address.
- **Know what the managed function does and doesn't tell you.** It returns an address only
  when its internal verification passes — but it does not surface catch-all/risky
  discrimination, and on a catch-all domain its interleaved verification can discard real
  addresses. When the send matters, add the explicit validation step and the catch-all
  branch.
- The common mistake: reporting whatever a single provider returns. One source's confident
  answer is exactly that — the waterfall, verification, and the matches-contact check are
  what make the result real.

## Rules

- MUST run the free domain pre-gates before any paid lookup; NEVER spend on or email a
  dead, null-MX, or trap/disposable domain.
- MUST resolve and validate the company domain before searching when given only a company
  name.
- MUST state cost and get approval before multi-person runs; re-check credits first.
- MUST run the email-matches-contact check; NEVER ship a role address (`info@`, `sales@`…)
  as a person's email.
- MUST ship provenance (track + provider) with every address.
- NEVER guess, construct, or pattern-infer a shippable address — domain probes are
  diagnostics, never results.
- NEVER report a catch-all address without its flag; unprobed catch-all is risky, not
  valid.

## Representative output

Two artifacts. **Every name, domain and address below is invented** (`.example` reserved
TLD). The six statuses are **valid / valid, catch-all probe-confirmed / catch-all risky /
rejected: role address / not found / blocked: dead or trap domain**, and every person asked
for lands in exactly one — including the ones that produce no address.

### Per-person results

| name | company domain | email | status | identified by | source |
|---|---|---|---|---|---|
| A. Rivera | northfield.example | a.rivera@northfield.example | valid | name + domain | managed waterfall, stopped at its second source |
| C. Park | initech-consulting.example | c.park@initech-consulting.example | valid, catch-all probe-confirmed | profile URL | catch-all track → mailbox probe returned `valid: true` + `result: catch_all_validated` |
| B. Osei | initech-consulting.example | b.osei@initech-consulting.example | catch-all risky | name + domain | catch-all track; the probe stayed `status: valid` + `sub_status: catch_all` — shipped flagged, not blessed |
| D. Haruki | fabrikam.example | — | rejected: role address | name + domain | the waterfall returned only `info@fabrikam.example`; a role local-part is not this person's email, and nothing person-matched remained |
| E. Lindqvist | nowhere.example | — | blocked: dead or trap domain | name + domain | free MX pre-gate, DNS: NXDOMAIN — zero credits, no waterfall run |
| F. Okonkwo | northfield.example | — | not found | name + domain | managed waterfall exhausted: `status: complete` with an empty `result: {}` — no pattern-guessed address |

Two rows carry the discipline. `D. Haruki` shows what the skill refuses to do: the only
address the waterfall produced was a role mailbox, and offering it as a person's email —
or offering a plausible `d.haruki@fabrikam.example` instead — is the one unrecoverable
failure. `F. Okonkwo` is an honest miss: the function returns a completed run with an
empty result, and that is the not-found signal rather than a reason to guess.

### Summary

```
6 people asked

  valid                            1   17%
  valid, catch-all probe-confirmed 1   17%
  catch-all risky                  1   17%
  rejected: role address           1   17%
  blocked: dead or trap domain     1   17%
  not found                        1   17%
                                  --
                                   6 of 6 accounted for

Deliverable addresses: 2 of 6. Shipped flagged for the user to decide: 1.
Spend: ~1.1 credits for the managed waterfall run, plus 0 credits +
2 action executions for the catch-all probes. Read the actual charge from run
usage metadata — the routines surface exposes no per-run actuals.
The free MX pre-gate removed 1 person before any paid call.

Timing, because it decides how you batch: a hit comes back in ~12 seconds and a
not-found takes ~4.5 minutes as the waterfall exhausts. A batch finishes at the
speed of its misses, not its hits.
```

## Worked example

Ask: "Get me a verified work email for Jordan Lee at northfield.example."
MX check: real records — proceed. Work Email function with full name + domain (+ LinkedIn
URL if on file) → waterfall stops at the second source, verification passes, local-part
`jordan.lee` matches the contact → `jordan.lee@northfield.example · valid · source: managed
waterfall`.
Catch-all case: "and Casey Park at initech-consulting.example" — the found address validates
as `catch_all`: the domain accepts everything. Switch tracks: validator-free find pass
returns `casey.park@initech-consulting.example`; Enrichley mailbox probe →
`catch_all_validated` → `valid, catch-all (probe-confirmed) · source: catch-all track +
provider name`. Had the probe stayed `catch_all`, the address ships flagged risky — the
user decides.
Counter-example: "someone called Alex at initech-consulting" → resolve domain first; the
waterfall returns only `info@initech-consulting.example` → `rejected: role address`, and with
nothing person-matched left → report `not found` — do not offer
`alex@initech-consulting.example` as a fallback.

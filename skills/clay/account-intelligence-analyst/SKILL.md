---
name: account-intelligence-analyst
description: |
  Answer a specific question about a list of accounts with graded, sourced evidence — not a
  dossier. Give it a question ("which of these are building an AI team", "which are expanding
  into EMEA", "which run on a competitor we displace") and it decomposes the question into
  observable proxies, prices each one, observes them cheapest-first per account, and returns
  yes / no / insufficient-evidence with the proxies that fired and the ones that could not be
  observed. Use whenever someone asks: which of my accounts are doing X, find out whether
  these companies are Y, research this question across my list, or answer a hypothesis about
  a target list. Do NOT use it to produce a fixed-field brief on one company
  (company-research-brief), to fill a standard field set across a list (enrich-account-list),
  to score ICP fit on a fixed formula (account-tier-scoring), or to watch a list for new
  events (monitor-buying-signals). Accounts the evidence does not settle are reported
  unsettled, never as no.
category: research
personas: [account-executive, sales-leader]
mechanism: functions
touches: read-only
keywords: []
---

# Account-intelligence analyst (question → graded answer)

The insight: **the other research plays fail by leaving a field blank; this one fails by
answering.** A brief that cannot find a company's headcount ships an empty field, and the
gap is visible. But a question — "are they building an AI team?" — always has a plausible
answer available from adjacent evidence: the homepage says "AI-powered", so the answer looks
like yes. That is marketing copy, not a hiring signal, and nothing in the output would
reveal the substitution. **A confident answer from thin evidence is indistinguishable from a
confident answer from good evidence, unless the skill reports what it actually observed.**

So the question is never answered directly. It is decomposed into **proxies** — specific
things that could be observed, each with a named arm that observes it and a declared cost —
and the answer is graded by **which proxies actually fired**, not by how the prose reads. An
account where nothing observable fired returns `insufficient evidence`, which is a real
answer and the most commonly correct one.

Two consequences that shape every step below:

- **Proxy cost varies ~10× for the same observable**, and some arms bill **per item
  returned** rather than per call — `creditCost: 0.8` on an addresses arm means 0.8 *per
  address*, 8 at its default and 80 at its cap, with the multiplier stated only in a
  parameter description. So cheapest-first ordering plus early exit is not tidiness, and
  neither is reading the parameter docs before quoting: both decide whether the play is
  affordable across 300 accounts or only across 30.
- **An unobservable proxy must be declared, not dropped.** "Do they have budget approved
  this quarter" has no arm. Silently dropping it shrinks the denominator and inflates every
  confidence score downstream.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The question** | a question they could answer per account by naming what would count as evidence | no default — a vague question answered anyway is the failure this play exists to prevent. Offer the tightened rewrite instead |
| **The bar for a yes** | what evidence counts: hiring, a shipped product, a named leader | ask — "building an AI team" has no verdict without it |
| **The account list** | accounts with domains; resolve names to domains first | no default. A wrong domain makes every proxy answer about a different company |
| **Budget ceiling** | credits available for paid proxies | state cost and wait for approval; step 3 exists for exactly this |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — your account list and the question you set, plus the public sources it researches against.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, or answers beyond what it actually read.
- **Halts** — Step 3 spend-approval.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run the Clay
plugin's `setup` skill, restart if it says to, and re-run this skill. Tell the user which
workspace they're in.

Resolve the arms you plan to use against the live catalog before promising any of them —
provider availability and price both change:

```
clay workflows actions list > /tmp/catalog.json     # cache once per run (~1.4 MB, 650+ actions)
```

`references/proxy-catalog.md` maps common question types to arms with their declared credit
costs, read from that catalog. Treat it as a starting point that must be re-resolved, never
as a price list to quote from memory.

## Step 1 — Turn the question into a decidable claim (interview; do not guess)

A question this play can answer is one where **you could say, per account, what would count
as evidence.** Test it out loud before spending anything:

| Asked | Verdict | Why |
|---|---|---|
| "Which accounts are building an AI team?" | usable after tightening | needs a bar: hiring? shipped product? named leader? |
| "Which accounts are expanding into EMEA?" | usable | offices, EMEA job posts, localized site |
| "Which accounts are a good fit?" | **reject** | that is ICP scoring — hand to `account-tier-scoring` |
| "Which accounts have budget this quarter?" | **reject** | no observable proxy exists at all |

If the question cannot be tightened into observable terms, say so and offer the rewrite. Do
not accept a vague question and answer it anyway — that is the failure this play exists to
prevent, arriving before any code runs.

Also collect: **the account list** (with domains — resolve names to domains first, a wrong
domain makes every proxy answer about the wrong company), **the bar** for a yes, and **the
budget ceiling** in credits.

## Step 2 — Decompose into proxies, and price them

Write the proxy set out and show it to the user **before spending**. For each proxy: what
would be observed, which arm observes it, its declared per-account cost, and its weight.

```
Question: "Which of these accounts are building an AI team?"

  proxy                              arm                          cost   weight  observable?
  1. open AI/ML job postings         cpj-find-lists-of-jobs        1 cr      3    yes
  2. eng headcount growth            cpj-get-company-employee-growth 1 cr    2    yes
  3. AI/ML named in own site copy    site fetch (free)             0 cr      1    yes
  4. named AI leader hired           news arm, date-windowed       1 cr      2    yes
  5. internal roadmap approval       —                             —         2    NO — declared unobservable
```

Three rules here, and each one exists because skipping it corrupts the arithmetic:

- **Weights are the user's, not yours.** Ask which proxies would actually convince them. A
  job posting may be worth more than a press mention, or the reverse, depending on the
  question.
- **An unobservable proxy stays in the table with `observable: no`** and its weight stays in
  the denominator. It is why an honest maximum confidence can be below 100%.
- **Prune before spending, not after.** The user drops proxies that are not worth their cost
  at their list size. `references/proxy-catalog.md` has the price spreads that make this a
  real decision.

## Step 3 — State the cost and get approval

```
per account = Σ (cost of each proxy the user kept)
total       = per account × accounts,  before early exit
```

**Summing `creditCost` is only valid for flat-priced arms.** Before pricing any arm, read its
parameter descriptions for a per-unit rate (`"credits for each …"`). If there is one, price it
at the cap you intend to pass, and pass one — a per-unit arm with an unset cap is an unbounded
per-account cost. Where a proxy only needs a *number*, prefer a flat counting arm over a
per-unit listing arm; the "cheaper" per-unit arm is dearer past a handful of items.

Worked: the four observable proxies above are 1 + 1 + 0 + 1 = **3 credits per account**;
across 120 accounts that is **360 credits before early exit**. Give the number, get a yes,
then spend. Early exit (step 5) typically lands the real spend below the ceiling, but quote
the ceiling — a quote that assumes best-case exit is not a quote.

## Step 4 — Anchor each account (free, before any paid proxy)

A wrong entity makes every proxy answer a question about a different company, and it does it
invisibly. Per account: pre-gate the domain with a free DNS/status probe, then fetch the
company's own site. Confirm the site is the company the user means — name collisions,
holdings vs operating entities, franchises and rebrands are the standard traps. A dead or
parked domain is a **finding**, reported as `anchor failed`, not a silent skip and not a
`no`.

Never run a paid proxy against an unanchored account.

## Step 5 — Observe the proxies, cheapest-first, with early exit

Order the kept proxies by cost ascending, free arms first. Per account, observe in that
order and record for each proxy exactly one verdict:

| Verdict | Meaning |
|---|---|
| `supports` | the observation was made and it supports a yes |
| `contradicts` | the observation was made and it argues against |
| `not_observed` | the arm ran and returned nothing usable, or the arm was not run |

Three traps verified on live payloads, each of which manufactures a verdict out of nothing:

- **A null is not a zero.** A growth arm returned nine horizons with the most recent one `null`
  and the other eight populated. Reading that null as 0% produces `contradicts` — a negative
  verdict assembled from a data gap. A null horizon is `not_observed` for that horizon.
- **Count the right unit.** A job-postings arm returned 10 rows that were 4 distinct titles
  across 6 locations, with a `jobCount` of 33 available. "33 openings", "10 postings" and "4
  roles" are all true and answer different questions. State the unit in the proxy definition, or
  the same evidence supports either verdict.
- **Topical relevance is not evidence.** A news query about a specific hiring event at a named
  company returned, among ten results, a *different* company hiring *former* employees of the
  target — which argues the opposite — plus opinion pieces mentioning the target. Adjacent text
  about the right company is the single easiest thing to mistake for `supports`. Require the
  observation to be about the claim, not about the company.

`not_observed` is one bucket on purpose: "the arm found nothing" and "we stopped early" are
both *absence of evidence*, and splitting them invites treating the first as a soft
`contradicts`. **An arm returning empty is never a contradiction.** A company with no AI job
postings visible to one provider has not been shown to be hiring nobody.

**Early exit:** stop observing an account once the remaining unobserved weight cannot change
the answer — if `|direction|` already exceeds the total weight left to observe, further calls
cannot flip it. Record which proxies were skipped by early exit and why; the coverage figure
in step 6 is computed on what was observed either way, so early exit lowers coverage
honestly rather than hiding.

## Step 6 — Grade the answer (exact, single-valued)

Same arithmetic family as `account-tier-scoring` on purpose — a house pattern, applied to a
different unit. There it is weighted ICP dimensions to a tier; here it is weighted proxies to
an answer.

```
coverage  = Σ weight(proxies with supports or contradicts) / Σ weight(ALL proxies, including unobservable)
direction = Σ weight(supports) − Σ weight(contradicts)
```

| Condition | Answer |
|---|---|
| `coverage ≥ 0.50` and `direction > 0` | **yes** |
| `coverage ≥ 0.50` and `direction < 0` | **no** |
| `coverage < 0.50`, or `direction = 0` | **insufficient evidence** |

| Condition | Confidence |
|---|---|
| answered, `coverage ≥ 0.75`, no `contradicts` | **high** |
| answered, otherwise | **medium** |
| `insufficient evidence` | not reported — a confidence on a non-answer is theatre |

The three answer conditions are exhaustive and mutually exclusive: `direction = 0` routes to
insufficient regardless of coverage, and coverage below 0.50 routes there regardless of
direction, so no account satisfies two rows and every account satisfies one. A tie is never
broken toward `no` — a split verdict is unsettled, and calling it `no` converts ignorance
into a negative claim about a real company.

Because unobservable proxies stay in the denominator, a question whose unobservable weight
exceeds half the total **cannot reach an answer for any account**. That is not a bug to
route around: it means the question is not answerable from observable evidence, and the
honest output is to say so once, at the top, rather than 120 times.

## Step 7 — Deliver

Per account: `domain · answer · confidence · coverage · direction` then the proxies, each
with its verdict and — for anything that fired — a quote or a dated source link. Anchor
failures listed separately from insufficient-evidence, because they are different problems
with different fixes.

Roll up: counts by answer, the mean coverage, the proxies that fired most and least often,
and the credits actually spent against the quote. Then the two lists that make this play
trustworthy rather than impressive:

- **The unsettled list is a first-class deliverable**, not a remainder. Name every account
  that returned insufficient evidence and which proxy would settle it — that is the user's
  next decision, and it is often cheaper than the run that produced it.
- **The proxy that never fired** is a finding about the *arm*, not about the accounts. A
  proxy with 0 supports and 0 contradicts across 120 accounts was probably observed wrong.
  Say it, rather than reporting 120 low-coverage answers.

## What this skill does not claim

- The play has not been run end to end, so how often it returns "insufficient evidence" on real accounts is unmeasured.
- Grading is proven to yield one verdict per account; whether that verdict is useful across a real book is not yet measured.

## What good looks like

- The user reads a `yes` and can see exactly which two things fired, with links.
- The `insufficient evidence` pile is large and nobody is embarrassed by it.
- Nothing was inferred from the model's background knowledge — it steered *where to look*
  and filled nothing. A claim without an observation behind it does not appear.
- The common failure: a homepage that says "AI-powered" graded as a hiring signal. The
  second-worst: an empty provider response read as `contradicts`, turning silence into `no`.

## Rules

- MUST decompose the question into weighted, individually-observable proxies before spending;
  NEVER answer the question directly from a single blended judgment.
- MUST keep unobservable proxies in the table and in the denominator; NEVER drop one silently.
- MUST anchor each account for free before any paid proxy; NEVER pay to observe an unanchored
  domain.
- MUST record exactly one verdict per proxy per account; NEVER treat `not_observed` as
  `contradicts`.
- MUST report `insufficient evidence` when `coverage < 0.50` or `direction = 0`; NEVER break a
  tie toward `no`.
- MUST report coverage alongside every answer; NEVER give an answer without the fraction of
  weight it rests on.
- MUST quote or link the observation behind every proxy that fired; NEVER assert a proxy
  verdict without its evidence.
- MUST re-resolve arms and their costs against the live catalog, and MUST read each arm's
  parameter descriptions for a per-unit rate before pricing it; NEVER quote a price from this
  file or from memory, and NEVER sum `creditCost` across arms without checking which are flat.
- MUST treat a null field as `not_observed` for that field; NEVER read a null as a zero and
  never let one become a `contradicts`.
- MUST state which unit a counting proxy counts (roles, postings, or available total); NEVER
  report a page length as a total when the arm returns a true count.
- MUST state the ceiling cost before spending, and the actual spend after; NEVER quote the
  best-case early-exit figure as the estimate.
- NEVER let background knowledge fill a proxy verdict, and NEVER answer a question that could
  not be tightened into observable terms.

## Representative output

Four artifacts, and the last two are the ones that make this trustworthy rather than
impressive. **Every account and domain below is invented** (`.example` reserved TLD).

The question: *"Is this account expanding into Europe?"* Five proxies, total weight 12, of
which one is unobservable and stays in the denominator.

### Per account

| domain | answer | confidence | coverage | direction |
|---|---|---|---|---|
| fabrikam.example | yes | high | 0.83 | +10 |
| northwind.example | yes | medium | 0.50 | +6 |
| quartzlane.example | no | medium | 0.58 | −7 |
| kirivale.co.uk | insufficient evidence | — | 0.50 | 0 |
| meridianops.example | insufficient evidence | — | 0.17 | +2 |

`kirivale.co.uk` is the case worth staring at. Coverage is fine — two proxies fired — and
they fired in **opposite directions**, so direction is zero. A tie routes to insufficient
evidence and is never broken toward `no`, because calling it `no` converts not knowing into
a negative claim about a real company. And no confidence is reported on a non-answer: a
confidence attached to "we don't know" is theatre.

### The proxies, for one account

`northwind.example`

| proxy | weight | verdict | evidence |
|---|---|---|---|
| job postings in EU locations, last 30 days | 3 | supports | 3 postings in Dublin and Berlin, most recent 2026-09-28, source link on each |
| new EU operating locations | 3 | supports | one new Dublin address, first observed 2026-08 |
| EU-language pages on the site | 2 | unobserved | the arm returned nothing. Recorded as unobserved, **not** as absence |
| news mentioning EU expansion | 2 | unobserved | no dated story inside the window |
| internal headcount by region | 2 | **unobservable** | no arm exposes this at all. It stays in the denominator rather than being quietly dropped |

`coverage = 6/12 = 0.50` · `direction = +6` → **yes**, medium confidence.

Keeping the unobservable proxy in the denominator is what stops a one-proxy answer from
looking fully evidenced. It also means a question whose unobservable weight exceeds half the
total cannot be answered for *any* account — which is a fact about the question, said once
at the top, rather than 243 low-coverage rows.

### Roll-up

```
243 accounts

  yes                      93
  no                       93
  insufficient evidence    57
                          ---
                          243

  plus 7 accounts that failed the free anchor gate, listed separately —
  a dead domain is a different problem, with a different fix, from
  "not enough evidence was gathered"

Mean coverage across answered accounts: 0.64

How often each proxy fired:
  job postings in EU locations     198 of 243
  new EU operating locations       141
  EU-language pages                 88
  news mentioning EU expansion      31
  internal headcount by region       0   unobservable by design

Spend: 3 credits per account on the cheap arms = 729 against a quote of 750.
The same five observables bought from the expensive providers in the same
catalogue cost roughly 30 per account — about 7,300 credits for this run.
Same observable, up to 10× the price, which is why proxies get decomposed and
priced before anything is bought.

One per-unit trap in that arithmetic: the operating-location arm is priced PER
LOCATION FOUND, not per account. A multi-site company can cost many times the
headline rate, so that parameter is passed explicitly rather than defaulted.
```

### The unsettled list

57 accounts returned insufficient evidence. This is a deliverable, not a remainder — each
row names the one thing that would settle it, and settling them is usually cheaper than the
run that produced them.

| account | why it is unsettled | what would settle it |
|---|---|---|
| kirivale.co.uk | two proxies fired in opposite directions, so direction is 0 | the news proxy, 1 credit |
| meridianops.example | coverage 0.17 — only one proxy returned anything | the job-postings proxy, 1 credit; it failed to resolve against this account's anchor |

A last note that is about the arms rather than the accounts: the news proxy fired on 31 of
243. Had any proxy fired **zero** times across 243 accounts, that would be a finding about
how it was observed — almost certainly wrong — and the honest response is to say so, not to
publish 243 answers dragged down by it.

## Worked example

Question: *"Which of these 40 accounts are building an AI team?"* Tightened bar, agreed with
the user: an open AI/ML engineering role **or** a named AI leader hired in the last 180 days.

Proxy table as approved: AI/ML job postings (w 3, 1 cr) · engineering headcount growth
(w 2, 1 cr) · AI/ML in own site copy (w 1, free) · named AI leader in dated news (w 2, 1 cr)
· internal roadmap approval (w 2, **unobservable**). Total weight 10, observable weight 8, so
**maximum achievable coverage is 0.80** — stated up front.

Cost: 3 credits per account × 40 = **120 credits ceiling**, approved. Two accounts fail the
free anchor (one parked domain, one holdings company whose operating entity is on a different
domain) and are reported as `anchor failed`, spending nothing.

One account: site copy mentions AI (supports, w 1) → job postings return two ML engineer
roles (supports, w 3) → direction is now 4 with 4 observable weight left; a full contradiction
of both remaining proxies would land at 0, which is `insufficient`, so the answer is not yet
settled and observation continues. Headcount growth is flat (contradicts, w 2), news finds
nothing (not_observed). `coverage = (1+3+2)/10 = 0.60`, `direction = 4−2 = +2` → **yes,
medium** — medium rather than high because coverage is under 0.75 and one proxy contradicts.

Another: site copy silent, no postings, headcount flat, no news. Every arm ran and returned
nothing usable → `coverage = 0.20` → **insufficient evidence**, not `no`. It appears on the
unsettled list with the note that a headcount-by-department arm at 8 credits would settle it.

Across the 40: 11 yes, 6 no, 21 insufficient, 2 anchor failed. Actual spend 94 credits against
the 120 ceiling, the difference being early exit. The site-copy proxy fired on 34 of 38
anchored accounts and is flagged in the roll-up as near-useless discrimination — it says
almost everyone mentions AI, which is a finding about the proxy, not about the market.

---
name: headcount-growth
description: |
  Measure a company's headcount growth with Clay — employee count plus percent
  change across 3/6/12/24-month windows, bucketed (shrinking / flat / growing /
  high-growth / hyper-growth) with a trajectory read and honest unverifiables.
  Use whenever someone asks: how fast is this company growing, get headcount
  growth for these accounts, which of these companies are hiring or shrinking,
  or filter my list to high-growth companies. Works per company from a
  company social URL (best) or domain;
  names resolve to a domain first. It verifies the answer is about the RIGHT
  company, never ships a percentage without its base counts, and reads two
  windows so a recent reversal isn't hidden by a 12-month average. Do NOT use
  it for job postings (Company Job Openings territory), funding or expansion
  events behind the growth (monitor-buying-signals), broad firmographics
  (enrich-account-list), or person-level moves (track-champion-job-changes).
  Built on the Find Company Headcount Growth action plus entity verification.
category: enrich
personas: [revops, sales-leader]
mechanism: workflow
touches: read-only
keywords: []
---

# Company headcount growth

The insight: **a growth percentage is a trajectory claim built on three silent
assumptions — right entity, meaningful denominator, and a window that isn't
hiding a reversal — and the bare action returns a confident number when any of
them is wrong.** +40% over 12 months can mean a 3-person company hired one
engineer, a different company than the one you asked about, or a real grower
that started shrinking last quarter. And the action's miss is success-shaped
AND billed: an empty result costs the same credit as a hit. This skill wraps
one cheap action with the checks that make its number safe to act on.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **An identifier per company** | a domain, a company profile URL, or a Clay company id — whichever the list already carries | one field takes all three, and the type is inferred from the value unless you name it. Set it explicitly when the column is mixed. Name-only rows resolve to a domain first, because a wrong domain measures the wrong company silently |
| **Which windows** | near-term momentum, sustained trend, or both | **3 and 12 months read together is defensible** and must be stated: one window alone is a number, not a trajectory |
| **Cost ceiling** | credits, knowing that misses bill too | dedupe companies first, state list × cost, and say that obscure and very small companies miss more — a low-coverage list burns credits on empty results |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — an identifier per company and the windows you choose, via headcount sources.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, or reports growth outside a window you declared.
- **Halts** — Step 1 spend-approval.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing,
run the Clay plugin's `setup` skill, restart if it says to, and re-run this
skill. Tell the user which workspace you're in. Confirm the growth action in
the live catalog by DISPLAY NAME ("Find Company Headcount Growth") — action
keys drift (`references/growth-mechanics.md`) — and read its declared cost.

## Step 1 — Scope (identifiers, windows, cost)

1. **Identifier per company** — **one field takes all three forms.** Pass the
   value in `company_identifier`; the type is inferred when you leave
   `company_identifier_type` empty (a profile URL reads as a social URL, a whole
   number as a Clay company id, anything else as a domain). Set the type
   explicitly when the column is mixed, from `company_domain`,
   `company_linkedin_url` or `clay_company_id`. There is no longer a separate
   arm per identifier and no hard-fail for putting a domain in the wrong field.
   Name-only rows still resolve the domain FIRST (resolve-company-domain — a
   wrong domain here silently measures the wrong company).
2. **Windows that matter** — near-term momentum (3/6-month) vs. sustained
   trend (12/24-month); default to reading 3 + 12 together (the reversal
   check). One window alone is a number, not a trajectory.
3. **Cost + coverage, stated before spend** — ~1 credit per company and
   **misses bill too**; obscure SMBs and very small companies miss more, so a
   low-coverage list burns credits on empty results. Dedupe companies first,
   state list × cost, get approval.

## Step 2 — Run the action (surface by list size)

Per unique company, run **Find company headcount growth** with the single
`company_identifier` input from Step 1. Small lists (≤20): ad-hoc action
execution — it has a 25-runs/day workspace quota, and if today's quota is
already spent the refusal is explicit and free, so switch surfaces rather than
waiting. Larger lists or spent quota: **one** workflow, per
`references/growth-mechanics.md` (workflow runs bypass the ad-hoc quota). Never
loop past the quota into errors.

## Step 3 — Read the payload honestly (four shapes)

- **Hit**: numeric `employee_count` + per-window backdated counts and
  percentages, plus `clay_company_id`. FIRST check the entity echo: the
  result's `name`/`url` name the company the action actually matched — if they
  don't match the company you asked about, the row is a wrong-entity hit; flag
  it, don't report its numbers.
- **Per-window nulls inside a hit are normal** (short-window and old-window
  data are often missing even for major companies) — a null window is "no
  snapshot", never zero growth.
- **Not found**: the step **completes**, `success: true`, `result` EMPTY, and
  the only signal is a `❌ Company Not Found` preview string. Verdict
  `unverifiable` — never "flat", never 0%. **This one bills.** Count it.
- **Invalid identifier**: the step **fails** with
  `ERROR_INVALID_INPUT — Invalid company identifier`, an `errors` array, and
  empty outputs. **This one is free.** It means the value was not a usable
  identifier at all, not that the company is unknown — so it is a data-quality
  finding about your list, not a verdict about the account, and it is cheap to
  discover. Note that a failing step fails the run, so screen obviously
  malformed identifiers before a batch rather than during it.

## Step 4 — Interpret (denominator, bucket, trajectory)

- **Denominator gate**: report the base counts next to every percentage. A
  base under ~50 employees never headlines a percentage — `+300%` on 3→12
  people ships as "grew 3→12 (micro-base)", flagged, not as hyper-growth.
- **Bucket** (12-month default): `<0` shrinking · `0–10%` flat · `10–30%`
  growing · `30–100%` high-growth · `>100%` hyper-growth.
- **Trajectory** (the direction-change check, both ways): compare the short
  window against the long one — growing 12-month + shrinking 3-month =
  `reversing`; growing year + a last quarter running well ahead of the year's
  pace = `accelerating`; flat 12-month + strong 3-month = `inflecting up`.
  Say which windows produced the verdict, and read the backdated counts for
  dip-and-rebound shapes the window percentages smooth over.
- **Measurement caveat, always shipped**: counts are professional-profile
  presence, not payroll — hourly, offshore, and contractor-heavy workforces
  undercount. A frozen flat-line on a company whose liveness is in doubt is
  a dead-company artifact, not stability (enrichment-style data persists for
  dead/acquired companies).

## Step 5 — Deliver

Per company: `identity (asked → matched echo) · employee_count · per-window
counts + % · bucket · trajectory · flags (micro-base, wrong-entity,
window-gaps) · verdict (measured / unverifiable)`. Plus the roll-up: companies
in, measured, unverifiable, wrong-entity, credits measured vs declared
(misses included). Every input company lands somewhere.

## What good looks like

- **Percentages never travel without their base counts** — no micro-base
  booms in the headline.
- **The entity echo was checked on every hit** — a wrong-entity number is
  worse than no number.
- **Unverifiable is honest and costed** — misses are reported as coverage
  (with their spent credits), never coerced to "flat" or dropped silently.
- **Trajectory over snapshot** — rows read from two windows; a 12-month
  average never hides a last-quarter reversal.
- The common mistake: treating the action's confident percentage as the
  answer. It answers for whatever entity it matched, at whatever base size,
  for one window — the wrapper's whole job is checking those three.

## Rules

- MUST resolve name-only rows to a domain before measuring; MUST set
  `company_identifier_type` explicitly when the identifier column is mixed,
  rather than relying on inference row by row.
- MUST check the entity echo (`name`/`url`) on every hit; a mismatched echo is
  a wrong-entity flag, never a reportable number.
- MUST treat empty-result success as `unverifiable` (billed, counted) — never
  zero growth; MUST treat per-window nulls as missing snapshots, never 0%.
- MUST ship base counts with every percentage and flag micro-bases; MUST read
  ≥2 windows before calling a trajectory.
- NEVER exceed the ad-hoc quota in a loop — route batches through the
  workflow surface; NEVER present profile-count growth as payroll truth.
- Batch: dedupe companies first, state cost (misses bill), get approval.

## Representative output

Two artifacts. **Every company below is invented.** Buckets are **shrinking / flat /
growing / high-growth / hyper-growth**; the verdict is **measured** or **unverifiable**;
and a percentage never appears without the counts underneath it.

### Per-company

| asked → matched echo | employees | 3-month | 12-month | bucket | trajectory | flags | verdict |
|---|---|---|---|---|---|---|---|
| Northwind Systems → *Northwind Systems* | 412 | 398 → 412, +3.5% | 330 → 412, +24.8% | growing | **accelerating** — the quarter is running ahead of the year's own pace, and the backdated counts show a dip and rebound that the window percentages smooth over | — | measured |
| Kirivale Ltd → *Kirivale Ltd* | 1,180 | 1,240 → 1,180, −4.8% | 1,020 → 1,180, +15.7% | growing | **reversing** — a growing year with a shrinking last quarter. Reported on the 12-month read alone this is a healthy account | — | measured |
| Meridian Ops → *Meridian Ops* | 12 | no snapshot | 3 → 12 | not headlined | — | micro-base · window-gaps | measured |
| Fabrikam Cloud → *Fabrikam Group Holdings* | — | — | — | — | — | **wrong-entity** | unverifiable |
| Halloway Industrial → *no match* | — | — | — | — | — | — | **unverifiable** |

Four of those rows exist to show a specific way this data misleads:

- **Meridian Ops grew 3 → 12 people.** That is `+300%`, and shipping it as hyper-growth
  would put a nine-person company at the top of a ranked list. Below roughly 50 employees
  the counts ship and the percentage does not.
- **Kirivale's year looks good and its quarter does not.** One window is a snapshot; two
  windows are a shape. The verdict names which windows produced it.
- **Fabrikam's row was caught only by the echo.** The action returned a confident, complete,
  numerically plausible growth record — for a different company. A wrong-entity hit is
  shaped exactly like a correct one, so comparing the result's own returned name against
  the company you asked about is the only thing that detects it. Its numbers are withheld
  rather than reported with a caveat.
- **Halloway's run succeeded.** The call completed, reported success, and returned an empty
  result — the only signal was a "Company Not Found" preview. That is `unverifiable`, never
  `flat` and never `0%`. **And the credit was still spent.**

A null inside an otherwise good row means *no snapshot taken*, never *no growth* — short
and old windows are often missing even for large companies.

### Roll-up

```
5 companies in

  measured        3
  wrong-entity    1
  unverifiable    1
                 --
                  5 of 5 — every input company lands somewhere

Spend: 7 credits measured against a 10-credit cap, and that figure includes
the miss. A not-found company bills exactly like a hit, so a list with dead
rows costs full price. Counting misses in the spend is the difference between
a cost estimate and a wrong one.

Shipped with every run, not as a footnote: these are professional-profile
counts, not payroll. Hourly, offshore and contractor-heavy workforces
undercount badly. And a perfectly flat line on a company whose liveness is in
doubt is a dead-company artifact rather than stability — this kind of data
persists for companies that have stopped trading.
```

## Worked example

Ask: "Which of these 30 accounts are actually growing? CSV has name, domain,
some LinkedIn URLs." Scope: dedupe 30 → 28; 9 rows LinkedIn+domain, 16 domain
only, 3 name only → resolved first (1 ambiguous, parked). Approval at ~28
credits. Run: workflow surface (batch > 20). Read: 24 hits (entity echo clean
on 23 — 1 mismatch flagged: a same-named company matched from a bare domain),
3 misses → unverifiable (credits counted), plus the parked ambiguous row.
Interpret: 6 high-growth (12-mo), but 2 of them show negative 3-month deltas →
`stalling` flag; 1 shows +180% on a 14-person base → micro-base flag, not
hyper-growth. Deliver: 23 measured rows with counts + buckets + trajectories,
5 unmeasured (3 unverifiable, 1 wrong-entity, 1 unresolved), 28 credits
measured vs 28 declared.

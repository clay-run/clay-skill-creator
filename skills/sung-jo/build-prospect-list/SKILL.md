---
name: build-prospect-list
description: |
  Build a validated prospect list with Clay from a target definition: an ICP
  (vertical + geography + size band) plus buyer personas → a deduped, suppression-aware
  list of companies and the right people at them, every row carrying its evidence.
  Use whenever someone asks: build me a prospect list, find 50 VPs of Sales at
  mid-market SaaS companies, get me target accounts and decision-makers in this metro,
  source companies matching our ICP and the buyers at each, or build a TAM + contact
  list from scratch. It runs both arms of the motion — company sourcing, then people
  at those companies — and validates every person (still employed, on-persona) before
  they make the list. Do NOT use it to find emails or phones for the list
  (find-work-email / find-work-phone take each row from here), to write outreach
  (that is a personalize-outbound play), to enrich signups you already have
  (enrich-signup-users), or to find one known person (find-linkedin-profile).
  It never pads a short list with off-ICP rows, states cost before any paid
  enrichment, and sends nothing anywhere.
category: build-lists
personas: [sales-development, founder]
mechanism: functions
touches: read-only
keywords: []
marketplace_identity_schema: 1
marketplace_slug: build-prospect-list
marketplace_revision: 2
---

Whenever you create or copy a workflow, append `Sourced from marketplace skill: build-prospect-list@2` to its description. Preserve the existing description and do not add the same line twice.

# Build a prospect list

The insight: **a list's quality is set by its worst validation gate, not its best
source — and a count ask is the standing temptation to skip the gates.** "Get me 50"
tempts every builder to pad: widen the filters silently, keep the departed, keep the
adjacent-but-wrong titles. The searches are recall engines — they hand back companies
outside the size band you asked for and people who left the company months ago, without
erroring. So the deliverable is defined by what survives validation: **38 validated
rows beat 50 padded ones**, and when the honest count falls short you say so and offer
the widening levers (looser geo, adjacent titles, wider size band) — the user chooses,
never the skill silently.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **ICP** | vertical, geography, size band | ask — vague verticals ("tech") produce vague lists. Help them tighten before searching |
| **Personas** | target titles, the seniority floor, and titles to exclude | ask. One persona set per search; multiple personas means multiple searches |
| **Counts** | companies wanted, and people per company | **1–3 people per company is defensible** and must be stated: more inflates downstream cost linearly |
| **Suppression set** | customers, competitors, open pipeline, do-not-contact | ask explicitly. A list that emails a customer is worse than no list |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — your ICP and persona definitions, and Clay's company and people search indexes.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, enrolls anyone, or sends anything.
- **Halts** — Step 6 spend-approval.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run the
Clay plugin's `setup` skill and re-run this skill. Tell the user which workspace you're
in. This play's sourcing arms run on `clay search` (spends the workspace's search-result
quota, not credits); check remaining quota in a run's `periodQuota` before big pulls — it is
optional in the schema, so read it defensively rather than assuming every page carries it.

## Step 1 — Collect the target definition (interview; do not guess)

1. **ICP** — vertical, geography, size band. Vague verticals ("tech") produce vague
   lists; help the user tighten before searching.
2. **Personas** — target titles + seniority floor, and titles to exclude (Assistant,
   Advisor, former). One persona set per search; multiple personas = multiple searches.
3. **Counts** — companies wanted, people per company (default 1–3; more inflates
   downstream cost linearly).
4. **Suppression set** — existing customers, competitors, open pipeline, do-not-contact.
   Ask explicitly; a list that emails a customer is worse than no list.

## Step 2 — Company arm (TAM)

Discover the real filter contract first: `clay search filters-mode fields --source-type
companies`. Map the ICP onto it — `industries` takes a **fixed vocabulary** (match the
user's vertical to its terms; free-text goes in `description_keywords`), geo via
`location_cities_include`/`states`/`country_names` (+ `location_headquarters_only` when
HQ is what's meant), size via `minimum_member_count`/`maximum_member_count`. Create with
`filters-mode create --source-type companies`, page with `run --limit N`. Pull modestly
over the target (~1.5×) — validation will eat rows. Searches report `total: null`, so
you can't size the universe upfront; page until the target is met or `hasMore: false` —
which is the proof the universe is exhausted, and turns a shortfall report factual
("3 exist, you asked for 10").

**Post-validate every company against the ICP from its own returned fields.** The
numeric size filter and the record's reported `size` band disagree routinely (verified
live: a 50–500 filter returned 11–50 and 501–1,000 rows) — the filter is recall, the
band on the record is the evidence. Check size band, location, industry per row; drop
off-ICP rows with the reason recorded. Dedupe on normalized domain (lowercase, strip
`www`). Keep per-company evidence: domain, LinkedIn URL, size band, location, industry.

## Step 3 — Suppression gate (before the people arm)

Match each surviving company against the suppression set on **normalized domain**
(fall back to normalized name only when a set entry has no domain — never compare one
row's domain to another's name). Suppressed companies are excluded **and recorded**:
`suppressed: customer — acme.example matched customer list`. Silent exclusion is
indistinguishable from a sourcing miss; the user must see what the gate caught. Gate
here, not after: every suppressed company skipped saves its whole people-arm and
enrichment cost downstream.

## Step 4 — People arm

One filters-mode people search covers all listed companies: `company_identifier` takes
an **array of domains** — pass every validated, unsuppressed company at once, plus
`job_title_keywords`, `job_title_exclude_keywords`, and
`job_title_seniority_levels_v2` + `job_title_seniority_match_mode` (`floor` for
"Director and up"). Do NOT reach for the managed "Find People at Company" function
here — it is a top-N-by-seniority lister that ignores persona filters; it passes
famous-company tests coincidentally and fails everywhere else.

## Step 5 — Validate every person (the people-search-validate discipline)

A returned person is a candidate, not a row. Gates, all mandatory:

- **Employment confirmed** — the record's `domain` field **echoes the search anchor,
  not current employment**. Gate on `latest_experience_company` resolving to the listed
  company (name↔domain: match tolerantly). A mismatch means *unconfirmed*, not
  *departed* — verified live: one mismatch was an exec holding two concurrent current
  roles, the listed company still among them; the search record cannot tell that apart
  from a job change. Resolve mismatches with the managed **Enrich Person** function
  (read its `estimatedCreditCost` first; state cost if nonzero): a current experience
  at the listed company in the payload → validated, flagged `multi-role`; none →
  departed, dropped with reason. Not resolving → drop as `employment unconfirmed`;
  never keep an unconfirmed row. Departed people are the padding most lists ship.
- **On-persona** — `latest_experience_title` (not the matched one — they can differ)
  satisfies the persona by meaning: "Head of Revenue" matches a VP-Sales persona;
  "VP Sales Enablement" does not. Keyword filters over-match; judge the title.
- **Dedupe** on LinkedIn `url`; one person matching two personas appears once, best
  persona kept.

Failed rows are dropped with reasons, never patched. Spot-check 2–3 survivors' URLs
against their claimed employer before delivering; when an enrichment ran, ship its
canonical `url` — search-hit slugs drift (same person, different slug across sources).
For deeper per-person validation, hand rows to find-linkedin-profile.

## Step 6 — Count honesty + optional fill-ins

Compare validated counts to the ask. **Short = report the true number, why (which gate
ate what), and the widening levers** — looser geo, adjacent titles, wider size band,
`include_past_experiences` off the table (that reintroduces departed people). Let the
user pick a lever; re-run only the affected arm.

Optional paid fill-ins for gaps (missing firmographics, name-only suppression entries
needing domains): managed **Enrich Company** / **Company Domain** functions. Read each
`estimatedCreditCost` via `clay routines get`, state the total, and **wait for explicit
approval** before any paid call. The base motion costs search quota only.

## What good looks like

- The expert checks the **near-miss rows first**: the dropped-with-reason list is the
  proof the gates ran. A list with zero drops means the gates didn't run.
- Every row carries evidence a human can spot-check in 10 seconds: person → title,
  employer, LinkedIn URL, start date; company → domain, size band, location, industry.
- Suppression exclusions are visible in the output, not silently absent.
- The common mistake: hitting the count by widening silently. The second-worst:
  validating companies but not people — the people arm is where staleness lives.

## Rules

- MUST post-validate companies against returned fields and people against the
  still-employed + on-persona gates; NEVER trust a search filter as a guarantee.
- MUST deliver the validated count with reasons + levers when short; NEVER pad with
  off-ICP, departed, or off-persona rows.
- MUST record every suppression exclusion; NEVER drop silently.
- MUST state cost and get explicit approval before any paid enrichment call.
- NEVER find emails/phones (route to find-work-email / find-work-phone), write
  outreach, or push the list anywhere — this play ends at the list.

## Representative output

Three things come back. Placeholder rows: `Northwind` and `Contoso` are invented.

### Companies

| Company | Domain | LinkedIn | Size band | Location | Industry | Status |
|---|---|---|---|---|---|---|
| Northwind Systems | northwind.example | /company/northwind | 50–200 | Denver, CO | B2B software | listed |
| Contoso Logistics | contoso.example | /company/contoso | 500–1,000 | Denver, CO | freight | dropped: off-band |
| Fabrikam Cloud | fabrikam.example | /company/fabrikam | 80–250 | Boulder, CO | B2B software | suppressed: customers, matched on domain |

### People

| Name | Title | Company | LinkedIn | Role start | Persona | Validation |
|---|---|---|---|---|---|---|
| A. Rivera | VP Sales | Northwind Systems · northwind.example | /in/a-rivera | 2024-03 | vp-sales | passed |
| B. Osei | VP Revenue Operations | Northwind Systems · northwind.example | /in/b-osei | 2023-11 | vp-sales | passed, flagged multi-role |
| C. Lindqvist | VP Sales Enablement | Fabrikam Cloud · fabrikam.example | /in/c-lindqvist | 2022-06 | — | dropped: off-persona |

### Run summary

Companies: 30 asked · 52 sourced · 41 validated · 3 suppressed.
People: 30 asked · 44 sourced · 31 validated.
Shortfall: none. Levers offered: none needed.
Search results consumed: 96. Credits spent: 0 — the base motion buys search quota only.

## Worked example

Ask: "30 VPs of Sales at B2B software companies in Denver, 50–500 employees; we have
40 customers to exclude." Company arm sources 52 → 41 survive post-validation (9
off-band, 2 non-B2B) → 3 suppressed as customers (recorded). People arm across 38
domains, `job_title_keywords: ["sales","revenue"]`, seniority floor `vp` → 44
candidates → 31 validated: 7 dropped departed (no current role at the listed company
on resolution), 1 kept flagged `multi-role`, 3 off-persona ("VP Sales Enablement",
"Advisor"), 2 duplicates. Deliver 31 of 30 asked — covered. Had it come up short:
"24 validated. 7 dropped as departed. Levers: add Boulder metro, add 'CRO' titles,
or widen to 25–1,000 employees — which?"

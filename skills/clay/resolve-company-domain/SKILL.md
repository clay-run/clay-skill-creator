---
name: resolve-company-domain
description: |
  Resolve a company name to its single canonical operating-company domain with Clay —
  validated, evidence-backed, or an honest "ambiguous", "not found", or "acquired"
  flag with the candidates listed. Use whenever someone asks: find the domain for this company,
  resolve the real domains for these company names, clean this messy company list
  before enriching it, what is the actual website of X, which domain is the operating
  entity, or verify these domains belong to these companies. The keystone task: a
  wrong domain poisons every downstream enrichment, so this skill validates that
  the domain actually belongs to the operating company and refuses to guess on
  ambiguous names. Do NOT use it to enrich the resolved company
  (enrich-account-list / company-research-brief), to find people there
  (find-decision-makers-at-company), or to source new companies
  (build-prospect-list). Built on the managed Company Domain function as candidate
  generator, wrapped with free validation probes and ambiguity refusal.
category: find-contact-data
personas: [gtm-engineer, revops]
mechanism: functions
touches: read-only
keywords: []
---

# Resolve a company's domain

The insight: **a wrong domain poisons every row downstream — refusing beats
guessing.** The naive version takes the first search hit or whatever a lookup
returns; the failure is silent, and every enrichment, signal, and email built on it
inherits the wrong company. So this skill treats any looked-up domain as a
CANDIDATE, validates it actually belongs to the operating company (not a parent, a
brand redirect, or a similarly-named stranger), and returns `ambiguous` or
`not_found` — with candidates — when the name doesn't pin one entity. An honest
refusal costs a re-ask; a confident wrong domain costs the whole row, invisibly.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **What they have per row** | a name plus a claimed domain, a name only, a domain only, or a company profile URL | no default — each route costs differently, and a claimed domain is validated rather than looked up, which is free |
| **Cost ceiling** | credits | dedupe names first, then state lookups × declared cost plus validation per survivor, and wait |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — what each row already carries, and the resolution ladder it runs.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, or returns a domain it could not validate.
- **Halts** — Step 1 spend-approval.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run
the Clay plugin's `setup` skill, restart if it says to, and re-run this skill. Tell
the user which workspace you're in. Confirm the managed **Company Domain** function
exists and read its declared cost (`clay routines list`, then `clay routines get
<id>` — `get` requires the routine id).

## Step 1 — Route by what you have

| You have | Path |
|---|---|
| Name + a claimed domain | validate the claim (Step 3) — no lookup spend |
| Name only | candidate lookup (Step 2) → validate |
| Domain only | validate (Step 3), entity name comes from the site |
| Neither, but a LinkedIn company URL | pull the site link from the profile → validate |

Batch input: dedupe names first; state cost (lookups × declared cost + ~0-1 credit
validation per survivor) and get approval before running.

## Step 2 — Candidate lookup (paid, name-only rows)

Run the managed **Company Domain** function (name → domain, ~1 credit). Its output
is a CANDIDATE, never a result — the function resolves *a* company for the name,
not necessarily *the* company (name collisions are the #1 failure), and lookups on
ambiguous or common-word names return confident wrong answers. Optional second
candidate source when hints exist (a known country/region, industry): the company
search arm — noting its identifier filter is recall-not-exact and can miss the
canonical entity entirely (gate on match confidence, never take position as truth).

## Step 3 — Validate the candidate (the lever; mostly free)

Run the ladder in `references/validation-ladder.md` — in order, cheap first:

1. **Normalize** (free, code): strip scheme/www/paths, registrable label
   (public-suffix aware).
2. **Liveness + redirect probe** (free): real HTTP status via the status-honest
   probe; NXDOMAIN/dead → `not_found` evidence; a redirect landing on social media
   or a parking page → inactive candidate; a redirect to ANOTHER domain → follow it
   and validate the destination (brand → corporate redirects are common).
3. **Site-content check** (~1 credit on survivors): fetch the homepage; the site
   must plausibly BE the company — name/brand present, business coherent with any
   hints. A parked/for-sale/soft-404 body fails (a scraper's SUCCESS is not
   page-existence).
4. **Operating-entity check**: is this the entity the user means — the operating
   company, not the holding parent or a regional clone? Name-boundary discipline
   applies ("X Partners"/"X Group" are different entities). **Acquisition is a
   verdict, not a pass**: if the evidence says the company was acquired or absorbed
   (site redirects to the acquirer, "now part of Y" content, acquirer branding),
   the old-name domain is NOT the canonical answer — return `acquired` with both
   the stale domain and the acquirer's domain named; a REBRAND of the same entity
   (same company, new name/site) may still resolve, with the reasoning stated.
   Enrichment corroboration when needed (~1 credit): the payload's `website` field
   (never its `domain` field, which can echo a link-shortener) — and remember
   enrichment PRESENCE proves the entity exists in data, never that the domain is
   alive: dead and acquired companies enrich fine on last-known data.

## Step 4 — Verdict (five values, no sixth)

- **resolved** — one candidate survived all gates → `canonical_domain` +
  `operating_entity_name` + `confidence` (validated / corroborated) + `provenance`
  (which gates it passed, quoting evidence).
- **acquired** — the named company was absorbed → the stale domain is never the
  answer; emit `acquired` + the acquirer's domain as the actionable candidate
  (resolving to the acquirer is a USER decision — the entity changed).
- **ambiguous** — the name pins multiple real entities → the candidate list with
  one line each; the USER picks. Common-word names land here by default.
- **not_found** — no living candidate → say what was tried.
- **mismatch** (claimed-domain path) — the claim failed validation → the evidence,
  plus the best candidate if one emerged.
Never a guessed domain asserted as fact; never "probably". Per-row provenance
always; batch output adds a summary (resolved / ambiguous / not_found / mismatch
counts, credits measured).

## What good looks like

- **Resolved rows are load-bearing** — downstream enrichment can key off them
  blindly; that's the whole point of the gates.
- **The ambiguous bucket has content on messy lists** — a 100% resolution rate on
  common-word names means the skill guessed; refusal IS the feature.
- **Provenance per row** — which gates passed, what the site showed; a domain
  without provenance is a rumor.
- **Free gates run first** — most candidates die (or pass) on normalization and the
  status probe before any credit is spent.
- The common mistake: treating the lookup function's answer as the answer. It
  resolves A company, confidently, every time — including for names that belong to
  three companies or none.

## Rules

- MUST treat every lookup output as a candidate; MUST run the validation ladder
  cheap-first; MUST follow redirects to the destination before judging.
- MUST refuse (ambiguous, with candidates) when the name doesn't pin one entity;
  MUST return not_found rather than a best guess when nothing survives.
- MUST read enrichment corroboration from `website`, never `domain`; MUST apply
  name-boundary discipline to candidate entities.
- NEVER assert an unvalidated domain, pattern-guess a domain from the company name,
  or let a parked page pass as an operating site.
- NEVER assert a stale old-name domain for an acquired company (the `acquired`
  verdict exists for exactly this); NEVER let enrichment presence stand in for
  liveness — dead companies enrich fine on last-known data; only the probe answers
  "is this domain alive".
- Batch: dedupe names first, state cost, cap the run; per-row provenance ships.

## Representative output

Two artifacts. **Every company name and domain below is invented** (`.example` reserved
TLD). The five verdicts are **resolved / acquired / ambiguous / not_found / mismatch**, and
there is no sixth — in particular there is no "probably".

### Per-row verdicts

| input | verdict | canonical domain | operating entity | confidence | provenance |
|---|---|---|---|---|---|
| Northwind Systems (US) | resolved | northwind.example | Northwind Systems Inc. | validated | lookup produced the candidate; the free status probe returned a live page whose title reads *"Northwind Systems — Inventory Software"*. The title **is** the semantic evidence |
| Kirivale (UK) | resolved | kirivale.co.uk | Kirivale Ltd | corroborated | the claimed domain validated. Normalization kept the `co.uk` family intact — a naive registrable-label split takes `co.uk` itself and kills every international row |
| Brandex | acquired | — | absorbed into Acme Corp | — | news screen confirms the acquisition. The stale `brandex.example` is **never** the answer; `acme-corp.example` ships as the actionable candidate, and resolving to the acquirer is your call because the entity changed |
| Summit (US) | ambiguous | — | three live candidates | — | a common-word name pinning three real companies: Summit Logistics, Summit Dental Group, Summit Capital Partners — one line each, you pick. This is the refusal working, not the skill failing |
| Halloway Industrial | not_found | — | — | — | no living candidate. The two name variants tried are listed, so you can see what was searched rather than trusting that something was |
| Fabrikam Cloud, claiming `fabrikam-cloud.example` | mismatch | — | — | — | the claimed domain serves a parked-registrar page. A better candidate did emerge — `fabrikam.example`, serving a live branded product page — and it is offered, never substituted in silently |

A resolved row is meant to be load-bearing: downstream enrichment can key off it without
re-checking. That is the entire purpose of making the other four verdicts available.

### Summary

```
6 rows in

  resolved     2
  acquired     1
  ambiguous    1
  not_found    1
  mismatch     1
              --
               6 of 6

Spend: 1 credit measured. The paid candidate lookup runs only on name-only rows;
four of these six were settled by free gates — normalization, the status probe,
the news screen — before any credit was spent.

A 100% resolution rate on a list of common-word names would mean the skill
guessed. The ambiguous bucket having content is the quality signal.
```

### What these gates cannot see

Measured against a 250-account labelled panel, and worth knowing before you trust a
`resolved` row absolutely: **a company can be dead or quietly acquired and still serve a
live, branded, content-rich site today.** On such a row the status probe passes, the news
screen is silent, and from a name and a region the row is indistinguishable from a healthy
company. Two rows in that panel behaved exactly this way and no amount of free gating
reached them.

So `resolved` means *this domain is the live operating site for this name, on the evidence
available* — not *this company is trading*. If a stale-account consequence is expensive for
you, that needs a registry or news deep-check priced per row, which this skill does not
spend on by default.

## Worked example

Ask: "Clean these 5 company names into real domains: Brightloop, Meridian, Subway,
Quartzlane Systems, Zzyqx Dynamics."
- **Brightloop** → lookup → brightloop.example → probe live, homepage says
  "Brightloop — workflow automation", entity matches → **resolved** (validated).
- **Meridian** → lookup returns a fintech's domain confidently — but the name pins
  a fintech, a consultancy, and a medical group → **ambiguous**, 3 candidates
  listed, user picks (the lookup's confidence changed nothing).
- **Subway** → subway.com resolves, but entity check notes it's the BRAND/franchise
  parent — flagged so the user confirms brand vs franchisee intent → **resolved
  (operating-entity note)**.
- **Quartzlane Systems** → lookup → a domain that redirects to
  quartzlane-holdings.example (a parent) → destination validated, holding-vs-
  operating flagged → **resolved (corroborated, entity note)**.
- **Zzyqx Dynamics** → lookup empty, no living candidate → **not_found** (tried:
  lookup, search, direct .com probe).
- Counter-case: "Loopwise" → lookup returns loopwise.example, which redirects to
  its acquirer's site ("Loopwise is now part of OrbitStack") → **acquired** — the
  stale domain is never asserted; the acquirer's domain ships as the candidate.
Summary: 3 resolved · 1 ambiguous · 1 not_found · ~4 credits measured (free gates
killed 60% of the paid validation).

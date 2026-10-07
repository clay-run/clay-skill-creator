---
name: signal-sourcer
description: |
  Source net-new accounts from live buying signals with Clay — no starting list:
  define the events that matter (funding, breach/incident, expansion, leadership
  change) plus ICP guardrails, and this play sweeps event-anchored news queries,
  harvests candidate companies from articles and roundups, resolves each name to a
  canonical domain, and re-qualifies every survivor against the ICP before it earns
  a row. Use whenever someone asks: find companies that just raised, source accounts
  hit by X event this week, who just got breached, expanded, or hired a new exec,
  build a list from trigger events, or signal-based prospecting with no seed list.
  Do NOT use it to watch a fixed account list for events
  (monitor-buying-signals), to source by static ICP alone (build-prospect-list), to
  track a known person's job change (track-champion-job-changes), or to score
  inbound leads (score-inbound-leads). Every delivered row carries a dated, sourced
  evidence line; a window with no qualified events is reported as zero, never padded.
category: signals
personas: [sales-development, gtm-engineer]
mechanism: workflow
touches: read-only
keywords: []
---

# Signal-sourcer (signal-first net-new sourcing)

The insight: **signals create rows; qualification creates prospects.** List-first
plays start from accounts whose identity is given — enrichment is the only risk.
Here every row is BORN from a noisy recall channel (an event-vocabulary news query),
so the row itself must earn existence through three gates the naive build skips:
(1) a **real, dated event** — the channel's date stamps are crawl dates, not event
dates, and years-old articles surface inside a one-week window looking fresh;
(2) the **right entity** — a headline names a brand word, not a company; it must
resolve to a canonical domain with corroboration before anything downstream spends
on it; (3) **in-ICP and net-new** — an event proves a state change, never fit, and
an event at an account already in the user's book is monitoring, not sourcing.
The naive build queries news and ships the headline list: rumor-shaped rows.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Signal menu** | which event types create a prospect for them | ask, and test each one: would the event make someone buy sooner? If not it is trivia |
| **ICP guardrails** | vertical, geography, size band | **non-negotiable.** Without them every fired event qualifies and the play degenerates into news clipping |
| **Window and cap** | how recent counts, and how many qualified rows they want | **the past week is defensible**, as is 2–3 query variants per signal type. State both |
| **The book** | existing customers, open pipeline, named accounts | ask — net-new is defined against this list, and without it the play sources their own customers. If they want events on accounts they already know, that is a different skill and say so |
| **Owner mapping** | territory or segment routing rules | optional. Without it rows deliver unrouted, which is a fine outcome |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — your book, the signal menu and ICP guardrails you set, over the window you cap.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, or sends outreach on a signal it sourced.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run
the Clay plugin's `setup` skill, restart if it says to, and re-run this skill. Tell
the user which workspace you're in. Confirm the detector arm exists before promising
it — read the live catalog, never your memory of it: `clay workflows actions list`,
grep for the news-query action
(`references/detector-mechanics.md` has the contract). Note what this surface does
NOT have: no RSS/trigger-source/webhook detector actions and no event filters on
company search — the event-anchored news query is the net-new arm here; the in-app
signal engine is the graduation path, not something this play builds.

## Step 1 — Collect the signal definition (interview; do not guess)

1. **Signal menu** — which event types create a prospect for THIS user (funding
   round, security incident, expansion/new market, leadership change, product
   launch…). For each: would the event make them buy sooner? If not, it's trivia.
2. **ICP guardrails** — vertical, geography, size band. Non-negotiable: without
   them every fired event qualifies and the play degenerates into news clipping.
3. **Window + cap** — how recent counts (default: past week) and how many
   qualified rows they want (cap query fan-out accordingly; default 2–3 query
   variants per signal type).
4. **The book (suppression set)** — existing customers, open pipeline, named
   accounts. Net-new is defined against this list; without it you will "source"
   their own customers. If they want events on KNOWN accounts, route to
   monitor-buying-signals instead — say so explicitly.
5. **Owner mapping (optional)** — territory/segment → owner rules if they want
   rows routed; otherwise rows deliver unrouted.

## Step 2 — State cost, get approval

Arithmetic before any spend: (signal types × query variants) × ~1 credit per query
— quiet queries bill the same; plus ~1 credit per surviving candidate for
resolution/qualification enrichment; plus optional premium corroboration
(structured funding/jobs lookups, ~6 credits each) for a named shortlist only.
State the worst case; wait for approval.

## Step 3 — Detector sweep (event-anchored queries)

Per signal type, run 2–3 query variants composed as **event vocabulary × ICP
qualifier** (e.g. funding vocabulary × vertical term; incident vocabulary ×
industry term), each windowed with the tightest relative bucket covering the ask.
Mechanics and the build-once query workflow are in
`references/detector-mechanics.md`. Discipline per call:

- Quiet = the results field is ABSENT, not an empty list — gate on
  absence-of-events; a quiet query still bills.
- The window bounds when the index SAW the page, not when the event happened —
  treat every returned date as a claim to verify in Step 4, never as the event date.
- Query phrases are recall, not precision: a quoted round name matches adjacent
  rounds and finance-instrument notices. The query's job is candidate flow;
  precision comes from the gates.

## Step 4 — Harvest candidates (article → candidate, deterministic first)

Each result is an ARTICLE; the deliverable unit is a CANDIDATE = (company, claimed
event). Harvest with the source-class rules (full table in
`references/detector-mechanics.md`):

- **Direct event articles** → one candidate each.
- **Roundup/digest pages** → harvest EVERY named company as a candidate (for
  sourcing, roundups are a candidate-rich source — the inverse of the monitoring
  posture, where aggregator pages are dropped). Each harvested candidate carries
  the roundup as provisional source only; it must be corroborated per-company
  before delivery.
- **Social posts, forums** → drop (unverifiable, frequently garbled numbers).
- **Law-firm / investigation PRs** → keep the entity, demote the source; find the
  primary report during corroboration.
- **Dedupe into event clusters first, then date the cluster** — the same breach
  or round appears in 3–4 outlets in one sweep (sometimes naming parent,
  subsidiary, or no company at all): one candidate per event, sources merged on
  event fingerprint, best-primary kept.
- **Event-date derivation** — from the cluster's best source's own content, never
  the crawl stamp; incident signals date from the DISCLOSURE. Out-of-window drops
  with a note; no derivable date → `undated`, deliverable only if corroboration
  dates it.

## Step 5 — Resolve the entity (name → canonical domain)

A harvested name is a brand word with article context, not an identity. Resolve
each candidate with the resolve-company-domain discipline, and start with the FREE
arm: company search with the article's context terms (description keywords ×
location/state) — company search has no name filter, so context terms are how a
collision name is disambiguated, and the returned records carry name, domain, size
band, and location (often enough to kill an off-ICP candidate before any credit is
spent). The paid domain lookup returns confident wrong entities on collision names,
and a plausible knowledge-prior domain can belong to a same-brand entity elsewhere —
BOTH are candidates, not answers: corroborate the chosen domain (enrichment/search
echo: name words + registrable label, never the TLD) before promoting. No corroborated domain → the candidate is delivered in the
exceptions tail as `unresolved`, never guessed. Generic brand names ("Moss",
"Clay") are exactly where wrong-entity rows are minted — partial-stem matches get
a stated reason or get dropped.

## Step 6 — Qualify (the gate that makes it a prospect)

On the RESOLVED entity's own enrichment fields (never the article's claims):

- **ICP gates** — size band, geography, industry vs Step 1 guardrails. Band
  strings, not numbers; enrichment presence ≠ liveness — corroborate liveness for
  anything acted on immediately.
- **Net-new gate** — normalized-domain match against the book; matches are
  excluded AND recorded (`suppressed: existing customer`), with a pointer to
  monitor-buying-signals for watching them.
- **Event corroboration (shortlist only)** — for rows the user will act on today,
  confirm the claimed event: a structured per-company lookup where one exists for
  the signal type (funding/jobs arms, ~6 credits) or the primary source;
  roundup-sourced and law-firm-sourced candidates REQUIRE corroboration before
  delivery. **Degraded mode** (no general web egress — sandboxed sessions often
  can't fetch article URLs, and incident-type signals have NO structured lookup):
  cross-outlet agreement counts — ≥2 independent outlets carrying the same event
  fingerprint corroborates; a candidate with one derivative source and no
  reachable primary drops with `uncorroborated — source unreachable`, and the
  delivery says which corroboration mode ran.

Failed rows drop with reasons, never silently. Zero qualified rows in a window is
a valid, reportable result — an honest zero beats a padded list.

## Step 7 — Deliver and route

Row: `company · domain · signal type · evidence line (≤140 chars, from the
source) · event date (+ how derived) · source URL(s) · ICP verdict · net-new check
· owner (if mapped)`. Summary: queries run, articles seen, candidates harvested,
per-gate drop counts, credits spent (measured from run metadata where the surface
exposes it). Then the routing note: this play delivers a POINT-IN-TIME sweep; a
standing version of the same ask should graduate to the in-app signal engine
(native signal subscriptions / signal-triggered workflows) — offer the hand-off
with the arithmetic, never rebuild it as a re-scraping loop.

## What good looks like

- The expert reads the **drop ledger first**: candidates killed per gate (stale
  date, wrong entity, off-ICP, in-book, uncorroborated) prove the gates ran. Zero
  drops means news clipping, not sourcing.
- Every delivered row is verifiable in one click, and its event date has a stated
  basis (in-text date / primary source), never a crawl stamp.
- Duplicate events collapsed: one row per (entity, event), sources merged.
- The common mistake: shipping the headline list. The second-worst: "sourcing"
  the user's own customers because nobody asked for the book.

## Rules

- MUST state cost and get approval before the sweep; quiet queries bill too.
- MUST derive event dates from content, NEVER trust the channel's relative date
  stamps; out-of-window and undated-uncorroborated candidates are dropped/tailed.
- MUST resolve every candidate name to a corroborated domain before enrichment
  spend or delivery; unresolved candidates go to the exceptions tail.
- MUST re-qualify against ICP + the book on resolved-entity fields; suppressed
  and dropped rows are recorded with reasons, never silent.
- MUST report an empty window as zero qualified rows — no padding, no widening
  the window silently.
- NEVER auto-send outreach, write to a CRM, or stand up a permanent re-scraping
  loop — deliver the sweep; graduate standing watches to the native signal engine.

## Representative output

Two artifacts, and an expert reads the second one first. **Every organisation and domain
below is invented** (`.example` reserved TLD). The ask was a security-incident signal across
US healthcare, 200+ employees, against a two-account book.

### Qualified rows

| company | domain | signal | evidence line | event date, and how it was derived | sources | ICP | net-new |
|---|---|---|---|---|---|---|---|
| Alderwood Health Systems | alderwoodhealth.example | security incident | "Alderwood notified 42,000 patients of unauthorized access at a billing vendor" | 2026-09-24 — the disclosure date stated in the notice | 2 independent outlets | fit · 1,400 staff · US | net-new |
| Kestrel Regional Care | kestrelcare.example | security incident | "Kestrel confirmed a ransomware incident affecting scheduling systems" | 2026-09-29 — stated in the article text | 3 independent outlets | fit · 650 staff · US | net-new |
| Harrow Medical Group | harrowmedical.example | security incident | "Harrow disclosed a breach affecting its imaging archive" | 2026-10-01 — stated in the article text | 2 independent outlets | fit · 310 staff · US | net-new |

Every event date has a **stated basis** and not one of them is a crawl timestamp. That
distinction is load-bearing: a years-old roundup surfaced inside a one-week sweep carrying a
fresh relative stamp, and anything trusting the crawl date would have shipped it as this
week's news.

`Harrow Medical Group` was harvested under a subsidiary's former brand name and resolved to
the parent organisation. Without the multi-name carry-forward it would have appeared as an
unresolvable entity and been dropped.

### Drop ledger — read this first

| gate | dropped | why |
|---|---|---|
| window and vocabulary noise | 22 | aggregator reprints of events already counted; a years-old roundup surfacing in a one-week window behind a fresh relative stamp; and a preferred-stock conversion notice that matched the signal vocabulary exactly while not being the signal |
| book gate — existing customer | 2 | both surfaced through litigation coverage. Excluded **and recorded**, with a pointer to the fixed-list watching play — these are accounts to watch, not to source |
| off-ICP | 1 | 90 staff against a declared floor of 200, compared as a band rather than a number |
| uncorroborated | 1 | a single derivative source — a law firm's own release — with the primary unreachable |
| unresolved entity | 1 | the article named an organisation that could not be resolved to a canonical domain |

```
30 articles seen
 8 candidates after event-cluster dedupe (one event across 3–4 outlets
   collapses to one candidate, sources merged)
 3 qualified, net-new

   8 = 3 qualified + 2 suppressed + 1 off-ICP + 1 uncorroborated + 1 unresolved

Up to 5 were asked for and 3 delivered, because the window supplied 3. Padding
to five would mean shipping the rows the gates had just killed.

Spend: 6 credits — 2 measured on the sweep queries, 4 a declared estimate on
enrichment, where the surface exposes no per-run actuals.

Corroboration mode: DEGRADED, and stated because it changes what the evidence
is worth. This run had no general web egress, and no structured lookup exists
for incident signals, so corroboration was cross-outlet agreement: two or more
independent outlets carrying the same event fingerprint.
```

**A window that qualifies nobody is a result** and gets reported as a zero. Zero *drops*, on
the other hand, means this was news clipping rather than sourcing — the ledger above is what
proves the gates ran at all.

This is a point-in-time sweep. A standing version of the same ask belongs on the in-app
signal engine rather than being rebuilt here as a re-scraping loop.

## Worked example

Ask: "Find healthcare companies hit by a data breach this week — we sell incident
response; 200+ employees, US only. Here are our 60 current accounts." Cost stated:
2 query variants ≈ 2 credits + ~1/candidate qualification ≈ 8 worst case — approved.
Sweep returns 10 articles → harvest: 7 candidates after (entity, event) dedupe
(one breach appeared in 3 outlets — merged), 1 social post dropped, 1 "breach
tracker" roundup harvested for 2 additional names flagged corroboration-required.
Resolution: 6/7 corroborated domains; "Meridian Health" stays `unresolved` (three
same-name orgs, article context insufficient). Qualification: 1 dropped off-ICP
(38 employees), 1 suppressed (already a customer — noted for
monitor-buying-signals), roundup-harvested names corroborated via primary
notices — 1 confirmed, 1 uncorroborated → dropped with reason. Deliver 3 qualified
net-new rows, each: domain, "breach exposed 310K patient records", event date from
the notification filing, source links, size/geo verdict, owner per territory map.
Drop ledger shows all 4 kills. Offer: make it standing via the native signal
engine instead of weekly re-sweeps.

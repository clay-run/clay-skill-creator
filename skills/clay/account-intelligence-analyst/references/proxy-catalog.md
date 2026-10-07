# Proxy catalog — observables, arms, and what they cost

Read from the live catalog on **2026-08-13** (`clay workflows actions list`, 656 actions), and
four arms probed live the same day.

**Re-resolve before quoting.** Providers appear, disappear and reprice; a price recited from
this file is a price from memory, which the skill forbids. The value here is the *shape* — which
observables have arms, which have many, and how wide the spread is — not the numbers.

## ⚠ `creditCost` is sometimes a PER-UNIT RATE, not a call price

The single most expensive mistake available in this file, and the first version of it made the
mistake. **4 of the 20 arms priced here bill per item returned**, and the multiplier appears only
in a *parameter description* — never in the `creditCost` field a cost model would read:

| Arm | `creditCost` | What it actually bills | Call cost at its default |
|---|---|---|---|
| `enigma-get-operating-location-addresses` | 0.8 | "0.8 credits **for each operating location**" | default 10 → **8 cr**; max 100 → **80 cr** |
| `sumble-enrich-company-technologies` | 6 | "6 Clay Credits **for each technology returned**" | 20 technologies → **120 cr** |
| `lusha-enrich-company-news-signal` | 8 | "charged 8 credits **for each signal found**" | 5 signals → **40 cr** |
| `lusha-enrich-company-jobs-growth-by-location-signal` | 8 | per location, `maxResultsPerSignal` up to 100 | unbounded without a cap |

Verified empirically: `enigma-…-addresses` with `maxOperatingLocations: 1` reported
`totalCost: 0.8`. So the rate is real and the default multiplies it tenfold.

**Rule this yields, and it belongs in every cost estimate:** before pricing an arm, read its
parameter descriptions for a per-unit rate, and if there is one, price it at the cap you intend
to pass — not at `creditCost`. Summing `creditCost` across arms is only valid for flat arms.
A per-unit arm with an unset cap is an unbounded per-account cost.

Corollary worth its own line: **for a COUNTING question, prefer the flat counting arm.**
`enigma-get-operating-location-count` is 6 credits flat; `-addresses` is 0.8 × N where N is
unknown before you pay. The count arm wins unless you are confident N < 8, and it is the honest
choice when the proxy only needs a number.

## The finding that shapes the play: the same observable costs 1–10 credits

| Observable | Cheapest arm | Cost | Expensive arm | Cost | Spread |
|---|---|---|---|---|---|
| Open job postings | `cpj-find-lists-of-jobs` | 1 | `pdl-enrich-company-job-post-insights` | 10 | **10×** |
| Employee growth | `cpj-get-company-employee-growth-v2` | **0.5** | `pdl-enrich-company-detailed-employee-trends` | 10 | **20×** |
| Hiring by department | `lusha-enrich-company-jobs-growth-by-department-signal` | 8 | — | — | — |
| News / press | `find-google-news-results` | 1 | `lusha-enrich-company-news-signal` | 8 | **8×** |
| Tech stack | `buyercaddy-enrich-company-tech-stack` | 4 | `cb-insights-company-technology-classification` | 8 | 2× |
| Web traffic | `se-ranking-get-ai-search-visibility` | 2 | `similarweb-get-website-visits` | 6.5 | 3× |
| Funding | `crunchbase-enrich-company-latest-funding-round` | 10 | `beauhurst-find-company-funding` | 16 | 1.6× |
| Operating locations | `enigma-get-operating-location-count` | 6 flat | `enigma-…-addresses` | 0.8 **× N** | see the per-unit warning — the "cheap" arm is dearer past 8 locations |

Two things follow, and they are the whole reason step 2 prices proxies before running them:

1. **Ordering is the cost model.** A four-proxy question costs 3 credits per account on the
   cheap arms and 30 on the expensive ones. At 300 accounts that is 900 versus 9,000 — the
   difference between a play someone runs weekly and one they run once.
2. **Cheap first is not just cheaper, it is better sequencing.** The cheap arms are usually the
   coarse ones (is there *any* posting) and the expensive ones the fine-grained ones (postings
   by department, by location, trended). Coarse-then-fine is the order that lets early exit
   work: the coarse arm often settles the answer, and the fine arm is only worth buying for the
   accounts still unsettled.

Note also the two **free** arms, which should almost always be proxy #1: the company's own site
(fetch/scrape) and a DNS/status pre-gate. Free arms cannot early-exit you *out* of a paid call
if they run first, and they anchor the entity — which the skill requires before any paid proxy.

## Question type → proxy set

Starting points, not prescriptions. The user's weights decide, and the bar comes from step 1.

### "Are they building a team / capability in X?"
| Proxy | Arm | Notes |
|---|---|---|
| Open roles naming X | job-postings arm | strongest single proxy; a posting is a committed spend |
| Growth in the relevant department | department-growth arm | expensive; buy only for unsettled accounts |
| X named in own site copy | site fetch (free) | **weak** — marketing copy, near-universal for hot categories |
| Named leader hired for X | news arm | **corroboration only** — probed: the window parameter is unreliable and results are topically adjacent, so it cannot settle a question alone |
| Internal roadmap / approval | **none** | declare unobservable |

### "Are they expanding into a geography?"
| Proxy | Arm | Notes |
|---|---|---|
| Job posts in that geography | jobs-by-location arm | direct; a role in-region is a commitment |
| Operating addresses in-region | `enigma-get-operating-location-*` | **per-unit** — see the warning above; use the flat count arm to count |
| Localized site / regional domain | site fetch (free) | localization is often marketing-led, not operational |
| Regional press | news arm | corroborates, rarely settles alone |

### "Do they run on / against a technology?"
| Proxy | Arm | Notes |
|---|---|---|
| Tech-stack detection | tech-stack arm | providers disagree; two agreeing beats one asserting |
| Integration/partner page on own site | site fetch (free) | strong when present, silent when absent |
| Job posts naming the technology | job-postings arm | often the best signal for internal tooling |

### "Are they growing / shrinking?"
| Proxy | Arm | Notes |
|---|---|---|
| Employee-count trend | employee-growth arm | 1 cr coarse, 10 cr trended |
| Web-traffic trend | traffic arm | direction only; absolute figures are estimates |
| Funding | funding arm | expensive (10–16 cr) and lumpy — a raise is not growth |
| Headcount band | company enrichment | **arrives as a BAND STRING** — report the band, never a number |

## Observables with no arm on this surface

Declare these `observable: no` and keep their weight in the denominator. Each is something
users ask for:

- **Budget, approval, procurement stage** — nothing observes internal finance.
- **Contract renewal dates** — not derivable from any catalog arm.
- **Private headcount by team** — department *growth signals* exist; actual team rosters do not.
- **Intent-data / category research activity** — `trustradius-enrich-company` is company
  enrichment; the category-scoped intent source is an in-app trigger, not a catalog action.
- **Identified website visitors** — `similarweb-get-website-visits` is volume, not identity.

## Provider disagreement is evidence, not noise

Where two arms observe the same thing and disagree, that is a real finding about the account —
usually a stale record on one side. Two arms agreeing is meaningfully stronger than one
asserting, and it is the only corroboration available without human review. Where the budget
allows exactly one arm, prefer the cheap coarse one and let `insufficient evidence` do its job;
a single expensive arm's assertion is not more true for having cost 10 credits.


## Probed live, 2026-08-13 — what the payloads actually do

Four arms executed once each, one call per arm. Costs below are each action's own
`metadata.upfrontCreditUsage.totalCost`, which matched the catalog every time. No payload
values are reproduced here beyond field names and counts.

### `cpj-find-lists-of-jobs` — 1 cr flat. The best-behaved arm probed.

Accepts a **bare domain** as `company_identifier`; `job_title_keywords` and
`max_num_days_since_posted` both worked as documented.

**It returns `jobCount` — the true total — alongside the capped result page.** Probe: 10 results
returned, `jobCount: 33`. So on this arm truncation *self-reports*, and a counting proxy is
answerable for 1 credit without paging or cap-equality guesswork. `limit` maxes at 10, but
`identifiers_only: true` lifts that to 500 (title + URL only) at the same price.

**But a job count is not a role count.** Those 10 results were **4 distinct titles** across 6
locations — the same role posted per-location, each row a genuine posting. "33 AI/ML openings"
and "4 AI/ML roles" are both true and mean different things, so a proxy must say which unit it
counted. For "are they building a team", distinct titles is the honest figure and the raw count
overstates by ~8×.

Payload note: full job descriptions ship by default — ~6–9 KB each, 72 KB for ten jobs. For an
AI-column build that is a context cost as well as a credit cost, and `identifiers_only` avoids
it.

### `cpj-get-company-employee-growth-v2` — 0.5 cr flat (re-verified 2026-10-07; key versioned to `-v2` and cost halved from 1).

The `website` (domain) path works, and **echoes back the resolved LinkedIn company URL** — free
corroboration that the arm resolved the same entity your anchor did. Use it as an anchor
cross-check. Its own schema warns the domain path is lower-accuracy than the LinkedIn URL path;
that trade is the price of being domain-anchored.

Returns absolute counts and percent growth at nine horizons (1/3/6/9/12/24/36/48/60 months).
**In the probe, the 1-month fields were `null` while all eight others were populated.** A null
horizon is a data gap, and reading it as zero produces "0% growth" → a `contradicts` verdict
manufactured out of missing data. The most recent horizon is the likeliest to be null, which is
exactly the one a freshness-minded author reaches for first.

Note this arm returns **integers**, while the managed Enrich Company function returns headcount
as a **band string**. Two representations of the same observable in one workspace; never compare
across them.

### `find-google-news-results` — 1 cr flat, and the least trustworthy arm probed.

- **`date_filter` has no declared value space** (no enum, no typeSettings, description is
  "Filters news results by date") and the value passed was **silently ignored**: a request
  filtered to the past month returned items dated five months back. It failed in the dangerous
  direction — stale results presented as fresh — with no error.
- **`date` mixes formats in one field**: relative for recent items ("1 week ago", "1 month ago"),
  absolute for older ("May 6, 2026"). Precise windowing off "1 month ago" is not possible.
- **`total_news_results` equals the returned count**, so despite the name it is *not* a
  total-available figure. Contrast `jobCount`, which is.
- **`outputParameters` is `null`** on this action: the declared output contract is not merely a
  subset of reality but entirely absent.
- **Relevance is topical, not answer-shaped.** Asked for a specific hiring event at a named
  company, the ten results included a *different* company hiring *former* employees of the
  target — evidence of the opposite — plus executive opinion pieces and unrelated product news.
  One result was an actual hire at the target, in a different function entirely.

That last point is the empirical case for this whole play. Hand those ten results to a model and
ask "is this company building an AI team?" and it will find abundant AI-adjacent text about the
right company and answer yes. The proxy fired; the question was not answered. **Treat the news
arm as corroboration only, never as a proxy that can settle a question alone**, and weight it
accordingly in step 2.

### `enigma-get-operating-location-addresses` — 0.8 cr **per location**, confirmed.

`maxOperatingLocations: 1` → `totalCost: 0.8` exactly. Returns `operatingLocations` (array) and
`operatingLocationsFound` (the same content as a string — redundant), plus
`operatingLocationRequestedCount` echoing the request. **There is no total-available count**, so
unlike the jobs arm you cannot learn how many locations exist without paying per location — which
is precisely why the flat 6-credit count arm is the right tool for a counting proxy.

### Process note: a timed-out call leaves the spend indeterminate

One further probe (re-testing `date_filter` with Google's own `qdr:w` syntax) **timed out at 60
seconds**. Whether the server executed and billed it is unknowable from this side, so it was not
retried — a blind retry risks paying twice for an unknown. The `date_filter` value space
therefore remains unresolved, and the skill treats the parameter as unreliable rather than as
broken.
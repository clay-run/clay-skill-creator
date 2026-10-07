---
name: source-local-businesses
description: |
  Build a deduped, validated list of local businesses with Clay — gyms, restaurants,
  clinics, retailers, agencies, any physical-location category — from a business type
  plus locations, or from a known brand whose locations you want. Use whenever
  someone asks: find local businesses in a city, source gyms in Brooklyn, build a
  list of HVAC companies near Austin, get all the coffee shops in these zip codes,
  list every location of a franchise brand, or scrape Google Maps listings.
  It asks the franchise question first (location or brand? — that decides the
  dedupe), discovers via the cheapest viable arm, normalizes domains before
  deduping, and ships unique, post-validated survivors. Do NOT use it to source B2B companies by firmographics
  (build-prospect-list), to find people at a company (find-decision-makers-at-company),
  to scrape an arbitrary non-directory page (scrape-any-website), or to research one
  business deeply (company-research-brief). Built on SERP scraping, OpenMart catalog
  actions, and review enrichments.
category: build-lists
personas: [founder, sales-development]
mechanism: functions
touches: read-only
keywords: [local-business]
---

# Source local businesses

The insight: **local-business lists die by duplication and staleness, not by
discovery — and the dedupe key is a sales question, not a data question.** Finding
200 "gyms in Brooklyn" is trivial; delivering unique, open, in-category businesses is
the work, and whether 12 Crunch Fitness locations are 12 rows or 1 row depends
entirely on whether you sell to the franchisee or the brand. So this skill asks the
franchise question first, discovers with the cheapest viable arm, normalizes domains
before any dedupe (the same business surfaces under prefixes, subpaths, and vanity
URLs), and spends enrichment credits only on survivors.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Category and locations** | the business type in their words, plus cities, postcodes or regions — or a known brand whose locations they want | no default; the brand case is a different route entirely |
| **The franchise question** | sell to the location or to the brand | ask. It decides the dedupe grain, and whether franchise-heavy results are signal or noise |
| **Target count and fields** | how many rows, and what each carries | ask — the fields decide whether the review-enrichment arm runs at all |
| **Cost ceiling and hard cap** | credits | state the arm arithmetic — pages × cost, enrichments × survivors — and a hard cap before anything runs |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — the category and locations you name, via local business search.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, enrolls anyone, or contacts a business it sourced.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run
the Clay plugin's `setup` skill, restart if it says to, and re-run this skill. Tell
the user which workspace you're in. Verify the arms live before promising them —
catalogs differ per workspace and the discovery-vs-brand distinction below was a
live finding, not folklore (`references/sourcing-arms.md`).

**Resolve every arm you intend to use, and read its real price, before quoting anything:**

```
clay workflows actions list                              # the action catalogue, greppable
clay workflows actions schema <packageId> <actionKey>    # real inputs, and per-unit rates
```

Identify each arm by the **pair** of `packageId` and `actionKey` — keys collide across packages,
so a key alone does not say which vendor or which price you are getting. And read the parameter
descriptions for a per-unit rate before pricing: an arm billed per result returned is not the
number its `creditCost` field shows.

## Step 1 — Scope (interview; the franchise question is mandatory)

1. **Category + locations** — the business type in the user's words plus cities/zips/
   regions; OR a known brand whose locations they want (a different arm entirely).
2. **The franchise question** — sell to the LOCATION (each franchisee = a row; dedupe
   on place) or the BRAND (one row per parent; locations become a count)? This
   decides the dedupe grain and whether franchise-heavy results are signal or noise.
3. **Target count + fields** — how many, and what per row (name, address, rating,
   website, phone…). Fields drive whether the review-enrichment arm runs.
4. **Cost + cap** — state the arm arithmetic (pages × cost, enrichments × survivors)
   and a hard cap before anything runs.

## Step 2 — Pick the arm (references/sourcing-arms.md has live configs + costs)

- **Category discovery** → paginated Google-SERP local results (UDM) via the
  rendering scraper with CSS extraction: ~1 credit/page ≈ 20 results/page. Selectors
  ROT quarterly — the reference carries the current map and the fallback.
- **Brand locations** → the OpenMart locations action: give it the parent's website,
  get its locations in a geo (max 30/call). This is a lookup of a KNOWN brand, not
  category discovery — the two jobs are different arms on this surface.
- **Depth on survivors only** → review enrichment (~1 credit/business) for website/
  phone/hours/score, AFTER dedupe — never enrich the raw haul.
- **Scale/recurrence honesty**: multi-city bulk (3+ cities or 500+ places) or a
  recurring refresh belongs in a table/workflow or a bulk pipeline — say so and
  offer the graduation instead of grinding pages ad hoc.

## Step 3 — Discover, bounded

Paginate with an explicit page cap stated up front. Per page: extract name, rating,
review count, address, and any website/detail fields the arm exposes. Every row
carries its source (page URL / call) and the raw fields. Empty or short pages end
pagination honestly — report the boundary, never loop past it.

## Step 4 — Normalize, dedupe, validate (free, in code)

1. **Normalize domains** before comparing: strip protocol/www/tracking, take the
   registrable label (public-suffix aware — naive split kills international TLDs),
   collapse subpaths; a missing website is normal for SMBs, key those rows on
   name+address instead.
2. **Dedupe per the Step-1 grain**: location grain → collapse exact place repeats
   (name+address); brand grain → collapse to parent (shared domain/brand name),
   carrying `location_count` as a column.
3. **Post-validate the category**: SERP keyword matching over-returns (a "gym"
   query returns physio clinics and supplement shops) — a cheap deterministic
   name/category screen first, and only genuinely ambiguous rows to an LLM pass
   that must quote what it ruled on.
4. Rows dropped at each gate are counted by reason — the funnel ships with the list.

## Step 5 — Enrich survivors and deliver

Only survivors get paid depth (website/phone/score via the review arm — costs
stated). Deliver: per business `name · address · category-as-evidenced · rating ·
reviews · website (normalized) · phone · source`, plus the funnel summary: pages
pulled, raw rows, dupes collapsed (by grain), category rejects, survivors, credits
spent (measured per call). A shortfall against the target is reported with which
locations/pages were exhausted — never padded with off-category rows.

## What good looks like

- **The grain matches the motion** — a franchisee-seller gets locations; a
  brand-seller gets parents with location counts. One list can't serve both.
- **The funnel is visible** — raw → deduped → validated counts per stage; a list
  without its funnel hides how much noise it started as.
- **Domains are normalized before dedupe** — prefix/subpath variants of one business
  never survive as two rows.
- **Category is evidenced** — survivors match the ask by name/category evidence, not
  by having appeared in the search.
- The common mistake: enriching the raw haul. Dedupe and validation are free;
  enrichment isn't — spend order is the whole economics of this play.

## Rules

- MUST ask the franchise/grain question and state arm costs + a page cap before any
  run; MUST paginate bounded.
- MUST normalize domains (public-suffix aware) before dedupe; MUST post-validate
  category before enrichment; enrichment on survivors only.
- MUST ship the funnel (counts by rejection reason) with the list.
- NEVER pad a shortfall with off-category rows; NEVER present stale/closed
  businesses knowingly (a dead website on a survivor is a flag).
- NEVER grind ad-hoc pages past the cap or for recurring refreshes — graduate to
  the table/workflow shape and say so.

## Representative output

Two artifacts, and the first one looks different depending on the grain you chose in
Step 1. **Every business, address, phone and domain below is invented** (`.example`
reserved TLD).

### The list — location grain

Each row is a place you could visit. Survivors only; the rejected rows are accounted for
in the funnel.

| name | address | category as evidenced | rating | reviews | website | phone | source |
|---|---|---|---|---|---|---|---|
| Fernwood Coffee Roasters | 418 Alder St, Westbrook | coffee shop — "Coffee Roasters" in the name | 4.7 | 312 | fernwoodcoffee.example | (555) 010-0118 | local results, page 1 |
| Marlowe & Sons Café | 22 Kestrel Ave, Westbrook | coffee shop — listed category "Café" | 4.5 | 188 | marlowesons.example | (555) 010-0147 | local results, page 1 |
| Brightline Coffee — Harrow Rd | 9 Harrow Rd, Westbrook | coffee shop — franchise location | 4.4 | 241 | brightlinecoffee.example | (555) 010-0163 | brand locations arm |

### The same haul at brand grain

One row per parent, with the location count carried as a column. A franchisee-seller wants
the table above; a brand-seller wants this one. **One list cannot serve both**, which is
why Step 1 asks before spending anything.

| name | category as evidenced | rating | reviews | website | location_count | source |
|---|---|---|---|---|---|---|
| Brightline Coffee Co. | coffee shop chain | 4.4 avg | 1,204 total | brightlinecoffee.example | 5 | brand locations arm |

The grain keys arrive in-band rather than being inferred: each location carried
`ownership_type: FRANCHISE`, a `brand_id`, and a `parent_company_locations_count`, plus
parsed address, both place ids and a per-location phone.

### Funnel

```
Pages pulled: 1 (cap: 3)

  raw rows                        17
  localized UI tokens stripped     3   names arrived with search-page chrome
                                       concatenated onto them
  collapsed as duplicates          4   including five URL variants — www, an
                                       /en-us path, a restaurants. subdomain and
                                       two tracking-tagged deep links — that
                                       normalize to ONE registrable domain
  rejected on category             2   a physio clinic and a supplement shop;
                                       both matched the keyword, neither is a
                                       coffee shop
  survivors                       11
                                  --
                        4 + 2 + 11 = 17  ✓

Paid depth ran on the 11 survivors only. Dedupe and category validation are free;
enrichment is not, so the spend order is the whole economics of this play.

Spend: 1 credit measured for the discovery page, 1 for the brand-locations call.
A third call on a brand that does not exist returned a no-data result and was
refunded by the provider — net zero for that call, and netted out of the total
rather than reported as spend.

Shortfall: none. 11 survivors against a target of 10. Had it come up short, the
report would name which pages and locations were exhausted — never padded with
the off-category rows above.
```

## Worked example

Ask: "Get me 50 independent coffee shops in Providence for our POS pitch."
Franchise question: selling to the LOCATION, but "independent" means franchise
brands are NOISE → location grain + brand-count filter (any brand with >3 locations
drops). Arm: UDM discovery, 5 pages × 1 credit stated and approved. Discovery: 96
raw rows. Normalize+dedupe: 81 places; brand filter drops 17 chain locations;
category screen drops 9 (two bakeries, a roastery-only, six restaurants that
serve coffee) → 55 survivors. Review enrichment on the 50 requested (50 × ~1
credit, approved) → websites/phones filled where they exist (12 have none — normal
for SMBs, keyed on name+address). Delivered: 50 rows + funnel (96 → 81 → 64 → 55)
+ ~55 credits measured. Counter-ask: "list every Crunch Fitness in New England" —
brand-locations arm with the parent website, 1 credit per geo call, no scraping.

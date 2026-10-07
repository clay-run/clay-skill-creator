---
name: scrape-any-website
description: |
  Extract structured data from any web page or site using Clay — pull the fields you
  name off a URL, a list of URLs, or a directory, and return clean rows. Use whenever
  someone asks: scrape this website, extract data from this page, pull all the links
  or emails or listings off a site, get the pricing or team or jobs page into a table,
  scrape a directory of profiles, or turn this page into structured data. It works
  down a cost ladder — a hidden JSON API first (free), predictable URL patterns next,
  a plain fetch for static pages, and a rendering anti-bot scraper only when the
  cheaper rungs fail — and everything it returns traces to what the page actually
  served. Do NOT use it to source local businesses from Google
  Maps (source-local-businesses), to detect a company's tech stack (detect-tech-stack),
  to compile a multi-source research brief (company-research-brief), or to watch pages
  for changes over time (monitor-buying-signals). Built on Clay's http-api-v2,
  scrape-website, and Zenrows catalog actions.
category: research
personas: [gtm-engineer]
mechanism: functions
touches: read-only
keywords: []
---

# Scrape any website

The insight: **the rendered page is the most expensive, most brittle place to get its
own data.** Most "scraping" jobs are an API call or a static fetch in disguise — the
pretty page is a thin front-end over JSON, or its URLs follow a pattern you can build
instead of crawl. So this skill works DOWN a ladder — **API → URL pattern → static
fetch → rendered/anti-bot scrape** — and only pays for the rung the target actually
requires. The bottom rung's CSS selectors rot quarterly; every trip down the ladder is
maintenance debt you should decline when a higher rung works.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The target** | one URL, a list of them, or an index page to expand | no default |
| **The fields** | exactly what comes out per row, named like table headers | **if they cannot name fields they want reading, not scraping** — offer a text pull instead of guessing at a schema |
| **Volume and recurrence** | one page, hundreds, or a recurring pull | ask. One page is an ad-hoc call; hundreds or a recurring cadence belongs in a table or workflow, and the skill should say so rather than looping |
| **Legitimacy** | that the pages are public | public pages only — no login walls, no paywalled content, and no personal-data harvesting beyond what a page publicly presents |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — the target you name and the fields you ask for, from pages it fetches.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, or fetches a target you have not confirmed you may.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run the
Clay plugin's `setup` skill, restart if it says to, and re-run this skill. Tell the
user which workspace you're in. Confirm the three actions exist in the catalog and
read their LIVE costs (`clay workflows actions list`) — verified costs and configs are
in `references/scraper-ladder.md`, and they drift.

## Step 1 — Scope the extraction (interview the user; do not guess)

1. **The target** — one URL, a list, or a directory/index page to expand.
2. **The fields** — exactly what comes out per row (name it like a table header). If
   the user can't name fields, they want reading, not scraping — offer a text pull.
3. **Volume + recurrence** — one page is an ad-hoc call; hundreds of pages or a
   recurring pull belongs in a table/workflow, and this skill should say so.
4. **Legitimacy check** — public pages only; no login walls, no paywalled content, no
   personal-data harvesting beyond what the page publicly presents.

## Step 2 — Pick the rung (the ladder, top down)

Test each rung cheaply before falling to the next
(`references/scraper-ladder.md` §Rung tests):

1. **Hidden API (free):** most directories and search UIs are a JSON API behind a
   front-end. Find it (DevTools → Network → Fetch/XHR), replicate with `http-api-v2`,
   parameterize query/page. Structured JSON out, no selectors to rot.
2. **URL interpolation:** predictable URL structure means you build the page list by
   formula from a slug/seed table instead of crawling an index.
3. **Static fetch (~1 credit/page):** `scrape-website` for plain HTML — text, links,
   or html output; `outputFields: ["links"]` is the canonical "give me every link so
   I can filter" move for index pages.
4. **Rendered / anti-bot (~1 credit/page):** `zenrows-run-scrape` with js_render /
   premium_proxy / anti_bot as the target demands, plus `css_extractor` to return
   named fields instead of raw HTML. Last rung, most brittle — selectors are
   maintenance debt with a shelf life.

State the chosen rung, why, and the cost arithmetic (pages × rung cost) — get
explicit approval before any multi-page run.

## Step 3 — Extract and structure

- Extract to the user's named fields. On the Zenrows rung, `css_extractor` returns
  column-major parallel arrays — recolumnize to rows before delivering.
- **Gate on served content, not call success**: an empty body, a soft-404, a consent
  interstitial, or a bot-challenge page is NOT the data — detect these shapes
  (`references/scraper-ladder.md` §Failure shapes) and report them as such.
- Paginate explicitly (bounded page count, stated up front); never loop unbounded.
- Per-row provenance: every row carries its source URL.

## Step 4 — Deliver honestly

Rows with the named fields + source URL, plus a run summary: pages fetched, rows
extracted, pages that failed and HOW (404 / blocked / empty / challenge), rung used,
credits spent (measured from usage metadata). A field the page doesn't contain stays
empty with a note — never inferred from the model's own knowledge of the site.

## What good looks like

- **The rung is justified** — an API-shaped target scraped with Zenrows is money and
  robustness thrown away; check the ladder out loud.
- **Extraction ≠ recall**: what ships traces to the fetched payload — quote-level
  fidelity for text fields; the model's memory of a site is never a source.
- **Blocked is a result** — anti-bot walls and login walls are reported, not worked
  around; escalating to heavier evasion is out of scope.
- **Selector debt is named**: any Zenrows css_extractor delivered to the user comes
  with the "selectors rot quarterly" warning attached.
- The common mistake: reaching for the scraper first. DevTools' Network tab finds a
  JSON API behind most directories in two minutes, and that rung is free.

## Rules

- MUST work the ladder top-down and state the chosen rung + cost before multi-page
  spend; MUST cap pagination.
- MUST gate every delivered row on actually-served content; NEVER backfill a field
  from model knowledge or another site.
- NEVER scrape behind logins/paywalls, bypass bot walls beyond the standard anti-bot
  rung, or harvest personal data beyond what the page publicly presents.
- NEVER inline API credentials in a column or chat — Named Credentials only.
- Recurring or hundreds-of-pages jobs → recommend the table/workflow shape, don't
  grind ad-hoc calls.

## Representative output

Two artifacts. **Every URL and value below is invented** (`.example` reserved TLD). The
ask was a product listing from a public catalogue, three named fields.

### Rows

Every row carries the URL it came from, so any value can be traced back to a payload
rather than taken on trust.

| name | price | sku | source URL |
|---|---|---|---|
| Alder Field Jacket | $248.00 | NW-4417 | northwind.example/api/catalogue?page=1 |
| Kestrel Rain Shell | $192.00 | NW-4418 | northwind.example/api/catalogue?page=1 |
| Harrow Wool Overshirt | — | NW-4419 | northwind.example/api/catalogue?page=1 |

`Harrow Wool Overshirt` has no price **because the payload has no price for it** — the
field is empty with a note. The model knows roughly what a wool overshirt costs and that
is exactly why it must not fill the cell; a plausible invented price is indistinguishable
from a real one to the person reading the spreadsheet.

### Run summary

```
Rung used: 1 — hidden JSON API, found behind the catalogue's front end

  pages fetched      1 of a stated cap of 3
  rows extracted     3   (exactly the 3 requested)
  pages failed       1   — see below
  spend              0 credits + 1 action execution

Why this rung: the target turned out to be a JSON API behind a front end, so no
scraper was needed. A scraper would have cost 1 credit per page and returned HTML
to parse with selectors that rot. Checking the ladder out loud took two minutes.

Failures, reported rather than smoothed over:
  northwind.example/catalogue/archive   404
      The scraper rung returned SUCCESS and a full page body for this URL.
      It genuinely 404s. The vendor exposes no HTTP status anywhere in the
      response, so the only thing that caught it was a free status probe on
      the same URL, which errored honestly with the 404.
      THIS IS WHY SUCCESS IS NOT THE GATE — served content is.

  One earlier attempt on the API rung returned 403 for a missing request
  header. An honest, diagnosable failure: fixed by sending the header, not by
  escalating to a heavier rung.
```

### What was not attempted

**The anti-bot rung was never exercised live.** Its configuration is documented from the
catalogue, and that is a different thing from having run it — treat its mechanics as
unverified until someone does. Two things are known about it regardless: it returns
column-major parallel arrays that need recolumnizing into rows before delivery, and any
selector set delivered from it is maintenance debt with a shelf life of about a quarter.

One live trap worth carrying into any run on the static rung: a plausible-looking output
field value that is not in the real enum **silently returns nothing while still billing
you**. Two calls established that. Read the enum from the live schema rather than from
what the parameter name suggests.

## Worked example

Ask: "Scrape the speaker list off this conference site into name / title / company."
Rung test: the speakers page loads its grid from `/api/speakers?page=1` (DevTools,
two minutes) → **rung 1**: `http-api-v2` GET, paginated 1..4, free, structured JSON —
names/titles/companies land as clean rows with source URLs; 2 pages returned 404
past the last page → reported as end-of-pagination, run stopped.
Counter-example: "get every portfolio company off this VC's site" — no API found,
but portfolio pages live at `/companies/a` … `/companies/z` → **rung 2** URL
interpolation (26 URLs) + `scrape-website` links output (~26 credits, approved) —
Zenrows never fired, no selectors to maintain.

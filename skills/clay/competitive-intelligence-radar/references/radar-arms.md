# Radar arms — sweep mechanics, costs, and traps per surface

Mechanics below marked "live-verified" were pinned in the isolated eval workspace
(2026-08-12, sibling-skill research on the same actions); re-verify per workspace —
catalogs, costs, and payload shapes drift on this platform.

## The news arm (backbone — live-verified mechanics)

Catalog action, free-text `query` + relative date bucket (`qdr:h/d/w/m/y`), ~1
credit per query, quiet or not. Find it by display name in the catalog dump
(`clay workflows actions list`); build a small reusable workflow (manual trigger
with `{query, date_filter}`, one tool node) so sweeps don't burn the workspace's
shared ad-hoc daily quota.

Query construction — ENTITY-anchored: `"<competitor name>" <angle vocabulary>`
(pricing terms, launch terms, leadership terms). Two to three angle variants per
competitor beat one broad query. Traps, all live-verified:

- **Quiet shape**: the results field is ABSENT entirely, not an empty list. Gate on
  absence-of-events; the credit bills either way.
- **Crawl-date illusion**: the returned dates are relative strings measuring when
  the index SAW the page, not when the event happened — a years-old roundup
  surfaces inside a one-week bucket stamped "3 days ago." Derive every event date
  from content (in-text date > URL-path date > dateline), and remember derivative
  coverage (a lawsuit story about last year's incident) dates the coverage, not
  the event.
- **Name-boundary**: the competitor name followed by org-suffix tokens
  (Partners/Group/Capital/Holdings) or embedded in a product/vessel designation is
  a DIFFERENT entity. Drop before classification.
- **Cross-outlet duplication**: one real event arrives in 3–5 outlets per sweep.
  Dedupe into event clusters — key (entity, event-class, approximate date), merge
  on event fingerprint (same figures, same timing) even when headlines differ.
  Lead source primacy: the competitor's own announcement > regulator/registry
  filing > trade press.
- **Roundups and listicles**: an event roundup naming your competitor contributes
  its in-window entry (corroborate to the primary link); a profile listicle
  ("top X vendors") is not an event — drop it.

## The hiring-pattern arm (optional; zero-credit reads)

People search (filters-mode) scoped to the competitor's domain reads two tells:
leadership arrivals in a function (a VP-of-X hire is a roadmap tell 2–3 quarters
out) and posting/headcount concentration by function. Traps: title keyword filters
are substring recall — post-validate role identity from the returned title; the
records' domain field echoes the search anchor, not verified current employment —
treat individual rows as signals in aggregate, never name individuals in the
digest (the digest reports "senior security leadership arrivals: 2," not people).
Cost: search-result quota, zero credits.

## The product/pricing-page arm (optional escalation; scheduled diff)

A scrape of the competitor's pricing/product pages only ever sees CURRENT state —
to make it an event source you must re-run on the sweep cadence and diff against
the stored prior copy (keep last sweep's extraction in the digest record; the diff
IS the event). Scrape traps (live-verified on the scrape actions): SUCCESS means
"a vendor served bytes," never "the page exists" — a 404 page can scrape as
SUCCESS content, so corroborate existence-critical reads with a status-honest
HTTP probe (needs a User-Agent header); output-field names must match the live
schema enum exactly — invalid values silently no-op AND bill; body text is
`bodyText`. ~1–2 credits per page per sweep.

## The structured corroboration arms (optional; per-company)

Funding lookups (~6 credits) and job-openings lookups take a DOMAIN as input —
they corroborate a specific claimed event (a raise, a hiring surge) for one
competitor, never discover events. Use for the rare act-on-now item worth a paid
confirmation. Read each action's declared cost from its schema before running;
where a surface exposes no per-run usage metadata, report declared estimates as
estimates.

## Degraded-mode rule (no general web egress)

Sandboxed sessions may be unable to fetch arbitrary article URLs (proxy denies
general egress). Then: corroborate via cross-outlet agreement (≥2 independent
outlets carrying the same event fingerprint), date from the strongest in-snippet
basis, and mark items `single-source — unverified` when neither is available.
Say which mode the sweep ran in; never silently claim primary-source verification
that didn't happen.

## Cost ladder (state before each sweep)

| Arm | Cost | Default? |
|---|---|---|
| News queries | ~1 credit × competitors × variants | yes |
| Hiring-pattern reads | search quota only | on request |
| Page diffs | ~1–2 credits × pages | on request |
| Structured corroboration | ~6 credits per confirmed item | act-on-now only |

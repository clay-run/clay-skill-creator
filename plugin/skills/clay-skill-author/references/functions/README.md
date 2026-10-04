# The observed function surface — index

**Read `platform-surfaces.md` first, then exactly one job leaf.** Not seven. Pick from the left column.

| The job you are building | Leaf |
|---|---|
| *any* — which command answers which question, and the traps in running them | [`platform-surfaces.md`](platform-surfaces.md) |
| a name or a company → a domain; is this domain alive; normalising anything | [`identity-and-domains.md`](identity-and-domains.md) |
| firmographics, headcount, revenue, tech stack, traffic, hierarchy | [`company-enrichment.md`](company-enrichment.md) |
| finding a person, a work email, a phone; resolving someone to a profile | [`contacts.md`](contacts.md) |
| what an action's input parameter actually accepts — the UI label, the table's binding and the schema are three different answers | [`contacts.md`](contacts.md) |
| checking an email address you already hold | [`email-validators.md`](email-validators.md) |
| counting or filtering job postings; hiring as a signal | [`signals-jobs.md`](signals-jobs.md) |
| funding, executive changes, third-party news about accounts | [`signals-funding-news.md`](signals-funding-news.md) |
| who engaged with your own social content | [`engagement-own-posts.md`](engagement-own-posts.md) |
| getting data off a web page | [`scraping.md`](scraping.md) |
| building a list or sizing a population from the company or people index | [`search.md`](search.md) |
| building a list of PEOPLE — which search mode, what the row omits, and what that costs per row | [`search-people.md`](search-people.md) |

**Before you agree to build it:** [`../../NO-FUNCTION-EXISTS.md`](../no-function-exists.md) — the jobs
the platform has no function for. That one is read during the interview, not here.

**Everything that applies to every skill** — the `(packageId, actionKey)` pair, reading the reported cost,
per-unit rates, the four billing outcomes, `outputParameters` as a floor, completion-status-is-not-data,
bands, nulls, `0`/`false`, counting the right unit — is in [`../../DETERMINISM.md`](../determinism.md)
and is deliberately not repeated here.

## What these leaves are, and are not

They are **evidence for traps**, not a price list. Every figure was read off a live response by a build
that spent the credits, and each leaf carries its own date range for that reason. The conclusion the
evidence supports is *anti-pricing*: read the actual charge from `metadata.upfrontCreditUsage`, never a
remembered figure — including a figure remembered from here.

What does not rot is the structural half, and it is why these files exist: field names, response shapes,
which arm can answer which question, which arms disagree with each other and by how much. A price is
stale in a month. "Two providers were 5,809 people apart on the same headcount, same day, both reporting
success" stays true.

# Contacts: finding people, emails and phones

> **Observed 2026-08-07 – 2026-08-14**, extended **2026-10-04** for the input-contract sections at the
> end, one workspace, one plan, by builds that spent the credits — except the 2026-10-04 additions,
> which are schema and catalogue reads and spent nothing. Every figure was read off a live response.
> **Report what you read; never quote a figure here as anyone's price.** Structural facts do not rot
> the way prices do. If the live catalogue disagrees, it wins.

| Need | Reach for | Cost as observed | Trap |
|---|---|---|---|
| find people by name at a company | `clay search filters-mode`, `names` + `company_identifier` — **both arrays** | search quota, **0 credits** | query-mode records carry **no URL**; only filters-mode does |
| find decision-makers by role | `clay search filters-mode`, `job_title_keywords` + company anchor | search quota | `job_title_keywords` is **substring recall** — see below |
| resolve someone to a canonical profile | the managed Enrich Person function | 0 credits + 1 action execution | **cannot find from name + company**, despite its own description |
| work email for a known person | the managed Work Email function | ~1.1 credits declared | not-found takes **minutes**; a hit takes ~12 s |
| mobile phone | a managed contact-details routine | **~9.9 credits/run** — about 9× the email finder | the standalone phone function is catalogued but **not enabled for API and CLI** |
| reverse-lookup a person from an email | the managed Enrich Person email arm | — | **low yield; opportunistic only, never load-bearing** |

## Do not use the managed Find People at Company as a finder

**It silently ignores every name-filter input key** and returns the company's top profiles by seniority
(`total: 10000` on a large company). It "found" a ground-truth CEO only because a CEO ranks first — which
means it would confidently return the **wrong person** for any non-famous name. Two independent live
observations. It costs ~3.3 credits declared; role-scoped filters-mode search returned the right function's
leadership for **zero**, and that measured gap is the whole reason a finding skill exists.

## Search recall is substring, and title indexes have holes

**`job_title_keywords` is substring recall.** A search for `["Chief Financial Officer","CFO"]` returned, as
its single hit, the **Chief of Staff to the CFO**. Keyword containment is not role identity, and a naive
Chief-token seniority rule promotes a staff role to C-level. Post-validate role identity, and carry the
exceptions explicitly — a Chief-of-Staff rule that fires *before* the Chief token, and a
Controller/Treasurer rule, which one build needed because a Corporate Controller otherwise fell to "Other"
and was dropped.

**Widen the vocabulary rather than trusting one exact title.** `["VP Finance","SVP Finance","Head of
Finance","Controller","Chief Financial"]` on the same anchor returned four real records where the exact
title returned one wrong one. **The sitting CFO was absent from the index entirely.** Report the
senior-most identifiable person and say so; never promote the nearest hit.

**Ambiguity has a measurable scale, and one filter can collapse it.** A very common name at a real company
returned 20 distinct profiles with `hasMore: true` — the honest verdict is `ambiguous` with a request for a
disambiguator, and adding one `job_title_keywords` filter collapsed 20+ to exactly 1.

**Search returns zero cleanly.** An implausible function at a real company returned 0 records with
`hasMore: false` and consumed nothing. There is no reason for a skill to invent a person.

## Employment: mismatch means unconfirmed, not departed

A live profile held **two concurrent current roles** — the newest at another company, the listed company
still current, a portfolio-executive pattern. A `latest_experience_company` that differs from your anchor
therefore means *unconfirmed*, and **only the enrichment payload's experience array distinguishes departed
from multi-role.** Route mismatches through resolution, flag `multi-role`, and drop as "employment
unconfirmed" when unresolved. Records carry
`latest_experience_{title,company,start_date}` plus the `matched_experience` that satisfied the filter —
read those, not the `domain` field, which echoes your search anchor.

**Slugs disagree across sources.** A search hit carried an alternate numeric-suffixed slug where the
canonical profile carried another, for the same person. **Ship the enriched URL, never the raw search
hit** — and treat a differing URL as a conflict signal only when both are present on otherwise-matching
records.

**Non-Latin names need one search per script**, native and romanised; providers index inconsistently.

## Enrich Person's real input contract

It requires a profile URL, a profile user id, a Sales Navigator URL, or an email. A run with name and
company inputs **fails per item asking for one of those**, while the undeclared keys pass request
validation silently. Not-found returns in seconds — a single lookup, no waterfall — and comes back
`status: complete` with `result: {}`.

**The email arm is low yield.** 0 of 3 real work emails resolved, including an ordinary employee at a
well-covered company, all `complete` + `{}` in seconds. Where a domain anchor exists, name+domain
filters-mode search is the reliable identification arm; reverse-email is a bonus path.

## Work email

**Timing is asymmetric and it decides your batch design: hits in ~12 s, not-founds in ~4.5 minutes** as the
waterfall exhausts. **A batch finishes at the speed of its misses.** The not-found signal is
`status: complete` with an empty `result: {}` after full exhaustion — no pattern-guessed address, which is
the behaviour you want and should verify rather than assume.

The managed function verifies internally but **does not surface catch-all or risky discrimination**, so
cold-outreach-at-volume needs an explicit validation step — see `email-validators.md`.

**A found address still has to plausibly belong to the person.** A role or functional local-part is not a
person's email; reject those, flag ambiguous handles, and never bless one. Implemented as deterministic
code over 10 candidate forms, this rejected every role address and passed every real name form.

## Phone

**Cost is the headline: ~9.9 credits per run, and at least one arm bills even when no number is found.**
Fourteen arms, each paired with a line-type validator. **Derived from that, not observed:** if every
finder has a validator behind it, the waterfall has to continue past a hit the validator rejects. Marked
because every other claim here was paid for.

Output is a **bare E.164 string with no type or provenance metadata**, so anything typed from another source
must be typed explicitly. Validators grade mobile / landline / **VoIP** plus active-or-disconnected;
direct-dial versus switchboard is a role label on top of that. **Non-US numbers without a country dial code
are labelled invalid.**

**Expected yield, so a miss is not read as a defect:** ~45–65% validated-mobile fill on senior US B2B is a
*good* run, lower down-market and in Europe, far lower in Asia-Pacific.

**Phone is the most expensive column, so it gets a persona gate**: spend only on contacts someone would
actually call. And the three-way timing model matters here too — a hit is seconds, a real-person miss is
minutes, an unresolvable profile URL fast-fails in about 60 s at resolution, *before* the waterfall runs,
which is a different not-found shape (`complete` at the run level wrapping an item-level `failed`).

## The parameter name tells you nothing about the accepted type

**Read 2026-10-04 from action schemas; no run, no credit.**

Three separate layers name the same input differently, and only one of them is binding:

| Where you read it | What it says | Binding? |
|---|---|---|
| the table UI's column label | *"Professional URL"* | no |
| the action's `inputsBinding` in table config | `person_identifier` | the name only |
| the action's **schema** | `semanticType: person-linkedin-url` | **yes** |

So a parameter whose name reads like a generic identifier may accept **only a URL**. A shipped skill
fed that parameter a personal email address and validated clean; the call returns `validation_error`
per item, and the step looks configured. **Confirm every input against
`clay workflows actions schema <packageId> <actionKey>` before wiring it** — `semanticType` is a
structured enum and it is the only one of the three layers that answers the question.

**And a table binds a shotgun, not a contract.** Clay's UI writes the same source column to every
plausible parameter name so that whichever one the provider reads picks it up — observed on one real
action column: `email`, `workEmail`, `inputFields|emailAddress`, `data`, `work_email`, `work-email`,
`search_input`, `personal_email` and more, all fed the same cell. Ten-plus candidates per action, most
of them wrong for the action they are bound to. A name lifted from a table is a candidate; the schema
says which one is real.

## A work-email input cannot be the first step of a work-email skill

**Read 2026-10-04 from action schemas; no run, no credit.**

Several managed person-enrichment arms declare their one required input as a **work email**
(`semanticType: work-email`, `required: true`) rather than any email. That makes them unusable for
resolving identity in a play whose *output* is the work email — the input is the thing you do not have
yet. Checked on the arms a personal-email play would naturally reach for: two of three wanted a work
address, and only one accepted a personal one (its schema says so in prose: *"the work or personal
email address of the person"*).

This compounds with the low-yield line in the index above. A skill that starts from a personal email
should establish, from schemas rather than from the arm's name, that **some** available arm accepts a
personal address at all — and when none does, say so and ask for a name or a profile URL instead of
shipping a waterfall that cannot run.

---
name: find-linkedin-profile
description: |
  Find a person's LinkedIn profile URL with Clay — from their name and company, or from an
  email — and validate it before reporting. Use whenever someone asks: find this person's
  LinkedIn, get the LinkedIn URL for a contact, what's X's LinkedIn profile at company Y,
  check whether this LinkedIn URL is still the right person, or fix a stale LinkedIn link.
  It searches Clay's people index by name + company, validates every candidate URL against
  known facts (name and current employer must match), flags name collisions instead of
  guessing, and recovers from stale slugs and wrong-person rejects to the canonical
  profile. Do NOT use it to source net-new prospects by persona or title (people-search /
  list-building skills), to find email addresses (find-work-email), or to pull full person
  data for downstream enrichment (enrich skills). It never reports an unvalidated URL and
  never fabricates one.
category: find-contact-data
personas: [sales-development, recruiter]
mechanism: functions
touches: read-only
keywords: []
---

# Find a LinkedIn profile

The insight: **a returned URL is a candidate, not an answer — and a rejected candidate is
not a dead end.** Finders hand back plausible URLs for the wrong person without erroring;
slugs go stale and vary; a reject usually means a same-name collision, not a miss. The
ladder: find → validate → recover — a wrong profile is worse than none.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **What they have per row** | a profile URL, an email, or a name plus company | no default — the route depends on it, and each route has a different failure mode |
| **The expected employer** | for personal-email rows, who they think the person works for | ask. A personal email carries no company anchor, so without this the match is unverifiable |
| **Budget** | credits, on the rows that need enrichment | rows that already carry a URL cost nothing; state the count that does |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — what each row already carries and the expected employer you supply.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, or returns a profile it could not tie to the employer you named.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run the Clay
plugin's `setup` skill and re-run this skill. Tell the user which workspace you're in.

## Step 1 — Triage the input

- **Have a URL** (validate/refresh ask) → Step 3.
- **Have an email** → Step 3 (enrichment accepts it). Personal emails carry no company
  anchor — ask for the expected employer.
- **Name + company** → resolve the company to a domain first, then Step 2. A wrong domain
  silently finds the wrong people.

## Step 2 — Find: search the people index

```
clay search filters-mode create --source-type people \
  --filters '{"names":["<full name>"],"company_identifier":["<domain>"]}'
clay search filters-mode run <searchId>
```

`company_identifier` must be an array. Records return `url`, name, current title, and role
start date; this spends search-result quota, not credits. **Gate on match count:**

- **0** → retry spelling variants; search non-Latin names once per script (native,
  romanized — providers index either). If they may have left, add
  `"include_past_experiences": true`. Still 0 → report honestly.
- **1** → a candidate — not yet an identity. Step 3.
- **>1** → collision, the dominant failure mode. NEVER take the top result — ranking is
  seniority, not identity. Narrow with `job_title_keywords` or location if given;
  otherwise show the name/title list and ask (`hasMore: true` = still more).

## Step 3 — Validate: three signals

Enrich the candidate with the managed **Enrich Person** function (`clay routines list` /
`get` to confirm — the list paginates). It accepts `Professional Profile URL` or `Email`
only — NOT name+company, despite its description. Envelope:
`{"items":[{"id":"<key>","inputs":{"Professional Profile URL":"<candidate>"}}]}` via
`clay routines runs start`. Score three signals:

1. **Name** — first name must match (hard-fail); tolerate nicknames (Robert/Bob) and
   middle names. A last-name mismatch passes only with employer + location corroboration
   (married names); a bare last initial may hide in the slug (e.g. `/in/priya-r` for a surname starting with R).
2. **Employer** — current company/domain matches the expected employer
   (parent/subsidiary/sister brands count). A missing anchor (personal-email input) is
   neutral, not a failure.
3. **Real profile** — the payload carries an experience history with dates, not a thin
   shell.

All three → **validated**: report the payload's `url` — the canonical slug, never the raw
search hit (sources disagree on slugs for one person). Two → **low confidence**; name the
failed signal. Name fails or fewer → **rejected** → Step 4. Empty `result: {}` with
`status: complete` = **not found** — completion is not data (not-founds return in seconds
here — no waterfall; a slow run signals trouble, not a miss). Name matches,
employer doesn't → **moved**: right person, new company — report URL + current employer +
flag. A stored URL that re-enriches empty = "could not re-verify" — recover; never
overwrite the stored value with nothing.

## Step 4 — Recover

A dead slug or a rejected candidate → re-run Step 2 with a disambiguator (title,
location). The recovered URL MUST differ from the rejected one and MUST pass Step 3
itself. No decisively better candidate → not found / ambiguous — empty beats wrong.

## What good looks like

The deliverable: the canonical enriched URL plus confidence and 1–3 short reasons quoting
the validating facts. Ambiguity is surfaced, never resolved by rank. The common mistake:
trusting one confident-looking hit — a single match can still be a same-named stranger.

## Rules

- MUST validate every candidate — including recovered ones — before reporting.
- MUST stop and disambiguate when more than one profile matches; NEVER pick by rank.
- NEVER construct a slug as a fallback; NEVER ship a URL that passed on one signal.
- MUST state cost and get approval before multi-person runs.

## Representative output

Three parts. **Every name, company and profile path below is invented** (`.example`
reserved TLD). Each person lands in exactly one of five statuses, and two of those five
return no profile at all.

### Per person

| name | company | profile | status | reasons |
|---|---|---|---|---|
| D. Whitfield | brightloop.example | /in/danawhitfield | validated | one search hit · title and employer match the enriched record · name exact |
| M. Torres | northfield.example | /in/m-torres-2 | low confidence | name and employer match, but the enriched record carries no title to corroborate them |
| A. Rivera | meridianbank.example | — | ambiguous — 6 candidates | a common name at a large employer · the six carry different titles · one more constraint would settle it |
| D. Okonkwo | kirivale.co.uk | /in/d-okonkwo | moved — now at fabrikam.example | the enriched record's current role names a different employer than the one asked about |
| J. Lindgren | halloway-industrial.example | — | not found | the search returned an empty result set cleanly, and an enrichment attempt came back as a completed run with an empty payload |

**The URL that ships is always the enriched one, never the raw search hit.** On a live run
the search returned a numeric-suffixed slug and the enrichment resolved the same person to a
different canonical slug. Both open in a browser; only one is stable, so a row built from
the search hit quietly diverges from the row the next run produces for the same person.

**Ambiguity has a size, and usually a cheap fix.** A common name at a large employer returned
20 distinct profiles with more available; adding a single job-title filter collapsed that to
exactly one. So `ambiguous — 6 candidates` is a request for one more constraint rather than a
dead end — and it is never resolved by taking the first result. A search that returns 20
people has produced a question, not an answer.

Neither empty shape is an error. An empty result set and a completed-but-empty enrichment
are both ordinary outcomes, and neither is a licence to offer a near-match.

### Summary

```
5 people asked for

  validated         1
  low confidence    1
  ambiguous         1
  moved             1
  not found         1
                   --
                    5 of 5

Spend: 0 credits. The search arm consumes search quota rather than credits, and
the enrichment arm billed no base credits on this surface — read the actual
charge from run usage metadata rather than trusting that figure.
```

### What has not been exercised

The statuses above are the full contract, and the evidence behind them is uneven. The
ground-truth, collision and not-found shapes are all live-verified. **The newer validation
logic is not**: the three-signal rubric, the name-match scoring, the non-Latin-script
handling — which needs one search per script, native and romanised, because providers index
them inconsistently — and the recover-on-reject stage were added as a desk revision and have
never been run. Treat those four as unverified prose until someone exercises them.

## Worked example

Ask: "Find the LinkedIn for Dana Whitfield at brightloop.example." One hit,
`/in/dana-whitfield-8a41b2` · "VP Operations". Enrich → canonical `/in/danawhitfield`, org
Brightloop, full history → validated ("VP Operations at Brightloop; name exact").
Counter-example: "Alex Rivera at meridianbank.example" → 6 profiles, different titles →
`ambiguous — 6 candidates` with the title list — never the first one.

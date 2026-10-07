---
name: find-work-phone
description: |
  Find a person's work phone number — ideally a validated mobile — using Clay, from their
  a social URL or name and company. Use whenever someone asks: find someone's phone number,
  get a mobile number for this contact, find a cell or direct-dial number for a person at a
  company, or turn a short list of prospects into callable numbers. It runs Clay's
  phone-finding waterfall (multiple providers, each candidate checked for line type and
  status before it counts as found) and reports every number with its type — mobile,
  direct-dial, or HQ line — plus a compliance caution before any dialing or texting.
  Do NOT use it to find email addresses (use find-work-email), to identify who owns a phone
  number you already have (reverse lookup), or to source net-new prospects by persona
  (people search). It never fabricates or pattern-guesses numbers, and it never dials,
  texts, or writes numbers anywhere without explicit approval.
category: find-contact-data
personas: [sales-development]
mechanism: functions
touches: read-only
keywords: [waterfall, find-phone-number]
---

# Find a work phone number

The insight: **phone is the most expensive and most regulated field in contact data — found
is not the same as dialable.** A mobile lookup costs ~5–10x an email lookup, and even a
good waterfall validates a mobile for only about half of senior US contacts, less
elsewhere — misses are normal. An HQ
switchboard is not a direct line, and an unconsented call or text to a mobile carries legal
risk (DNC registries, US TCPA, GDPR) that a cold email doesn't. So the find includes
line-type validation, honest typing, and a compliance flag — never just "here's a number."

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **A profile URL per contact** | the professional profile, not just a name | **this is a hard requirement, not a preference** — the phone surface is keyed on the profile. A name-only row resolves the URL first and confirms it is the right person |
| **A known email** | if they have one | optional; raises the hit rate where accepted |
| **The gate** | which contacts they would actually call | ask before a batch. Phone credits are worth spending only on the right persona at a qualified company |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — the profile URL or known email on each contact, and the phone providers it queries.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, or dials anything.
- **Halts** — Step 2 spend-approval.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run the Clay
plugin's `setup` skill (or follow
https://raw.githubusercontent.com/clay-run/agent-plugins/main/GETTING_STARTED.md), restart
the agent if setup says to, and re-run this skill. Tell the user which workspace you're in.

## Step 1 — Collect what identifies the person

Phone waterfalls are keyed on the professional profile, not the name: the managed phone
functions **require a LinkedIn URL** (email waterfalls don't).

1. **LinkedIn URL** (plus name/company) — run directly.
2. **Name + company only** — resolve the URL first (find-social-profile, or managed
   Enrich Person) and confirm it's the right person; a wrong profile poisons the lookup.

A known email raises the hit rate — pass it through if accepted. On a batch, gate first:
phone credits only on contacts the user would actually call (right persona, qualified
company).

## Step 2 — Run the managed function

Find the workspace's managed phone function (names vary — "Mobile Phone Number", or a
combined function returning email + phone) and confirm it's runnable: `clay routines list`
paginates and omits functions; `clay functions list` shows the catalog, but a listed
function can still be **not enabled for API & CLI** (`clay routines get` → not_found);
fall back to a table/workflow, or admin registration (`clay routines create`).

**Check `estimatedCreditCost` before running — always.** At ~10 credits per lookup, state
the total and get explicit approval. CLI envelope:
`{"items":[{"id":"<key>","inputs":{...}}]}` via `--input -`. Timing: hits return in
seconds; a real-person miss takes minutes (every provider tries, some bill anyway); an
unresolvable LinkedIn URL fails fast, before the waterfall starts. A batch finishes at the
speed and cost of its misses; hits resolve early, under the flat estimate.
Large or multi-region batches belong in a Clay table's native phone waterfall (provenance,
regional tuning), not a CLI loop.

## What good looks like

- **Every number ships with its type.** Validators grade line type — mobile, landline,
  VoIP — plus active/disconnected status; direct-dial vs HQ is a role label on top. The
  managed waterfall validates each arm's candidate and keeps going past a rejected hit
  (find-until-valid; the common mistake is trusting one provider's answer), but returns a
  bare E.164 string: mobile by construction, no type or provenance. Type any other source
  explicitly with a catalog line-type validator (fractions of a credit; non-US numbers
  need a country dial code or they come back falsely invalid).
- **Not-found stays empty — completion is not data, at two levels.** A run can report
  `status: complete` while the item inside failed (unresolvable profile URL), or the item
  completes empty (waterfall miss). Both are not-founds: gate on an actual number, never
  on run status.
- **Numbers are PII with dialing rules attached.** Report, don't act: flag DNC/TCPA/local
  consent before any call or SMS use. Before a real call block, offer a second independent
  validation (~0.2 credits/number: line status, activity score, litigator screen);
  validator disagreement goes to a human, not the dialer.

## Rules

- MUST check the function's credit cost and get approval before any run; re-check credits.
- MUST resolve and confirm the LinkedIn URL first when given only name + company.
- MUST pre-gate batches on persona/qualification — spend only on callable contacts.
- NEVER fabricate, pattern-guess, or pad a phone number (a switchboard is only ever `HQ`).
- NEVER report a number without its type, or an unvalidated number as "valid."
- NEVER dial, text, or export numbers anywhere without explicit user approval.

## Representative output

Three parts, and the third one is not optional. **Every name, company and number below is
invented** — the numbers use the `555-01xx` range reserved for fiction, and a real run
returns real numbers that should be handled accordingly.

### Per person

| name | company | phone | type | status | identified by |
|---|---|---|---|---|---|
| P. Raman | brightloop.example | +1-555-010-4821 | mobile | valid | profile URL |
| D. Okonkwo | northfield.example | +1-555-010-2277 | direct-dial | valid | profile URL |
| R. Calloway | meridianops.example | +1-555-010-7734 | mobile | valid, **flagged VoIP** | profile URL — an active VoIP line is not necessarily a person's handset |
| M. Torres | kirivale.co.uk | +44-20-7946-0315 | landline | valid | profile URL. The country code travels with the number: a non-US number arriving without one is graded invalid |
| J. Lindgren | fabrikam.example | — | — | not found | the profile URL would not resolve. Fast-failed in about 60 seconds, **before** the waterfall ran — and note the run itself still reports as complete, with the failure one level down |
| A. Rivera | halloway-industrial.example | — | — | not found | a real person the waterfall could not reach. All arms exhausted, which takes minutes — **and this row still cost credits** |

The main switchboard is never substituted for a person's number. If you ask for it, it
arrives labelled `HQ` and not as a direct line.

### Summary

```
6 contacts attempted, every one pre-gated — phone is the most expensive column
here, so only people someone would actually call were submitted at all.

  valid, mobile          2     one flagged VoIP
  valid, direct-dial     1
  valid, landline        1
  not found              2     one fast-fail at resolution,
                               one full waterfall exhaustion
                        --
                         6 of 6

Validated-mobile fill: 2 of 6. On senior US B2B, roughly 45–65% is a GOOD run;
lower down-market and in Europe, considerably lower in Asia-Pacific. A miss
rate in this region is the normal shape of the work, not a malfunction.

Spend: ~9.9 credits per run — about nine times the work-email finder. The
not-found rows are NOT free: at least one arm bills even when it finds nothing,
so budget on attempts rather than on hits.

Three timing shapes, which decide how you batch: a hit returns in about 8
seconds, an unresolvable profile fast-fails in about 60 seconds before the
waterfall starts, and a real-but-unlisted person takes minutes as all arms
exhaust.
```

### Before you dial any of it

The returned value is a **bare string with no type or provenance attached**, so every
line-type and status label beside it came from a separate validator and is attributed to that
validator rather than assumed from the number itself.

Before anything high-stakes — a call block, a dialler import — run the second independent
validation at about 0.2 credits and route any disagreement between the two validators to a
person.

A validated mobile is not permission to dial it. Calling rules vary by jurisdiction and by
line type, and that remains the caller's responsibility.

## Worked example

Ask: "Get me a mobile number for Priya Raman at brightloop.example."
URL on file → state ~10-credit cost, get approval → waterfall hits early →
`+1-XXX-XXX-4821 · mobile · valid`; offer the 0.2-credit status + litigator screen before
the call block.
Counter-example: an unresolvable profile URL fails fast (run still says complete) →
report `not found`; don't substitute the main line unless asked, then only labeled `HQ`.

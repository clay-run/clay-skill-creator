---
name: clean-email-list
description: |
  Clean a CSV or table of email addresses into keep / risky / remove segments with
  per-row evidence — free deterministic passes first (dedupe, syntax, role and
  disposable screens, domain MX check), then a paid mailbox validator only on rows
  that survive. Use whenever someone says: clean this email list, scrub my list
  before a send, remove invalid or duplicate emails from this CSV, how many of
  these addresses are still good, or prep this list for cold outreach. Every
  removed row ships with its reason — nothing is silently deleted, and rows that
  can't be verified are flagged, never guessed. Do NOT use it to check one or two
  addresses (verify-email-deliverability), to find or replace missing emails
  (find-work-email), or to merge duplicate CRM contact *records* (dedupe-contacts).
  It states total cost before spending any credits.
category: verify-and-clean
personas: [revops, marketing]
mechanism: functions
touches: read-only
keywords: [catch-all-domains]
---

# Clean an email list

The insight: **a list's value is set by its worst segment.** Bounce rate is measured
over the whole send — a few percent of dead rows can gate the other 95% out of inboxes.
So cleaning is triage, not filtering: every input row lands in exactly one of
keep / risky / remove / could-not-verify, with quoted evidence, and rows are never
silently deleted — a row you can't account for is a row you can't defend. The other
half is ordering: every free deterministic pass runs before the first paid call, so the
validator only ever sees rows that could still be sendable.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The list** | a CSV or table, and which column holds the email | no default, and no other column is ever edited |
| **The purpose** | cold volume send, CRM refresh, or re-engagement | ask — it decides the policy: for cold sends role mailboxes are removed and freemail is risky; for the others both are only risky |
| **Budget** | credits for paid validation after the free passes | free passes run regardless; state the cost of what survives them before spending |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — the address list you supply, and the validators it runs against it.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, sends to any address, or deletes a row from your list.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run the
Clay plugin's `setup` skill (or follow
https://raw.githubusercontent.com/clay-run/agent-plugins/main/GETTING_STARTED.md),
restart if told to, and re-run. Tell the user which workspace you're in.

## Step 1 — Collect the inputs

1. **The list** (CSV/table) and which column holds the email. Never edit other columns.
2. **The purpose** — cold volume send vs CRM refresh vs re-engagement. It decides the
   policy segments: for cold sends, role/generic mailboxes (`info@`, `support@`…) go to
   remove and personal/freemail goes to risky; for other purposes both go to risky.

## Step 2 — Free passes (zero credits, deterministic code — not an LLM)

Run in order, recording per-row reason + evidence at each:

1. **Normalize + dedupe.** Trim, lowercase for comparison (keep the original string).
   Exact-match duplicates: keep the first, mark the rest `remove: duplicate` with a
   pointer to the kept row.
2. **Syntax.** One local-part `@` one domain with a dot, no spaces — a cheap structural
   check, not full RFC. Failures → `remove: syntax-invalid`, quoting the string. Never
   "fix" a typo and keep the fixed version silently.
3. **Role/generic screen.** Local-part blocklist (production lists run ~40 tokens):
   admin, info, contact, support, sales, billing, hr, press, help, hello, office, team,
   marketing, careers, jobs, noreply, no-reply, postmaster, abuse, webmaster… Segment
   per the Step 1 policy — these are policy calls, not deliverability verdicts (a
   `support@` box may be genuinely read).
4. **Disposable domains.** Known disposable providers (mailinator, guerrillamail,
   yopmail…) → `remove: disposable`.
5. **MX per unique domain** (any DNS tool — don't hardcode a DoH URL; some networks
   block them). Three shapes: NXDOMAIN or no MX → dead; **null MX** (single record
   `0 .`) → the domain declares it takes no mail — dead *even though a record exists*;
   real MX → survives. Dead domains → `remove: dead-domain` for every row on them,
   quoting the DNS answer. This kills paid calls on dead rows for free.

## Step 3 — Classify survivors (Clay-native, ~free)

Run `extract-email-components` (Clay action; catalog tier 1) per surviving row: it
returns `domain` plus `isLikelyPersonalEmail` / `isLikelyCompanyEmail` /
`isLikelyEducationEmail`. Personal → risky under a cold-send policy. Read the actual
charge from run usage metadata (verified at 0 credits + 0 action executions in one
workspace — but read it, don't assume).

## Step 4 — Paid validation on what's left (approval gate)

Pick a validator from the live catalog (`clay workflows actions list`), lowest
`priorityTier` that separates catch-all from valid (tier 2 is typically ZeroBounce
`validate-email` or `enrichley-verify-email`, ~0.1 credits/check). **State survivor
count × per-check cost and get approval before running.** Then call it per row (Clay
MCP `execute_clay_action`); checks return in seconds for every verdict. Map field
PAIRS, never one field — vocabularies invert across validators: ZeroBounce puts
catch-all at `status: valid` + `sub_status: catch_all`; Enrichley puts it at
`valid: false` + `result: catch_all`. Verdicts: plain valid (`sub_status: ""` — empty
string) → **keep**; catch-all → **risky** (Enrichley's `catch_all_validated` upgrade =
keep, probe-confirmed); `do_not_mail` / suppression / disposable sub-statuses →
**remove**, quoting the sub-reason; `invalid` → **remove**; `unknown`, timeouts, empty
payloads → **could-not-verify** — never rounded either way. Fuse validator with
classifier: a freemail address can validate as deliverable (observed live: `valid` /
`sub_status: alternate` + `free_email: true` on a Gmail address) — a mailbox verdict
never overrides the policy segment. Run status is not data: it reports SUCCESS for
every verdict. For many hundreds of rows or a recurring clean,
build it as a Clay table/workflow instead and say so.

## What good looks like

- **Reconciliation is the first check**: rows in = keep + risky + remove +
  could-not-verify. If the numbers don't add up, a row was dropped silently — the
  cardinal failure of list cleaning.
- Every removed row carries a reason AND quoted evidence (the DNS answer, the validator
  field pair, the duplicate pointer) — an audit trail, not a verdict.
- The common mistake: reading one validator field as a boolean. Catch-all hides inside
  the safest-looking field, in opposite directions per provider.
- Could-not-verify is an honest segment, not a failure — a common shape is `unknown` /
  `mail_server_temporary_error`, which is retryable later; the user decides whether to
  spend more checks.

## Rules

- MUST account for every input row in exactly one segment — never silently drop.
- MUST run all free passes before any paid call, and state cost + get approval first.
- MUST report raw provider fields alongside each verdict.
- NEVER guess a verdict for an unverifiable row; NEVER silently correct a malformed
  address; NEVER report catch-all, role, or disposable rows as plain valid.

## Representative output

Three artifacts come back. The rows below are the shape of a real cold-send clean, at the
scale this skill was validated on — an 11-row list. **Every address and domain is
invented** (`.example` reserved TLD, RFC-2606 names); `freemail.example` stands in for a
consumer mail provider. The only four segments are **keep / risky / remove /
could-not-verify**, and every input row lands in exactly one.

### Audit CSV — every input row

| email | normalized | segment | reason | evidence | duplicate_of | provider |
|---|---|---|---|---|---|---|
| dana.whitfield@example.com | dana.whitfield@example.com | keep | mailbox valid | `status: valid` + `sub_status: ""` (empty string) | — | validator |
| r.calloway@example.net | r.calloway@example.net | risky | catch-all domain accepts anything | `status: valid` + `sub_status: catch_all` | — | validator |
| j.okafor@freemail.example | j.okafor@freemail.example | risky | personal mailbox, risky under a cold-send policy | classifier `isLikelyPersonalEmail: true`; validator `status: valid` + `sub_status: alternate`, `free_email: true` | — | classifier + validator |
| Dana.Whitfield@Example.com | dana.whitfield@example.com | remove | duplicate, case variant | identical to row 1 after lowercasing | row 1 | free pass |
| dana.whitfield@example.com | dana.whitfield@example.com | remove | duplicate, exact | second occurrence of row 1 | row 1 | free pass |
| t.ibrahim@@example.org | — | remove | syntax-invalid | two `@` in `t.ibrahim@@example.org`; string kept exactly as supplied, not corrected | — | free pass |
| s.novak@nowhere.example | s.novak@nowhere.example | remove | dead domain | DNS answer: NXDOMAIN | — | free pass (DNS) |
| m.haruki@nullmx.example | m.haruki@nullmx.example | remove | dead domain | single MX record `0 .` — the domain declares it takes no mail (RFC 7505) | — | free pass (DNS) |
| burner@disposable.example | burner@disposable.example | remove | disposable provider | domain on blocklist; agreement probe returned `status: do_not_mail` + `sub_status: global_suppression` | — | free pass + validator |
| info@example.com | info@example.com | remove | role mailbox, removed under a cold-send policy | local part `info` on the blocklist — no paid call spent on this row | — | free pass |
| p.lindgren@slowmail.example | p.lindgren@slowmail.example | could-not-verify | validator could not reach the mailbox | `status: unknown` + `sub_status: mail_server_temporary_error` — retryable later | — | validator |

Note the two rows a single-field read would get wrong: the catch-all is sitting under
`status: valid`, and the freemail address is genuinely deliverable (`valid`) while still
being risky for a cold send. The mailbox verdict never overrides the policy segment.

### keep.csv — the sendable list

Original strings, original columns untouched.

| email | first_name | last_name | company | source_row |
|---|---|---|---|---|
| dana.whitfield@example.com | Dana | Whitfield | Northwind Systems | 1 |

### Summary

```
Rows in: 11 → unique addresses: 9 (2 duplicates removed)

  keep               1   9.1%
  risky              2  18.2%   (1 catch-all, 1 personal/freemail)
  remove             7  63.6%   (2 duplicate, 1 syntax, 2 dead domain,
                                 1 disposable, 1 role)
  could-not-verify   1   9.1%
                    --  -----
                    11  100.0%     11 in = 1 + 2 + 7 + 1  ✓

Spend, read from run usage metadata: 0 credits + 5 action executions.
  4 classifier calls on the free passes' survivors — 0 credits, 0 executions
  5 tier-2 validator calls — 0 credits, 1 action execution each
Free passes removed 5 of 11 rows before the first paid call.

Recommendation for a cold send: send to keep.csv. The catch-all is worth one
escalation probe if the list matters; the personal address needs a human call on
whether consumer mailboxes belong in this campaign. Retry the could-not-verify row
later — a temporary mail-server error is not a verdict.
```

## Worked example

Ask: "Clean this 500-row conference list for a cold send." Free passes: 62 duplicates,
8 syntax-invalid, 41 role, 5 disposable, 37 on dead domains (3 of them null-MX) — 347
survive, zero credits. Classify: 29 personal → risky. Validation quote: 347 × ~0.1cr ≈
35 credits — approved. Result: 214 keep, 71 risky (29 personal + 42 catch-all), 203
remove, 12 could-not-verify. 500 = 214 + 71 + 203 + 12 ✓. Recommendation: send to
keep; Enrichley-escalate the 42 catch-alls (~4 credits) if the list matters.

---
name: convert-personal-email-to-work-email
description: |
  Turn a personal email (gmail, outlook, etc.) into a validated work email using Clay, in two
  stages — first resolve the person's professional identity from the personal address (their
  profile, name, and current company domain), then run a work-email waterfall across several
  providers, validating each result and stopping at the first that passes. Works on one address or
  a list. Use whenever someone asks: find the work email behind this personal email, convert gmail
  addresses to business emails, get the company email for these signups, or turn a list of personal
  emails into reachable work contacts. It reads public identity and contact data and hands back a
  table — it never writes to a CRM and never emails anyone. Do NOT use it to find personal emails
  (this goes the other way), to enrich people you already have a work email or LinkedIn URL for
  (start there instead), to find phone numbers, or to validate a single address you already have.
  It states cost before spending and emits only validated emails.
category: find-contact-data
personas: [gtm-engineer, sales-development]
mechanism: functions
touches: read-only
keywords: []
---

# Convert a personal email to a work email

The insight: **you cannot go straight from a personal email to a work email — you have to find the
person in between.** A gmail address carries no company, so the only path is: resolve the personal
address to a professional identity (profile, name, current company domain), and only then hunt the
work email with that name and domain. Each of those two steps is a waterfall because any single
provider misses a meaningful share — but firing every provider at every person pays many times for
the one answer the first already gave. So both stages run **sequentially and stop at the first good
result**, and no work email is emitted until it passes validation: a plausible address that bounces
is worse than an honest blank, because someone sends to it.

**Ported from a deprecated Clay template.** The original used action keys Clay has since renamed
(the MixRank→CPJ migration) and two providers it has retired (RocketReach, Nymblr — no same-provider
successor). This skill is pinned to the **current** actions; the retired providers are simply
dropped, since six work-email providers remain. Full key mapping in `references/action-mechanics.md`.

## What this skill touches

- **Reads** — the personal email(s) you supply, and the public identity and contact data the Clay
  enrichment and email-finder actions return.
- **Writes** — nothing. The deliverable is a table of resolved work emails handed back to you.
- **Never** — writes to a table, workflow, or CRM; emails or contacts anyone; emits an unvalidated
  email; or stores your inputs anywhere outside this conversation.
- **Halts** — Step 3 spend-approval

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it,
never substitute a plausible default, and where an answer does not exist say which step becomes
unavailable rather than guessing.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The personal email(s)** | one personal email address, or a list (paste, CSV, or export) | no default. Required; without it there is nothing to resolve |
| **Identity-stage providers** *(optional)* | which resolvers to use and in what order | default: CPJ → Clearbit → Snov (then stop at first that returns a profile + company domain). Some bill through the installer's connected account — skip and say so if one isn't connected |
| **Work-email providers** *(optional)* | which finders to use and in what order | default: Findymail → LeadMagic → Prospeo → Dropcontact → Hunter → Datagma, then stop at first validated |
| **Validation strictness** *(optional)* | accept only "safe/deliverable", or also "risky/catch-all" | default: safe only (`onlySafe = true`). Loosening it means saying so in the output |
| **Cost ceiling** | a maximum credit spend, or a maximum number of addresses | dedupe first, state worst-case and typical cost below, and wait for approval |

**If an answer sheet is present beside this skill, load it and ask only for what it does not
cover.** A partial sheet is normal; a missing value is asked for on its own. **Say which values came
from the sheet** before using them. **If there is no sheet, say nothing about sheets.** At delivery,
offer to save the answers back — provider order and strictness only; never a token or password,
private and never published — phrased so it explains itself.

## Step 0 — Verify Clay is working, then state posture

Run `clay whoami; echo "exit_code=$?"`. If it fails or `clay` is missing, name the one command that
fixes it (the Clay plugin's `setup` skill, restart if told) and stop — a broken environment is the
installer's to repair. On success, name the workspace out loud. Then state, in two sentences: this
skill **reads** identity and contact data and **writes nothing** — the output is a table you keep,
and no email it finds is ever sent.

## Step 1 — Scope (interview; do not guess)

1. **The personal email(s).** One or a list. **Dedupe to unique addresses before any spend.**
2. **Provider order + strictness** — confirm or take the defaults. Note which providers need a
   connected account in this workspace.
3. **Cost + cap.** State the worst case (both waterfalls run through every provider for an address
   that never resolves) and the typical case (resolves early in each stage). Name the cap; approve.

## Step 2 — Two sequential waterfalls (the CLI envelope and keys are in the reference)

Read `references/action-mechanics.md` before running. For each unique personal email:

**Stage A — resolve the professional identity (stop at first that returns a profile + company
domain).** Run the identity providers in order; each maps the personal email to a profile, a name,
and a current company domain. **Gate on payload** — a provider that completes without a company
domain has not resolved the identity; fall through to the next. No identity resolved → the address
ends as `identity_not_found`; the work-email stage cannot run without a name and domain.

**Stage B — find the work email (stop at first validated).** With the resolved name + company
domain, run the work-email providers in order, validating each result, and **stop at the first email
that passes validation** (verdict `.result.status`). A finder that returns nothing, or whose email
fails validation, falls through. Record which provider produced the accepted email (`email source`).
No validated email from any provider → an honest **`work_email_not_found`**, never an unvalidated
guess.

**Neither stage runs every provider once one succeeds.** That is the whole cost argument for a
sequential waterfall: most addresses resolve early in each stage.

## Step 3 — One gate, then spend

**Exactly one approval gate, carrying the whole bill.** Everything free (dedupe) has already run. In
a single message: unique-address count, the per-provider prices read in Step 1, worst-case and
typical totals, the cap, and the fact that **nothing is written and no email is sent**. Then stop
and wait. For a list, run the first ~10 unique addresses as a small batch, show real output and real
cost, and continue only on the installer's say-so. After the batch, **re-read the credit balance and
report actual spend** (from each call's `metadata`), reconciled against the estimate.

## Step 4 — Deliver

One row per unique personal email, joined back to every input row that shared it. Each row carries:
personal email, resolved name, company, company domain, **validated work email**, **email source**
(which provider), **identity source** (which resolver), and a status (`resolved` /
`identity_not_found` / `work_email_not_found`). Report missing values as `unknown`, never a blank
that reads as a value. Summary: addresses in, unique, identity-resolved %, work-emails found %,
provider hit-distribution, credits measured vs. declared.

## Representative output

### Per-address result

| Personal email | Name | Company | Company domain | Validated work email | Email source | Identity source |
|---|---|---|---|---|---|---|
| dana.o@gmail.com | Dana Okafor | Northwind | northwind.com | dana.okafor@northwind.com | Findymail (safe) | CPJ |
| sam.r@outlook.com | Sam Reyes | Contoso | contoso.io | work_email_not_found | — (6 providers, none validated) | Clearbit |
| lee.p@gmail.com | — | — | — | identity_not_found | — | — (no resolver returned a company) |

*Identity source names the resolver that produced the profile + domain; email source names the
finder (and validation verdict) behind the accepted address. A row at "not found" has been through
the whole waterfall — an honest miss, not a skipped step.*

## What good looks like

- **Spend tracks the waterfalls, not the provider count** — most addresses resolve early in each
  stage; cost equal to addresses × all providers means the stop-at-first rules weren't applied.
- **Identity is resolved before the email hunt** — a work-email stage run without a company domain
  is searching on nothing; `identity_not_found` is a real, distinct outcome.
- **Every emitted email passed validation** — the whole point; an unvalidated address in the output
  is the cardinal failure.
- **Both sources are populated** — identity source and email source make each result traceable and
  the provider order tunable.
- The common mistake: treating a resolver's "success" as an identity, or a finder's raw return as a
  work email. A resolved identity needs a company domain; an emitted email needs a passing validation.

## Rules

- MUST dedupe to unique addresses and get cost approval at the single Step 3 gate before any spend.
- MUST resolve identity (profile + company domain) before the work-email stage; no domain → no
  work-email stage, recorded as `identity_not_found`.
- MUST run both waterfalls sequentially and STOP at the first success (identity: first with a
  domain; email: first validated) — never run later providers once one succeeds.
- MUST validate every candidate email and NEVER emit an unvalidated email.
- NEVER write to any table, workflow, or CRM, and NEVER send or draft an email — delivery is a
  table/CSV; any outreach is the installer's own move.
- Personal-email finding (the reverse), phone numbers, and enriching already-known contacts are out
  of scope — say so rather than swelling the skill.

## Worked example

Ask: "Convert these 50 personal emails to work emails." → 50 rows dedupe to 48 unique. Stage A
resolves 41 identities (CPJ gets 33, Clearbit 6, Snov 2; 7 return no company domain →
`identity_not_found`). Cost stated at the single gate: 48 identity attempts + up to 6 work-email
providers each for the resolved ones, worst vs. typical; under the cap — approved. First 10 run as a
small batch: 8 resolve identity, 6 get a validated work email (5 on Findymail/LeadMagic, 1 on
Prospeo), 2 reach `work_email_not_found`. Installer okays the rest. Delivered: 48 rows joined back to
50 inputs, each found email tagged with source + verdict and each identity with its resolver, honest
misses shown, and actual credits reconciled against the estimate.

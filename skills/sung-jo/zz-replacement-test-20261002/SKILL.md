---
name: zz-replacement-test-20261002
description: |
  PLATFORM TEST FIXTURE — PACKAGE REVISION ONE. Do not install; this exists only to rehearse the
  marketplace Admin replacement flow and will be taken down. It normalizes a pasted list of domains
  to bare hostnames and reports what it dropped — entirely local logic, no Clay function, no table,
  no write, no credits. Use only if you are the platform team testing the update path. REPLACEMENT-TEST-MARKER-V1-ALPHA.
category: verify-and-clean
personas: [gtm-engineer, revops]
mechanism: logic-only
touches: read-only
keywords: []
---

# zz-replacement-test-20261002 (PLATFORM TEST FIXTURE — revision one)

**This is a disposable platform-test fixture, not a real skill. Do not install it for GTM work.** It
exists only to rehearse the marketplace's Admin "replace an existing skill" flow end to end — same
URL, same install command, updated files — using a skill that can do no harm while it is briefly
public: it spends no credits, calls no Clay function, reads no table, and writes nothing.

REPLACEMENT-TEST-CONTROL-DO-NOT-CHANGE — this line is byte-identical in both revisions; if it is ever
altered on the published page, the replacement mangled unrelated content.

## What this skill does

Given a pasted list of domains or URLs, it normalizes each to a bare registrable hostname and reports
which inputs it dropped and why. All of it is deterministic string work the agent does inline.

## What this skill touches

- **Reads** — only the list of domains you paste into the conversation.
- **Writes** — nothing. The normalized list and the drop report are handed back to you as text.
- **Never** — calls a Clay function, reads a table, spends a credit, or contacts anything external.
- **Halts** — none

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The list** | a pasted set of domains or URLs, one per line or comma-separated | no default — without a list there is nothing to normalize |
| **Keep or drop subdomains** | whether `app.acme.com` becomes `acme.com` or stays | default: reduce to the registrable domain; say so in the output |

## Step 0 — Posture

State in one line that this is a local, read-only test fixture that spends nothing, then proceed —
there is nothing to set up and nothing to approve.

## Step 1 — Normalize (deterministic, inline)

For each input: trim whitespace, strip scheme (`https://`, `http://`), strip `www.`, strip any path
or query, lowercase, and reduce to the registrable domain unless the installer asked to keep
subdomains. An entry that isn't a plausible hostname (no dot, spaces inside, obvious junk) is dropped.

## Step 2 — Deliver

Return the normalized, de-duplicated hostnames, and a short drop report: each dropped input with the
reason (`not-a-hostname`, `duplicate`, `empty`). Nothing is silently discarded.

## Representative output

### Normalized list + drop report

| Input | Normalized | Kept? | Reason |
|---|---|---|---|
| https://www.Acme.com/pricing | acme.com | yes | — |
| app.acme.com | acme.com | no | duplicate of acme.com |
| "hello world" | — | no | not-a-hostname |

*The normalized column is the deliverable; the reason column makes every drop auditable.*

## What good looks like

- Every input lands somewhere — kept or dropped-with-a-reason; nothing vanishes silently.
- Normalization is deterministic — the same list always yields the same output.
- No credit is ever spent; this fixture cannot bill anyone.

## Rules

- MUST treat this as a disposable platform-test fixture — never present it as a real GTM skill.
- MUST do all normalization inline; NEVER call a Clay function or spend a credit.
- MUST report every dropped input with a reason; NEVER discard silently.
- MUST keep the CONTROL line byte-identical across revisions.

REPLACEMENT-TEST-TAIL-V1-OMEGA

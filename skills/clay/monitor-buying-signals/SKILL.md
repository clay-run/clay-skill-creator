---
name: monitor-buying-signals
description: |
  Watch a fixed list of target accounts for buying signals with Clay — funding rounds,
  M&A, executive hires, expansion and other news events — and turn each sweep into an
  evidence-backed digest of who to act on now. Use whenever someone asks: monitor my
  target accounts for buying signals, alert me when an account raises or gets acquired,
  watch these companies for news, or which of my accounts had trigger events this week. Every fired
  signal carries a date, a quote-sized evidence line, and a source link; a quiet week
  is reported as quiet, never padded. Do NOT use it to track PEOPLE changing jobs
  (track-champion-job-changes), to find who engaged with your own social content
  (inbound-triggers-monitor), to score inbound leads (score-inbound-leads), to source
  net-new accounts (build-prospect-list), or for a point-in-time tech-stack snapshot
  (detect-tech-stack). Built on date-windowed news pulls, deterministic
  signal classification, and Clay's native signal subscriptions for standing watches.
category: signals
personas: [account-executive, revops]
mechanism: workflow
touches: writes-own-output
keywords: []
---

# Monitor buying signals

The insight: **a buying signal is a dated event you haven't acted on yet — not a fact
about a company.** The naive build asks "what's in the news about X?" and gets an
undated archive: old rounds, recycled press, the same story surfacing every sweep. This
skill never asks that question. Every sweep pulls a **bounded date window** (new since
the last look), classifies each event against a menu tied to *outbound hook quality*,
and requires evidence + source + date on every fired signal. And the normal result for
most accounts is **no signal this window** — an honest quiet week beats an invented
hook, because a rep who chases one stale or fabricated "signal" stops trusting the
whole digest.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The account list** | a CSV, table, audience or pasted list with at least a domain column | no default. Dedupe to unique domains first — ten contacts at one account are one watch. **Fifty domains is a defensible sweep cap**, stated as such |
| **The signal menu** | which events matter to their motion: funding, exec hires, M&A, expansion, layoffs | **funding, M&A and leadership hires is defensible** and must be stated. Each chosen signal has to pass one test: would a rep open an email with it? |
| **The window** | the first-sweep lookback; after that, last sweep to today | **30 days is defensible** for the first sweep, and the sweep date goes in every digest |
| **Cadence and destination** | how often, and where the digest lands | **weekly is defensible.** The digest goes to a table, a CSV or the conversation — this skill sends nothing anywhere |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — your account list and the signal menu you pick, over the window you set.
- **Writes** — only its own output, to the destination you name (a table, a CSV, or the
  conversation). It never changes a record that already exists.
- **Never** — writes to a CRM, or sends outreach on a signal it surfaced.
- **Halts** — Step 2 spend-approval.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run the
Clay plugin's `setup` skill, restart if it says to, and re-run this skill. Tell the
user which workspace you're in. Confirm the news arms exist before promising them —
read the live catalog, never your memory of it: `clay workflows actions list` for the catalog arm and
`clay routines get` for the managed **Company News** function — read the declared
costs; they differ by an order of magnitude (see `references/news-arms.md`).

## Step 1 — Collect the inputs (interview the user; do not guess)

1. **The account list** — CSV, Clay table/Audience, or pasted list; minimum one domain
   column. Dedupe to unique domains before anything (ten contacts at one account are
   ONE watch). Cap the sweep (default: 50 domains) and say so.
2. **The signal menu for THIS user** — which events matter to their motion (funding?
   exec hires? M&A? expansion? layoffs?). Default: funding + M&A + leadership hires.
   Each chosen signal must pass the relevance test: would a rep open an email with it?
   (`references/signal-menu.md` has the menu with hook-quality ratings.)
3. **The window** — first sweep: how far back (default 30 days). After that, each
   sweep's window is [last sweep date → today]; record the sweep date in the digest.
4. **Cadence + destination** — weekly is the sensible default. Digest goes to a table,
   CSV, or summary; this skill sends nothing anywhere.

## Step 2 — Choose the tier and state cost (mandatory gate)

Two tiers; pick by how standing the watch is, and get explicit approval with the
arithmetic stated:

- **Windowed sweep (this skill runs it):** per unique domain per sweep, the catalog
  news action (~1 credit) — escalate to the managed **Company News** function
  (~6.7 credits, aggregated multi-source) ONLY for a named shortlist of priority
  accounts. Worst case = domains × arm cost; state it, wait for approval.
- **Standing subscription (graduate when the watch becomes permanent):** Clay's native
  signal feed (`trigger-source`, News & fundraising) on an in-app table — the
  subscription is free and each landed EVENT costs ~0.5-1 credit, so cost scales with
  events, not accounts × sweeps. At roughly weekly cadence on 100+ accounts this is
  the cheaper and more timely shape — offer to hand off per
  `references/news-arms.md` §Graduation. Never rebuild the feed by re-scraping —
  windowed sweeps are for lists you don't watch continuously.

## Step 3 — Sweep: pull the window per domain

For each unique domain, run the chosen arm with the window pinned
([last sweep → today]; first sweep uses Step 1's lookback). Discipline per call:

- Gate on actual events in the payload, never on run status — a complete run with an
  empty result is the QUIET path, not an error (completion is not data).
- Never pull without a date window. An unwindowed news call returns the archive, and
  archives create the stale-hook failure this skill exists to prevent.
- Record per-call cost from usage metadata where the surface exposes it; the routines
  surface exposes none — say "declared estimate" when that's what it is.

## Step 4 — Classify each event (deterministic first, judgment second)

Map each event to the signal menu in code — keyword/pattern rules over title +
snippet + date (funding vocabulary, M&A vocabulary, leadership-change titles,
expansion/layoff terms; `references/signal-menu.md` carries the rule table). An event
matching no menu entry is `other` — surfaced in the digest tail, never promoted to a
signal. Only genuinely ambiguous events go to an LLM pass, and its verdict must quote
the evidence line it classified from.

Every fired signal emits four fields, none nullable:
`signal_present` (boolean) · `signal_evidence` (≤140 chars, from the actual event) ·
`signal_source` (the event's URL) · `signal_date`. A signal without a source link or
with a date outside the window is dropped with a note, not shipped.

## Step 5 — Route and digest

- **act-now** — menu signal with strong hook quality (funding, M&A, exec hire) inside
  the window → top of digest, with the opener angle named (congrats-on-round,
  new-leader, post-acquisition).
- **watch** — real event, weak hook (minor press, event presence) → logged.
- **quiet** — no events in window → listed as quiet with the window shown. Quiet is a
  RESULT; silent row drops are the cardinal sin.
- **Re-qualify before anyone acts** (the step naive builds skip): an event proves a
  state change, not deal fit — before outreach on an act-now row, confirm the premise
  still holds (the account is still in ICP, the hire is still in seat, the entity in
  the news is YOUR account and not a similarly-named company — match on domain, never
  on name strings).

Digest per account: `domain · route (act-now / watch / quiet) · signal type ·
evidence · source · event date · sweep window`, plus a summary: accounts swept, events
found, signals fired by type, quiet count, credits spent (measured where the surface
reports it, declared estimate where it doesn't).

## What good looks like

- **Every fired signal is traceable in one click** — evidence line + source URL +
  date. A digest row a rep can't verify is a rumor.
- **Quiet dominates.** On a healthy target list most accounts are quiet most weeks; a
  digest that fires on everything has a classification problem, not a great week.
- **No repeats across sweeps** — the window boundary is the dedupe; the same event
  reported twice means the window wasn't pinned.
- **Cost scales with the list knowingly** — the user approved domains × arm cost, and
  the digest reports what was actually spent.
- The common mistake: monitoring people-moves here. A champion changing jobs is
  track-champion-job-changes' whole play (native JobChange feed, FOLLOW/BACKFILL) —
  this skill watches ACCOUNTS.

## Rules

- MUST dedupe to unique domains and state cost + get approval before any sweep; MUST
  cap the sweep size.
- MUST pin a date window on every pull; NEVER report an event outside the window or
  without a source link.
- MUST gate on actual event payloads, never run status; quiet is reported as quiet.
- NEVER fabricate, embellish, or "summarize into existence" a signal — every evidence
  line traces to a returned event verbatim.
- NEVER auto-send outreach or write to a CRM — the digest is the deliverable; acting
  on it is the user's move (or the enrich-and-route-leads play).
- NEVER stand up a re-scraping loop for a permanent watch — graduate to the native
  subscription (Step 2) instead.

## Representative output

Three artifacts. **Every account, headline and URL below is invented** (`.example`
reserved TLD). The three routes are **act-now / watch / quiet**, and every account swept
appears in exactly one.

### Digest

| domain | route | signal type | evidence | source | event date | window |
|---|---|---|---|---|---|---|
| northwind.example | act-now | funding | "Northwind Systems raises $42M Series B" — opener angle: congrats-on-round | northwind-press.example/series-b | 2026-09-29 | past 30 days |
| meridianops.example | act-now | exec hire | "Meridian Ops names a Chief Revenue Officer" — opener angle: new-leader | tradepress.example/meridian-cro | 2026-10-01 | past 30 days |
| fabrikam.example | watch | expansion | "Fabrikam Cloud opens a Dublin office" — real event, weak hook | fabrikam.example/press/dublin | 2026-09-18 | past 30 days |
| kirivale.co.uk | quiet | — | — | — | — | past 30 days |
| halloway-industrial.example | quiet | — | — | — | — | past 30 days |

Every fired signal carries a source link and a date inside the window. A signal missing
either is **dropped with a note**, never shipped — which is what the next table is for.

### The tail — what was returned and is not a signal

This table is the honest half of the deliverable. A radar that shows only its hits cannot
be audited.

| event | why it is not a signal |
|---|---|
| "Former Northwind exec launches a new venture" | the account appears as a **modifier**. This is a person's story, not the account's. It matches funding vocabulary perfectly and is still not a Northwind event |
| "Supplier to Northwind Systems wins a contract" | the account is named inside somebody else's news. Entity discipline matches on **domain**, never on a name string |
| "Quartzlane Systems announces a partnership" | **no date anywhere in the payload.** An event that cannot be dated cannot be placed in a window, so it is dropped rather than assumed recent — on one real premium-arm call, 36 of 100 events arrived undated |
| "Northwind Systems updates its careers page" | matched no menu entry, so it is `other` — surfaced here, never promoted to a signal |

### Summary

```
5 accounts swept · window: past 30 days

  act-now      2    1 funding, 1 exec hire
  watch        1    1 expansion
  quiet        2
              --
               5 of 5 — quiet is a RESULT. A silently dropped row is the
                        cardinal failure of a radar, because it reads
                        identically to "nothing happened".

  events returned      14
  signals fired         3
  dropped to the tail  11    4 entity-discipline, 3 undated, 4 off-menu

Spend: 5 credits, 1 per account, measured. The two quiet accounts billed
exactly like the three with events — a quiet sweep is not a free sweep, and a
cost model that assumes otherwise understates a book of dormant accounts.

Three live traps this run had to work around:
  - On the cheap arm, event dates arrive as RELATIVE STRINGS ("3 weeks ago")
    rather than timestamps, and are resolved against the sweep date before any
    window comparison.
  - The quiet shape is the result FIELD BEING ABSENT, not an empty list. Code
    expecting an empty array reads a quiet account as a malfunction.
  - The premium arm ignores its own result-cap input: asked for 5 events, it
    returns 100. Budget for 100 and post-filter, or the arithmetic is wrong
    before the first call.
```

**Nothing above is outreach-ready, including the act-now rows.** An event proves a state
change, not deal fit. Before anyone contacts the funding row, confirm the account is still
in ICP, the new leader is still in seat, and the company in the story is yours — matched
on domain, not on a name that reads the same.

## Worked example

Ask: "Watch my 40 target accounts for funding, M&A, and exec hires — weekly."
Dedupe: 40 rows → 34 unique domains. Cost stated: 34 × ~1 credit/sweep (catalog arm),
premium arm reserved for the 5 named tier-1 accounts (~33 extra) — user approves the
1-credit arm for all. First sweep, 30-day window:
- `northwind-systems.example` → one event 2026-07-28: "Northwind raises $40M Series B"
  → funding vocabulary match → **act-now**, evidence "raised $40M Series B led by
  Veylmark Capital", source link, opener angle: congrats-on-round.
- `initech-consulting.example` → three events, all `other` (product blog syndication)
  → **watch**, digest tail.
- 29 domains → no events in window → **quiet**, listed with the window.
- `brightloop.example` → "Brightloop names new CRO" 2026-08-02 → exec-hire match →
  act-now — re-qualify note: confirm the CRO is still in seat and brightloop.example
  is the account you target (domain match), then the congrats-on-role angle.
Summary: 34 swept · 5 events · 2 signals fired (1 funding, 1 exec hire) · 31 quiet ·
~34 credits measured from per-call usage. Next sweep's window starts 2026-08-11.

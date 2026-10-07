---
name: buyer-classification
description: |
  Classify each contact in a list as buyer / influencer / not-a-buyer FOR YOUR
  PRODUCT — is_buyer, a buyer-persona label, confidence, and a one-line
  rationale per contact, from job title plus company context. Use whenever
  someone asks: which of these contacts are actual buyers, classify this list
  by buyer persona, flag decision-makers in my CRM export, is this title a
  buyer for us, or add an is_buyer column.
  Works from titles you already have — it derives what "buyer" means from YOUR
  product first (owning function × deciding seniority), runs auditable keyword
  gates before any judgment, reads ambiguous titles through company headcount,
  and says "unclear" instead of guessing. Do NOT use it to compute composite
  lead scores or tiers (score-inbound-leads), find new decision-makers
  (find-decision-makers-at-company), enrich raw signups (enrich-signup-users),
  or verify titles are current (clean-and-refresh-contact-data). Zero credits:
  classification is code plus stated judgment, not paid lookups.
category: score-and-qualify
personas: [revops, sales-development]
mechanism: logic-only
touches: read-only
keywords: []
---

# Buyer classification

The insight: **is_buyer is a product-relative verdict, not a title attribute —
the same Controller is THE buyer for spend management and noise for DevTools.**
There is no universal buyer list to look up, so classification starts by
deriving two requirements from the user's product: the FUNCTION that owns this
purchase, and the SENIORITY that can decide it — both must hold. Then the cheap
discipline: deterministic keyword gates run first (auditable, free, identical
on re-run), judgment spends only on the residual, and company headcount decides
what an ambiguous middle title means. The naive version asks an LLM "is this a
buyer?" per row and gets confident, unexplainable, product-blind answers.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The product, and who owns buying it** | one sentence each | no default — the classifier is derived from this |
| **Function definition** | which department owns or directs the purchase, with inclusion keywords **and** exclusion traps | ask. For a finance product, "Account Executive" is sales, not accounting |
| **Seniority line** | the deciding tier, and the sub-decider line below it | ask — where a title stops being a decision-maker is theirs, not ours |
| **Persona enum** | 5–8 labels their team actually uses | ask, then add `Influencer`, `Non-Buyer Leader` and `Unclear` |
| **Output shape** | a lean is-buyer flag, or full committee framing | lean by default. Build the committee machine only when something downstream genuinely consumes it |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — the contacts you supply and your definition of function, seniority and persona.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes a classification back to a CRM, or infers a persona from a title it was not given.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing,
run the Clay plugin's `setup` skill, restart if it says to, and re-run this
skill. (Classification itself spends no credits; Clay is needed only if titles
are missing and the user wants enrichment first — that's a sibling's job.)

## Step 1 — Derive the buyer definition (the product interview)

Before touching a row, establish with the user:

1. **What the product is** and who owns buying it — one sentence each.
2. **The two requirements** (`references/classification-mechanics.md`):
   - FUNCTION: which department/function owns or directs this purchase —
     with inclusion keywords AND exclusion traps (for a finance product,
     "Account Executive" is SALES, not accounting).
   - SENIORITY: the deciding tier — inclusion keywords (chief, VP, head of,
     director…) and the sub-decider line (manager, analyst, specialist…).
3. **The persona enum** — 5-8 labels the user's team actually uses, plus
   `Influencer`, `Non-Buyer Leader`, and `Unclear`.
4. **Right-size the output** (the KB rule): single product + single persona →
   this lean is_buyer shape. Full committee framing (MEDDPICC roles,
   seniority + department enums) ONLY when something downstream genuinely
   consumes it — don't build the committee machine to fill a boolean.

Show the derived definition (keywords, exclusions, enum) and get approval —
it IS the classifier; the user must be able to disagree with it in review.

## Step 2 — Classify: gates first, judgment on the residual

Per contact (dedupe first; title required — no title → `unclear`, never a
guess):

1. **Normalize** the title (case, punctuation, split compound titles on
   slashes/commas/"&": classify each part, best verdict wins).
2. **Deterministic gates** (code): exclusion traps first, then function
   keywords, then seniority keywords — word-boundary matching, and
   role-relation discipline: "Chief of Staff to the CFO" contains CFO but IS
   NOT the CFO (support-relation phrases beat contained seniority keywords).
3. **Headcount modifier** (when company size is available): a mid-tier title
   (manager-level) in the owning function is a de facto decider at a small
   company and an influencer at a large one — the reference sets the default
   thresholds; state them in the output.
4. **Judgment on the residual only**: titles the gates can't place (unusual
   phrasing, vertical-specific ranks, non-English) get reasoned one at a time
   against the SAME two requirements, labeled `via: judgment` — never batch
   them into vibes. Still stuck → `Unclear` with the reason.

Every verdict carries: `is_buyer · persona · confidence (gate-matched /
judgment / unclear) · rationale (≤20 words quoting the title evidence)`.

## Step 3 — Deliver

The classified table + the funnel (contacts in, buyers, influencers,
non-buyers, unclear) + the definition used (keywords, exclusions, thresholds —
so the next run is reproducible) + a review sample: every `judgment` row and
5-10 gate rows for spot-checking. Flag Procurement/Legal/Security-type roles
separately when relevant: they classify cleanly but are process gatekeepers,
not buyers — the user decides whether they get outreach.

## What good looks like

- **The definition is visible and approved** — the user can point at a keyword
  and say "that's wrong for us", and re-running with the fix is free.
- **Gate verdicts are reproducible** — same list, same definition, same
  answers, zero credits.
- **Ambiguous middles read through headcount** — no "Finance Manager is always
  (never) a buyer" absolutism.
- **Unclear has content** — gibberish, empty, and genuinely odd titles land
  there with reasons, not in a guessed bucket.
- The common mistake: classifying titles against a universal notion of
  seniority. "Is this person senior?" is the wrong question; "can this person
  decide THIS purchase?" is the job — function and seniority must BOTH hold.

## Rules

- MUST derive and get approval on the two requirements + persona enum before
  classifying; MUST right-size (lean is_buyer unless committee framing is
  consumed downstream).
- MUST run exclusion traps before inclusion keywords; MUST use word-boundary
  matching; MUST let support-relation phrasing ("to the", "assistant to",
  "office of") beat contained seniority keywords.
- MUST classify with headcount context when available and state the
  thresholds; MUST label every verdict gate-matched vs judgment.
- MUST output `Unclear` for empty/undecidable titles — NEVER a guess, NEVER a
  silent drop; absence of title evidence is not evidence of non-buyer.
- NEVER spend credits in this skill (enrichment belongs to siblings); NEVER
  reorder or re-tier by anything other than the stated rules.

## Representative output

Three artifacts. The titles below are generic job titles rather than anyone's record, and
the headcounts are invented. The product being sold is spend-management software — the
verdicts are only meaningful relative to that, which is why the definition ships with the
table.

### The classified table

Every row decided by `judgment` rather than a gate is marked, and those rows **are** the
review sample — they are the ones to spot-check.

| title | headcount | verdict | reason | decided by |
|---|---|---|---|---|
| CFO | 1,200 | buyer | finance function and decision authority both hold | gate |
| Interim CFO | 400 | buyer | authority is intact; flagged **interim**, since the tenure may be short | gate |
| VP Finance | 900 | buyer | function plus VP seniority | gate |
| Director of FP&A | 2,000 | buyer | `FP&A` is one token. Splitting on a bare `&` shreds it into "FP" and "A" and the function match dies — so splitting happens only on whitespace-delimited separators | gate |
| Finance Manager | 50 | buyer | **promoted on headcount** — at 50 people a finance manager signs. Flagged as size-promoted so you can disagree | gate |
| Finance Manager | 5,000 | influencer | the same title at 5,000 people is not the signer | gate |
| Finance Manager | unknown | influencer | **never promoted on missing data.** Flagged size-unknown — absent headcount is not permission to assume a small company | gate |
| AP Specialist | 800 | influencer | accounts-payable function without authority. Matched on a boundary-matched `ap`, which is safe only under word-boundary matching | gate |
| Procurement Lead | 1,100 | gatekeeper | classifies cleanly, and is a process gatekeeper rather than a buyer. Flagged separately — whether gatekeepers get outreach is your call, not this skill's | gate |
| Project Manager | 600 | non-buyer | the over-promotion trap: "Manager" is seniority with none of the function | gate |
| Account Executive | 300 | non-buyer | the exclusion trap, and exclusions run before inclusions | gate |
| Chief of Staff to the CFO | 1,200 | influencer | the contained-keyword trap: "CFO" is in the string and the person is not the CFO | gate |
| Founder & CFO | 80 | buyer | compound title, best part wins | gate |
| Head of Revenue Operations | 700 | influencer | adjacent function — owns the systems the spend runs through, not the spend | judgment |
| *(empty)* | 450 | unclear | no title on the row. Recorded with its reason rather than guessed into a bucket | gate |
| `—·—` | 450 | unclear | symbol-only title | gate |

### The funnel

```
16 contacts in

  buyers        6
  influencers   5
  gatekeepers   1
  non-buyers    2
  unclear       2
               --
               16 of 16 accounted for

Decided by deterministic gate: 15.  Decided by judgment: 1.
Spend: 0 credits. Re-running the same list against the same definition
produces identical verdicts.
```

### The definition used

Shipped so the next run is reproducible, and so you can point at a line and say it is
wrong for your product — correcting it and re-running costs nothing.

```
Product: spend-management software

Buyer requires BOTH:
  function   finance / accounting / spend ownership
             keywords: cfo, finance, controller, fp&a, accounting, ap, ar,
             treasury          (all boundary-matched)
  authority  chief, vp, head or director — or manager-and-above at fewer
             than ~200 employees

Exclusions, applied BEFORE inclusion:
  account executive, sales, business development, recruiting,
  customer success

Relation rule:  "<role> to the <buyer title>" is an influencer, never the buyer
Compound split: whitespace-delimited separators only  (/  ,  " & "  " and ")
                so FP&A, M&A and R&D remain single tokens
Headcount:      promote manager-level below 200; never promote on unknown
```

The question these gates answer is **"can this person decide *this* purchase?"** — not
"is this person senior?". Function and seniority must both hold, which is why a Project
Manager at 600 people is a non-buyer and a Finance Manager at 50 is not.

## Worked example

Ask: "Tag our 400-contact conference list — we sell spend-management software.
Who's a buyer?" Interview → FUNCTION: finance/accounting (keywords: finance,
FP&A, controller, treasury, CFO…; exclusions: account executive/manager =
sales); SENIORITY: director+ (with the manager-at-small-co modifier, threshold
200); enum: CFO · VP Finance · Controller · Finance Decision-Maker · Finance
Influencer · Non-Finance Leader · Unclear. Approved. Classify: 396 unique;
gates place 371 (94%): 44 buyers (11 CFOs, 9 VP Finance, 24 director-tier), 61
finance influencers (analysts, AP specialists, one "Chief of Staff to the CFO"
caught by the relation rule), 259 non-buyers (a "Account Executive, Mid-Market"
correctly SALES), 7 headcount-modified (finance managers at sub-200
companies → Finance Decision-Maker, threshold stated). Judgment places 18
long-tail titles (each with rationale); 7 land Unclear (blank, emoji-only, two
untranslatable). Deliver: table + funnel + the definition block + review
sample. 0 credits.

---
name: detect-tech-stack
description: |
  Detect the technologies a company runs on its website — CMS, ecommerce platform,
  analytics, chat, marketing and ad tools — from a domain, using Clay's managed Website
  Technology Stack function. Use whenever someone asks: what tech stack does this company
  use, do they run Shopify or HubSpot or Marketo, detect technologies on this domain, get
  technographics for these accounts, or find displacement targets from their current
  tools. It returns detected technologies grouped for GTM use, graded by how well the
  evidence supports *current* usage, plus an explicit list of what this method cannot
  see. Do NOT use it to prove a company does NOT use a tool (website detection cannot
  show absence), to detect back-office SaaS — finance, HR, ERP, most CRMs (invisible to
  website scanning; that needs deeper research), or to find people at the company
  (people search). It never pads sparse results and states cost before spending credits.
category: research
personas: [sales-development, marketing]
mechanism: functions
touches: read-only
keywords: [tech-stack]
---

# Detect a company's tech stack

The insight: **technographics answer "what can the website prove?", never "what does the
company use?" — and the raw answer is a lifetime archive, not a snapshot.** The managed
function reads the site's source code (BuiltWith-backed), so it sees what runs in a
visitor's browser and is blind to everything server-side or back-office (finance, HR,
ERP always; CRM unless a form embeds it). And it returns *every technology ever
detected*, current and historical, indistinguishably — a current Shopify Plus store
still lists Magento and WordPress from years past. Both verdicts are traps: **detected**
may be history, and **not detected is never evidence of non-use**.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Domains** | one hostname per row | given only a company name, resolve the domain first and sanity-check it — a wrong domain returns a confidently wrong stack with no error |
| **The GTM question** | map the visible stack, confirm one named tool, look below the SaaS layer, or detect a back-office competitor | ask **before** spending. This surface fully answers the first, answers the second only when the tool is website-visible, and only contributes partial evidence to the last two |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — the domains you supply, and the technology sources it queries per domain.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, or claims a technology it did not observe.
- **Halts** — Step 2 spend-approval.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run the
Clay plugin's `setup` skill (or follow
https://raw.githubusercontent.com/clay-run/agent-plugins/main/GETTING_STARTED.md),
restart if told to, and re-run this skill. Tell the user which workspace you're in.

## Step 1 — Collect the inputs

1. **Domain(s)** — the function's declared schema takes exactly one input,
   `Company Domain` (hostname). Given only a company name, resolve the domain first (a
   managed Company Domain function exists) and sanity-check it: a wrong domain returns a
   confidently wrong stack with no error.
2. **The GTM question** — which scenario, because it sets the confidence bar:
   (a) map the visible stack; (b) confirm one named tool; (c) infrastructure below the
   SaaS layer; (d) back-office competitor detection. This function fully answers (a),
   answers (b) only when the named tool is website-visible, and only contributes partial
   evidence to (c) and (d) — say which case applies *before* spending, not after.

## Step 2 — Run the managed function

Use the workspace's managed **Website Technology Stack** function — confirm it exists
with `clay routines list` / `get`. ~2 credits per domain, and website-scan providers
**charge on a miss too**; state total cost and get approval before multi-domain runs
(the routines surface reports no measured billing — quote the declared rate as an
estimate). CLI envelope: `{"items":[{"id":"<key>","inputs":{"Company Domain":
"acme.example"}}]}` via `clay routines runs start ... --input -`. Runs return in seconds.
For hundreds of domains or a recurring refresh, move to a table/workflow and say so.

## Step 3 — Read the raw output for what it is

The result is one flat comma-separated string in `Website Tech Stack` — no categories,
no dates. Know its three defects before reporting anything:
- **Not-found is an empty string** with run status still `complete` — gate on content,
  never on status.
- **Silent truncation**: big stacks cut off at exactly 8,192 characters, mid-name — an
  exact-8KB string means the list is incomplete; say so.
- **Pseudo-entries**: BuiltWith metadata rides along (Copyright Year ..., CrUX/Common
  Crawl ranks, stock-exchange listings, hreflang tags, "403 Error"). Filter these out;
  they are not technologies.

Then grade each real finding:
- **Detected, corroborated** — multiple same-family entries (Shopify + Shopify Hosted +
  Shop Pay...) or a structural role you can confirm on the live site. Safe to cite.
- **Detected, uncorroborated** — a single mention; may be years old (the archive
  problem). Usable for whitespace/ICP inference, never quoted as current usage in
  outreach without a live-site check. Contradictory sets (Magento *and* Shopify; three
  different web servers) are the archive showing itself — pick what the live evidence
  supports.
- **Not detected (visible category)** — weak evidence of absence, still not proof.
- **Not assessable (invisible category)** — the scan proves nothing either way; name
  these explicitly when they're what the user asked about.

## What good looks like

- Displacement outreach cites only corroborated detections — a stale archive entry
  quoted as current is the mistake that burns the email.
- A sparse result on a real but minimal site is a finding ("little detectable
  technology"), not a failure to fix by re-running or padding.
- The common mistake: reporting "no CRM detected" as "no CRM". The honest line is "no
  CRM visible on the website — most CRM usage isn't."

## Rules

- MUST state per-domain cost before running, including that misses still bill.
- MUST filter metadata pseudo-entries and flag 8KB-truncated lists as incomplete.
- NEVER report "not detected" as "does not use".
- NEVER present an uncorroborated (possibly historical) detection as current usage.
- NEVER pad a sparse result with plausible-sounding technologies.

## Representative output

Three parts per domain. **Every domain and technology pairing below is invented**
(`.example` reserved TLD). Evidence is `corroborated` or `uncorroborated` — there are no
other grades, because this surface returns no dates and a recency grade cannot honestly
be computed from it.

### Detected technologies, grouped

**northfield-outfitters.example** — a detectable stack

| category | technology | evidence |
|---|---|---|
| commerce | Shopify, Shopify Hosted, Shop Pay, Shopify Custom Theme | corroborated — a four-member family, consistent with the live storefront |
| commerce | Magento | uncorroborated — a lone entry contradicted by the corroborated Shopify family. Archive noise; **not** reported as in use |
| marketing / ads | Google Ads, Meta Pixel | corroborated |
| analytics | Google Analytics 4 | corroborated |
| support | Gorgias | uncorroborated — single entry, nothing corroborating it |
| infrastructure | Cloudflare, nginx | corroborated |

> **Truncated.** The provider returned exactly 8,192 characters, ending mid-name. This
> list is incomplete and the provider gives no truncation flag — so a large stack looks
> like a complete small one unless the length is checked.

**holbrook-industrial.example** — little detectable

| category | technology | evidence |
|---|---|---|
| infrastructure | IIS, Apache, nginx | uncorroborated — three web servers listed at once is the archive signature, not a concurrent stack |
| analytics | basic page analytics | corroborated |

85 entries came back against 525 for the storefront, and most were metadata
pseudo-entries — copyright-year tags, crawl-rank markers, a stock-exchange listing, even
a `403 Error` — all filtered out before reporting. **The thin result is reported as thin.**
Padding it with the archive would turn a minimal static site into a technology portfolio.

### What this surface cannot see

Website-visible technology only. HR, finance, ERP, CRM, data warehouse and anything else
that leaves no trace in page source is **structurally invisible here**, so absence is not
evidence of absence. And because the list is a lifetime archive with no dates, a current
technology and one retired three years ago are indistinguishable: detected ≠ used now,
not-detected ≠ not used.

### Readout

> **"Does northfield-outfitters.example run Shopify? We sell a Shopify competitor."**
> Yes — a corroborated four-member Shopify family, consistent with the live storefront.
> Displacement-qualified. The Magento entry in the same list is archive noise and is not
> a second platform.
>
> **"Do they use Workday?"**
> Not assessable on this surface, and no amount of spend here will change that. HR systems
> do not appear in website source. Job postings or provider research answer it instead.

```
Spend: 2 credits per domain at the declared rate. The routines surface exposes no
per-run billing fields, so that is a declared estimate and not a measurement —
read the actual charge where your surface reports one.
Not-found shape: the run completes and the output field is PRESENT but empty.
The field existing is not data; gate on non-empty content.
```

## Worked example

Ask: "Does northfield-outfitters.example run Shopify? We sell a Shopify competitor."
Scenario (b), website-visible — this surface can answer. Run (~2 credits, approved):
the list includes Shopify, Shopify Hosted, Shop Pay, Shopify Custom Theme → corroborated
current storefront — displacement-qualified. The same list also contains "Magento":
archive noise, contradicted by the corroborated Shopify family — not reported as in
use. Counter-case: "Do they use Workday?" → not assessable — HR systems don't appear in
website source; recommend job-postings/provider research instead of spending here.

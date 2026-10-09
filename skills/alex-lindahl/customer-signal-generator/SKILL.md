---
name: customer-signal-generator
description: "Generate Ideal Customer Signals (ICS) analysis for any company — a deep GTM intelligence deliverable that maps observable buying signals to outreach plays, grounded in live web research and, when the Clay MCP is connected, back-tested against real customer data and turned into a live list of accounts currently firing. Use this skill whenever the user asks to identify buying signals, ideal customer signals, ICS, purchase intent signals, or trigger-based selling opportunities for a company or product. Also trigger when the user asks for signal-based prospecting frameworks, intent signal mapping, signal back-testing, or GTM signal analysis. Even if the user just names a company and says 'run ICS' or 'what are the buying signals for X', use this skill. Also use it to check a single prospect account against an existing ICS ('why now for X', 'what's firing at X', 'is X a good target'), to refresh a saved signal board ('re-run the board', 'what changed since last time'), or for a quick ICS for a demo."
category: signals
personas: [gtm-engineer, sales-development]
mechanism: functions
touches: writes-own-output
---

# Customer Signal Generator (find who to call first, and why now)

## What This Skill Does

Produces a comprehensive Ideal Customer Signals analysis for a target company. The output maps observable external signals (hiring patterns, tech adoption, funding events, org changes, etc.) on the target company's *prospects* to buying intent, then connects each signal to actionable GTM plays — messaging angles, campaign ideas, channels, and detection methods.

ICP is the filter on the universe (who qualifies). ICS is the clock that sets entry order within that qualified set. This skill produces the clock.

The analysis is grounded in live web research. When Clay is available, it is also grounded in Clay data: firmographics for the target, a back-test of each proposed signal against real customers, and a live signal board of accounts firing right now.

## Declared inputs

**Nothing here ships with a value except where a default is named.** Ask for each one the request doesn't already settle, never invent a value, and when a default is used, say so in the report header.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Company** | the company whose buyers to analyse, by name or domain | no default — the skill cannot run |
| **Seller perspective** | whose outreach the plays are written for: the company's own sellers, a business unit, a product line, or a third-party vendor | defaults to the company's own sellers prospecting new buyers; stated in the header |
| **Focus segment** | a vertical, region or product line to narrow the ICP | the whole ICP inferred from research; stated in the header |
| **Competitors** | named competitors for displacement analysis | competitors are inferred from research and Clay, and labelled as inferred |
| **Clay mode** | `off`, `public` or `audiences` | `public` when Clay tools are present, `off` otherwise; `off` means web research only, no back-test and no live board |
| **Board hiring signal** | the one hiring signal that sources the live board | derived from the champion persona in Section 2 and named in the report |
| **Sample sizes** | accounts for the back-test and the board | 20 customers, 20 comparison accounts, up to 50 board accounts; stated |
| **Output format and theme** | HTML (default), docx, pdf or markdown; `clay` or `neutral` theme | HTML with the `clay` theme |
| **Saved signals** (Account and Refresh modes) | a `signals.yaml`, a previous report, or a link to one | Account mode runs Quick mode first; Refresh mode stops and offers a Quick or Full run |

Do not stop to ask for inputs that have a named default. Ask only when the seller perspective is genuinely ambiguous.

## What this skill touches

- **Reads** — public web pages; Clay company and contact search; Clay company data points for the target and board accounts; Clay Audiences accounts and deal history only in `audiences` mode.
- **Writes** — its own output only: the HTML report and `signals.yaml` (published as an artifact where the environment supports it, otherwise saved to the working directory). Enrichment results land on the skill's own Clay search task.
- **Never** — writes to or edits a CRM record, sends a message, enrolls anyone in a sequence, or copies the workspace's own CRM fields (pipeline, owners, opportunities) into the report.
- **Halts** — Step 4 spend-approval, Step 6 spend-approval, Step 6 sample-review.

## Workflow

### Step 0: Setup

0. **Say what this run touches.** Tell the user in one sentence: it reads the web and Clay, writes only its own report and `signals.yaml`, never edits CRM records, and asks before spending credits.
1. **Pick the run mode.** Read `references/run-modes.md` and choose Full, Quick, Account, or Refresh. Full is the default for a company that hasn't been analysed yet. For Quick, Account, or Refresh, follow that file's steps; they reuse the steps below where they say so. The rest of this workflow describes Full mode.
1. Use today's date in the report header, not a date inferred from search results.
2. Read `references/analysis-framework.md` now. It defines the **10 sections** of the analysis. If the file is missing, stop and tell the user — do not improvise a structure.
3. Check for Clay tools: the Clay MCP connector or the Clay Agent Plugin (in some environments tools are deferred, so search for them first). If unavailable, set Clay mode to `off` and skip every phase marked [Clay]. Use whatever web search and fetch tools the environment provides for Step 1.
4. If Clay mode is not `off`, read `references/clay-signal-recipes.md` and `references/signal-schema.md`.

### Step 1: Web research (always)

Run 4-6 searches covering:
- What the company sells, core product lines, and value proposition
- Target market, pricing model, and GTM motion (PLG vs sales-led vs hybrid)
- Recent news, funding, partnerships, product launches (last 6-12 months)
- Key competitors and competitive positioning
- If competitors were provided by the user, research those too
- If a focus segment was given, how the company sells into that segment

Do NOT skip research or rely solely on training data.

### Step 2 [Clay]: Ground the target company

Run `search-companies` on the target's domain, then `add-company-data-points` with: Headcount Growth, Annual Revenue, Latest Funding, Recent News, Company Customers, Company Competitors. Use these values in Section 2 instead of remembered figures. When a Clay value conflicts with a cited source (for example a revenue bucket far from reported ARR, or an implausible headcount jump), use the cited figure, drop the Clay value, and mention it in the report's status banner. Use Company Competitors to confirm or extend the competitor list for Section 8. Keep the Company Customers output — Step 4 needs it.

### Step 3: Analysis (Chain of Thought)

Work through Sections 2–8 of the framework in order. Write Section 1 (Executive Summary) last.

When Clay mode is on, every signal in Section 5 must also be expressed in the schema in `references/signal-schema.md`, including `decay_window_days`, `clay_source`, and `threshold`. Every signal needs a decay window, Clay or not — signals without expiry turn into noise.

### Step 4 [Clay]: Back-test signals against customers

Before finalising Section 7, test which Section 5 signals actually appear on real customers.

1. **Build the customer sample (max 20 companies by default).** In `audiences` mode, use `query-objects` to pull closed-won customer accounts. Otherwise, use the Company Customers list from Step 2, filtered to the ICP and focus segment. If it returns fewer than 10 companies, build the sample from the target's published case studies or customer page instead, and cite it.
2. **Build the baseline sample (same size).** Use `search-companies` for ICP lookalikes that are not known customers.
3. **Credit gate.** Show the user both rosters, the data points to be run, and a rough credit estimate. Wait for a clear yes before enriching.
4. **Enrich both samples** with the data points and custom data points mapped in `references/clay-signal-recipes.md`. Enrichment is async — start it, then poll `get-task-context` filtered by `entityIds`.
5. **Score each signal** using the back-test rules in `references/signal-schema.md` and record a verdict: Validated, Weak, Not observed, or Not testable via Clay.
6. Feed the results into Section 7. The Conversion Likelihood score must reflect the back-test where one exists; say so in the Rationale column.

### Step 5 [Clay, audiences mode only]: Mine deal history

Call `ask-question-about-accounts` on up to 10 closed-won accounts with a question such as: "What events, hires, or changes at this company preceded the first opportunity being created, and roughly how long before?" Use the answers to add or re-rank triggers (Section 3) and signals (Section 4). Mark anything found this way as `source: deal_history`. If owner-scoped access blocks the call, say so and continue.

### Step 6 [Clay]: Live signal board

**Rule: the board is sourced by exactly one hiring signal.** Pick the hiring signal from Section 4 that best matches the champion persona (for Snyk: open AppSec, DevSecOps or Product Security roles). Don't add other signals as board columns; they stay in the report's signal sections and in Account mode.

1. **Find the accounts.** Run that one hiring signal as a `search-companies` filter over ICP lookalikes (20–50 accounts, respecting the focus segment). Searches need no credit gate.
   - Exclude the target itself, its known customers, competitors and partners.
   - Drop staffing agencies, job boards and recruiters: they post roles for clients. Say what was removed under the board.
   - `existsInAudiences` reflects the Clay workspace running the skill, not the seller's CRM. Only use it to mark net-new accounts when that workspace belongs to the seller company; otherwise set `net_new: null`.
2. **Pull the job posts (paid).** Show the account list and a credit estimate, and get a yes.
   - **Pilot first:** run on 3 accounts before the full batch. If fewer than 2 return a posting, stop, show the user what came back, and ask before spending more.
   - **Known limits:** Open Jobs returns only a company's 10 most recent postings, so at large, fast-hiring companies the role the search matched is often missing. The custom web-research prompt misses most postings that aren't on a careers page. Neither reliably returns the matched posting (in testing, a strict web-research prompt found 1 of 16 and Open Jobs 0 of 3 exact matches; the current prompt accepts similar titles and undated postings).
   - **Order of sources:** first check `list_subroutines` for a workspace job-search function that can filter by title, and use it if one exists. Otherwise use Open Jobs for companies under about 2,000 employees, and the custom prompt as a fallback. For large companies, tell the user the job post may not be retrievable before spending credits.
   - Poll `get-task-context` filtered by `entityIds`; wait a few minutes between polls rather than polling repeatedly.
3. **Write the "Why now" column.** For each account, one or two sentences from the job-post summary on why it fits now: named tools or competitors, AI coding or agent work, supply-chain or SBOM duties, compliance (PCI DSS, FedRAMP, CRA), team size or first-hire language. Paraphrase; quote no more than a few words.
4. **Rate fit and time left.** Give each account a fit rating (Strong, Moderate, Weak) based only on the job-post summary, and compute days left in the hiring signal's decay window from the posting date. Drop accounts whose posting has expired.
5. **Rank** by fit, then by days left. The top five go in the hero.
6. **Contacts.** For the top 5 accounts, run `search-contacts` for the persona titles from Section 2. Don't enrich emails unless the user asks.

If the user declines the paid step, show the board with the hiring signal only and "Job post not pulled" in the Why now column, and say so in the status banner.

### Step 7: Output

**HTML report (default):** Write the report as a content JSON file and render it with `scripts/render_report.py`, as described under "Report content file" in `references/report-design.md`. That file also defines the layout it produces: the reader-order layout (hero with the accounts to call first, executive summary and company understanding, the board as a Clay-style table, clusters and templates, with the deep-dives as reference at the bottom), the components, and the colour rules. Inline `references/clay-theme.css` in full. All 10 framework sections still appear, under the names and order in that file. Show each signal's back-test verdict as a small badge (e.g. "13 / 20 customers · 3.1x lift").
- **Delivery:** if the environment can publish or render an HTML artifact, use it. Otherwise (Claude Code, Codex, Cursor), write `ics-{company}.html` and `signals.yaml` to the working directory and give the user the paths.

**Signal export (every Full and Quick run, Clay or not):** Write `signals.yaml` using the file structure in `references/signal-schema.md`, including `meta.icp` and the `board_snapshot` when Step 6 ran. Present it alongside the report so the user can keep it. Also embed the same YAML in the HTML report inside `<script type="application/yaml" id="ics-signals">…</script>`, so the report alone is enough for Account and Refresh modes later. Account and Refresh modes depend on this file; never skip it.

**Document formats:** For docx or pdf, use the environment's Word or PDF skill or library if one is available, and follow its conventions.

**Markdown:** Output directly in chat.

## Quality Standards

The difference between a good ICS analysis and a generic one is specificity. Every signal, messaging angle, and campaign idea should be clearly tied to *this* company's products, personas, and market position — not interchangeable boilerplate that could apply to any B2B SaaS company.

Signals should pass the "swap test": if you could swap in a different company name and the signal still reads the same, it's too generic. Rewrite it with concrete product names, specific persona titles, named technologies, and real competitive dynamics.

The "How to Programmatically Detect" field is especially important — it should describe real, implementable detection logic using actual data sources (job boards, technographic APIs, news feeds, SEC filings, G2, Clay data points, etc.), not vague suggestions like "monitor industry trends."

Signals describe what the company's *customers and prospects* exhibit — not signals about the company itself.

**Provenance.** Every number in the report must come from a cited web source or from Clay. Tag figures and signal evidence as [Web], [Clay], [Deal history], or [Inferred]. Never present an estimate as a fact. If a figure isn't available, leave it out rather than guess.

**Small samples.** Back-tests on 20 accounts are directional. Say so once in Section 7 and don't overstate lift figures.

## Handling Competitors

If the user provides competitor names:
- Research each competitor during Step 1
- Weave competitive displacement signals throughout the analysis (not just in a separate section)
- In Section 8, provide specific competitor-by-competitor displacement signals with messaging that references real product gaps or switching triggers
- In the outbound templates (Section 9), include at least one competitor displacement template

If no competitors are provided, still include a general competitive displacement section in Section 8, and note which competitors you're inferring based on research (and from Clay's Company Competitors data point when available).

## Clay guardrails

- Searches (`search-companies`, `search-contacts`) don't spend enrichment credits and don't need the credit gate. Data points, custom data points and subroutines do.
- Keep the running workspace's own CRM data (Audiences fields such as pipeline, opportunities, owners) out of the report. It describes the user's relationship with the account, not the target's buyers, and the report may be shared.

- Never spend Clay credits without showing the roster and getting a yes. If a call fails on credit approval, ask the user to approve in the Clay widget.
- Default caps: 20 customers and 20 baseline accounts for the back-test, 50 accounts for the signal board. Raise only on request.
- Never claim data wasn't found without calling `get-task-context` first.
- When standard enrichment comes back empty, check `list_subroutines` for a workspace function that covers it before giving up.
- If Clay is unavailable or fails mid-run, finish the report with web research only and label signals "Not back-tested".


## Representative output

### Report hero

**Call these two first** — Sixteen companies are hiring AppSec engineers right now. Two have job posts that show why now; Northwind's window closes in about a week.

### Live signal board

| # | Account | AppSec hiring (45-day window) | Why now (from the job post) | Fit |
|---|---|---|---|---|
| 1 | Northwind Systems | Security Engineer · 7d left · posted 31 Aug | Works with product teams on secure-SDLC and DevSecOps; names SAST, dependency analysis and container scanning across Python and Go. | Strong |
| 2 | Contoso Data | Security Infrastructure roles · 41d left · posted 4 Oct | Senior security infrastructure roles on an AI and agent platform; confirm the AppSec role before outreach. | Moderate |
| 3 | Fabrikam Pay | AppSec role · 30–45d left · posted 23 Sep–8 Oct | Job post not pulled. Clay's search matched an open AppSec role posted in the last 15 days. | Not rated |

### Signal entry in signals.yaml

```yaml
- id: appsec_hiring
  name: "Open AppSec, DevSecOps or Product Security role posted in the last 45 days"
  category: hiring_org_design
  decay_window_days: 45
  weight: 25
  clay_source: { type: search_filter, name: "jobs.exists" }
  backtest: { verdict: not_backtested }
```

## What this skill does not claim

- Weights and conversion scores are reasoned unless Step 4 ran, and even then a back-test on about 20 accounts is directional, not statistical. A back-test on current customers shows a signal is typical of customers, not that it came before the purchase; only deal history can show sequence.
- Clay company search confirms a matching open role exists but does not return the posting. Job-post summaries depend on data points that can miss postings, especially at large companies, so some board rows say "Job post not pulled" rather than guessing.
- Board accounts may already be customers of the seller; the skill cannot see the seller's CRM unless the Clay workspace belongs to the seller.
- Intent, web-visit and first-party product signals are named and scored on reasoning but are not detectable through Clay.
- Clay credit costs are shown by the Clay widget at run time; the skill does not quote prices.

## What good looks like

- Every signal passes the swap test: it names this company's products, personas and technologies, and would read wrong for a different company.
- Every signal has a threshold, a decay window and a detection recipe someone could build in Clay.
- The board is sourced by exactly one hiring signal, and every "Why now" is paraphrased from a real job post or says plainly that the post wasn't pulled.
- Every figure carries a Web, Clay or Inferred tag, and nothing untagged appears.
- No credits were spent without the installer seeing the account list and an estimate first.

A finished run, for reference: `references/examples/snyk-sample-report.html` (the report) and `references/examples/snyk-signals.yaml` (its saved signals), rendered from `references/examples/snyk-report-content.json` (its content file).

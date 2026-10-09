# Clay Signal Recipes

How to detect each Section 4 signal category with the Clay MCP, plus the call patterns that keep runs reliable. Read this before Steps 2, 4 and 6.

## Available data points

**Standard company data points** (`add-company-data-points`, `type` must match exactly):
Headcount Growth, Recent News, Investors, Company Competitors, Company Customers, Tech Stack, Website Traffic, Open Jobs, Revenue Model, Annual Revenue, Latest Funding

**Standard contact data points** (`add-contact-data-points`):
Email, Summarize Work History, Find Thought Leadership

**Custom data points:** `{ "type": "Custom", "dataPointName": "...", "dataPointDescription": "..." }`. Write the description as a precise, answerable question with a time window and an output format. Do not use the deprecated `customDataPoint` field.

**Workspace functions (subroutines):** Call `list_subroutines` at the start of any Clay phase. Function names and IDs differ by workspace, so never hard-code them. Useful types to look for: tech stack / technographic enrichment, latest funding, website traffic, LinkedIn post finders, and contact enrichment fallbacks.

## Recipes by signal category

| Section 4 category | Clay source | Example threshold / custom prompt |
|---|---|---|
| Demographic & Firmographic | Latest Funding, Annual Revenue, Headcount Growth, Investors | "Latest round ≥ $50M closed in the last 90 days"; "Headcount growth ≥ 20% over 12 months" |
| Hiring & Org Design | Open Jobs + custom data point | Custom: "Count open job postings in the last 30 days whose title or description mentions [TERMS]. Return the count and up to 3 example titles." |
| Technographic | Tech Stack, or a workspace tech-stack subroutine | "Tech Stack includes [TOOL]" / "does not include [COMPETITOR TOOL]" |
| People Movement | `search-contacts` filtered by title at the account, then Summarize Work History | Custom contact: "Did this person start in their current role within the last 120 days? Return yes/no and the start month." |
| Initiatives & Programs | Recent News + custom data point | Custom: "Has the company publicly announced a [INITIATIVE] program in the last 12 months? Return yes/no, date, and source URL." |
| Public Announcements & Strategy | Recent News, Company Customers, custom data point | Custom: "List partnerships or product launches in the last 90 days that involve [TECHNOLOGY/VENDOR], with dates and URLs." |
| Web & Content Signals | Website Traffic (own-site trend only); Find Thought Leadership for people | Mostly `not_testable` in Clay — needs first-party web analytics or reverse-IP data |
| Intent & Behavioral | Not available in Clay MCP | `not_testable` — needs G2, Bombora, or similar. Set `external_source`. |

Competitor displacement (Section 8): use Tech Stack for the competitor's product, plus a custom data point such as "Does this company publicly reference using [COMPETITOR]? Return yes/no with evidence URL."

## Job-post prompt (Step 6 board)

Fallback only: use it after the standard Open Jobs data point returns nothing for an account. It runs web research and can miss postings that the jobs index holds (an earlier, stricter version found 1 of 16 postings the search had matched, because it required exact titles and a visible posting date). Custom company data point, name "Hiring signal job post", one run per account. Replace the bracketed parts with the chosen hiring signal and the seller's product themes:

> Find this company's open job posting for a role similar to [Application Security, DevSecOps or Product Security Engineer] (include close variants such as Security Engineer, Software Security or Cyber Security roles that work with development teams). Check the company's careers page, its applicant-tracking pages (Greenhouse, Lever, Ashby, Workday) and LinkedIn Jobs. Prefer postings from the last [45] days; if the posting date isn't shown, still return the posting and write "date unknown". Return: the job title; the posting date (YYYY-MM-DD or "date unknown"); the posting URL; and a one- to two-sentence summary of the parts of the description relevant to [developer security tooling]: named tools or competitors, languages and CI/CD, AI coding assistants or AI agents, open-source supply chain or SBOM, compliance (PCI DSS, FedRAMP, EU Cyber Resilience Act), and team size or whether this is a first hire. Quote no more than 10 words. Return "none" only if there is no open posting of this kind at all.

The posting date also sets `evidence_precision: exact`, which replaces bucketed date ranges.

## Writing good custom prompts

- Put a time window in every prompt ("in the last 30 days").
- Ask for a count or yes/no plus evidence, so the threshold can be applied mechanically.
- Always ask for a source URL or date, so the decay window can be checked.
- Use one prompt per signal. Combined prompts make the back-test unreadable.

## Call patterns

- **Free first.** Express signals as `search-companies` predicates wherever possible (`jobs.exists(...)`, `jobs.count(...)`, `people.exists(...)`, `employee_growth_12mo`, `technographics.any(...)`, `locations.any(...)`). Searches don't spend enrichment credits.
- **Bucketed dates.** For a job-posting signal, run the same predicate with `job_posted_date >= today() - interval 15 days`, then 30, then 45. An account's first appearance gives its bucket (0–15, 16–30, 31–45 days), which sets `evidence_precision: bucket`. Use the Open Jobs data point only when exact dates are worth the credits.
- **Payload size.** Search results include Audiences fields for matched accounts and can be large. Use `limit`, don't render intermediate searches, and never copy those CRM fields into the report.

- **Search first, then enrich.** Every enrichment needs a `taskId` from `search-companies`, `search-contacts`, or `search-contacts-by-name`. Never invent a `taskId`.
- **Async.** Enrichment returns before values are ready. Kick it off, continue web research in parallel, then poll `get-task-context` with the `taskId` and `entityIds` until states are `completed` or `error`.
- **Filter payloads.** Pass `entityIds` to `get-task-context` to avoid huge company payloads.
- **Rendering.** Don't call `render-search-results` for back-test or signal-board searches; they're intermediate steps. The enrichment tools render their own widgets.
- **Pagination.** `search-companies` returns about 20 results per page; use `load-more-search-results` only when the sample needs more rows.
- **Audiences.** In `audiences` mode, use `query-objects` to find accounts and `ask-question-about-accounts` (max 10 account IDs per call) for deal history. Use `existsInAudiences` from search results to flag net-new vs existing accounts; when the field is absent, don't claim either.
- **Credits.** Show the roster and a rough credit estimate before each enrichment batch. If a call fails on approval, ask the user to approve in the Clay widget.
- **Fallbacks.** If standard enrichment returns empty values, check for a matching workspace subroutine and use `run_subroutine` with the existing `taskId`.

## What goes in the report

For each signal, the Section 5 "How to Programmatically Detect" field should name the Clay source and the exact threshold, then any non-Clay source needed. Example:

> Clay: `Open Jobs` + custom data point "Count postings in the last 30 days mentioning CUDA, DGX, InfiniBand or Spectrum-X". Fires at ≥ 10. Decay: 45 days. Back-test: 13/20 customers vs 4/20 baseline (3.25x) [Clay].

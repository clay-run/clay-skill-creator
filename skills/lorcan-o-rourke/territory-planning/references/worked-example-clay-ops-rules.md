# Worked example: one team's complete rules document

This is the rules document one GTM Ops team wrote for its own territory planning and shared publicly, kept
here as the worked example for Step 1 (interview) and Step 2 (rubric). It answers every interview question
in one place: segments and rep capacity, geography, hierarchy, cadence, feedback, the weighted Account Fit
Score with its grades, the single eligibility rule, and the exclusions. The specific lists are theirs; the
structure is what to copy. Read it next to `territory-rules-starter.md` and `rubric-starter.md`, which hold
the same decisions in the machine-readable shape the scripts read.

Two things in it map directly onto this skill's defaults: the exclusions in section 4 are applied at
scoring time by the Score node's default overrides (capped at 40, Low Fit) and again by the carve gates;
the hierarchy rule in section 1 is what `scripts/pick_root_domain.py` implements, including the holding
company exception.

---


**What this is:** the rules Clay's GTM Ops team uses to carve accounts into rep territories: the segments, the Account Fit Score that ranks accounts, the single eligibility rule, and what gets excluded before anything is scored. Shared as a reference for How Clay Uses Clay: Territory Planning.

**The whole rule in one line:** an account is carved into a territory when its Account Fit Score is above 60, it has no open opportunity, and no rep is already assigned. Everything else here is how we get to that score and who the account goes to.

**Use it to:** decide your own segments, pick and weight your scoring criteria, and write down your exclusions before you carve. The specific lists are ours; the structure is what to copy.

## How the carve runs

Apply in order. The first step that decides an account wins.

1. Exclude: drop accounts on the exclusion list (section 4).
2. Score: give every remaining account an Account Fit Score from 0 to 100 (section 2).
3. Check eligibility: Fit Score above 60, no open opportunity, no rep assigned (section 3). Accounts with an open opportunity or an owner stay where they are.
4. Segment and route: by the Ultimate Parent's headcount and by region (section 1).
5. Assign: within each segment and region, deal accounts to reps from the highest score down until every rep is at capacity. Anything left waits in the unowned pool.

## 1. Rules of Engagement

Segment is derived from the Ultimate Parent's employee count. Rep capacity is the number of accounts a rep holds in their book.

| Segment | Employees | Rep capacity (accounts) |
|---|---|---|
| SA (Sales-Assist) | 50–350 | 60 |
| SL1 / SL2 (Sales-Led, shared territory) | 350–3,000 | 50 (+10 in EMEA) |
| SL3 (Sales-Led) | >3,000, excluding F500 | 45 |

### Geography
- Regions: NAMER (US East / US West); EMEA (France; rest of EMEA pooled).
- Pooled geos: SF Bay Area, New York City, London. These route across all reps of a segment in the region, ignoring sub-region.
- Cross-sub-region assignment is off by default.

### Hierarchy
- A parent and its subsidiaries are one account family. The Ultimate Parent's headcount sets the segment; the parent's owner owns the whole hierarchy.
- Exception: holding companies (PE funds, conglomerates) whose subsidiaries run independently. Each subsidiary is segmented on its own.
- F500: an Ultimate Parent on the current Fortune 500 list is F500 regardless of headcount and sits with the Enterprise team, so it is not carved here.

### Cadence
Books are rebalanced on a rolling basis, not in an annual reset. The closer to continuous the better; the limit is how long a rep needs to work an account, not the tooling.

### Feedback
Managers and reps can reject an account from a book, but must give a reason. Rejections feed the next scoring iteration. Expect roughly 10–15% of a book to be flagged at first and drive that down over time.

## 2. Account Fit Score: criteria and weightings

Score each factor from 0 to 100, multiply by its weight, add them up: Account Fit Score (0–100).

Where the factors came from: research into what actually changes how a company buys: their GTM motion, the tooling they use, who they target, and the shape of their go-to-market team. Some are standard enrichment fields; the rest come from AI research on the account.

No black box: every component score is written back next to the total, so a rep can see exactly why an account scored the way it did.

| Factor | Weight | How to score (0–100) | Data needed |
|---|---|---|---|
| Technographics | 29% | CRM + data warehouse + competing data vendor = 100; CRM + DW = 80; any one = 50; none = 20 | Tech stack |
| GTM Motion | 20% | PLG + Sales (hybrid) = 100; PLG only or Sales only = 75; weak / early = 50 | GTM motion (AI research) |
| 12m Employee Growth | 12% | 30% or more = 100; 15–30% = 70; 5–15% = 40; under 5% or shrinking = 10 | Headcount now vs 12 months ago |
| Sales Team | 12% | GTM Engineer hired, or sales HC 50 or more, or 5% or more of employees = 100; 10–49 = 70; 1–9 = 40; none = 10 | Sales headcount, SDR job postings |
| Fundraising | 11% | Equity raise in last 18 months of $20M or more = 100; $5M or more = 70; older or smaller = 40; none or debt only = 0 | Last round date, amount, type |
| Business Model | 10% | B2B = 100; B2B + B2C = 70; B2C = 30. Then SaaS +15, non-SaaS −15, AI-native +15 (clamp to 0–100) | Business model, SaaS flag (AI research) |
| Ops Team | 4% | Ops / RevOps HC 3 or more = 100; 1–2 = 70; 0 = 20 | Ops / RevOps headcount |
| Employees (Size) | 4% | Linear: 0–500 employees maps to 0–100, capped at 100 | Employee count |

### Grades

| Grade | Account Fit Score |
|---|---|
| Best Fit | 80 or more |
| Good Fit | 65–79 |
| Moderate Fit | 50–64 |
| Low Fit | under 50 |

### Picking your own weights
- Start with the factors that explain your best existing customers, not every field you can enrich.
- Put most of the weight on the top two or three; the rest are tie-breakers.
- Test on about 6 accounts you already know (three strong fits, two in the middle, one clearly off) and adjust until the ranking matches your judgment.
- Only then run the full list. Weights will move again once rep feedback comes in.

## 3. Eligibility

An account is carved into a territory only if all three hold:
1. Account Fit Score above 60.
2. No open opportunity on the account.
3. No rep assigned: unowned, not already being worked, not a current customer with an owner.

- Fails 2 or 3: keeps its current owner. The carve never takes an account someone is working.
- Fails 1: stays in the unowned pool and is re-scored next cycle.

We used to run a second, industry-based gate alongside the score. The V2 scoring update absorbed it: sector weight came down, technographics went up, and now it is one score and one threshold. Resist adding gates the score should already be handling.

## 4. Exclusions

Removed before scoring and carving. The specific lists are ours. The point is to decide up front which accounts should never land in a rep's book. Every exclusion is also a data point you need to enrich.

| Exclude | Rule | Data needed |
|---|---|---|
| Industry | Industries outside our ICP, e.g. retail and consumer goods, manufacturing, pharma, healthcare services, untagged | Industry tag |
| Company type | Agencies, PE / VC firms, IT services, MSPs, staff augmentation, consultancies, system integrators, and education institutions (universities, .edu; EdTech companies are allowed) | Company type (AI research), domain |
| Offshore-majority | Legally headquartered in-region, but most employees sit elsewhere | Top country by headcount, in-region headcount, where the ops team is based |

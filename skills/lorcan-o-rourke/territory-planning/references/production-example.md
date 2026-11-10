# What a production rules set looks like (worked example)

This is one B2B SaaS company's live territory system, kept here so the interview asks the questions a
RevOps leader will actually have answers to, and so the outputs look like what reps and managers
already use. Copy the structure and the habits. Do not copy the values; the interview supplies those.

## 1. The scoring model has a version, a rationale per factor, and evidence for changes

| Factor | Weight | How it is scored | Why this weight |
|---|---|---|---|
| Technographics | 29% | CRM + warehouse + competing vendor = 100; CRM + warehouse = 80; one = 50; none = 20. Competing vendors named. | The strongest signal that is not a tautology of the ICP. |
| GTM Motion | 20% | PLG + sales (hybrid) = 100; PLG or sales alone = 75; weak or early = 50. GTM agencies = 100. | GTM maturity correlates with fit. |
| 12m Employee Growth | 12% | Percent growth over the past year, banded. | Growth validates demand. |
| Sales Team | 12% | Absolute headcount plus the sales-to-employee ratio; no team = 10. GTM Engineer hired = 100; 20+ SDR postings = 100, fewer postings a variable lift. (This skill's own build counts the GTM Engineer hire under Ops Team instead; see `enrichment-playbook.md`.) | Go-to-market investment. |
| Fundraising | 11% | Recency, amount and type (equity, not debt). VC firms default to 80. | Growth capacity; debt excluded. |
| Business Model | 10% | B2B = 100; B2B + B2C = 70; B2C = 30; VC firms and GTM agencies = 100; education = 0; SaaS +15, non-SaaS -15, AI-native +15. | Core fit driver. |
| Ops Team | 4% | 3+ = 100; 1 to 2 = 70; 0 = 20. GTM agencies and GTM Engineer hired = 100. | Readiness for structured ops. |
| Employees (Size) | 4% | Linear 0 to 500 employees → 0 to 100, capped. | Size; the heavy signals live elsewhere. |
| Sector Fit | 0% (was 20%) | Retired. Was: three core sectors = 100, four others = 50, the rest = 20. | It under-scored non-SaaS accounts the team was winning. |

**The change note that justified V2:** retiring Sector and moving its weight to Technographics raised
recall of non-SaaS closed-won accounts at fit ≥ 65 from 51.3% to 82.6%, captured +17 winners across the
rep-covered book (363 → 380 of 424 since 2024-01-01), and cost a small in-sector regression that the
eligibility gate's competing-vendor branch catches anyway. Splitting the points into Sales headcount was
rejected because sales headcount is already a hard gate downstream; double-counting it would dilute fit.

Habits to copy: a version and date on the model; a one-line rationale per weight; a back-test against
closed-won when a weight changes; the alternative you rejected and why.

## 2. Segment treatments and a risk/rescue layer sit beside the weighted score

| Segment | Treatment | Why |
|---|---|---|
| VC firms | Always score high (Best Fit if otherwise reasonable). | They are good customers, even with no funding events and small teams. |
| GTM agencies | Always score high. | Multipliers: they implement for many customers. |
| SaaS companies | Positive weighting. | Closest to the ICP. |
| Education institutions | Always Bad Fit. | Not a target market. |
| Everything else | The weighted factors. | Systematic evaluation. |

**Risk/rescue:** risk signals (no funding, under 20 employees, no GTM motion, no sales team, pure B2C,
education domain, weak region, no CRM or warehouse) add penalty points; rescue signals (recent raise,
high growth, real sales presence, SaaS, strong PLG, mature stack) subtract. High net risk plus a low
weighted score = Bad Fit. SaaS gets a stricter threshold so promising early-stage companies are not
excluded. This is a grade override, kept out of the weighted maths.

Grades: Best Fit ≥ 80; Good 65 to 79; Moderate 50 to 64; Low < 50; Bad Fit by override only.

**Scoring vs carving are different decisions.** VC firms and GTM agencies score high *and* are excluded
from the carve, because another motion owns them. Both rules are deliberate; write both down.

## 3. Segments are derived from the Ultimate Parent

| Segment | Parent-company employees | Accounts per rep |
|---|---|---|
| SA (Sales-Assist) | 50 to 350 | 60 |
| SL1 / SL2 (Sales-Led, shared territory) | 350 to 3,000 | 50 (+10 in EMEA) |
| SL3 (Sales-Led) | over 3,000 | 45 |

A parent and its subsidiaries count as one family: the parent's owner owns them all, and the family's
maximum headcount sets the segment. Regions: NAMER (US East, US West) and EMEA; pooled cities SF Bay
Area, NYC, London. Recarved every quarter.

## 4. The territory logic is a lookup table reps can read: what is in, what is out, and why

| Category | Rule | Requirement | Why |
|---|---|---|---|
| Composition | Self-serve customers | 30 to 40% of an SA book; 20 to 25% of SL1/2/3. Mix of annual and monthly. | Expansion revenue lives in the book, not in a separate motion. |
| Composition | Industry mix | 70/30 core (Software & SaaS, FinTech, HealthTech) vs all other allowed industries, across the entire book, self-serve and net-new combined. The self-serve floor applies within both halves. | Core sectors win most; the other 30% is where the book grows. |
| Include | Core industries | Fit ≥ 60 | ~92% of closed-won winners come from these three sectors. |
| Include | All other allowed industries | Fit ≥ 60, or (Ops headcount ≥ 3 and has a competing vendor and (Sales headcount ≥ 50 or ≥ 5% of employees)) | "This company has a real GTM function." Without the gate every mid-size company gets in. |
| Include | Competing vendors | Any of the named vendors, case-insensitive match on the tech-stack field | Displacement is the easiest win. |
| Exclude | Industries | Retail & Consumer Goods, Manufacturing & Industrial, Life Sciences & Pharma, Healthcare Services, untagged | Zero closed-won winners in these since 2024. |
| Exclude | Owned by another team | Enterprise tier: Fortune 500, Top-100 US, PE-team accounts | Stays with the motion that owns them. |
| Exclude | Open opportunity | Anywhere in the corporate family | Stays with the motion working the deal. |
| Exclude | Company type | Agencies, PE/VC firms, IT services, MSPs, staff aug, consultancies, system integrators, digital agencies | Detected from type tags and description keywords. |
| Exclude | Direct competitor | `Is_Competitor = true` | |
| Exclude | Education | `.edu` and `.org` domains and universities (multi-language name match); EdTech companies allowed | |
| Exclude | Non-sellable EMEA | Middle East, Israel, Africa, CIS, Russia, Belarus, Ukraine | |
| Exclude | Manager exclusion | Accounts a manager excluded in a past review | Soft block: prevents swap-and-repeat. |
| Exclude | India-heavy | Top country by headcount = India | |

The floor moved from 65 to 60 in one quarter to keep enough assignable accounts. That is a rules change,
not a model change, and it was announced.

## 5. Every recarve ships with a "What's new" and a FAQ

The patch doc opens with the changes since last quarter, in the reps' language:

> 1. Self-serve customers are now in your book: 30 to 40% of every patch.
> 2. Non-SaaS industries are open: only four permanent exclusions remain; everything else passes a headcount and technographics gate.
> 3. Fit model updated to V2: Sector 20% → 0%, Technographics 9% → 29%.
> 4. The fit floor is dropping from 65 to 60 so there are enough accounts to assign.

Then the criteria table above, then an FAQ for the common questions (why is X not in my book, how do I
swap, what happens to my open deals). Reps get a lookup table, not a spreadsheet.

## What the interview should therefore ask (Block 4 in `interview.md`)

Who owns which accounts today and how (parent roll-up or entity); whether existing customers belong in
books and at what share; the industry mix target and how it is measured (whole book or net-new only);
the fit floor and whether it may move; which teams own the exceptions (enterprise, PE, partners); the
field that holds competitor technographics and where it comes from; which exclusions are hard and which
are soft (manager lists); what reps receive after a carve (patch doc, FAQ, Slack approval) and who
approves; the validation window after a carve and the swap rule.

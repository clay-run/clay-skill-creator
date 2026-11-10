# Interview

Ask in this order. Stop after the first block if the answers change scope or cost; ask the rest at the
step that needs them. Take their words; do not translate into factor names yet.

A business brief the user hands over by name ("use brief.md as my business profile", a Notion export, a
one-pager) is the Block 1 answers: read that one file, say which questions it answered, and ask the rest.
A file nobody named is not read; a brief never answers a gate.

## Block 1: scope and cost (ask first)

1. **What do you sell, in one sentence, and to whom?** Industries, company sizes, buyer roles.
2. **What makes a deal bigger?** Seats, usage, conversations, locations, revenue. This is the unit of
   value; the rubric's heaviest factor should be its best public proxy.
3. **Five accounts you already know, with the grade you expect for each** (Best, Good, Moderate, Low).
   Ideally your best customers, one you lost *for fit reasons* (a churn for pricing or a lost champion
   teaches the rubric nothing) and one obvious non-fit; those roles are guidance, not a form. Any five
   that span at least three grades will do, and on a developer-edition run from a sample list, pick
   five from the list. An account a rule excludes ("too small, Not eligible") may carry an expected
   carve status instead of a grade: grades are checked at the Step 4 gate, carve statuses at the Step 7
   pool report. Domain plus the grade or status.
4. **Where do the accounts live?** CRM and object, or a CSV. Roughly how many: the count times the cost
   per account measured in Step 4 is the budget (the four reference runs measured 18 to 73 data credits
   per account, most of it the tech-stack lookup, which bills per product record it returns). A CSV needs at least
   `Name` and `Website` (the domain the enrichment resolves on); other columns load into Salesforce
   only if they match an Account field name (`BillingState`, `BillingCountry`, `Industry`,
   `NumberOfEmployees`).
5. **Which CRM environment is this, and what is the org alias?** Sandbox, developer edition, production,
   or none; the `sf` CLI alias the org is signed in under, so Step 0 can check the connection. A first
   run never writes to production; if they only have production, offer sandbox or a CSV. Whether a
   Clay Audiences Salesforce source already syncs Accounts is optional production plumbing for the weekly
   top-up, not a prerequisite: the first run scores the imported list through the workflow's manual
   domain input.
6. **Do you want scores written back to the CRM?** If yes, can you create custom fields, or do you need
   a package or metadata file? Rubric-specific enrichment values (a sector, a compliance headcount, an
   engineering headcount) are written too, as extra fields `sf_setup.py fields --extra-fields` creates;
   the fixed field set is a default, not a contract.

## Block 2: fit (ask before Step 2)

7. **Must-have technology.** Tools a good account almost always runs (a CRM, a warehouse, a help desk,
   a competitor of yours). Then the sharper question: **which specific products identify a good
   account?** Name products, not vendors (the ERP by name, a CMMS, GitHub, a core banking platform):
   they become the pinned product list in the tech-stack lookup, at most about 12, because the lookup
   bills per product record it returns and a vendor-wide pin (Microsoft, Oracle, SAP) returns dozens of
   unrelated records at full price. That lookup was 60 to 90% of the spend in the reference runs. Name
   the competitors separately; they are `eligibility.competing_vendors` (the other-industries gate) and
   the competitor exclusion.
8. **Team shape.** Which teams or titles signal readiness: sales headcount, ops, support, a specific hire.
9. **Growth and funding.** Does recent funding or headcount growth predict a win for you, or not? Funding
   research is skipped for VC/PE firms, schools, government bodies and public or exited companies
   (`research-prompts.md`); say so if those are in their universe, and say if your buyers rarely raise
   (banks, credit unions), so "no round" is not punished hard.
10. **Business model.** B2B, B2C, both; SaaS or not; anything that flips a score (agencies, VC firms,
   education, public sector). By default an excluded type is capped under the threshold at scoring time
   and kept out of the carve; a type can instead score high and still be kept out (the opt-in lift); see
   the note under the mapping table.
11. **Disqualifiers.** Industries, countries, company types or sizes you never sell to.
12. **Too big for us?** Is there a size above which another team sells, or nobody does (5,000+
    employees, say)? Should those accounts carry a Low Fit grade in the CRM, be excluded from the carve,
    or both? Both is allowed. The rule reads the CRM employee count first and the enrichment headcount
    only when the CRM has none: LinkedIn counts over-count 5 to 9x for some companies. It is written once, as
    `overrides.size_cap` in the rules file: the Score node reads it for the grade, and the carve node
    reads the same block to take the account out of the pool (`Not eligible` for `action: Low Fit`,
    `Excluded` for `action: exclude`); `exclusions.min_employees` is the floor.

## Block 3: territory (ask before Step 6)

13. **Segments.** v1 segments on employee count (revenue needs a CRM revenue field; say if you have
    one and we will segment on it, otherwise employees). The boundaries; capacity per rep in each, and any
    regional bonus (EMEA +10, say). If they don't know capacity, derive it: quota ÷ ACV × pipeline
    coverage ÷ opportunity rate. Knob: `segments[]` (`name`, `min_employees`, `max_employees`,
    `capacity`, `capacity_bonus`).
14. **Reps.** How many per segment and region, with names and CRM user ids, or "propose it" (pool size ÷
    capacity, rounded up, and the skill names the gap). When a rep's own capacity in `reps.csv` differs
    from the segment's, which wins? Default: the rep's number; say it is a default. When `reps.csv` is
    given, the eligible ÷ capacity maths is a note in the carve summary and overflow goes `Unowned`;
    adding a rep is the approver's decision, recorded as a `reps.csv` change. Knob: `reps.csv`
    (`segment`, `sub_region`, `capacity`).
15. **Routing.** What groups accounts after the segment: region, state, metro, vertical, or a named
    list? Name each region, its sub-regions and the states or countries in each, and the pools (a
    shared metro dealt across every rep of the segment in the region) with the cities that map to each.
    Language or time-zone routing is a sub-region with its countries listed; there is no separate knob.
    Knob: `routing.by` (`segment`, `region`, `sub_region`, `country`, `state`, `metro`, `vertical`,
    `named_list`) and `routing.regions`.
16. **Protections.** Open opportunity keeps the owner (from which stage; the account only or its whole
    family)? Active pursuit (touches in 30 days, a meeting in how many days)? Rep picks (how many; they
    are recorded per rep as `protected_domains` in `reps.csv`)? Does an existing customer keep its
    relationship owner? Partner registration (how many days)? Churned customers out of the pool for how
    many months? A protection whose field the CRM does not have is skipped and the proposal says so.
    Knob: `protections` (`open_opportunity`, `active_pursuit`, `rep_picks.max`, `customer_owner`,
    `partner_registration.days`, `churn_cooloff.months`).
17. **Balance.** What should be equal between two reps in the same segment? v1 balances on count and
    mean fit; revenue, workload and composition are reported next to the books, not balanced. Knob:
    `allocation.balance_on`. Composition targets themselves are Block 4.
18. **Method and order.** Deal by score (snake), round robin, let reps draft, manager assigns, or
    continuous (dynamic books: deal only to reps below capacity, the weekly top-up does the rest)?
    Default snake; say it is a default. A hybrid is common: the manager places a named top N and the
    rest is dealt (`allocation.method: manager` with `allocation.named_accounts.top_n`). Dealt in which
    order: fit score (default), revenue, or propensity? Knobs: `allocation.method`, `allocation.sort_key`.
19. **Cadence and notice.** Recarve quarterly? Top up weekly? Retrieve accounts after how many idle
    days, and rest them how long before they re-enter the pool? How many weeks' notice before a recarve
    takes effect? Knobs: `cadence` (`recarve`, `top_up`, `stale_days`, `rest_days`),
    `governance.notice_weeks`. The weekly top-up is an Audiences segment trigger on the scoring
    workflow; it is created after the first full run as a draft and left unpublished until the team
    wants it live, because publishing it scores every record in the segment at once.

## Block 4: production details (ask before Steps 6 and 7)

These are the questions a RevOps leader already has answers to; `production-example.md` shows one
company's answers and the outputs they produce.

20. **Ownership today.** Does the parent's owner own the subsidiaries, or is each entity its own
    account? The carve must match how owners are read today or every family looks reassigned. Knob:
    `hierarchy.mode` (`family`, `entity`; `buying_centre` is not implemented in v1).
21. **Existing customers in books.** Do self-serve or existing customers belong in a book, and at what
    share per segment? Knob: `composition_targets.self_serve_share`.
22. **Industry mix.** Which industries are core, in the CRM's own Industry values (the carve matches
    `eligibility.core_industries` against the Account Industry field; a value not listed is "other"), the
    core-vs-other target, and how it is measured: across the whole book, or net-new only? Knobs: `eligibility.core_industries`,
    `composition_targets.core_industry_share`.
23. **Fit floor.** The score an account needs to be eligible (default 60; say it is a default); whether
    other industries get an alternative gate (ops headcount, a competing vendor from
    `eligibility.competing_vendors`, sales headcount or ratio); and whether the floor may move to keep enough assignable accounts. A floor move is a rules
    change, not a model change, and it is announced. Knobs: `eligibility.threshold`,
    `eligibility.other_industries_gate`.
24. **Who owns the exceptions.** Which teams own accounts the carve must not touch: enterprise or
    strategic, Fortune 500, Top-100, a PE team, partners, house accounts, and the field that marks them. Knobs:
    `exclusions.other_teams`, `exclusions.other_teams_field`.
25. **Competitor technographics.** Which field marks a direct competitor, and where the tech-stack data
    comes from (a CRM field, a vendor, the enrichment this skill runs). Knob:
    `exclusions.competitors_field`; the competitor names go to `eligibility.competing_vendors`, and the
    products named in Q7 are the pinned list the Technographics factor reads.
26. **Hard and soft exclusions.** Which exclusions are permanent (industries, company types, regions,
    education) and which are soft: accounts a manager excluded in a past review, with the reason, so a
    swap cannot bring them back. Knobs: `exclusions.industries`, `exclusions.company_types`,
    `exclusions.regions`, `exclusions.education`, `exclusions.min_employees`, `exclusions.manager_list`.
27. **What reps receive, and who approves.** Reps receive the patch doc `scripts/carve_summary.py` writes
    (`patch-doc.md`: a "what's new" skeleton to fill in, the criteria table, each rep's book and a FAQ:
    why is X not in my book, how do I swap, what happens to my open deals), next to `carve-summary.md`
    and `carve-proposal.csv`; nothing is sent until the books are approved. Who approves the books
    before owners change, and where: a Slack channel, or in this session, in which case the files stay
    in the project and the recorded yes is the approval. Say now that the owner write itself is a bulk
    routine run that Claude Code asks the human to approve ("Modify Shared Resources"), so the approver
    is at the keyboard for it. Knobs: `governance.approver` and the rules file's `deliverables` block
    (`patch_doc`, `whats_new`, `faq`, `approval_channel`); the carve's proposal follows them.
28. **Validation window and swaps.** How long after a carve do they review engagement and pipeline per
    rep against the proposal (30, 60, 90 days)? The swap rule (default one-for-one within a segment,
    manager approves, reason recorded on both accounts). Knob: `governance.swap_rule`; the validation
    window has no knob and is recorded in the governance section.

## Block 5: after the carve (ask before Step 8)

29. **What counts as engagement.** Which of the three signals matter for this team: company news and
    funding, GTM leadership hires, sales and RevOps job postings; the titles and topics to watch; and
    how many points each event is worth. Say the defaults (25 / 30 / 15, cap 100) and that they are
    defaults. Knobs: `engagement.signals.*`, `engagement.cap`.
30. **How fast heat fades.** Whether the score should decay weekly (default keep 75%) or run as a total
    for the quarter. Knob: `engagement.decay`; the decay workflow stays a draft until the team wants it.
31. **When a pool account comes back.** The engagement and fit an unassigned account needs to be a
    candidate again mid-quarter (default engagement 40 with fit 50), and that assigning it is still the
    Step 7 loop with an approval. Knob: `engagement.reentry`.
32. **Who watches book health, and when.** Who asks for `book-health.md` (the manager, weekly or monthly)
    and whether a rep with room gets the hot pool accounts first or the highest fit first. No knob; the
    answer is recorded in the governance section.

Each answer maps to a knob in the rules file (`territory-rules-starter.md`), or where no knob exists
the question says so and the answer is written into the rules file as prose; `carve-scenarios.md`
explains every option.

## Mapping answers to factors

| They said | Factor | Kind |
|---|---|---|
| specific products a good account runs (the pinned list), competitors | Technographics | map (combination present) |
| sales headcount, sales ratio, SDR hiring | Sales Team | bands (count or ratio; 20+ open SDR roles = top band) |
| ops / RevOps / support headcount, GTM engineer hired | Ops Team (rename to their team) | bands (one combined count; GTM Engineer titles count here, as built) |
| recent raise matters | Fundraising | bands (amount, recency; older than 18 months = band 40) |
| headcount growth matters | Headcount Growth | bands (percent) |
| company size band | Headcount (Size) | linear or bands (any size cap reads the CRM count first; Q12) |
| B2B / SaaS / AI-native flips | Business Model | map with modifiers |
| self-serve vs sales-led | GTM Motion | map |
| anything no vendor measures (who they sell to, product complexity, policy density) | new factor via AI research (`research-prompts.md`, step-budgeted) | map, with evidence |

A disqualifier is not a factor. It goes to the rules file as an exclusion or an override.

The starter assumes a sales-led B2B software seller; its factors are a default, not a contract. The
reference runs replaced them freely: a fintech seller scored Institution Type (47) and Compliance team
(28), an industrial seller Sector (40) and Plant headcount (25) with SaaS penalised, a PLG seller
Engineering team (25). Rename or replace a factor when the interview says so, and carry its enrichment
value to the CRM with `sf_setup.py fields --extra-fields`.

Exclusions run twice on purpose. By default agencies, VC/PE firms and education institutions are capped
at 40 and graded Low Fit by the Score node (the research step gives a VC firm a flat fundraising band) and
excluded again by the carve, because another motion owns them; the opt-in lift lets them score high
instead where they are real customers. Both rules are intended; write both down and say so when
the user sees a Best Fit account in the exclusion list.

## Record

When the user agrees, write the answers to `territory-planning.answers.yaml` one directory above the
skill folder (identifiers only, no credentials), so the next run asks fewer questions. A later run loads
that file only when its user says to; no other file in a project is ever read as an answer. Offer it in plain words: "want me to save your answers so the next person on
your team doesn't have to answer these again?"

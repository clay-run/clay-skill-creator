---
name: compliance-buying-window
description: |
  Place each target account in its security compliance cycle (preparing, inside an audit
  observation period, recently certified, established, or not visibly in one) from what the
  account publishes about itself: its trust or security page, its own compliance and GRC job
  postings, and its own certification announcements. Every placement is made per framework
  (SOC 2, ISO 27001, HIPAA, PCI DSS, or whichever ones you sell into), carries a date and a
  quoted evidence line, and abstains when nothing dates it. Free page reads run on every
  account before any paid job or news call. Use whenever someone asks: which of my accounts
  are going through SOC 2, who is preparing for an ISO 27001 audit, find companies hiring
  their first GRC or compliance person, which accounts just got certified, is this company in
  its audit window, or when should we time outbound for a compliance or security product.
  Do NOT use it for general news and funding monitoring (monitor-buying-signals), for counting
  or trending job postings (hiring-radar), for ICP fit scoring (account-tier-scoring), for
  detecting a website's tech stack (detect-tech-stack), or for sourcing net-new accounts from
  events (signal-sourcer).
---

# Compliance buying window (date the audit cycle, not the announcement)

The insight: **for anyone selling security or compliance into software companies, a published
certification marks the end of the buying window, not the start of it.** A SOC 2 Type II report
describes controls operating over an observation period, which in practice usually runs from three
to twelve months, and the report only issues after that period closes and the auditor finishes
fieldwork. The readiness tooling, the auditor, the policy set and often the first compliance hire
were all chosen before the period began. So the "achieves SOC 2" announcement that most signal
lists fire on arrives months after the decisions it seems to announce. ISO 27001 has the same
shape on a different calendar: certification, then yearly surveillance audits, then
recertification in the third year.

What follows from that: the question worth asking per account is **where in its own audit cycle
is this company, and what did it publish that dates that position?** The evidence is mostly first
party and mostly free to read. Trust pages say "Type II in progress". Job postings say "own our
first SOC 2 audit". Announcement posts carry a date. This skill reads that evidence, places each
account per framework, and says it cannot place an account when nothing dates it, because a timing
play built on an undated badge is a guess with a logo on it. It comes out of running outbound for
security and developer tooling vendors, where this timing question decides most account lists.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it,
never substitute a plausible default, and if an answer does not exist say which step becomes
unavailable rather than guessing. Where a default IS defensible it is named below, and using it
means saying so in the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The account list** | a CSV, table, Audience or pasted list with at least a company domain per row; a company name column helps the news step | no default: there is nothing to place. Dedupe to registrable domains first |
| **Frameworks in scope** | the audits your buyers face: SOC 2, ISO 27001, HIPAA, PCI DSS, FedRAMP, CMMC, or others you name | no default: stop and ask. A framework you do not sell into is noise in the digest |
| **What you sell, against the cycle** | which stages mean "reach out now" for your offer, which mean "nurture" and which mean "skip". A readiness product usually wants `preparing`; a penetration testing or continuous monitoring offer may want `in-observation` and `recently-certified` | no default: this is a judgment about your own product. Without it the skill still places accounts, leaves the next move column empty, and says why |
| **Compliance role vocabulary** | the job titles that count as compliance preparation for you | Step 1 proposes a starting list; use it only after the installer approves it, and record whether it was chosen or accepted |
| **Hiring window** | how far back a posting still counts, in days | 90 days is defensible and must be stated in the output; never leave it unset, which silently means all time |
| **Recent certification window** | how long after a dated certification an account still counts as recently certified, in months | 12 months is defensible because SOC 2 reports and ISO surveillance audits both run on a yearly rhythm; state it if used |
| **Budget ceiling** | the most Clay credits this run may spend | no default: Step 4 prices the run and stops for approval either way |
| **Output destination** | the conversation, or a CSV path the installer names | the conversation. A file is written only at a path the installer names |

**If an answer sheet is present beside this skill, load it and ask only for what it does not
cover.** A partial sheet is normal; a value it is missing gets asked for on its own rather than
restarting the interview. **Say which values came from the sheet** before using them, because a
sheet applied silently is a wrong field nobody catches. **If there is no sheet, say nothing about
sheets**: the check is a file lookup, not a question. At delivery, offer to save the answers back
(identifiers only, never a token or a password), private and never published, and phrase the offer
so it explains itself: *"want me to save your answers to a file, so the next person on your team
doesn't have to answer these again?"*

## What this skill touches

- **Reads**: your account list; the public homepage, trust, security and compliance pages of those accounts; public job postings and news results for those accounts through Clay functions.
- **Writes**: nothing to any system you run. The digest is returned in the conversation, or as one CSV file at a path you name.
- **Never**: writes to a CRM, enrolls anyone in a sequence, contacts an account, submits a form or an access request on a trust portal, opens an NDA gated report, or sends account data anywhere other than the Clay calls named in Step 5.
- **Halts**: Step 4 sample-review, Step 4 spend-approval.

## Step 0: Check the platform, and say where the work runs

Run `clay whoami; echo "exit_code=$?"` and `clay --version`. If either fails, say which component
failed, which version is required if the CLI says so, and the one command that fixes it (the Clay
plugin's setup skill), then stop. Do not install, upgrade or fetch anything to repair it. Tell the
installer which workspace the run is in.

Then tell the installer where the work runs, in these words or close to them: *"The page reads and
every placement run here in this conversation and cost no Clay credits. Clay credits are spent only
in Step 5, on job posting and news lookups, and only after you approve a priced plan in Step 4.
Nothing is written to your CRM or any other system."*

Confirm the functions Step 5 expects against the live catalogue before pricing anything:

```
clay routines list --limit 100
clay routines get <id>
clay workflows actions list
clay workflows actions schema <packageId> <actionKey>
```

Check these subcommand names with `--help` on the installed version first. For each function you
will call, record the `(packageId, actionKey)` pair, its `paymentType` and its declared cost; the
list call does not carry costs, so read them by id. Page through the list rather than trusting one
page. If a function Step 5 needs is absent or not callable, say so and drop that evidence source from
the run. Never substitute the nearest function silently.

Do not start a step before the steps above it have their answers. If a declared input is missing,
ask for it; never assume a default and continue.

## Step 1: Collect the definition (interview; do not guess)

1. **The account list.** Normalize every domain (lowercase, strip the scheme, the path and `www.`),
   dedupe, and report the count before and after. Ask how subsidiaries should be treated before
   collapsing them, because it changes the row count.
2. **Frameworks in scope.** Ask. If the answer is "security in general", ask which audits their
   buyers actually go through; do not pick for them.
3. **What they sell, against the cycle.** Show the seven stages from Step 2 and ask which mean
   "reach out now", which mean "nurture" and which mean "skip". Record the answer as a small mapping
   table; Step 7 reads the next move column from it.
4. **The role vocabulary.** Propose this starting list and ask for additions and removals: GRC
   analyst or manager, governance risk and compliance, security compliance, compliance manager or
   analyst, information security manager, head of security, security program manager. Broad
   engineering titles are left out on purpose; a security engineer posting counts only if its text
   names an in scope framework (Step 2, stage 3).
5. **The two windows and the budget ceiling.** Offer the defensible defaults named in Declared
   inputs and record whether each one was chosen or merely accepted.

## Step 2: The stage model (the decision this skill exists to make)

Placement is per account **per framework**, because one company can hold a SOC 2 report and be
preparing for ISO 27001 in the same quarter. Seven stages, no eighth. Evaluate them in this order
and stop at the first match:

| Order | Stage | Matches when | Dated by |
|---|---|---|---|
| 1 | `unreadable` | the homepage probe failed, and no trust page and no Step 5 source returned readable content for this account | nothing; the row says what failed |
| 2 | `in-observation` | the account's own page says an audit period for this framework is underway ("Type II in progress", "currently undergoing our audit", "observation period", "report expected"), or a Type I is published with Type II named as the next step | the page statement, plus an expected report date if one is stated |
| 3 | `preparing` | no certification for this framework is published, and inside the hiring window there is at least one of: a posting with a title from the approved vocabulary, a posting whose text names this framework as something to achieve, obtain, lead or prepare for, or a page statement of intent ("pursuing", "working towards", "planned for") | the posting date, or the page statement |
| 4 | `recently-certified` | a certification for this framework is published with a date inside the recent window: a report period end date, a certificate issue date, or the account's own dated announcement | that date |
| 5 | `certified-undated` | the account shows a certification for this framework and no date can be found beside it or in its own announcements | nothing; the row says so |
| 6 | `established` | a certification for this framework is published with a date older than the recent window | that date |
| 7 | `no-evidence` | every source for this account was read cleanly and none mentions this framework, a role from the vocabulary, or a statement of intent | the read date |

Rules that keep the order honest:

- **`unreadable` and `no-evidence` are different answers.** One means the skill could not look; the
  other means it looked and found nothing. Never merge them.
- **A posting that names no framework attaches to every in scope framework the account has no
  published certification for.** If the account is certified on all of them, the posting is reported
  as a note on the account, not as a stage.
- **Only a date written beside the framework mention, or the date of the account's own announcement
  of it, dates a certification.** A copyright year, a "last updated" stamp or a blog index date is
  not one.
- **Third party pages never place an account.** A vendor's customer list, an auditor's case study or a
  directory badge may be quoted as a note. The account's own domain, its own job postings and its own
  announcements are the evidence.
- **Because the order runs top down, an in progress statement outranks a certification badge on the
  same page.** That is deliberate: a badge on a page that also says "in progress" is usually the Type I,
  and the account is still inside its window.

**The account's headline stage** is the one the installer's mapping ranks most actionable, with ties
broken by the most recent date. Without a mapping, the headline is the most recently dated stage and
the next move column stays empty. Every per framework row ships either way.

## Step 3: Free reads before anything paid

Everything in this step runs in this conversation at zero Clay credits, using the free HTTP utility
(`http-api-v2` in the August 2026 catalogue) or the agent's own fetch tool. Send a normal browser
`User-Agent` header, because some sites refuse requests without one.

1. **Homepage probe.** GET `https://<domain>/`. Record the HTTP status and the final URL after
   redirects. A redirect to a different registrable domain is recorded as a possible acquisition or
   rebrand, and the row continues on the new domain only if the installer agrees at Step 4. A DNS
   failure or a timeout marks the row `unreadable` for now.
2. **Trust page candidates, in this fixed order:** `/security`, `/trust`, `/trust-center`,
   `/compliance`, `/security-and-compliance` on the account's domain, then the `trust.` and
   `security.` subdomains, then any homepage link whose text or URL contains `trust`, `security` or
   `compliance`. Fetch every candidate; reading all of them is free.
3. **Served content gate.** A 200 response is not a page until it passes three tests: its title is
   not the homepage title, its body does not read as a not found page, and its visible text runs to
   more than a few sentences. A response that fails the gate counts as absent, not as empty evidence.
4. **Rendered portals.** Some hosted trust portals ship an empty shell and load everything with
   JavaScript. A candidate that returns 200 with a script bundle and almost no visible text is marked
   `rendered, not read`. Step 4 offers a paid render for these rows; it never happens by default.
5. **Read the statements.** For each in scope framework, find every sentence on the account's pages
   that names it and classify it as a certification claim, an in progress claim, an intent claim, or
   a mention only (a blog post explaining the framework is a mention). Quote the sentence. Take a date
   only from the same sentence or the line beside it.
6. **Free placement.** Apply Step 2 to what the free reads found. A framework placed as
   `in-observation`, `recently-certified` or `established` on a dated first party statement is
   finished and earns no paid call.

The free pass therefore decides which accounts earn paid calls; nothing is paid by default.

- **A job lookup** runs for an account when at least one in scope framework has no published
  certification for it and the installer's mapping treats `preparing` as worth acting on.
- **A news lookup** runs for an account with a `certified-undated` framework, or with no trust page
  at all, because the account's own announcement is the remaining way to date it.
- **A render** runs only for a `rendered, not read` page, and only if the installer approves it.

## Step 4: Ten rows, then one gate

Before anything bills, send one message that carries all of the following, then stop and wait:

1. **The batch.** Ten accounts from the free pass, in full: every page read, every quoted
   statement, the stage so far. Include at least one account the free pass could not place, so the
   installer sees a failure as well as a success.
2. **The plan.** How many accounts earn each paid call and why, from the rules at the end of Step 3,
   for example *"142 job lookups (no certification published for at least one framework), 18 news
   lookups (certified, undated), 6 renders (portal shell)"*.
3. **The price.** For each function, the live `paymentType` and declared cost read in Step 0, times
   the row count, and the total against the budget ceiling. Say plainly that a lookup that finds
   nothing can still bill. If a function bills per result rather than per call, say so and pass the
   smallest result cap that still answers the question. A function on the installer's own connected
   account may cost no Clay credits at all; say that instead of quoting a number that does not exist.
4. **The writes.** *"This run writes nothing to your CRM or any other system. Output goes to the
   conversation"*, or *"to one CSV at the path you named"*.
5. **The ask.** Approve all of it, a subset, or none. The free results are delivered either way.

Stop a second time only if the first ten paid calls reveal something the plan did not anticipate: a
job lookup returning postings for a different company more than once, a cost per call above what
Step 0 read, or a row count far off the plan. Say which one happened and ask again.

## Step 5: Paid evidence, only on the rows Step 4 approved

Read each function's live schema before its first call. The inputs below describe the job, not a
frozen parameter list, and the names given are the ones the creator kit's August 2026 references
recorded, which Step 0 has already confirmed or dropped.

| Evidence | What runs | What goes in | What to verify before using it | Cost |
|---|---|---|---|---|
| **Compliance postings** | among the job posting functions whose schema accepts a company domain, a title keyword filter and a posted within N days filter, and whose output carries a posting date, the one with the lowest live cost. The August 2026 references list `theirstack-find-jobs` and `cpj-find-lists-of-jobs` among them | the account domain, the approved role vocabulary as title keywords, the hiring window | the posting's company matches the account's domain; its posting date is inside the window; reposts first posted before the window are dropped | as read in Step 0, per call |
| **Certification dates** | a general news results function (`find-google-news-results` in the August 2026 references) | the company name in quotes plus the framework name, limited to the recent window where the schema allows | the result is the account announcing its own certification, on its own domain or as its own press release, and not a vendor case study, a customer list or an aggregator page. Relative dates such as "3 weeks ago" are converted against the call date, and both are kept | as read in Step 0, per call. A quiet result can still bill |
| **Rendered portals** | a rendering scraper | the trust page URL that returned a shell | run only after the free probe returned 200 for that URL, because a scraper can return a plausible body for a page that does not exist; then apply the Step 3 served content gate to its output | as read in Step 0, per page |

Two notes on postings:

- **Read the whole response.** Posting text often names the framework outright ("you will own our
  SOC 2 and ISO 27001 programs"), and that sentence is the best evidence line the digest can carry.
- **A page of postings is capped, so a count read off it is a floor.** Report "at least 3 compliance
  postings in 90 days", and never rank accounts on that number.

Then run Step 2 again on every account with the new evidence.

## Step 6: Place, and account for every row

Apply Step 2 per account per framework, then the headline rule. Count every row into exactly one of:
placed on at least one framework, `unreadable`, or `no-evidence` on every framework. The three
counts must add up to the deduped account total; if they do not, a row was dropped silently, so
find it before delivering.

## Step 7: Deliver

Per account per framework: the domain, the framework, the stage, the date that placed it and where
that date came from, the quoted evidence line, and the next move from the installer's mapping. Then
a coverage line, a spend line built from what the calls themselves reported (never a balance
difference, which other sessions can move), and the list of rows not placed with the reason for each.

Say which inputs were chosen and which were defaults accepted. Say that a stage is true on its read
date: an account `preparing` today is `in-observation` within months, so a monthly re-run is what
keeps the digest honest. Then make the answer sheet offer from Declared inputs.

## Representative output

### Compliance stage digest

| Account | Framework | Stage | Dated by | Evidence | Next move |
|---|---|---|---|---|---|
| ledgerline.example | SOC 2 | preparing | job posting, 19 Aug 2026 (48 days old, window 90) | "GRC Analyst: you will own our first SOC 2 Type II audit" | reach out now |
| quillstack.example | SOC 2 | in-observation | trust page, read 6 Oct 2026 | "Type I report available on request. Type II observation period underway, report expected Q1 2027" | nurture, continuous monitoring angle |
| harborgrid.example | ISO 27001 | recently-certified | own announcement, 2 Jun 2026 (4 months old, window 12) | "Harborgrid is now ISO 27001 certified", on the company's own blog | skip |
| tallyforge.example | SOC 2 | certified-undated | nothing dated it | a SOC 2 badge on its security page, no report date beside it, no announcement found in 12 months | ask about audit timing in discovery; do not lead with it |
| corvel.example | none | unreadable | nothing | homepage timed out twice; every trust page candidate failed to connect | check by hand, or drop |
| mintpaper.example | SOC 2 | no-evidence | all sources read, 6 Oct 2026 | no trust page; no compliance postings in 90 days; no announcement in 12 months | nothing visible yet |

The stages are the seven in Step 2 and no others. "Unreadable" means the skill could not look;
"no-evidence" means it looked and found nothing. The next move column is copied from the installer's
own mapping, not decided by the skill.

### Coverage and spend line

186 accounts after dedupe · 171 placed on at least one framework · 7 unreadable · 8 no evidence on
any framework · 5 trust portals left unread (render not approved) · 151 job lookups and 25 news
lookups run · 55.2 credits reported by the calls.

## What this skill does not claim

- It has never been run end to end in a live Clay workspace, so there is no measured cost, run time or hit rate behind it.
- The function names and filters it relies on come from the creator kit's August 2026 references rather than from a catalogue read by the author, which is why Step 0 re-reads them on every run.
- The three to twelve month observation period is the common range in practice, not a rule of the standard, so an installer who knows their buyers' calendars should set both windows themselves.
- A trust page states what a company says about itself; the skill does not verify that an audit is really underway or that a certificate is valid.
- No public evidence is not the same as no compliance program, because many companies prepare for audits without posting a role or a page, so "no-evidence" says only that nothing public was found.
- Statement classification is written for English pages, so a trust page in another language is reported as read but not classified.
- NDA gated reports and access request portals are never opened, so any date that lives only behind them stays unknown.

## What good looks like

A good run reads like a calendar, not a leaderboard. Every placed row names the date that placed it
and quotes the sentence that date came from, so a rep can check it in one click and open the
conversation with something the account actually said about itself. Most accounts land in
`established`, `certified-undated` or `no-evidence`, and that is normal. A digest where most of the
book is `preparing` usually means the role vocabulary is too broad, or postings from outside the
window slipped through.

A thin run looks different in specific ways: stages with no date beside them, evidence quoted from a
vendor's customer page instead of the account's own domain, `unreadable` and `no-evidence` merged
into one bucket, or a posting count used as a ranking. Any one of those means a rule in Step 2 or
Step 5 was skipped.

The test for a single row: could the installer defend it to a colleague using nothing but its
evidence column? If yes, the row is good.

## Rules

- MUST place per account per framework, with the date that placed it and a quoted evidence line; NEVER deliver a stage without its evidence.
- MUST evaluate the seven stages in the stated order, and MUST keep `unreadable` and `no-evidence` separate.
- MUST run every free read before any paid call, and MUST stop at the Step 4 gate with the batch, the price and the writes in one message.
- MUST place a stage only on first party evidence: the account's own domain, its own postings, its own announcements. Third party pages are notes.
- NEVER take a certification date from a copyright line, a page update stamp or a blog index.
- NEVER rank accounts on a posting count read off a capped page; report it as a floor.
- NEVER write to a CRM, enroll anyone, contact an account, or submit anything on a trust portal. The digest is the deliverable.

## Worked example

Ask: *"We sell a compliance automation platform. Which of these 200 Series A and B software
companies are about to go through SOC 2 or ISO 27001?"*

Interview: frameworks SOC 2 and ISO 27001. Mapping: `preparing` means reach out now,
`in-observation` means nurture with a continuous monitoring angle, everything else means skip. Role
vocabulary accepted as proposed, with "head of security" removed by the installer. Hiring window 90
days and recent window 12 months, both accepted defaults and stated as such. Budget ceiling 60
credits.

Dedupe: 200 rows to 186 domains (14 duplicates and subsidiaries, collapsed at the installer's
request). Free pass: 7 homepages failed on DNS or timeout, 74 trust pages passed the served content
gate, 5 returned portal shells. Free placement on dated first party statements: 9 frameworks
`in-observation`, 22 `established`, 6 `recently-certified`, and 31 badges with no date beside them.

Gate: ten accounts shown in full, one of them unreadable and one with no evidence. Plan: 151 job
lookups and 31 news lookups, plus 5 renders, which the installer declined. In this illustrative
workspace the gate read 0.2 credits per job lookup and 1 credit per news lookup, so the full plan was
151 × 0.2 + 31 × 1 = 61.2 credits, over the 60 ceiling. The installer cut the news lookups to the 25
accounts in their main region: 30.2 + 25 = 55.2 credits, approved. Your prices will differ; the gate
reads them live.

Result: 17 accounts `preparing` on SOC 2, each on a dated posting from the approved titles, 5 of
which named SOC 2 in the posting text. 4 more `preparing` on ISO 27001 while `established` on SOC 2.
9 `in-observation`. The news lookups dated 8 of the 25 undated badges from the accounts' own
announcements (3 inside 12 months, 5 older). 7 `unreadable`, 8 with no evidence on either framework,
and the rest `established` or still `certified-undated`. The 21 `preparing` accounts went to the rep
with their quoted postings, and nothing was written anywhere else.

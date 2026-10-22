---
name: email-to-linkedin-profile
description: |
  Build an always-on Clay workflow that turns a bare email address into a verified professional
  profile on the person's Audiences record — LinkedIn URL, first and last name, current title,
  current employer, company website and city/state/country — and links the person to a company
  record keyed on that website. Every new person added to a segment runs through it unattended:
  clean the name, find the LinkedIn URL through a gated waterfall, enrich, decide whether the
  latest role is still current, look the employer up on the web only when it is not, and write
  back only what was confirmed. Built for lists that are mostly personal webmail, where there is
  no company domain to lean on. Use whenever someone asks: enrich my subscribers from just their
  email, find LinkedIn profiles for my signups, who are the people behind these gmail addresses,
  fill in name, title and company for my audience, or attach my contacts to their companies.
  Do NOT use it to find work emails or phone numbers, to search for net-new people, to score or
  tier the people it enriches, or to dedupe or clean up records that are already populated.
category: enrich
personas: [gtm-engineer, revops]
mechanism: workflow
touches: writes-records
keywords: [plg, waterfall, crm-hygiene]
---

# Enrich a list of personal and work emails

The purpose, in the author's words: **take a messy, incomplete list of emails and find out who they
are** — their LinkedIn profile URL, their job title, their company, and what city they are in — so the
list can be made sense of.

A messy list means many records arrive with no name, only a first name, or a personal webmail address
with no company domain to lean on. So the workflow branches on what each record actually carries
instead of treating every row alike. A usable full name goes to a name-based search. Anything less
goes down an email-only waterfall. Each stage records where its answer came from. A LinkedIn URL found
by web search carries the searcher's confidence rather than a provider's name, because, as the source
code puts it, *"the provider name tells you nothing about whether a guess is right."*

The employer step carries the author's own rule: **"An honest blank is correct. A confident wrong
employer gets written to a customer record."**

## Step 0 — Posture, then a gate

**This skill reads your Audiences people and writes to them.** It writes ten person fields and a
company association, and it creates or updates company records keyed on website domain. It never
deletes a record, never clears a populated field, never sends anything, and never moves data outside
your Clay workspace.

Check, and stop if any fails. Name the component, the version and the one fix, then stop. Never
install, upgrade or fetch anything to repair the platform yourself:

| Check | Command | If it fails |
|---|---|---|
| CLI present and signed in | `clay whoami` | "Run `clay login`, then ask again." |
| Node commands exist on this version | `clay workflows nodes --help` | "This needs a Clay CLI with `workflows nodes create`. Update the Clay plugin, then ask again." |
| Audiences reachable | `clay audiences --help` | same message, naming `audiences` |

## Declared inputs

**Nothing here ships with a value.** Ask for each. Never substitute a plausible default. Where the
source workflow used a value, it is shown as *the source used*, and using it means saying so.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Trigger segment** | the Audiences segment whose newly added people should be enriched | no default — ask; the workflow fires on *member added* |
| **Source fields on the person** | which fields hold email, first name, last name, and company name (if any) | email is required; the others may be absent, and the name stage then works from the email alone |
| **Destination fields** | which person fields receive: full name, first name, last name, title, company name, company website, LinkedIn URL, LinkedIn source, city, state, country | ask per field; a field with no destination is not written |
| **Company records** | whether to create/update a company record per resolved website and link the person to it | the source does; if declined, skip Step 2 nodes 23–25 |
| **Stale-role window** | days after an end-dated role that looks like a badly recorded promotion beyond which it is withheld rather than written as current. A role that looks like a real departure is withheld at any age | the author set **365 days** (the source workflow used 180); show it as the default and ask |
| **Minimum confidence for a web-search LinkedIn match** | 0–100; below it the LinkedIn URL is left blank | the author set **70**; show it as the default and ask |
| **Masked-relay domains** | email domains with no person behind them, skipped before any paid step | the author's list: `privaterelay.appleid.com`, `duck.com`, `passmail.net`; show it and ask what to add |
| **Placeholder domains** | domains never to accept as a company website | the source used `example.com`, `example.org`, `example.net`, `unknown.com`, `notfound.com`, and `company.com` unless the company is literally named that |
| **Model account for the two LLM steps** | the connected account the agent nodes run on, if the workspace requires one | ask; never read, print or store its key |
| **Spend ceiling for a backfill** | the most credits to spend when running existing people through (Step 6) | ask before any backfill; no default |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them. **If there is no sheet, say
nothing about sheets.** At delivery, offer to save the answers to a file beside the skill: it is not
part of the skill, it holds the segment, field mappings and thresholds they chose, it means they never
answer these again, and a teammate given it beside the skill is asked only what it does not cover. It
is never submitted or published, and it holds no passwords or API keys.

## Why this is a workflow

A signal starts it — a person landing in a segment — and nobody is present when that happens. A
conversation that enriched the list once would leave every later signup blank.

## Step 1 — Resolve every capability against the live catalogue

Before building, confirm each arm exists and read its real inputs and price. Where the catalogue
disagrees with this file, **the catalogue wins.**

| Job | What the source ran (package id, action key) | Inputs that matter | Price the source saw | What to verify in the response |
|---|---|---|---|---|
| parse the email | `4299091f-3cd3-4d68-b198-0143575f471d` `extract-email-components` (Clay) | `email` | not priced in the catalogue | `$.result.domain`, `$.result.isLikelyCompanyEmail`, `$.result.address` |
| find LinkedIn from name + email + company | the managed *Person LinkedIn URL* function | full name, email (as both work and personal), company name, account domain | not listed for CLI routines — read it in the node palette | `$.result["LinkedIn URL"]` |
| find LinkedIn from email alone, arm A | `caf1e6c2-b261-4b53-a640-31a11e7ca882` `contactout-social-url-from-email` | `personalEmail` (the schema types it as a personal email) | 3 credits | `$.result.linkedinUrl` |
| arm B | `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2` `cpj-enrich-person` | `email` | 0.5 credits | `$.result.url` |
| arm C | `78593846-c4d6-481c-94bf-76b7912cf94d` `enrich-person-v2` (People Data Labs) | `email`, `requireLinkedIn: true` | 3 credits | `$.result.linkedin_url` |
| enrich the person | `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2` `cpj-enrich-person` | `email` **and** `person_identifier` = the LinkedIn URL | 0.5 credits | `$.result.org`, `.title`, `.experience[]`, `.name`, `.first_name`, `.last_name`, `.location_name`, `.country` |
| company website from a name | the managed *Company Domain* function | `Company Name` | 0.8 credits per run | `$.result.Domain` |
| write person / company | `b1ab3d5d-b0db-4b30-9251-3f32d8b103c1` `upsert-audiences-record` | see Step 2 | action execution, no credits listed | `$.result.entityId` on the company write |

```
clay workflows actions list            # confirm each actionKey resolves, read creditCost and paymentType
clay workflows actions schema <packageId> <actionKey>    # read semanticType, never the parameter name
```

**`person_identifier` wants a URL.** The schema types it as a LinkedIn URL. Feeding it an email
returns a validation error per item, and the step still looks configured.

**The email-only arms run in the source's order: A, then B, then C, with a gate after each that
stops on a hit.** That is a real waterfall, so order does change cost. Arm B is the cheapest at the
source's prices. *Proposed, not inherited:* run B first. Re-check the three prices live, put the
cheapest first, and say which order you used. Yields per arm were never measured in the source, so
cost is the only basis for the order.

## Step 2 — Build the graph

Confirm node syntax on the installed version first. **Never hardcode the command form:**

```
clay workflows create --help
clay workflows nodes --help
clay workflows nodes create --help
```

The node list, edges and every code and prompt body are in
[`references/node-graph.md`](references/node-graph.md). Build them in this order. Each node is
*name · type · what feeds it → where it goes*:

1. **Segment** · trigger, `audience_segment` on the declared segment → 2
2. **Normalize name** · agent, no web search · email, first name, last name → 3
3. **Parse email** · tool `extract-email-components` · email → 3a
3a. **Person behind it?** · code — `skip` when node 2 flagged a role address, or the email's domain
    is on the declared masked-relay list → 3b. *Added for this skill; not in the source workflow.*
3b. **Skip role and relay addresses** · conditional: `skip = no` → 4. **`endRunOnNoMatch: true`** —
    the run ends before any paid step, and nothing is written for that record.
4. **Has a usable name?** · conditional: full name non-empty **and** ≠ `Name Not Found` **and**
   contains a space → 5; default → 8
5. **LinkedIn from name** · the *Person LinkedIn URL* function → 6
6. **Function found nothing?** · conditional: URL empty → 7; default → 13
7. **LinkedIn via web search** · agent with web search · name, company, email domain, title → 13
8. **Email arm 1** · tool → 9
9. **Arm 1 found?** · conditional: URL non-empty → 13; default → 10
10. **Email arm 2** · tool → 11
11. **Arm 2 found?** · conditional: URL non-empty → 13; default → 12
12. **Email arm 3** · tool → 13
13. **Merge LinkedIn URL** · code — takes the first valid `linkedin.com/in/` URL in the order
    function → web search → arm 1 → arm 2 → arm 3, normalises it, and records its source → 14
14. **Enrich person** · tool `cpj-enrich-person` · email + LinkedIn URL → 15
15. **Resolve current role** · code → 16
16. **Needs web lookup?** · conditional: `needs_lookup = yes` **and** a LinkedIn URL exists → 17;
    default → 18
17. **Find current employer (web)** · agent with web search → 18
18. **Final company + title** · code — picks the employer, withholds stale roles, parses name and
    location, resolves the company website with a mismatch guard → 19
19. **Website missing?** · conditional: website empty **and** company named → 20; default → 21
20. **Company Domain** · function · company name → 21
21. **Resolved website** · code — cleans to a hostname, rejects placeholder domains → 22
22. **Write person** · `upsert-audiences-record`, `CONTACT`, looked up by record `id` → 23
23. **Company resolved?** · conditional: website **and** company name both non-empty → 24.
    **`endRunOnNoMatch: true`** — no match ends the run successfully, after the person is saved.
24. **Write company** · `upsert-audiences-record`, `ACCOUNT`, looked up by `domain`, writing name +
    domain → 25
25. **Attach company** · `upsert-audiences-record`, `CONTACT` by `id`, `associations|accountId` ←
    node 24's `$.result.entityId`, re-writing the company website it already holds

Every conditional except nodes 3b and 23 continues unmatched records down its default edge.

**Topology, read off the source's edges:** every conditional has exactly one rule plus a default edge.
Nodes 13, 18 and 21 each receive edges from more than one branch, and only the branch that ran
delivers a value: 13 has five incoming edges, 18 and 21 have two each. The source runs
this way. If the installed version leaves such a node pending, see the traps below. **Nothing here is
parallel.** Every path is a chain, so nothing needs a merge node beyond the three the source has.

**Where judgment lives.** Every comparison, threshold and routing decision is in a code or
conditional node. The three agent nodes do only what code cannot: read a name out of messy text,
search the web for a profile, and search the web for a current employer. **An agent node MUST NOT
route, threshold or compare.**

### Node traps — each one fails silently

- **Tool and function outputs are addressed `$.result.…`; code node outputs are `$.…`.** Agent
  outputs differ by agent kind. The source read two of its agents through `$.structuredOutputs.…` and
  the employer agent directly as `$.…`, so read each agent's real output path once before wiring
  anything downstream of it. A wrong prefix resolves to nothing, which looks exactly like a genuine
  no-match.
- **A mapped tool input needs both halves:** the source binding in the input schema *and* the
  reference in the tool's input mapping. With only one half, the action reports success and drops the
  value. The same applies to an agent's prompt variables: a `{{variable}}` with no source bound
  arrives empty.
- **A tool node does not echo its inputs.** Pin trigger fields from the trigger node, never through a
  tool.
- **A node fed by both sides of a conditional must not wait on the side that did not run.** If the
  installed version holds nodes 13, 18 or 21 pending on a skipped branch, rewire that branch's
  default through a pass-through code node. Say you did, and why.

### Writes never blank a populated field

The source writes every person field with `always_write` and `removeNullValues: true`. That combination
is only safe if a missing value reaches the write as **null**, not as an empty string. **So every code
node in `references/node-graph.md` returns `None` for an unknown value, never `""`.** Before going
live, prove it in Step 4 on a record whose title is already populated.

### Stamp the workflow

Say it out loud: *"I'm writing a line into the workflow's description so this can be traced back to
the listing."* If this installed copy carries `marketplace_slug` and `marketplace_revision`, append
`Sourced from marketplace skill: <slug>@<revision>` on its own last line, preserving any existing
description. If it does not, say *"Marketplace attribution is unavailable for this skill"* and skip
it. Never substitute the `name`.

## Step 3 — Validate the draft graph

```
clay workflows graph validate <workflowId>
clay workflows graph get <workflowId> --mode full
```

Read it back. Check: every edge, every conditional's rule and default, and every pin against the
traps above. In particular, check every prompt variable has a bound source.

## Step 4 — Test on 10 real people

Pick 10 people from the segment whose destination fields are **empty**, so the test can write but
has nothing to overwrite. Add **one** person whose title is already populated, to prove a blank never
replaces it. Then run the **draft** on those records. Confirm the form first with
`clay workflows runs test --help`; on the version measured it was
`clay workflows runs test <workflowId> --trigger <triggerId> --record-ids <ids>`.

Show the installer, per person: the LinkedIn URL and its source, name, title, company, website,
location, and which branch ran. Then show the populated-title person's title, before and after.
**Do not judge a code node by an empty step dump.** Verify through what landed on the record.

## Step 5 — One gate, then go live

One message, carrying everything:

- the 10-row result, and anything surprising in it;
- the cost per person, **measured from the test** rather than multiplied from list prices, because
  the branches decide which arms run. Then the same figure times the segment's expected weekly adds.
  For scale only: the author's one 50-record test on 2026-10-16, against subscribers with no last
  name and no LinkedIn URL, spent about 1.22 credits and 2.46 action executions per record. It found
  a LinkedIn URL and last name for 32% and a company for 44%. Never quote those figures as the
  installer's;
- exactly what will be written: these destination fields, on every person who enters the segment from
  now on, plus a company record created or updated per resolved website;
- the ask: *publish and turn on the trigger?*

Then stop and wait. Only on a yes: publish, and enable the trigger.

## Step 6 — Existing people (optional)

The trigger fires only when someone is **added**, so people already in the segment never run. To
backfill, re-run them through the **published** version in batches. On the version measured,
`--record-ids` took at most 50 ids per call. Confirm with `--help`.

This bills. Ask for the spend ceiling first. Run **one** batch, report its real credit spend from the
balance before and after, and then ask before the rest. Stop at the ceiling. Exclude role and alias
addresses and masked relays from the batch: no person sits behind them.

## Representative output

### Enriched person record

| Email | LinkedIn URL | LinkedIn source | Name | Title | Company | Company website | City | Country |
|---|---|---|---|---|---|---|---|---|
| ana@gmail.com | linkedin.com/in/ana-example | ContactOut | Ana Example | Head of Growth | Northwind | northwind.com | Austin | United States |
| j.doe@contoso.com | linkedin.com/in/jdoe-example | Claygent (confidence 82/100) | Jo Doe | — withheld: role ended | — | — | Leeds | United Kingdom |
| k.lee@gmail.com | — | — | Kim Lee | — | — | — | — | — |

A dash means nothing was confirmed and nothing was written. That is the design, not a failure.

## What this skill touches

- **Reads** — Audiences people in the declared segment, and the action catalogue
- **Writes** — the declared person fields; company records keyed on website domain; the person-to-company association; one provenance line in the built workflow's description
- **Never** — deletes a record, clears a populated field, sends a message, or moves data outside the workspace
- **Halts** — Step 4 sample-review, Step 5 spend-approval, Step 5 write-approval, Step 6 spend-approval

## What this skill does not claim

- That "leave it blank rather than write something wrong" governs every field. The author stated that rule for the employer step. Elsewhere, the website guard and the stale-role withholding behave consistently with it, but that was not stated as a principle.
- How often each arm finds a profile. The source records which arm won, but nothing in it measures the yield of each.
- That the source's arm order is the right one. It was not chosen by price, and running the cheapest arm first is a proposal.
- How many records the role-and-relay skip saves on a given list. The author's own test matched `system@` to a profile named "System Hacked", but the skip rate was not measured.
- That 365 days is a measured window. The author chose it for this skill, replacing the source's 180.
- That 70 is a measured cut-off. The author chose it for this skill; the source workflow itself wrote matches at any confidence.
- The cost of the three agent steps. They carry no catalogue price, and the per-person figure has to come from the Step 4 test.
- That the managed *Person LinkedIn URL* function exists in every workspace. It was not listed as a callable routine when read.
- In the source, two agent prompts referenced variables that had no source bound (the name field going into name cleanup, and all four inputs going into the LinkedIn web search). This skill binds them. The source's own results therefore came from agents that saw less than their prompts describe.
- The source's company-website guard trusts a work-email domain only when the provider named a current role, or when the domain's root appears in the company name. That rule is kept as written and was not measured.

## What good looks like

A person enters the segment and, within minutes, their record carries a LinkedIn URL with its source,
a title and employer that are current, or nothing at all where nothing was confirmed. No populated
field was ever blanked. Every company record has a website that belongs to that company.

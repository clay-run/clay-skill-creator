---
name: clay-org-chart-builder
description: |
  Build an interactive org chart of a target account's current C-Suite and VP leaders from Clay
  people search, with reporting lines inferred from titles and always labeled as inferred, a Needs
  review tray for anyone with no evidence of a manager, drag-and-drop manager corrections, focus
  mode, "new in role" badges from each leader's role start date, a recent-news section, on-click
  email and mobile lookups through the viewer's own Clay connection, and optional styling in the
  seller's own brand. Use whenever someone asks: org chart for this company, map the leaders at X,
  who runs what at this account, build an account map, show me the exec team at X, who reports to
  the CTO there, which leaders are new in their role, add more people to the X org chart. Works from
  a company name or domain. Do NOT use it to find one named person's email or profile, to build a
  prospect list across many companies, to enrich or score a whole account list, or to write
  anything to a CRM or sequence.
mechanism: functions
touches: writes-own-output
---

# Clay Org Chart Builder (titles come from Clay; reporting lines are inferred and labeled)

The insight: **Clay's people search returns titles, locations and role start dates, and never who
reports to whom.** Checked on the live response for a 1,500-person software company: every leader
record carried a current title and a start date for that title, and none carried a manager. So an
org chart built from it has two kinds of fact in it, and the whole design keeps them apart: the
people and titles are Clay's, and every line between them is an inference from titles and functions
that the page labels as inferred, gives a reason for, and lets the viewer correct. People with no
evidence for a manager are not parked under the CEO to make the chart look complete; they wait in a
Needs review tray.

The output is one self-contained page with two views:

- **Org chart:** the top executive, with their reports grouped into function lanes. Lines are dashed
  when inferred, dotted amber when low confidence, and solid when the viewer set them. Anyone can be
  dragged onto someone else's tile to change who they report to.
- **By level:** C-Suite and VP Leadership groups.

Each tile opens a side panel with the reason for its line, the buying role and level (editable), Clay
details, recent news, and "Find email / Find mobile with Clay" buttons that run only when the viewer
clicks and confirms. `references/page-behavior.md` describes every control on the page.

Do not start a step before the steps above it have their answers. If a declared input is missing, ask
for it — never assume a default and continue.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Target company** | a company name, or better a website domain | no default — ask. A bare name is resolved and confirmed before any people search (Step 4) |
| **Branding choice** | yes or no: style the page in their own company's brand | ask. No means the default style (off-white page, purple accents) |
| **Their website** | the seller's own site, only if they chose branding | no brand is extracted; the default style is used and the reply says so |
| **First-build size** | how many leader records to pull on the first build | **30 is the author's default and must be stated**; never more than 50 on a first build |
| **Mobile lookup function** | a function in their Clay workspace that finds a mobile number, picked from their own function list (Step 5) | the page offers email lookup only and the reply says so |
| **News window** | how far back the news section looks | **3 months is the author's default and must be stated** |
| **Clay workspace** | whichever workspace their Clay connection is signed in to | confirmed at Step 0, never assumed |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question. At delivery, offer to save the durable answers back (brand website, mobile
lookup function, build size, news window; identifiers only, never a token or a password), private and
never published — and phrase the offer so it explains itself: *"want me to save these settings to a
file, so the next chart you or a teammate builds doesn't ask them again?"* The target company changes
every run, so it is never saved.

## What this skill touches

- **Reads** — Clay company search and people search for the one company you name (current title,
  location, LinkedIn URL, role start date); the list of enrichment functions in your Clay workspace,
  read only; the computed styles of your own website, if you chose branding; public news pages, through
  web search, for the news section.
- **Writes** — its own output only: one self-contained HTML page (published as a private page where the
  host can publish pages, otherwise saved as a file). Nothing in Clay, a CRM, a table or a sequence.
- **Never** — runs email, phone or work-history enrichment while building; writes to a CRM, table or
  sequence; contacts anyone on the chart; uses your workspace's own CRM record fields for anyone;
  puts Clay credentials in the page, a log or a URL.
- **Halts** — Step 2 spend-approval, Step 4 other.

Contact lookups on the finished page are the viewer's own action: each one runs through the viewer's
own Clay connection, only after they click and confirm an inline notice that it uses their Clay
credits.

## Step 0 — Check the platform, say where the work runs

1. Confirm the Clay tools are available: company search, people search, load more search results,
   current workspace, and list functions. If they are deferred, load them and read their full
   descriptions, especially the search grammar and the people and company field lists.
2. Call the current-workspace tool (or `clay whoami` where the Clay CLI is installed) and tell the user
   which Clay workspace the search will run in, in one line.
3. Check that `python3` runs; the page is built by `scripts/orgatlas.py`, which needs only the standard
   library.

If any check fails, say which component is missing and the one thing that fixes it (connect the Clay
connector, or sign in with `clay login`), then stop. Do not install, upgrade or fetch anything to repair
it, and never continue with other data.

Say the posture in two sentences before Step 1: *"This reads Clay's search results for one company and
writes one org chart page. It never writes to Clay or a CRM, and it runs no email or phone lookups while
building."* All classification, deduping and line inference runs locally in the script, so it costs
nothing; only the Clay searches can use credits.

## Step 1 — Ask which company

If the user has not named the target company, ask: "Which company do you want to build the org chart
for? A website domain helps me find the right one." Wait for the answer.

## Step 2 — Set expectations and ask about branding (the spend gate)

Send this notice, filled in, **together with** the branding question, as one message:

> I'll search Clay for current C-Suite and VP leaders at **{Company}**: CEOs and other chiefs,
> presidents, EVPs, SVPs and VPs. Former employees, directors, advisors, consultants and board-only
> seats are left out. **The first build includes up to {first-build size, default 30} people**, and you
> can add more later. The search charges per result at your workspace's search pricing, and it runs as
> soon as you answer below. It writes nothing anywhere except the org chart page.

Question: **"Do you want the org chart styled with your company's brand?"**

- **Yes, use my brand** — then ask for their company website.
- **No, use the default style**.

Answering this question is the go-ahead for the search. No search runs before it.

## Step 3 — Extract the seller's brand (only if they said yes)

The brand is the **user's** company (the seller), not the target account.

1. Open the homepage with a browser tool that can run JavaScript and read computed styles: the main
   call-to-action buttons' `backgroundColor`, the `fontFamily` of `h1` and `body`, hex custom properties
   on `:root`, Google Fonts `<link>` tags and the header logo. A page-to-markdown fetch drops the CSS,
   so use one only when no browser is available. Take only what is present:
   - **Brand name:** `og:site_name`, the `<title>` prefix, or the logo `alt` text.
   - **Primary color,** in order: the main call-to-action background when it has a hue; custom
     properties that name the brand (`--primary`, `--brand`, a named swatch); `<meta name="theme-color">`.
     Ignore black, white, greys and pale tints; if the only colored button is a pale tint, take the
     strongest saturated brand swatch instead.
   - **Fonts:** the `family=` values of Google Fonts links, else the first family in the heading and
     body declarations.
   - **Logo:** only inline `<svg>` markup or a small SVG file returned as text, base64-encoded as a
     `data:image/svg+xml;base64,...` URI. Otherwise leave it empty and the page shows the brand name as
     a wordmark. Do not download binary images.
2. Fonts must come from Google Fonts. If the brand font is not there, pick the closest Google font and
   say you substituted it.
3. Write `theme.json`:
   ```json
   {"brandName":"Acme","primary":"#0A66FF","fontHeading":"Space Grotesk","fontBody":"Inter",
    "googleFontsUrl":"https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600;700&display=swap",
    "logoDataUri":null,"source":"acme.com"}
   ```
   The renderer adjusts the primary color so text meets WCAG AA contrast in light and dark mode; mention
   it if the adjustment is visible.
4. If the site cannot be read or yields no usable color, say so in one line and continue with the
   default style. Branding never blocks the build.

## Step 4 — Resolve the target company

1. **Domain known:** company search with `select from companies where domain = "<domain>"`.
2. **Only a name:** use the company-name field the company-search schema lists, exact match first, then
   a looser operator from the schema, with a small limit such as `limit 5`.
3. **One clear match:** use it.
4. **Several:** show up to 5 choices with name, domain, industry and location (whatever Clay returned)
   and ask the user to pick. Never auto-pick between plausible matches. This is the Step 4 halt.
5. **None:** say so and ask for the domain. Never guess a domain.
   - A domain can return the parent plus an acquired unit that shares it (for example "Initech
     Analytics (acq. by Initech)"). When the extra record is clearly labeled as acquired or a
     subsidiary, use the parent and say so in one line. Otherwise ask.
6. Save `company.json` with only values Clay returned: `{"name":..., "domain":..., "clayCompanyId":...,
   "industry":..., "location":..., "linkedinUrl":...}`. From here on pass the company's **LinkedIn
   company URL** as the identifier, never the bare name, because a shared domain pulls in the
   subsidiary's people. Use the domain only if Clay returned no LinkedIn URL.

## Step 5 — Search current leaders

Call people search with `companyIdentifiers: ["<resolved LinkedIn company URL>"]`, which filters by
current employer. Start from this query, then adjust field names and operators to match the people
schema exactly:

```
select from people where experiences.any(is_current = true and (
  job_title contains ("chief", "president", "ceo", "cfo", "coo", "cto", "cio", "cmo", "cro", "cpo", "chro", "clo")
  or job_title is_similar_to ("Vice President", "Executive Vice President", "Senior Vice President")
)) limit 30
```

- Use only fields and operators that appear in the schema you can see this session. Never invent one.
- If the schema offers a seniority field for current experiences, add it as an OR branch for VP and
  C-level seniority, and record each person's seniority so "Head of" titles can qualify as VP.
- **First build:** the declared first-build size (default 30). A page returns at most 20 contacts, so a
  first build normally needs one load-more call with the returned `taskId` while `hasMore` is true.
  Never fetch more than 50 records on a first build.
- Keep every search page's `taskId` and record which one each contact came from; the page's email
  lookup and Step 8 use it.
- **Mobile lookup setup:** list the workspace's functions (read-only, no credits) and look for one that
  finds a mobile or phone number.
  - Prefer one named like "Mobile Phone Number", then "Get Phone Number". Its required inputs must be
    fillable from: the person's `linkedinUrl`, `name`, `companyName`, `companyDomain`, `email` (the
    sourced email, if any), the company's `companyLinkedinUrl`, or `none`.
  - **If one fits,** write `enrich.json`:
    `{"server":"Clay","email":true,"phone":{"id":"<function id>","name":"<function name>","inputs":{"<input name>":"<field>"}}}`.
    Show the user which function and input mapping you picked, and let them correct it.
  - **If none fits,** write `{"server":"Clay","email":true}` and say in one line that the page will
    offer email lookup only.
  - **Never** pick a function whose description says it writes to a CRM, sequence or outbound tool.
- **Errors:** report Clay's message in plain words, with no raw payload or credential. Auth or
  connection: reconnect Clay. Quota or credits exhausted: the workspace is out of search credits. Rate
  limited: wait a minute and ask again. Anything else: a general Clay error. Never retry in a loop and
  never substitute other data.

## Step 6 — Normalize, classify and infer lines

1. Convert each returned contact into this shape, **copying only fields Clay actually returned**:
   - `profile_id` → `clayId`, `name` → `name`, `latest_experience_title` → `title`, `url` →
     `linkedinUrl`, `location_name` → `location`, `entityId` → `clayEntityId`, the page's `taskId` →
     `clayTaskId`.
   - `latest_experience_start_date` (`YYYY-MM`) → `roleStartDate`. This is when the person started
     their **current title**, so it can be a promotion rather than a new hire. Keep it only when
     present; never estimate it.
   - `isCurrent: true` when `latest_experience_company` matches the resolved company; `false` when it
     names another company. Use the current title **at the resolved company**, not the headline.
   - **Ignore `audienceFields` entirely.** That block is the workspace's own CRM record, and its titles,
     emails, phones and "no longer at company" flags often describe a previous employer.

   ```json
   {"clayId":"...", "name":"...", "title":"<current title at this company>", "linkedinUrl":"...",
    "location":"...", "roleStartDate":"YYYY-MM", "email":"<only if already in the result>",
    "seniority":"<only if returned>", "isCurrent": true}
   ```
   Save the list as `raw.json`.
2. Run `python3 scripts/orgatlas.py normalize --raw raw.json --company company.json --out people.json --limit 30`
   (the limit is the declared first-build size). It is deterministic and free:
   - **Excludes** former employees, directors and below, advisors, consultants, assistants and
     board-only seats, "Head of" titles without VP seniority, and field or deputy C-titles such as
     "Field CTO", which are not the company's C-Suite seat.
   - **Classifies level:** "Chief … Officer", C-level acronyms and President are C-Suite; EVP, SVP, VP
     and Global VP are VP.
   - **Maps function** from the title to one of: Executive, Revenue, Sales, Marketing, Finance, Product,
     Engineering, People, Legal, Operations, Strategy, Customer, Other.
   - **Dedupes** by Clay ID, then normalized LinkedIn URL, then normalized name plus company domain.
   - **Infers reporting lines** as `reportsTo: {id, basis, confidence}`, in this order, first match
     wins:
     1. The CEO, or else the President, is the top of the chart.
     2. A Chief Accounting Officer reports to the CFO; a CISO to the CIO, or else the CTO. Medium.
     3. Other C-Suite report to the top executive. Medium.
     4. A VP reports to the closest more-senior VP in the same function (EVP, then SVP, then VP), or
        else to that function's C-level head. Medium.
     5. An EVP with no same-function leader goes under the top executive. Low.
     6. Anyone else is `unplaced` and goes to the Needs review tray.

     Every line points to someone more senior, so the chart cannot contain a cycle.
   - Prints a report of counts, exclusion reasons and line confidence. Keep it for the reply.

## Step 7 — Recent news about these leaders

Find recent news that names the charted leaders. This is web search only, not Clay, so it costs no
Clay credits. It is the one web-sourced section, it is labeled as such on the page, and nothing in it
ever changes a person, title or line.

1. **Search** with the host's web search, in one turn where possible: the company plus "news" with the
   current and previous two months; the top executive by name; each other C-Suite leader by name with
   the company; any VP whose name is distinctive enough to search reliably. Prefer the most recent
   results the search offers.
2. **Verify every item** by fetching it: read its publication date and which charted leaders it
   actually names or quotes. Keep an item only when its date is inside the declared news window
   (drop undated items), it names at least one charted person as the same person, and it is a news
   article, a company press release or newsroom post, or a byline the leader wrote. Skip people-search
   and profile sites and job posts. For a syndicated press release, keep the original and list copies
   under `alsoAt`.
3. **Write `news.json`.** Summaries are one or two sentences in your own words: never copy article text
   beyond a few words, and never put words in a leader's mouth.
   ```json
   {"checkedAt":"YYYY-MM-DD","windowMonths":3,"items":[
     {"date":"YYYY-MM-DD","title":"<headline>","url":"https://...","source":"<outlet>",
      "kind":"News | Press release | Byline","summary":"<your words>",
      "people":["<people.json id>"],"alsoAt":[{"source":"<outlet>","url":"https://..."}]}]}
   ```
   The renderer drops any item with no date, no https link, no title, or no one on the chart.
4. If nothing qualifies, write `news.json` with an empty `items` list; the page says no news named these
   leaders.

## Step 8 — Build and deliver the page

1. Run `python3 scripts/orgatlas.py render --people people.json --company company.json [--theme theme.json] --enrich enrich.json --news news.json --out "<Company> Org Chart.html"`.
   The template is `scripts/orgchart_template.html`. The default output is a page body with no
   doctype, html, head or body tags, for hosts that publish pages; add `--full-document` for a
   standalone file.
2. **Where the host can publish a private page,** publish it with a chart icon, a one-sentence
   description, and the connector capability the lookups need, naming the Clay connector and exactly
   these tools: add contact data points, get task context, search contacts by name, and — only when
   `enrich.json` has a phone function — run function direct. On a republish, keep the stored
   capability unless the tool list changes.
3. **Otherwise** save the full-document file to the user's outputs or connected folder. The chart,
   tray, editing and news all work; the lookup buttons explain that they need the page opened where the
   Clay connector is available.
4. Reply briefly: leaders found (C-Suite and VP counts); what was excluded, from the report; the
   workspace searched; how many people are in Needs review and how many lines are low confidence; news
   items found and whom they mention; that lines are inferred from titles, not supplied by Clay; that
   dragging a tile changes a manager and edits are saved in the viewer's browser; that the lookup
   buttons use the viewer's Clay credits; and that they can say "add 20 more to the {Company} org
   chart". Then offer to save the durable settings (see Declared inputs).

## Step 9 — Adding more people later

1. Recover the dataset: reuse `people.json`, `company.json` and `theme.json` from the same session, or
   read the published page back and run `python3 scripts/orgatlas.py extract --html <file> --outdir .`,
   which recovers all three.
2. Get the next batch: load more with a `taskId` from this session if one is still valid; otherwise
   re-run the Step 5 query with a limit of current total plus the requested amount, and deduping drops
   the people already charted. Default to 20 more if no number is given, and say it uses Clay credits
   before running it.
3. Merge: `python3 scripts/orgatlas.py normalize --raw raw_more.json --company company.json --existing people.json --out people.json --limit <N more>`.
4. Re-run Step 7 so the news covers the new people, re-render with the same theme, and republish to
   the same page so the link is unchanged. Viewer edits carry over, including manual manager changes.
5. Report how many were added, and say plainly if Clay had no more qualifying leaders.

## Representative output

### Reply after a first build

> Built the Northwind Robotics org chart from Clay (workspace: Acme GTM): **25 leaders — 7 C-Suite,
> 18 VP.** Left out 5: 2 field CTO titles, 1 former employee, 1 executive assistant, 1 non-VP title.
> 10 people are in **Needs review** because Clay's data has no same-function leader for them, and 1 line
> is low confidence. The news section has 6 items from the last 3 months, naming 4 leaders. Reporting
> lines are inferred from titles, not supplied by Clay. First build size 30 and news window 3 months are
> the defaults.

### Coverage strip on the page

| Leaders | Champions | Exec buyers | Not yet classified | Contacts found | Need a manager | Lines you set | New in role (6 mo) |
|---|---|---|---|---|---|---|---|
| 25 · 7 C-Suite · 18 VP | 0 | 0 | 25 | 0 | 10 | 0 | 7 |

### Tiles and their lines

| Person | Title | Lane | Reports to | Line | Why |
|---|---|---|---|---|---|
| Dana Whitfield | Chief Executive Officer | top of chart | — | — | most senior title in Clay's results |
| Omar Reyes | Chief Technology Officer · New · 4 mo | Engineering & Security | Dana Whitfield | inferred, medium | C-Suite executives usually report to the CEO |
| Lena Park | VP, Platform Engineering | Engineering & Security | Omar Reyes | inferred, medium | same function (Engineering) as the Chief Technology Officer |
| Priya Nair | VP, Demand Marketing | Needs review | — | none | no same-function leader in this dataset |

### A news card

| Date | Outlet | Type | Headline | Names |
|---|---|---|---|---|
| Aug 4, 2026 | Northwind newsroom | Press release | Northwind launches autonomous fleet monitoring | Omar Reyes |

## What this skill does not claim

- It does not claim any reporting line is true. Every line is inferred from titles and functions,
  Clay supplies no manager data, and the page labels each line with its reason and confidence.
- It does not claim to find every leader. A first build is capped (30 by default), and in the one
  company it was tested on, a later search found three current VP-and-above leaders the first 30
  records did not include.
- It does not claim the email and mobile lookups parse every Clay result correctly. They were built
  against the documented shape of task results and tested against simulated responses, not against a
  live lookup result.
- It does not claim the lookups work everywhere. They need the page opened on a host that grants the
  page the viewer's Clay connector; elsewhere the page is read-only.
- It does not claim a "new in role" badge means a new hire. It uses the start date of the current
  title, so a recent promotion also counts.
- It does not claim the news section is current after the build. It is searched once at build time,
  shows the date it was checked, and is refreshed only by rebuilding.
- It has no measured credit cost or run time. It has been run end to end on one company with one brand.

## What good looks like

- **Every line on the chart carries its basis.** Opening any tile shows why its line exists and at what
  confidence, and nothing without evidence sits under the CEO; it is in Needs review instead. A chart
  where every VP hangs off the CEO with no tray is the failure this skill exists to avoid.
- **Counts reconcile.** Leaders shown plus exclusions equals records returned, and the reply names each
  exclusion reason. A good run on a mid-size company typically shows most C-Suite placed, VPs grouped
  into lanes, and a Needs review tray that is honest rather than empty.
- **Titles are current and at the right company.** No former employees, no subsidiary's people, no
  field or deputy C-titles counted as the company's C-Suite.
- **The news is dated and linked.** Every card has a date inside the window, an outlet and a link, and
  names someone on the chart. Zero items is a valid result and the page says so.
- **A thin run is visible as thin.** Few leaders, many exclusions or a large tray mean Clay's data for
  this company is sparse; the reply says that plainly rather than padding the chart.

## Rules

- **NEVER** state a reporting line as fact, as Clay data, or as confirmed. Never "improve" the
  inference with web search or memory.
- **NEVER** run email, phone or work-history enrichment while building the chart. Contact lookups happen
  only from the page, one person at a time, after the viewer confirms.
- **NEVER** search before the user has answered the Step 2 message, and never re-run a search just to
  check.
- **NEVER** fill a gap with a guess: every person, title, location, start date and email comes from
  Clay's results, and a missing field is shown as "Not returned by Clay".
- **NEVER** use `audienceFields` or any other CRM-record data for a person.
- **NEVER** auto-pick between plausible company matches.
- **NEVER** put Clay credentials in the page, a log or a URL.
- **NEVER** present demo data as Clay results. `--demo` exists only for testing the page, labels every
  record Demo, and is never a fallback when Clay fails.
- **ALWAYS** keep the news section labeled as web-sourced, dated and linked, and never let it change a
  person, title or line.

## Worked example

Ask: "Org chart for northwind-robotics.example, styled in our brand, acme.example."
Step 0 confirms the Clay workspace. Step 2 sends the notice and branding question; the user says yes and
names their site. Step 3 reads the site's computed styles: primary `#3859F9`, a geometric sans heading
font available on Google Fonts, no inline logo, so the wordmark is used. Step 4 resolves the domain to one
company and saves its LinkedIn company URL. Step 5 returns 20 records, then 10 more with load more;
the workspace has a mobile-number function taking a LinkedIn URL, which the user confirms. Step 6: 30
records → 25 leaders (7 C-Suite, 18 VP), 5 excluded (2 field CTOs, 1 former employee, 1 assistant, 1
non-VP title); lines: 13 medium, 1 low (an EVP with no same-function leader), 10 unplaced. Step 7 finds 6
dated, verified items naming 4 leaders and drops 2 undated ones. Step 8 publishes the page privately and
replies with the counts above.

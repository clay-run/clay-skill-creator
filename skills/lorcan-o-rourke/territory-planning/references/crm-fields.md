# CRM setup (Step 5)

Clay cannot create CRM fields, so the skill does it through the Salesforce CLI. `scripts/sf_setup.py`
reads the confirmed rubric and creates everything the later steps write to. Requires
`sf org login web -a <alias>` once (login.salesforce.com for a Developer Edition, test.salesforce.com for
a sandbox). Never run it against production on a first pass.

The script lives under the skill folder, not the project, and the project directory is where `rubric.md`,
`reps.csv` and the rules file sit. So every command below is run from the project with the skill's
absolute path. Set it once: `SKILL="<absolute path of the folder that holds this skill's SKILL.md>"` and
call `"$SKILL/scripts/sf_setup.py"`. A relative `scripts/sf_setup.py` fails with "no such file" from the
project directory.

## What it creates

| Where on the page | Fields |
|---|---|
| **Account Details** (the standard section; an untouched Developer Edition labels it **Account Information**, and the script finds either) | Account Fit Score (number 0-100), Fit Score Summary (the one-line reason), and the default enrichment values: Sales Team Headcount, Ops Team Headcount, Headcount Growth (12m %, Number(7,1)), Last Funding Round, Last Funding Amount (USD), Last Funding Date, GTM Motion, Business Model, Entity Type, Tech Stack, Clay Last Enriched, plus any `--extra-fields` the rubric needs |
| **Fit Score Components** (new section) | one `<Factor> Score` field per rubric factor, two columns |
| **Territory** (new section) | Account Fit Grade, Segment, Sub-region, Proposed Owner (lookup to User; the carve workflow's proposal, Owner untouched until approval), Carve Status, Carve Reason, Engagement Score (number 0-100, Step 8: points per signal event, weekly decay), Last Signal (text: type, headline, points), Last Signal Date, Open Opportunities (roll-up count of open opps), Territory Plan (checkbox: in scope), Is Competitor, Scoring Status, Rubric Version |

The enrichment values in the first row are a default, not a contract. They fit a rubric built from the
starter template (sales and ops headcount, growth, funding, GTM motion). Rubrics differ per customer: a
fintech rubric weighted Institution Type and Compliance team headcount, an industrial one Sector and
Plant headcount, a PLG one Engineering team headcount. The value behind each of those factors needs its
own field, or the rep sees a score with nothing to back it up. Pass them with `--extra-fields` (below),
once per field, in the same `fields` run; the script creates them in Account Details and grants them on
the permission set. Default fields a rubric never writes stay blank; say so in the delivery rather than
leaving the team to wonder.

The carve workflow's code node (`scripts/carve_node.py`, Step 7) and `scripts/carve_summary.py` read
the fields this script creates, by these API names: the score, grade and scoring status, the segment
and carve fields, Proposed Owner, Open Opportunities, Is Competitor, Entity Type, Tech Stack, the
headcount values and the standard `NumberOfEmployees`, `Industry`, `Billing*`, `Type`, `ParentId` and
`OwnerId`. The Step 8 workflows (`scripts/engagement.py`) write `Engagement_Score__c`, `Last_Signal__c`
and `Last_Signal_Date__c` and nothing else; the carve gates read `Engagement_Score__c` for the re-entry
rule. Rename nothing by hand.

Plus: permission set "Territory Planning" (assigned to the admin), list view "Territory Plan" (with the
Proposed Owner column), and two reports: **"Territory – Proposed Books"** grouped by Segment then
Proposed Owner over Proposed and Assigned accounts, with record count and average fit, which is what
the approver reads before any owner changes; and **"Territory – Accounts by Owner"** grouped by Segment
then Owner, the fairness check after the write and what a manager opens when a rep says their
territory is bad.

Field API names follow the rubric: "GTM Motion" → `GTM_Motion_Score__c`, "Headcount (Size)" →
`Headcount_Size_Score__c`. The `plan` output is the authoritative list.

## What the workflow writes, and when

Step 3 ends at the Score node and the two Audiences upserts. The Salesforce node (`update-object`, inputs
`recordId`, `object_type` = Account, `object_fields` by API name, `removeNullValues` = true) is built in
**Step 6**, after `fields` and `verify` have run, because its field list is read from the org and the
custom names do not exist before this script. New fields can take a few minutes to show up in the
action; refresh the connection and retry rather than typing the names in. `recordId` is the Salesforce
Account Id. The Audience record synced from Salesforce does not carry it (the sync maps the owner id,
not the record id; four of four fresh-workspace runs confirmed this), so Step 6 adds a **Find the
Salesforce Id** node first: `salesforce-lookup-via-soql` on Website with `Territory_Plan__c = true` and
the four URL forms of the domain (the `https` and `http` schemes, each with and without a `www.`
prefix; the import writes Website as `https://<domain>`), then a small code node that picks the Id, then
an Audiences write to a "Salesforce Account Id" field the workflow fills. The `update-object` node takes
`recordId` from that picked Id. If your source maps `Id`, use that field instead and skip the lookup.
Owner is never mapped here; the Write Owners run writes it in Step 7, after approval.

Mapping, by API name. Headline and component fields come from the Score node. The enrichment values are
the raw research outputs: map each from the research node that produced it, or from the Score node when
the build passes it through under a stable name. A held account (Scoring Status other than scored, for
example a provider that failed twice or a resolve that returned no domain or an under-10-employee match
for a known company) writes status, reason line and rubric version only; no component scores and no
enrichment values, so a wrong match never lands on the record.

| Salesforce field | Fed by |
|---|---|
| `Account_Fit_Score__c`, `Account_Fit_Grade__c`, `Fit_Score_Summary__c`, `Scoring_Status__c`, `Rubric_Version__c` | Score node: fit score, grade, reason line, scoring status, rubric version |
| `<Factor>_Score__c` (one per rubric factor) | Score node: that factor's component score |
| `Sales_Team_Headcount__c` | the sales role count from the headcount-by-criteria node (the raw count, not the scored value, which the rules cap or lift: 20+ open SDR roles scores 100, a sales ratio at or above 5% scores at least the 50 band) |
| `Ops_Team_Headcount__c` | the ops role count (RevOps, SalesOps, GTM Ops, Marketing Ops and GTM Engineer titles, one combined count) |
| `Headcount_Growth_Pct__c` | the 12-month growth percentage from the headcount growth node. The field is Number(7,1); a real value of +39,800% overflowed the earlier Number(5,1) and failed the whole component write for that account, so the Score node also clamps the value to the field's range before it is mapped |
| `Last_Funding_Round__c`, `Last_Funding_Amount__c`, `Last_Funding_Date__c` | the fundraising research agent's round name, amount in USD and date; blank for VC/PE, education and government, and for public or exited companies (Harmonic stage EXITED), where funding research is skipped (see `references/research-prompts.md`) |
| `GTM_Motion__c`, `Business_Model__c`, `Entity_Type__c` | the classification agent's three enums (business model flags are appended to the business model text) |
| `Tech_Stack__c` | the technographics evidence: the named tools the tech-stack node found, comma-separated |
| `Is_Competitor__c` | true when the technographics node finds a competitor product from the rubric's competitor list; the rules file's `competitors_field` and the carve's competitor exclusion read it |
| `Clay_Last_Enriched__c` | the time the write-back node runs (now), so a stale score is visible on the record |
| fields from `--extra-fields` | the research node that produces that rubric's value (a compliance or engineering headcount count, an institution type or sector enum, a site-count band); one field per value the rubric gates or scores on |
| `Segment__c`, `Sub_Region__c`, `Carve_Status__c`, `Carve_Reason__c`, `Proposed_Owner__c` | the Territory Carve workflow (Step 7), one run per account; never `OwnerId` |
| `OwnerId` (plus Carve Status `Assigned`) | the Write Owners workflow (Step 7), run in bulk after the recorded yes, from the Proposed rows only |

Note the two different decisions here: a VC firm or a GTM agency can score Best Fit and still be
excluded from the carve in Step 7, because another motion owns them. Both rules are intentional, so the
score field and the carve status disagree on purpose for those accounts.

## Commands

```
SKILL="<absolute path of the territory-planning skill folder>"
python3 "$SKILL/scripts/sf_setup.py" plan     --rubric rubric.md                       # show the field list; no org needed
python3 "$SKILL/scripts/sf_setup.py" fields   --org <alias> --rubric rubric.md \
        --segments "SA,SL1/SL2,SL3" --subregions "US West,US East,Pooled: SF Bay Area,Pooled: New York City,Rest of EMEA,Pooled: London"
        # or: --rules territory-rules.md, which reads both lists from the rules file
        # add --extra-fields for every rubric value the default set has no field for, specs separated by ';':
        #   --extra-fields "Compliance_Team_Headcount__c:Compliance Team Headcount:number:7,0;Institution_Type__c:Institution Type:text:60"
python3 "$SKILL/scripts/sf_setup.py" reps     --org <alias> --reps reps.csv            # creates users; fills crm_user_id in reps.csv
python3 "$SKILL/scripts/sf_setup.py" accounts --org <alias> --accounts accounts.csv    # Step 6: import, flagged Territory_Plan__c
python3 "$SKILL/scripts/sf_setup.py" verify   --org <alias> --rubric rubric.md         # repeat the same --extra-fields here
        # --without API1,API2 on plan, fields and verify leaves planned fields out (e.g. --without Proposed_Owner__c if the org rejects the lookup)
```

`--segments` and `--subregions` are the picklist values for `Segment__c` and `Sub_Region__c`. Take them
from the rules file's segments table and routing section, verbatim, so the carve's labels match the
picklist; the defaults in the script are only the starter file's values. Rerun `fields` if the rules file
changes them later.

`--extra-fields` takes one string of `API_Name__c:Label:kind[:size]` specs separated by `;`, where kind
is `text` (size = length, default 255), `number` (size = `precision,scale`, default 18,0), `longtext`,
`date`, `checkbox` or `picklist=a|b|c`; the flag is given once, not repeated. Use it whenever the confirmed rubric scores or gates on a
value that is not in the default enrichment set: walk the rubric's factors, and for each one whose raw
value a rep would want to see on the record (the count, the enum, the band) and that has no default
field, add one. Decide this before `fields` runs, from the design worksheet, so one idempotent deploy
creates the whole set; pass the same flags to `plan` to see the names first and to `verify` so it checks
them. The fields land in Account Details with field-level security on the "Territory Planning"
permission set, and the Step 6 write node maps them like any other enrichment value. Doing this by hand
later means a second metadata project and a permission-set patch, which is what every run without the
flag ended up building.

`fields` is idempotent: after a rubric change it adds the new factor fields and re-places the layout
sections. It retrieves every Account page layout in the org and patches each one. `--without
Proposed_Owner__c` is the safety valve if an org rejects the User lookup: the field, its list-view
column and the Proposed Books report are left out, the carve then writes Carve Status and Carve Reason
only, and `verify` with the same flag does not look for it. The `lookup` kind is internal; it is not
accepted in `--extra-fields`.

## Reps

A Developer Edition ships with a handful of licences (typically 4 Salesforce, 6 Salesforce Platform,
one each used by the admin). `reps` uses Platform licences first, writes `Department = segment` and
`Division = sub-region` on each user, and stops with a clear message when licences run out. Five reps
is the comfortable number for a demo org.

It writes each rep's Salesforce user id into the `crm_user_id` column of `reps.csv` itself, so Step 7
can read owners from the one file, and still writes `reps.with-ids.csv` (name, id, licence) as a record of
what it did. It is safe to rerun: a rep whose user already exists is reused, and a rep deactivated by an
earlier `reset` is reactivated by name rather than recreated, because Salesforce keeps a deactivated
user's username forever. Users are created with the CRM Content permission off; a Developer Edition has
only a couple of Content feature licences and the third user fails without that.

## Accounts (Step 6, empty orgs only)

`accounts` takes a CSV with at least a domain column: `Website`, or `domain`, which it maps to
`Website` and from which it derives `Name` when the file has none (so a domain-only list imports).
`Name`, `NumberOfEmployees`, `BillingCity`, `BillingState`, `BillingCountry`, `Industry` help. It detects
whether the org uses state and country picklists and maps the columns either way, adds
`Territory_Plan__c = true`, and imports with the Bulk API. `references/sample-accounts.csv` has 200 real B2B companies for attendees without a list.

`NumberOfEmployees` matters more than it looks. LinkedIn headcount over-counts 5-9x for some companies
(one account showed 7,000 against 800 in the CRM), so a "too big" rule in the rules file (5,000+
employees to Low Fit or excluded) falls back to the CRM count, and the carve's segment boundaries read
the same number. Import it when the list has it.

`Account.OwnerId` is required in Salesforce, so every imported account is owned by the admin who ran the
import. There is no such thing as an ownerless account. "Unassigned" in this skill therefore means:
owner is the import user **and** `Carve_Status__c` is blank or `Unowned`. The eligible segment in Step 6
and the carve in Step 7 both use that definition; a rep's own user id as owner is what "assigned" means.

## Carve Status

`Carve_Status__c` is a picklist with exactly six values, and the reason goes in `Carve_Reason__c`
(text, 255), not in the status:

| Value | Meaning | Typical reasons |
|---|---|---|
| `Proposed` | the carve workflow named a rep in `Proposed_Owner__c`; Owner untouched until the approved write | `snake deal, SA / US West, rank 7 of 38`, `dynamic deal, SL1/SL2 / US East: rep with the most room`, `named account, manager allocation`, `rep pick` |
| `Assigned` | the approved Write Owners run copied Proposed Owner to Owner; owner is the rep | the Proposed reason, unchanged |
| `Protected` | kept with its current owner, never dealt | `existing owner`, `parent's owner`, `open opportunity`, `existing customer` |
| `Excluded` | out of the plan by rule | `direct competitor`, `company type vc_pe: another motion owns it`, `partner`, `owned by another team`, `education / institution domain`, `industry <value>: excluded`, `non-sellable region (Israel)`, `manager exclusion`, `too big: ...` when the size cap's action is `exclude` |
| `Not eligible` | in the plan, but failed the gate | `fit 54 below 60`, `below minimum size`, `no employee count`, `not scored` (any `Held:` status), `too big: ...` when the size cap's action is `Low Fit` |
| `Unowned` | eligible, not dealt | `over capacity`, `no routing match`, `no rep for segment / region`, `named account, no rep with capacity`, `awaiting draft pick (pick 3 of 12, SA / US West)`; stays in the pool for the next run |

These are the strings the carve node (`scripts/carve_node.py`) writes; `carve-proposal.csv` carries the
same ones, so a rep's "why is X not in my book" and the CRM record read alike.

Excluded accounts keep their component scores. VC firms, GTM agencies and education institutions arrive
capped at 40 and graded Low Fit by the default override and are excluded by the carve too; the report
shows both, and that is the expected picture, not a bug.

`Segment__c` and `Sub_Region__c` take only the values the rules file lists. An unsegmented or unrouted
row leaves both empty and carries the reason in `Carve_Reason__c`; never write a made-up value such as
"Unsegmented" into the picklist.

## Writing owners (Step 7)

The Territory Carve workflow writes the proposal (Segment, Sub-region, Carve Status, Carve Reason,
Proposed Owner) and never Owner. The owner write runs through a small **Write Owners** workflow in
Clay, because `update-object` is a Clay action and because the Audiences record needs the same values
mirrored. `python3 "$SKILL/scripts/carve_workflow.py" writer --out ./carve` builds it as a draft; it has
been proven at 200 rows: 0 errors, 0 data credits.

The workflow: a manual trigger with inputs `account_id`, `domain`, `owner_id`, `segment`, `sub_region`,
`carve_status`, `carve_reason`; one Salesforce `update-object` node with `recordId` = `account_id`,
`object_type` Account, `object_fields` `OwnerId`, `Segment__c`, `Sub_Region__c`, `Carve_Status__c`,
`Carve_Reason__c`, `removeNullValues` true (so a row without `owner_id` would leave the owner alone);
then an Audiences upsert that mirrors the same fields on the company record. Build it during the Step 6
batches, leave it unpublished, and run nothing through it before the Step 7 approval.

After the recorded yes, three separate commands:

```
clay workflows publish <write-owners workflow>
clay routines create workflow <write-owners workflow>
clay routines runs start <routine> --bulk ./carve/write-owners.jsonl
clay routines runs get <run> --bulk            # status and per-row count; --limit cannot be combined with --bulk
```

`write-owners.jsonl` is `scripts/carve_summary.py`'s output: one JSON object per **Proposed** account,
keys matching the trigger inputs, `carve_status` `Assigned` and `owner_id` the proposed rep. Protected,
Excluded, Not eligible and Unowned accounts are not in it; the carve workflow already wrote their status
and reason, so the approved write touches owners only. Claude Code's permission classifier asks the human
to approve the bulk run as "Modify Shared Resources"; expect that prompt, say what it is, and let the
person answer it. Do not chain publish, create and run into one command: the denial then covers all
three. If the Clay write is blocked, the admin route is `sf data update bulk --sobject Account --file
<csv>` from the same rows (Id, OwnerId, Carve_Status__c), with the Audiences mirror run afterwards.

Before the write, snapshot `Id, OwnerId, Carve_Status__c, Proposed_Owner__c` for the plan accounts with
`sf data query` so the write can be reversed. After it, the counts in the "Territory – Accounts by
Owner" report must match `carve-summary.md` (Proposed rows now Assigned; protected, excluded, not
eligible, unowned unchanged) before the patch docs go out.

## The three routes, if the script cannot be used

**A. Metadata deploy** is what the script does; the generated project is left in `./sf-territory` so an
admin can deploy it themselves with `sf project deploy start --source-dir force-app`.
**B. Unmanaged package:** build once in a source org from that project, create an unmanaged package,
share the install link. One click for a room full of attendees.
**C. Manual:** Setup → Object Manager → Account → Fields. Use the `plan` output as the checklist; about
20 minutes for the full set. The headline and enrichment fields go in the standard section, called
Account Details or Account Information depending on the org; add the "Fit Score Components" and
"Territory" sections to the layout by hand.

## No CRM

Skip this step. Steps 6 and 7 run entirely in Audiences: scores and assignments are fields on the
Audience record, and the segment per rep is the territory. Say so in the delivery.

#!/usr/bin/env python3
"""Salesforce setup for territory planning, driven by the confirmed rubric. Uses the `sf` CLI.

  python3 sf_setup.py plan     --rubric rubric.md [--rules territory-rules.md] [--segments SA,SL1/SL2,SL3] [--subregions "US West,US East"]
                                                                           [--extra-fields "<spec>;<spec>"]
  python3 sf_setup.py fields   --org <alias> --rubric rubric.md [...]      create fields, layout sections, permission set, list view, reports
  python3 sf_setup.py reps     --org <alias> --reps reps.csv               create rep users (Department = segment, Division = sub-region);
                                                                           fills crm_user_id in reps.csv by name
  python3 sf_setup.py accounts --org <alias> --accounts accounts.csv        import accounts, flagged Territory_Plan__c = true; a CSV with
                                                                           only a domain column works (Name derived, Website = the domain with https:// prefixed)
  python3 sf_setup.py verify   --org <alias> --rubric rubric.md [...]       confirm fields, reps (with their user ids) and account count
  python3 sf_setup.py reset    --org <alias> --rubric rubric.md --yes       dev orgs and sandboxes only: delete planned accounts, deactivate
                                                                           reps, remove fields, sections, reports, list view, permission set

Segment__c and Sub_Region__c picklist values come from --segments/--subregions, else from the rules file given with
--rules (its YAML block: segments[].name, routing.regions sub-region keys and pool sub_region_value), else the starter defaults.
Idempotent: rerunning `fields` after a rubric change adds the new factor fields and re-places the sections.

The built-in enrichment-value fields (Sales/Ops headcount, growth, funding, GTM motion, business model, entity type,
tech stack) are a default for the starter rubric, not a contract. Rubrics differ per customer (a fintech scores
Institution Type and compliance headcount, an industrial seller Sector and plant headcount, a PLG vendor engineering
headcount), so give the values behind rubric-specific factors their own Account fields with --extra-fields, a
semicolon-separated list of specs:

    API_Name__c:Label:kind[:length | :precision,scale]
    kinds: text (default length 255), number (default 18,0), longtext, date, checkbox, picklist=a|b|c
    e.g. --extra-fields "Compliance_Team_Headcount__c:Compliance Team Headcount:number:7,0;Institution_Type__c:Institution Type:text:40"
    (the `lookup` kind is internal: plan() uses it for Proposed_Owner__c, a lookup to User; --extra-fields does not accept it)

They are created on Account, added to the Territory Planning permission set and placed in the Account Details
section like the built-in ones, and `plan` lists them. Pass the same --extra-fields to `verify` (it checks them)
and to `reset` (it removes them); otherwise they stay. --no-enrichment drops the built-in set and keeps the extras.
Headcount_Growth_Pct__c is Number(7,1): a real 12-month growth of +39,800% overflowed Number(5,1) and failed the
whole component write for that account.
Carve_Status__c takes Proposed (the carve workflow in Clay proposed a rep; Owner untouched until approval), Assigned,
Protected, Excluded, Not eligible, Unowned. Proposed_Owner__c (lookup to User) holds the proposed rep; the
"Territory – Proposed Books" report groups the plan by it, which is what the approver reads before owners are written.
Never touches Owner. Writes only to the org named with --org, and only to a sandbox or Developer Edition unless
--allow-production is given (reset never runs against production). Requires `sf org login web -a <alias>` first.
This script lives in the skill folder, not the project, so call it by its absolute path from the project directory.
"""
import argparse, csv, json, os, re, shutil, subprocess, sys, tempfile
from xml.sax.saxutils import escape

NS = 'xmlns="http://soap.sforce.com/2006/04/metadata"'
API_VERSION = "62.0"
GRADES = ["Best Fit", "Good Fit", "Moderate Fit", "Low Fit", "Bad Fit"]
# The status is the category only; the detail ("open opp", "over capacity", the rep and pool for Assigned) goes in
# Carve_Reason__c. Proposed = the carve workflow proposed a rep (Proposed_Owner__c); Owner untouched until approval.
# A VC firm or GTM agency can score Best Fit and still be Excluded: another motion owns it, on purpose.
CARVE_STATUSES = ["Proposed", "Assigned", "Protected", "Excluded", "Not eligible", "Unowned"]
DEFAULT_SEGMENTS = "SA,SL1/SL2,SL3"
DEFAULT_SUBREGIONS = "US West,US East,Pooled: SF Bay Area,Pooled: New York City,Rest of EMEA,Pooled: London"
FACTOR_MARKER = "in rubric"   # plan() writes this into every factor field's description; reset deletes only fields that carry it

# ---------- rubric ----------

def read_rubric(path):
    text = open(path).read()
    m = re.search(r"```json\n(.*?)```", text, re.S)
    if not m:
        sys.exit(f"{path}: no ```json block found")
    return json.loads(m.group(1))


# ---------- rules file (segments and sub-regions for the picklists) ----------

def _yaml_scalar(s):
    s = re.sub(r"\s+#.*$", "", s).strip()
    m = re.match(r"""^(?:"([^"]*)"|'([^']*)'|(.*))$""", s)
    return next(g for g in m.groups() if g is not None).strip()


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def read_rules(path):
    """Return (segments, subregions) from the rules file's ```yaml block with a small line parser (no PyYAML).
    segments: every `name:` under the top-level `segments:` key. subregions: under routing.regions, each region's
    `sub_regions:` keys in order, then each pool's `sub_region_value:` (or "Pooled: <name>" when it has none)."""
    text = open(path).read()
    m = re.search(r"```ya?ml\n(.*?)```", text, re.S)
    if not m:
        print(f"{path}: no ```yaml block found; picklists fall back to --segments/--subregions or the defaults"); return [], []
    lines = [l for l in m.group(1).splitlines() if l.strip() and not l.strip().startswith("#")]

    def section(start_re, within=None):
        """Lines belonging to the first key matching start_re (deeper indent than the key), searched inside `within`."""
        src = within if within is not None else lines
        for i, l in enumerate(src):
            if re.match(start_re, l):
                base = _indent(l); out = []
                for l2 in src[i + 1:]:
                    if _indent(l2) <= base: break
                    out.append(l2)
                return out
        return []

    segments = []
    for l in section(r"^segments:"):
        for mm in re.finditer(r"""(?:^|[{,\s-])name:\s*("[^"]*"|'[^']*'|[^,}\n]+)""", l):
            v = _yaml_scalar(mm.group(1))
            if v and v not in segments: segments.append(v)

    subregions = []
    regions = section(r"^\s+regions:", section(r"^routing:"))
    region_indent = _indent(regions[0]) if regions else None
    region_keys = [i for i, l in enumerate(regions) if _indent(l) == region_indent and re.match(r"^\s*[^\s:#][^:#]*:\s*(#.*)?$", l)]
    for n, i in enumerate(region_keys):
        body = regions[i + 1: region_keys[n + 1] if n + 1 < len(region_keys) else len(regions)]
        subs = section(r"^\s+sub_regions:", body)
        if subs:
            d = _indent(subs[0])
            for l in subs:
                if _indent(l) == d and ":" in l:
                    v = _yaml_scalar(l.split(":", 1)[0])
                    if v and v not in subregions: subregions.append(v)
        pools, cur = [], None
        for l in section(r"^\s+pools:", body):
            if re.match(r"^\s*-", l):
                cur = {}; pools.append(cur); l = re.sub(r"^\s*-\s*", "", l)
            if cur is None: continue
            for kv in re.finditer(r"""(name|sub_region_value):\s*("[^"]*"|'[^']*'|[^,}\n]+)""", l):
                cur[kv.group(1)] = _yaml_scalar(kv.group(2))
        for p in pools:
            v = p.get("sub_region_value") or (f"Pooled: {p['name']}" if p.get("name") else None)
            if v and v not in subregions: subregions.append(v)
    return segments, subregions


def picklists(a):
    """Segment__c and Sub_Region__c values: explicit flags win, then the rules file, then the starter defaults."""
    segs = [s.strip() for s in a.segments.split(",")] if a.segments else None
    subs = [s.strip() for s in a.subregions.split(",")] if a.subregions else None
    if getattr(a, "rules", None) and (segs is None or subs is None):
        rs, rr = read_rules(a.rules)
        if segs is None and rs:
            segs = rs; print(f"segments from {a.rules}: {', '.join(segs)}")
        if subs is None and rr:
            subs = rr; print(f"sub-regions from {a.rules}: {', '.join(subs)}")
    return segs or DEFAULT_SEGMENTS.split(","), subs or DEFAULT_SUBREGIONS.split(",")


def api_name(label, suffix):
    base = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")
    base = re.sub(r"_+", "_", base)[: 40 - len(suffix) - 3]
    return f"{base}_{suffix}__c"


# ---------- field plan ----------

EXTRA_KINDS = ("text", "number", "longtext", "date", "checkbox", "picklist")


def parse_extra_fields(spec):
    """--extra-fields: 'API_Name__c:Label:kind[:length | :precision,scale]' specs separated by ';'. kind picklist takes its
    values after '=' with '|' between them (picklist=Bank|Credit union). Returns field dicts in plan()'s shape."""
    out = []
    for item in [x.strip() for x in (spec or "").split(";") if x.strip()]:
        parts = [x.strip() for x in item.split(":")]
        if len(parts) < 3:
            sys.exit(f"--extra-fields '{item}': expected API_Name__c:Label:kind[:length | :precision,scale]")
        api, label, kind, size = parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else ""
        values = None
        if kind.startswith("picklist"):
            kind, _, vals = kind.partition("=")
            values = [v.strip() for v in vals.split("|") if v.strip()]
            if not values:
                sys.exit(f"--extra-fields '{item}': picklist needs values, picklist=a|b|c")
        if kind not in EXTRA_KINDS:
            sys.exit(f"--extra-fields '{item}': kind must be one of {', '.join(EXTRA_KINDS)}")
        if not re.match(r"^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)*__c$", api) or len(api) > 43:
            sys.exit(f"--extra-fields '{item}': '{api}' is not a valid custom field API name (letters, digits, single underscores, ends in __c, 43 chars max)")
        if not label:
            sys.exit(f"--extra-fields '{item}': the label is empty")
        f = dict(api=api, label=label, kind=kind, description="Rubric-specific enrichment value, created from --extra-fields. Written by Clay.")
        try:
            if kind == "number":
                prec, _, scale = size.partition(",")
                f["precision"], f["scale"] = int(prec or 18), int(scale or 0)
            elif kind == "text":
                f["length"] = int(size or 255)
            elif size:
                sys.exit(f"--extra-fields '{item}': {kind} takes no length")
        except ValueError:
            sys.exit(f"--extra-fields '{item}': '{size}' is not a length or precision,scale")
        if kind == "picklist":
            f["values"] = values
        out.append(f)
    return out


def plan(rubric, segments, subregions, enrichment=True, extras=()):
    """Return (fields, layout). fields: list of dicts; layout: which fields go where. extras: parse_extra_fields() output,
    rubric-specific enrichment values placed in Account Details after the built-in ones."""
    F = []
    def add(api, label, kind, **kw): F.append(dict(api=api, label=label, kind=kind, **kw))

    # headline (Account Details)
    add("Account_Fit_Score__c", "Account Fit Score", "number", precision=4, scale=1,
        description="0-100 weighted sum of the factor scores. Written by Clay.")
    add("Fit_Score_Summary__c", "Fit Score Summary", "longtext", description="One-line reason: strongest and weakest factor. Written by Clay.")
    add("Account_Fit_Grade__c", "Account Fit Grade", "picklist", values=GRADES)
    add("Scoring_Status__c", "Scoring Status", "text", length=80, description="scored, or Held: <factor> <reason>")
    add("Rubric_Version__c", "Rubric Version", "text", length=10)

    # one component per rubric factor (Fit Score Components)
    components = []
    for f in rubric["factors"]:
        api = api_name(f["name"], "Score")
        add(api, f"{f['name']} Score", "number", precision=3, scale=0,
            description=f"0-100. Weight {f['weight']}% in rubric {rubric.get('version')}." + (" Retired (weight 0)." if f["weight"] == 0 else ""))
        components.append(api)

    # enrichment values found (Account Details)
    enr = []
    if enrichment:
        for api, label, kind, kw in [
            ("Sales_Team_Headcount__c", "Sales Team Headcount", "number", dict(precision=7, scale=0)),
            ("Ops_Team_Headcount__c", "Ops Team Headcount", "number", dict(precision=7, scale=0)),
            ("Headcount_Growth_Pct__c", "Headcount Growth (12m %)", "number", dict(precision=7, scale=1)),
            ("Last_Funding_Round__c", "Last Funding Round", "text", dict(length=40)),
            ("Last_Funding_Amount__c", "Last Funding Amount (USD)", "number", dict(precision=18, scale=0)),
            ("Last_Funding_Date__c", "Last Funding Date", "date", {}),
            ("GTM_Motion__c", "GTM Motion", "text", dict(length=40)),
            ("Business_Model__c", "Business Model", "text", dict(length=80)),
            ("Entity_Type__c", "Entity Type", "text", dict(length=40)),
            ("Tech_Stack__c", "Tech Stack", "longtext", {}),
            ("Clay_Last_Enriched__c", "Clay Last Enriched", "datetime", {}),
        ]:
            add(api, label, kind, **kw); enr.append(api)
    for f in extras:
        if any(x["api"] == f["api"] for x in F):
            sys.exit(f"--extra-fields: {f['api']} is already a planned field; drop it from the list or rename it")
        F.append(dict(f)); enr.append(f["api"])

    # territory (Territory section)
    add("Segment__c", "Segment", "picklist", values=segments + ["Unsegmented"])
    add("Sub_Region__c", "Sub-region", "picklist", values=subregions)
    add("Proposed_Owner__c", "Proposed Owner", "lookup", reference="User",
        description="Rep the carve workflow proposed. Owner is written only after approval. Written by Clay.")
    add("Carve_Status__c", "Carve Status", "picklist", values=CARVE_STATUSES)
    add("Carve_Reason__c", "Carve Reason", "text", length=255)
    add("Engagement_Score__c", "Engagement Score", "number", precision=4, scale=1,
        description="0-100 heat from signals after the carve: each event adds points, the weekly decay takes some away. Written by Clay (Step 8).")
    add("Last_Signal__c", "Last Signal", "text", length=255, description="Latest signal event: type, headline, points. Written by Clay (Step 8).")
    add("Last_Signal_Date__c", "Last Signal Date", "date", description="When the latest signal event happened. Written by Clay (Step 8).")
    add("Territory_Plan__c", "Territory Plan", "checkbox", description="In scope for the territory plan. The pool, list view and report filter on it.")
    add("Is_Competitor__c", "Is Competitor", "checkbox")
    add("Open_Opportunities__c", "Open Opportunities", "rollup_open_opps", readonly=True,
        description="Count of open opportunities. Protects the account from the carve.")

    layout = dict(
        details=["Account_Fit_Score__c", "Fit_Score_Summary__c"] + enr,
        components=components,
        territory=["Account_Fit_Grade__c", "Segment__c", "Sub_Region__c", "Proposed_Owner__c", "Carve_Status__c", "Carve_Reason__c",
                   "Engagement_Score__c", "Last_Signal__c", "Last_Signal_Date__c", "Open_Opportunities__c", "Territory_Plan__c", "Is_Competitor__c", "Scoring_Status__c", "Rubric_Version__c"],
    )
    return F, layout


# ---------- metadata writers ----------

def field_xml(f):
    d = f"\n    <description>{escape(f['description'])}</description>" if f.get("description") else ""
    k = f["kind"]
    if k == "number":
        inner = f"    <precision>{f['precision']}</precision>\n    <required>false</required>\n    <scale>{f['scale']}</scale>\n    <type>Number</type>\n    <unique>false</unique>"
    elif k == "text":
        inner = f"    <length>{f['length']}</length>\n    <required>false</required>\n    <type>Text</type>\n    <unique>false</unique>"
    elif k == "longtext":
        inner = "    <length>32768</length>\n    <type>LongTextArea</type>\n    <visibleLines>5</visibleLines>"
    elif k == "date":
        inner = "    <required>false</required>\n    <type>Date</type>"
    elif k == "datetime":
        inner = "    <required>false</required>\n    <type>DateTime</type>"
    elif k == "checkbox":
        inner = "    <defaultValue>false</defaultValue>\n    <type>Checkbox</type>"
    elif k == "picklist":
        v = "".join(f"\n            <value>\n                <fullName>{escape(x)}</fullName>\n                <default>false</default>\n"
                    f"                <label>{escape(x)}</label>\n            </value>" for x in f["values"])
        inner = (f"    <required>false</required>\n    <type>Picklist</type>\n    <valueSet>\n        <restricted>false</restricted>\n"
                 f"        <valueSetDefinition>\n            <sorted>false</sorted>{v}\n        </valueSetDefinition>\n    </valueSet>")
    elif k == "lookup":   # Metadata API element order: deleteConstraint, description, externalId, label, referenceTo, relationship*, required, type
        rel = f["api"][:-3] if f["api"].endswith("__c") else f["api"]
        d = f"\n    <deleteConstraint>SetNull</deleteConstraint>{d}\n    <externalId>false</externalId>"
        inner = (f"    <referenceTo>{escape(f['reference'])}</referenceTo>\n"
                 f"    <relationshipLabel>{escape(f['label'])} Accounts</relationshipLabel>\n    <relationshipName>{rel}_Accounts</relationshipName>\n"
                 "    <required>false</required>\n    <type>Lookup</type>")
    elif k == "rollup_open_opps":
        inner = ("    <summaryFilterItems>\n        <field>Opportunity.IsClosed</field>\n        <operation>equals</operation>\n        <value>False</value>\n"
                 "    </summaryFilterItems>\n    <summaryForeignKey>Opportunity.AccountId</summaryForeignKey>\n    <summaryOperation>count</summaryOperation>\n"
                 "    <type>Summary</type>")
    else:
        raise ValueError(k)
    return f"<CustomField {NS}>\n    <fullName>{f['api']}</fullName>{d}\n    <label>{escape(f['label'])}</label>\n{inner}\n</CustomField>"


def write(base, rel, body):
    p = os.path.join(base, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write('<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n")


def write_metadata(project, fields, layout):
    base = os.path.join(project, "force-app", "main", "default")
    for f in fields:
        write(base, f"objects/Account/fields/{f['api']}.field-meta.xml", field_xml(f))
    fp = "".join(f"\n    <fieldPermissions>\n        <editable>{'false' if f.get('readonly') else 'true'}</editable>\n"
                 f"        <field>Account.{f['api']}</field>\n        <readable>true</readable>\n    </fieldPermissions>" for f in fields)
    write(base, "permissionsets/Territory_Planning.permissionset-meta.xml",
          f"<PermissionSet {NS}>\n    <description>Read and edit the territory-planning fields on Account.</description>{fp}\n"
          f"    <hasActivationRequired>false</hasActivationRequired>\n    <label>Territory Planning</label>\n</PermissionSet>")
    apis = {f["api"] for f in fields}
    cols = "".join(f"\n    <columns>{c}</columns>" for c in
                   ["ACCOUNT.NAME", "Account_Fit_Score__c", "Account_Fit_Grade__c", "Segment__c", "Sub_Region__c", "CORE.USERS.ALIAS", "Proposed_Owner__c", "Carve_Status__c", "Open_Opportunities__c"]
                   if not c.endswith("__c") or c in apis)
    write(base, "objects/Account/listViews/Territory_Plan.listView-meta.xml",
          f"<ListView {NS}>\n    <fullName>Territory_Plan</fullName>{cols}\n    <filterScope>Everything</filterScope>\n"
          f"    <filters>\n        <field>Territory_Plan__c</field>\n        <operation>equals</operation>\n        <value>1</value>\n    </filters>\n"
          f"    <label>Territory Plan</label>\n</ListView>")
    rcols = "".join(f"\n    <columns>\n{('        <aggregateTypes>Average</aggregateTypes>' + chr(10)) if c == 'Account.Account_Fit_Score__c' else ''}"
                    f"        <field>{c}</field>\n    </columns>" for c in
                    ["ACCOUNT.NAME", "Account.Account_Fit_Score__c", "Account.Account_Fit_Grade__c", "Account.Sub_Region__c", "Account.Carve_Status__c"])
    write(base, "reports/unfiled$public/Territory_Accounts_by_Owner.report-meta.xml", f"""<Report {NS}>
    <chart>
        <backgroundColor1>#FFFFFF</backgroundColor1>
        <backgroundColor2>#FFFFFF</backgroundColor2>
        <backgroundFadeDir>Diagonal</backgroundFadeDir>
        <chartSummaries>
            <axisBinding>y</axisBinding>
            <column>RowCount</column>
        </chartSummaries>
        <chartType>HorizontalBarStacked</chartType>
        <enableHoverLabels>true</enableHoverLabels>
        <expandOthers>true</expandOthers>
        <groupingColumn>Account.Segment__c</groupingColumn>
        <legendPosition>Right</legendPosition>
        <location>CHART_TOP</location>
        <secondaryGroupingColumn>USERS.NAME</secondaryGroupingColumn>
        <showAxisLabels>true</showAxisLabels>
        <showPercentage>false</showPercentage>
        <showTotal>false</showTotal>
        <size>Medium</size>
        <summaryAxisRange>Auto</summaryAxisRange>
        <textColor>#000000</textColor>
        <textSize>12</textSize>
        <title>Accounts per rep, by segment</title>
        <titleColor>#000000</titleColor>
        <titleSize>18</titleSize>
    </chart>{rcols}
    <filter>
        <criteriaItems>
            <column>Account.Territory_Plan__c</column>
            <columnToColumn>false</columnToColumn>
            <isUnlocked>true</isUnlocked>
            <operator>equals</operator>
            <value>1</value>
        </criteriaItems>
    </filter>
    <format>Summary</format>
    <groupingsDown>
        <dateGranularity>Day</dateGranularity>
        <field>Account.Segment__c</field>
        <sortOrder>Asc</sortOrder>
    </groupingsDown>
    <groupingsDown>
        <dateGranularity>Day</dateGranularity>
        <field>USERS.NAME</field>
        <sortOrder>Asc</sortOrder>
    </groupingsDown>
    <name>Territory – Accounts by Owner</name>
    <reportType>AccountList</reportType>
    <scope>organization</scope>
    <showDetails>true</showDetails>
    <showGrandTotal>true</showGrandTotal>
    <showSubTotals>true</showSubTotals>
    <sortColumn>Account.Account_Fit_Score__c</sortColumn>
    <sortOrder>Desc</sortOrder>
    <timeFrameFilter>
        <dateColumn>CREATED_DATE</dateColumn>
        <interval>INTERVAL_CUSTOM</interval>
    </timeFrameFilter>
</Report>""")
    pcols = "".join(f"\n    <columns>\n{('        <aggregateTypes>Average</aggregateTypes>' + chr(10)) if c == 'Account.Account_Fit_Score__c' else ''}"
                    f"        <field>{c}</field>\n    </columns>" for c in
                    ["ACCOUNT.NAME", "Account.Account_Fit_Score__c", "Account.Account_Fit_Grade__c", "Account.Sub_Region__c", "Account.Carve_Status__c", "Account.Carve_Reason__c"])
    # The approver's view: Proposed (and already Assigned) accounts per proposed rep, by segment. Both criteria AND by default.
    if "Proposed_Owner__c" in apis:
      write(base, "reports/unfiled$public/Territory_Proposed_Books.report-meta.xml", f"""<Report {NS}>
    <chart>
        <backgroundColor1>#FFFFFF</backgroundColor1>
        <backgroundColor2>#FFFFFF</backgroundColor2>
        <backgroundFadeDir>Diagonal</backgroundFadeDir>
        <chartSummaries>
            <axisBinding>y</axisBinding>
            <column>RowCount</column>
        </chartSummaries>
        <chartType>HorizontalBarStacked</chartType>
        <enableHoverLabels>true</enableHoverLabels>
        <expandOthers>true</expandOthers>
        <groupingColumn>Account.Segment__c</groupingColumn>
        <legendPosition>Right</legendPosition>
        <location>CHART_TOP</location>
        <secondaryGroupingColumn>Account.Proposed_Owner__c</secondaryGroupingColumn>
        <showAxisLabels>true</showAxisLabels>
        <showPercentage>false</showPercentage>
        <showTotal>false</showTotal>
        <size>Medium</size>
        <summaryAxisRange>Auto</summaryAxisRange>
        <textColor>#000000</textColor>
        <textSize>12</textSize>
        <title>Proposed accounts per rep, by segment</title>
        <titleColor>#000000</titleColor>
        <titleSize>18</titleSize>
    </chart>{pcols}
    <filter>
        <criteriaItems>
            <column>Account.Territory_Plan__c</column>
            <columnToColumn>false</columnToColumn>
            <isUnlocked>true</isUnlocked>
            <operator>equals</operator>
            <value>1</value>
        </criteriaItems>
        <criteriaItems>
            <column>Account.Carve_Status__c</column>
            <columnToColumn>false</columnToColumn>
            <isUnlocked>true</isUnlocked>
            <operator>equals</operator>
            <value>Proposed,Assigned</value>
        </criteriaItems>
    </filter>
    <format>Summary</format>
    <groupingsDown>
        <dateGranularity>Day</dateGranularity>
        <field>Account.Segment__c</field>
        <sortOrder>Asc</sortOrder>
    </groupingsDown>
    <groupingsDown>
        <dateGranularity>Day</dateGranularity>
        <field>Account.Proposed_Owner__c</field>
        <sortOrder>Asc</sortOrder>
    </groupingsDown>
    <name>Territory – Proposed Books</name>
    <reportType>AccountList</reportType>
    <scope>organization</scope>
    <showDetails>true</showDetails>
    <showGrandTotal>true</showGrandTotal>
    <showSubTotals>true</showSubTotals>
    <sortColumn>Account.Account_Fit_Score__c</sortColumn>
    <sortOrder>Desc</sortOrder>
    <timeFrameFilter>
        <dateColumn>CREATED_DATE</dateColumn>
        <interval>INTERVAL_CUSTOM</interval>
    </timeFrameFilter>
</Report>""")
    open(os.path.join(project, "sfdx-project.json"), "w").write(json.dumps(
        {"packageDirectories": [{"path": "force-app", "default": True}], "name": "territory-planning", "namespace": "", "sourceApiVersion": API_VERSION}))


# ---------- layouts ----------

def _items(fields, readonly):
    return "".join(f"            <layoutItems>\n                <behavior>{'Readonly' if f in readonly else 'Edit'}</behavior>\n"
                   f"                <field>{f}</field>\n            </layoutItems>\n" for f in fields)


def _section(label, left, right, readonly):
    return ("    <layoutSections>\n        <customLabel>true</customLabel>\n        <detailHeading>true</detailHeading>\n"
            f"        <editHeading>true</editHeading>\n        <label>{label}</label>\n        <layoutColumns>\n"
            + _items(left, readonly) + "        </layoutColumns>\n        <layoutColumns>\n"
            + _items(right, readonly) + "        </layoutColumns>\n        <style>TwoColumnsTopToBottom</style>\n    </layoutSections>\n")


def patch_layout(path, fields, layout):
    s = open(path).read()
    managed = [f["api"] for f in fields]
    readonly = {f["api"] for f in fields if f.get("readonly")}
    for f in managed:   # idempotency: remove prior placements and prior sections
        s = re.sub(r"\s*<layoutItems>\s*<behavior>\w+</behavior>\s*<field>%s</field>\s*</layoutItems>" % re.escape(f), "", s)
    s = re.sub(r"\s*<layoutSections>(?:(?!</layoutSections>).)*?<label>(?:Fit Score Components|Territory)</label>.*?</layoutSections>", "", s, flags=re.S)
    i = s.find("<label>Account Details</label>")
    if i == -1:
        i = s.find("<label>Account Information</label>")
    if i == -1:
        raise RuntimeError(f"{os.path.basename(path)}: no Account Details or Account Information section")
    sec_end = s.find("</layoutSections>", i)
    cols = [m.start() for m in re.finditer("</layoutColumns>", s[i:sec_end])]
    if len(cols) >= 2:   # headline + enrichment: alternate into the two columns of Account Details
        left, right = layout["details"][0::2], layout["details"][1::2]
        c1, c2 = i + cols[0], i + cols[1]
        s = s[:c1] + _items(left, readonly) + s[c1:c2] + _items(right, readonly) + s[c2:]
    else:
        c1 = i + cols[-1]; s = s[:c1] + _items(layout["details"], readonly) + s[c1:]
    sec_end = s.find("</layoutSections>", i) + len("</layoutSections>\n")
    comp = layout["components"]; half = (len(comp) + 1) // 2
    terr = layout["territory"]; thalf = (len(terr) + 1) // 2
    new = _section("Fit Score Components", comp[:half], comp[half:], readonly) + _section("Territory", terr[:thalf], terr[thalf:], readonly)
    s = s[:sec_end] + new + s[sec_end:]
    open(path, "w").write(s)


# ---------- sf ----------

def sf(*args, cwd=None):
    r = subprocess.run(["sf", *args, "--json"], capture_output=True, text=True, cwd=cwd)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"status": 1, "raw": (r.stdout + r.stderr)[-2000:]}


def deploy_report(d):
    res = d.get("result") or {}
    print(f"deploy: {res.get('status')} {res.get('numberComponentsDeployed')}/{res.get('numberComponentsTotal')} {(d.get('message') or d.get('raw') or '')[:300]}")
    fails = (res.get("details") or {}).get("componentFailures") or []
    for f in fails if isinstance(fails, list) else [fails]:
        print("  FAIL", f.get("componentType"), f.get("fullName"), "-", f.get("problem"))
    return res.get("status") == "Succeeded"


def retrieve_account_layouts(org, project):
    lst = sf("org", "list", "metadata", "--metadata-type", "Layout", "--target-org", org)
    if lst.get("status") != 0:
        sys.exit(f"could not list layouts: {(lst.get('message') or lst.get('raw') or '')[:300]}")
    names = [x["fullName"] for x in (lst.get("result") or []) if x.get("fullName", "").startswith("Account-")]
    if not names:
        print("no Account layouts listed; skipping layout patch"); return []
    args = []
    for n in names: args += ["--metadata", f"Layout:{n}"]
    r = sf("project", "retrieve", "start", *args, "--target-org", org, cwd=project)
    paths = []
    for root, _, files in os.walk(os.path.join(project, "force-app")):
        for fn in files:
            if fn.endswith(".layout-meta.xml") and fn.startswith("Account-"):
                paths.append(os.path.join(root, fn))
    if r.get("status") != 0 or not paths:
        sys.exit(f"layout retrieve failed ({(r.get('message') or r.get('raw') or 'no layout files came back')[:300]}); fix and rerun")
    if len(paths) != len(names):
        print(f"warning: {len(names)} Account layouts listed, {len(paths)} retrieved; the missing ones will not show the fields")
    print(f"retrieved {len(paths)} Account layout(s): {', '.join(os.path.basename(p) for p in paths)}")
    return paths


def guard_org(a, action):
    """Writes go to a sandbox or Developer Edition. Anything else needs --allow-production; reset refuses outright."""
    recs = (sf("data", "query", "-q", "SELECT IsSandbox, OrganizationType FROM Organization", "-o", a.org).get("result") or {}).get("records") or [{}]
    sandbox, kind = bool(recs[0].get("IsSandbox")), recs[0].get("OrganizationType") or "unknown"
    print(f"org {a.org}: {kind}{' (sandbox)' if sandbox else ''}")
    if sandbox or kind == "Developer Edition":
        return
    if action == "reset":
        sys.exit("refusing to reset: the org is not a sandbox or Developer Edition")
    if not getattr(a, "allow_production", False):
        sys.exit(f"{action}: this looks like a production org; rerun with --allow-production if that is really intended")


def fresh_project(path):
    """Empty the generated sfdx project, but only a folder this script made or an empty/new one. Never the working
    directory or one of its parents, which would take rubric.md, reps.csv and the saved research with it."""
    project = os.path.abspath(path); cwd = os.getcwd()
    if project == cwd or cwd.startswith(project + os.sep):
        sys.exit(f"--project-dir {path} is the working directory or one of its parents; use a subfolder such as ./sf-territory")
    if os.path.isdir(project) and os.listdir(project):
        try:
            ours = json.load(open(os.path.join(project, "sfdx-project.json"))).get("name") == "territory-planning"
        except Exception:
            ours = False
        if not ours:
            sys.exit(f"--project-dir {path} exists and was not generated by this script; pick a new or empty folder")
    shutil.rmtree(project, ignore_errors=True); os.makedirs(project)
    return project


def owned_score_fields(org, project, candidates):
    """Of the Account *_Score__c fields the plan did not name (a retired factor, or a field from another tool), keep only
    those whose description carries plan()'s marker. The retrieved field files are removed again so they are not redeployed."""
    if not candidates:
        return set()
    args = []
    for c in candidates: args += ["--metadata", f"CustomField:Account.{c}"]
    sf("project", "retrieve", "start", *args, "--target-org", org, cwd=project)
    fdir = os.path.join(project, "force-app", "main", "default", "objects", "Account", "fields")
    owned = set()
    for c in candidates:
        p = os.path.join(fdir, f"{c}.field-meta.xml")
        if os.path.exists(p) and re.search(r"<description>[^<]*%s" % re.escape(FACTOR_MARKER), open(p).read()):
            owned.add(c)
    shutil.rmtree(fdir, ignore_errors=True)
    left = sorted(set(candidates) - owned)
    if left:
        print(f"leaving {len(left)} score field(s) this script did not create: {', '.join(left)}")
    return owned


DESCRIBE_TYPES = {"number": {"double", "int"}, "text": {"string"}, "longtext": {"textarea"}, "date": {"date"}, "datetime": {"datetime"},
                  "checkbox": {"boolean"}, "picklist": {"picklist"}, "rollup_open_opps": {"double", "int"}, "lookup": {"reference"}}


def check_existing_fields(org, fields):
    """A field with a planned API name may already exist in a sandbox. Same type: fine, the deploy updates it in place
    (label, description, picklist values). Different type: the deploy would fail or redefine it, so stop and say which."""
    desc = sf("sobject", "describe", "-s", "Account", "-o", org)
    existing = {f["name"]: f for f in (desc.get("result") or {}).get("fields", [])}
    same, clash = [], []
    for f in fields:
        e = existing.get(f["api"])
        if not e: continue
        (same if e.get("type") in DESCRIBE_TYPES[f["kind"]] else clash).append((f["api"], e.get("type"), e.get("label")))
    if same:
        print(f"{len(same)} planned field(s) already exist and will be updated in place: " + ", ".join(x[0] for x in same))
    return clash


def apply_without(a, fields, layout):
    """--without API1,API2: leave those planned fields out of the deploy, the layout, the list view and the reports.
    The safety valve for a field type an org rejects (for example the Proposed Owner lookup); the carve then runs without it."""
    drop = {x.strip() for x in (getattr(a, "without", "") or "").split(",") if x.strip()}
    if not drop:
        return fields, layout
    unknown = drop - {f["api"] for f in fields}
    if unknown:
        print("--without: not planned anyway:", ", ".join(sorted(unknown)))
    fields = [f for f in fields if f["api"] not in drop]
    layout = {k: [x for x in v if x not in drop] for k, v in layout.items()}
    print("--without: leaving out", ", ".join(sorted(drop & {f["api"] for f in fields} | (drop - unknown))))
    return fields, layout


def cmd_fields(a):
    rubric = read_rubric(a.rubric)
    segments, subregions = picklists(a)
    fields, layout = plan(rubric, segments, subregions, not a.no_enrichment, parse_extra_fields(a.extra_fields))
    fields, layout = apply_without(a, fields, layout)
    project = fresh_project(a.project_dir)
    write_metadata(project, fields, layout)
    print(f"{len(fields)} fields planned for rubric {rubric.get('version')}: " + ", ".join(f["api"] for f in fields))
    if a.dry:
        print("dry run: metadata written to", project); return
    guard_org(a, "fields")
    clash = check_existing_fields(a.org, fields)
    if clash:
        for api, t, label in clash:
            print(f"  CLASH {api}: exists as {t} '{label}', planned type differs")
        if not a.overwrite_existing:
            sys.exit("existing fields of a different type; rename them in the org, or rerun with --overwrite-existing to try the deploy anyway")
    for p in retrieve_account_layouts(a.org, project):
        patch_layout(p, fields, layout); print("patched", os.path.basename(p))
    ok = deploy_report(sf("project", "deploy", "start", "--source-dir", "force-app", "--target-org", a.org, "--wait", "20", cwd=project))
    if not ok:
        sys.exit("deploy failed; fix the failures above and rerun (safe to rerun)")
    ps = sf("org", "assign", "permset", "--name", "Territory_Planning", "--target-org", a.org)
    print("permission set assigned:", "ok" if ps.get("status") == 0 else json.dumps(ps)[:200])
    cmd_verify(a)


def write_rep_ids(reps_csv, rows, fieldnames, ids):
    """Fill crm_user_id in reps.csv by name, keeping every other column and the row order. The previous file is kept as .bak."""
    if "crm_user_id" not in fieldnames:
        fieldnames = list(fieldnames) + ["crm_user_id"]
    filled = 0
    for r in rows:
        rid = ids.get(r.get("name"))
        if rid:
            r["crm_user_id"] = rid; filled += 1
    shutil.copyfile(reps_csv, reps_csv + ".bak")
    with open(reps_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n"); w.writeheader(); w.writerows(rows)
    return filled


def cmd_reps(a):
    org = a.org
    guard_org(a, "reps")
    lic = {r["Name"]: r for r in (sf("data", "query", "-q", "SELECT Name, TotalLicenses, UsedLicenses FROM UserLicense WHERE Name IN ('Salesforce','Salesforce Platform')", "-o", org).get("result") or {}).get("records", [])}
    free = {k: v["TotalLicenses"] - v["UsedLicenses"] for k, v in lic.items()}
    print("free licences:", free)
    profiles = {p["Name"]: p["Id"] for p in (sf("data", "query", "-q", "SELECT Id, Name FROM Profile WHERE Name IN ('Standard User','Standard Platform User')", "-o", org).get("result") or {}).get("records", [])}
    org_id = (sf("org", "display", "-o", org).get("result") or {}).get("id", "org")[-6:].lower()
    with open(a.reps, newline="") as fh:
        reader = csv.DictReader(fh); rows = list(reader); fieldnames = list(reader.fieldnames or [])
    # users this script made before (active or deactivated by `reset`): reuse by name instead of creating duplicates,
    # because Salesforce keeps a deactivated user's username forever
    prior = {u["Name"]: u for u in (sf("data", "query", "-q", "SELECT Id, Name, IsActive FROM User WHERE Username LIKE '%@territory-plan.example' OR (IsActive = true AND Title = 'Account Executive')", "-o", org).get("result") or {}).get("records", [])}
    created = []
    for r in rows:
        u = prior.get(r.get("name"))
        if u and u["IsActive"]:
            print(f"exists {r['name']} {u['Id']}"); created.append((r["name"], u["Id"], "existing")); continue
        if u and not u["IsActive"]:
            if free.get("Salesforce Platform", 0) + free.get("Salesforce", 0) <= 0:
                print(f"no licence left to reactivate {r['name']}"); break
            res = sf("data", "update", "record", "-s", "User", "-i", u["Id"], "-v",
                     f"IsActive=true Department='{r.get('segment', '')}' Division='{r.get('sub_region', '')}'", "-o", org)
            if res.get("status") == 0:
                print(f"reactivated {r['name']} {u['Id']}"); created.append((r["name"], u["Id"], "reactivated"))
                k = "Salesforce Platform" if free.get("Salesforce Platform", 0) > 0 else "Salesforce"; free[k] -= 1
                continue
            print(f"could not reactivate {r['name']}: {json.dumps(res)[:200]}; creating a new user instead")
        if free.get("Salesforce Platform", 0) > 0 and "Standard Platform User" in profiles:
            prof, lic_name = profiles["Standard Platform User"], "Salesforce Platform"
        elif free.get("Salesforce", 0) > 0 and "Standard User" in profiles:
            prof, lic_name = profiles["Standard User"], "Salesforce"
        else:
            print(f"no licence left for {r.get('name')}; stop here and remove unused users, or create the rest by hand"); break
        first, last = (r.get("name") or "Rep X").split(" ", 1) if " " in (r.get("name") or "") else (r.get("name") or "Rep", "User")
        uname = f"{first}.{last}.{org_id}@territory-plan.example".lower().replace(" ", "")
        vals = {"FirstName": first, "LastName": last, "Email": r.get("email") or f"{first}.{last}@example.com", "Username": uname,
                "Alias": (first[:1] + last)[:8].lower(), "ProfileId": prof, "TimeZoneSidKey": "America/Los_Angeles", "LocaleSidKey": "en_US",
                "EmailEncodingKey": "UTF-8", "LanguageLocaleKey": "en_US", "Title": "Account Executive",
                "Department": r.get("segment", ""), "Division": r.get("sub_region", ""), "IsActive": "true",
                # Developer Editions carry only a couple of CRM Content feature licences; without this the 3rd+ user fails
                # with LICENSE_LIMIT_EXCEEDED "content feature license limit exceeded"
                "UserPermissionsSFContentUser": "false"}
        v = " ".join(f"{k}='{str(x).replace(chr(39), '')}'" for k, x in vals.items())
        res = sf("data", "create", "record", "-s", "User", "-v", v, "-o", org)
        rid = (res.get("result") or {}).get("id")
        if rid:
            created.append((r.get("name"), rid, lic_name)); free[lic_name] -= 1; print(f"created {r.get('name')} ({lic_name}) {rid}")
        else:
            print(f"FAILED {r.get('name')}: {json.dumps(res)[:300]}")
    stem, _ = os.path.splitext(a.reps)
    out = stem + ".with-ids.csv"
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["name", "crm_user_id", "licence"]); w.writerows(created)
    filled = write_rep_ids(a.reps, rows, fieldnames, {name: rid for name, rid, _ in created})
    print(f"{len(created)} reps ready; crm_user_id filled for {filled}/{len(rows)} rows in {a.reps} (previous copy: {a.reps}.bak); record in {out}")
    if filled < len(rows):
        print("rows without an id: " + ", ".join(r.get("name") or "?" for r in rows if not r.get("crm_user_id")) + ". Step 7 cannot deal to them.")


# common CSV headers (lower-case) and the Account field each one means. Keep an employee-count column when the list has
# one: LinkedIn headcounts over-count 5-9x for some companies, and a "too big" rule falls back to NumberOfEmployees.
HEADER_ALIASES = {"domain": "Website", "website": "Website", "url": "Website", "company_domain": "Website", "primary_domain": "Website",
                  "name": "Name", "company": "Name", "company_name": "Name", "account": "Name", "account_name": "Name",
                  "employees": "NumberOfEmployees", "employee_count": "NumberOfEmployees", "headcount": "NumberOfEmployees",
                  "city": "BillingCity", "state": "BillingState", "country": "BillingCountry", "industry": "Industry", "type": "Type"}


def bare_domain(url):
    """linear.app from https://www.linear.app/path, for duplicate checks and derived names."""
    host = re.sub(r"^[a-z]+://", "", (url or "").strip().lower()).split("/")[0].split("?")[0]
    return host[4:] if host.startswith("www.") else host


def cmd_accounts(a):
    org = a.org
    desc = sf("sobject", "describe", "-s", "Account", "-o", org)
    names = {f["name"] for f in (desc.get("result") or {}).get("fields", [])}
    if "Territory_Plan__c" not in names:
        sys.exit("Territory_Plan__c missing: run `fields` first")
    guard_org(a, "accounts")
    with open(a.accounts, newline="") as fh:
        reader = csv.DictReader(fh); rows = list(reader); headers = list(reader.fieldnames or [])
    picklists = "BillingStateCode" in names
    # header -> Account field: exact API names pass through, common aliases map (domain -> Website), the rest are dropped and listed
    colmap, dropped = {}, []
    for k in headers:
        if k is None: continue
        target = k if k in names else HEADER_ALIASES.get(k.strip().lower())
        if target is None or (target not in names and target not in ("BillingState", "BillingCountry", "BillingStateCode", "BillingCountryCode")):
            dropped.append(k); continue
        colmap[k] = target
    if dropped:
        print(f"dropping {len(dropped)} column(s) that are not Account fields: {', '.join(dropped)}")
    if "Website" not in colmap.values():
        sys.exit(f"{a.accounts}: no Website or domain column; the enrichment keys on the domain, so one is required")
    if "Name" not in colmap.values():
        print("no Name column: deriving Name from the domain (linear.app -> Linear); rename accounts in the org later if needed")
    # idempotent: skip domains already in the plan, so a rerun after a timeout does not double the universe
    have = {bare_domain(r.get("Website")) for r in (sf("data", "query", "-q", "SELECT Website FROM Account WHERE Territory_Plan__c = true", "-o", org).get("result") or {}).get("records", [])}
    have.discard("")
    out_rows, skipped, seen = [], 0, set()
    for r in rows:
        o = {}
        for k, target in colmap.items():
            v = (r.get(k) or "").strip()
            k2 = target
            if picklists and target in ("BillingState", "BillingCountry"): k2 = target + "Code" if len(v) <= 3 else target
            if not picklists and target in ("BillingStateCode", "BillingCountryCode"): k2 = target[:-4]
            if k2 in names and v: o[k2] = v
        dom = bare_domain(o.get("Website"))
        if not dom:
            skipped += 1; continue
        if dom in have or dom in seen:
            skipped += 1; continue
        seen.add(dom)
        if not re.match(r"^[a-z]+://", o["Website"].lower()): o["Website"] = "https://" + o["Website"].strip()
        if not o.get("Name"): o["Name"] = dom.split(".")[0].replace("-", " ").title() or dom
        o["Territory_Plan__c"] = "true"
        o.setdefault("Type", "Prospect")
        out_rows.append(o)
    if skipped:
        print(f"skipped {skipped} row(s): no domain, duplicate in the file, or already in the plan")
    if not out_rows:
        print("nothing new to import"); return
    cols = sorted({k for o in out_rows for k in o})
    tmp = os.path.join(tempfile.gettempdir(), "territory_accounts_import.csv")
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n"); w.writeheader(); w.writerows(out_rows)
    print(f"importing {len(out_rows)} accounts with columns {cols}")
    res = sf("data", "import", "bulk", "--sobject", "Account", "--file", tmp, "--line-ending", "LF", "--wait", "10", "-o", org)
    r = res.get("result") or {}
    ji = r.get("jobInfo") or r
    failed = ji.get("numberRecordsFailed", r.get("failedRecords")) or 0
    print("import:", ji.get("state") or ("ok" if res.get("status") == 0 else "error"), "| processed", ji.get("numberRecordsProcessed", r.get("processedRecords")),
          "| failed", failed, (res.get("raw") or "")[:300])
    n = (sf("data", "query", "-q", "SELECT COUNT(Id) n FROM Account WHERE Territory_Plan__c = true", "-o", org).get("result") or {}).get("records", [{}])[0].get("n")
    print("accounts now in plan:", n)
    if res.get("status") != 0 or int(failed or 0) > 0:
        job = ji.get("id") or r.get("jobId")
        print((res.get("message") or "")[:500])
        if job: print(f"row errors: sf data bulk results --job-id {job} -o {org}")
        sys.exit("import did not complete cleanly; fix the rows above and rerun (already imported domains are skipped)")


def cmd_verify(a):
    org = a.org
    rubric = read_rubric(a.rubric) if a.rubric else None
    desc = sf("sobject", "describe", "-s", "Account", "-o", org)
    names = {f["name"] for f in (desc.get("result") or {}).get("fields", [])}
    want = ["Account_Fit_Score__c", "Fit_Score_Summary__c", "Account_Fit_Grade__c", "Scoring_Status__c", "Rubric_Version__c",
            "Segment__c", "Sub_Region__c", "Proposed_Owner__c", "Carve_Status__c", "Carve_Reason__c", "Territory_Plan__c", "Open_Opportunities__c",
            "Engagement_Score__c", "Last_Signal__c", "Last_Signal_Date__c"]
    if rubric: want += [api_name(f["name"], "Score") for f in rubric["factors"]]
    want += [f["api"] for f in parse_extra_fields(a.extra_fields)]
    drop = {x.strip() for x in (getattr(a, "without", "") or "").split(",") if x.strip()}
    want = [w for w in want if w not in drop]
    missing = [w for w in want if w not in names]
    print("fields:", f"{len(want) - len(missing)}/{len(want)} present", ("MISSING " + ", ".join(missing)) if missing else "")
    n = (sf("data", "query", "-q", "SELECT COUNT(Id) n FROM Account WHERE Territory_Plan__c = true", "-o", org).get("result") or {}).get("records", [{}])[0].get("n") if "Territory_Plan__c" in names else "n/a"
    print("accounts in plan:", n)
    reps = (sf("data", "query", "-q", "SELECT Id, Name, Department, Division FROM User WHERE IsActive = true AND Title = 'Account Executive'", "-o", org).get("result") or {}).get("records", [])
    print("reps:", len(reps), "(name, user id, segment/sub-region; the ids are what reps.csv crm_user_id must hold)")
    for r in reps:
        print(f"  {r['Name']:28s} {r['Id']}  {r.get('Department') or '-'}/{r.get('Division') or '-'}")


def cmd_reset(a):
    """Return the org to its pre-skill state: delete planned accounts and their opportunities, deactivate the reps this
    script created, remove the fields/list view/report/permission set, and strip the two layout sections."""
    org = a.org
    if not a.yes:
        sys.exit("reset deletes data: rerun with --yes (dev orgs and sandboxes only)")
    if "prod" in (org or "").lower():
        sys.exit("refusing to reset an org whose alias contains 'prod'")
    guard_org(a, "reset")
    rubric = read_rubric(a.rubric) if a.rubric and os.path.exists(a.rubric) else None
    if rubric is None:
        print("no rubric file: factor fields are found by the marker in their description instead")
    desc = sf("sobject", "describe", "-s", "Account", "-o", org)
    names = {f["name"] for f in (desc.get("result") or {}).get("fields", [])}
    # 1. data: opportunities then accounts in the plan
    if "Territory_Plan__c" in names:
        for sobj, q in (("Opportunity", "SELECT Id FROM Opportunity WHERE Account.Territory_Plan__c = true"),
                        ("Account", "SELECT Id FROM Account WHERE Territory_Plan__c = true")):
            ids = [r["Id"] for r in (sf("data", "query", "-q", q, "-o", org).get("result") or {}).get("records", [])]
            if ids:
                tmp = os.path.join(tempfile.gettempdir(), f"territory_delete_{sobj}.csv")
                open(tmp, "w").write("Id\n" + "\n".join(ids) + "\n")
                r = sf("data", "delete", "bulk", "--sobject", sobj, "--file", tmp, "--wait", "10", "-o", org)
                print(f"deleted {len(ids)} {sobj} records:", (r.get("result") or {}).get("jobInfo", {}).get("state") or r.get("status"))
    # 2. reps: deactivate (Salesforce cannot delete users)
    reps = (sf("data", "query", "-q", "SELECT Id, Username FROM User WHERE IsActive = true AND Username LIKE '%@territory-plan.example'", "-o", org).get("result") or {}).get("records", [])
    for u in reps:
        sf("data", "update", "record", "-s", "User", "-i", u["Id"], "-v", "IsActive=false", "-o", org)
    print(f"deactivated {len(reps)} rep users")
    # 3. layouts: strip our sections and fields before deleting the fields
    project = fresh_project(a.project_dir)
    os.makedirs(os.path.join(project, "force-app", "main", "default"))   # sf refuses to retrieve into a missing package dir
    open(os.path.join(project, "sfdx-project.json"), "w").write(json.dumps(
        {"packageDirectories": [{"path": "force-app", "default": True}], "name": "territory-planning", "namespace": "", "sourceApiVersion": API_VERSION}))
    segments, subregions = picklists(a)
    fields, layout = plan(rubric or {"version": "?", "factors": []}, segments, subregions, True, parse_extra_fields(a.extra_fields))
    planned = {f["api"] for f in fields}
    # only fields this script made: the plan's names, plus *_Score__c fields whose description carries plan()'s marker
    # (a factor retired since, or a run without the rubric). Score fields from other tools are left alone.
    managed = planned | owned_score_fields(org, project, sorted(n for n in names if n.endswith("_Score__c") and n not in planned))
    paths = retrieve_account_layouts(org, project)
    for p in paths:
        s = open(p).read()
        for f in managed:
            s = re.sub(r"\s*<layoutItems>\s*<behavior>\w+</behavior>\s*<field>%s</field>\s*</layoutItems>" % re.escape(f), "", s)
        s = re.sub(r"\s*<layoutSections>(?:(?!</layoutSections>).)*?<label>(?:Fit Score Components|Territory)</label>.*?</layoutSections>", "", s, flags=re.S)
        open(p, "w").write(s)
    if paths:
        deploy_report(sf("project", "deploy", "start", "--source-dir", "force-app", "--target-org", org, "--wait", "20", cwd=project))
    # 4. destructive deploy: fields, list view, report, permission set (unassign it first; an assigned permission set
    #    cannot be deleted and the destructive deploy is atomic, so one failure would keep every field)
    for asg in (sf("data", "query", "-q", "SELECT Id FROM PermissionSetAssignment WHERE PermissionSet.Name = 'Territory_Planning'", "-o", org).get("result") or {}).get("records", []):
        sf("data", "delete", "record", "-s", "PermissionSetAssignment", "-i", asg["Id"], "-o", org)
    to_delete = sorted(managed & names)
    d = os.path.join(project, "destructive"); os.makedirs(d, exist_ok=True)
    types = {"CustomField": [f"Account.{f}" for f in to_delete], "ListView": ["Account.Territory_Plan"],
             "Report": ["unfiled$public/Territory_Accounts_by_Owner", "unfiled$public/Territory_Proposed_Books"], "PermissionSet": ["Territory_Planning"]}
    body = "".join(f"    <types>\n{''.join(f'        <members>{m}</members>{chr(10)}' for m in ms)}        <name>{t}</name>\n    </types>\n" for t, ms in types.items() if ms)
    open(os.path.join(d, "destructiveChanges.xml"), "w").write(f'<?xml version="1.0" encoding="UTF-8"?>\n<Package {NS}>\n{body}    <version>{API_VERSION}</version>\n</Package>\n')
    open(os.path.join(d, "package.xml"), "w").write(f'<?xml version="1.0" encoding="UTF-8"?>\n<Package {NS}>\n    <version>{API_VERSION}</version>\n</Package>\n')
    ok = deploy_report(sf("project", "deploy", "start", "--metadata-dir", d, "--target-org", org, "--wait", "20", "--ignore-warnings", cwd=project))
    if not ok:
        sys.exit("reset incomplete: the destructive deploy failed, so the fields are still there; fix the failures above and rerun")
    print(f"reset done: {len(to_delete)} fields removed; rerun `fields` to start again")


def cmd_plan(a):
    rubric = read_rubric(a.rubric)
    segments, subregions = picklists(a)
    extras = parse_extra_fields(a.extra_fields)
    fields, layout = plan(rubric, segments, subregions, not a.no_enrichment, extras)
    fields, layout = apply_without(a, fields, layout)
    print(f"Rubric {rubric.get('version')}: {len(fields)} fields" + (f" ({len(extras)} from --extra-fields)" if extras else "") + "\n")
    for sec, keys in (("Account Details", layout["details"]), ("Fit Score Components", layout["components"]), ("Territory", layout["territory"])):
        print(f"[{sec}]")
        for k in keys:
            f = next(x for x in fields if x["api"] == k); print(f"  {f['label']:32s} {f['api']:34s} {f['kind']}")
    print(f"\nSegment__c values: {', '.join(segments)}\nSub_Region__c values: {', '.join(subregions)}")
    print(f"\nnext: python3 \"{os.path.abspath(__file__)}\" fields --org <alias> --rubric {a.rubric}" + (f" --rules {a.rules}" if a.rules else "")
          + (f" --extra-fields \"{a.extra_fields}\"" if a.extra_fields else "")
          + "   (run from the project directory; the script lives in the skill folder)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["plan", "fields", "reps", "accounts", "verify", "reset"])
    ap.add_argument("--yes", action="store_true", help="required by reset; it deletes data")
    ap.add_argument("--org"); ap.add_argument("--rubric", default="rubric.md"); ap.add_argument("--reps"); ap.add_argument("--accounts")
    ap.add_argument("--segments", help=f"Segment__c picklist values, comma-separated (else from --rules, else {DEFAULT_SEGMENTS})")
    ap.add_argument("--subregions", help=f"Sub_Region__c picklist values, comma-separated (else from --rules, else the starter defaults)")
    ap.add_argument("--rules", help="territory rules file; its YAML block supplies segment and sub-region names when the flags above are not given")
    ap.add_argument("--no-enrichment", action="store_true", help="skip the built-in enrichment-value fields (the starter rubric's set); --extra-fields still apply")
    ap.add_argument("--extra-fields", default="", help="rubric-specific enrichment-value fields, 'API_Name__c:Label:kind[:length | :precision,scale]' separated by ';' "
                    f"(kinds: {', '.join(EXTRA_KINDS)}; picklist=a|b|c); pass the same list to verify and reset")
    ap.add_argument("--project-dir", default="./sf-territory"); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--allow-production", action="store_true", help="let fields/reps/accounts write to an org that is not a sandbox or Developer Edition")
    ap.add_argument("--overwrite-existing", action="store_true", help="fields: deploy even when a planned field already exists with a different type")
    ap.add_argument("--without", default="", help="plan/fields/verify: planned fields to leave out, comma-separated (e.g. Proposed_Owner__c if the org rejects the lookup)")
    a = ap.parse_args()
    if a.command != "plan" and not a.org and not a.dry:
        sys.exit("--org <alias> is required (run `sf org login web -a <alias>` first)")
    {"plan": cmd_plan, "fields": cmd_fields, "reps": cmd_reps, "accounts": cmd_accounts, "verify": cmd_verify, "reset": cmd_reset}[a.command](a)

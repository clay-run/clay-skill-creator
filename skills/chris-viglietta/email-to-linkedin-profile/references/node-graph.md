# Node graph — bodies for every code and agent node

Node numbers match Step 2 of `SKILL.md`. Each body is taken from the source workflow, with exactly
three kinds of change. Each is marked where it occurs:

- **null, not empty** — a value that is unknown is returned as `None`, so a write with
  `removeNullValues: true` skips it instead of blanking a populated field;
- **declared input** — a number or list the source hardcoded is read from an input the installer set;
- **bound** — a prompt variable the source referenced but never fed is now fed.

Wire each code node's declared-input values as static inputs on that node. Never paste a value into
the code.

## Pins, by node

| Node | Input | Pin |
|---|---|---|
| 2 Normalize name | `nameField` | trigger `$.fields[<first name field>]` + `" "` + `$.fields[<last name field>]` — **bound**; build it in the input mapping, or feed both and adjust the prompt line |
| 2 | `emailAddress` | trigger `$.fields[<email field>]` |
| 2 | `supportingText` | none — the source fed nothing here; leave empty |
| 3 Parse email | `email` | trigger `$.fields[<email field>]` |
| 3a Person behind it? | `is_generic_email`, `email_domain`, `relay_domains` | node 2 `$.structuredOutputs.is_generic_email` · node 3 `$.result.domain` · static, the declared masked-relay list |
| 3b Skip? | `skip` | node 3a `$.skip` |
| 4 Has a usable name? | `full_name` | node 2 `$.structuredOutputs.fullName` |
| 5 LinkedIn from name | Full name / Work email / Personal email / Company name / Company domain | node 2 `$.structuredOutputs.fullName` · trigger email (both email slots) · trigger `$.fields[<company name field>]` · trigger `$.accounts[0].Domain` |
| 7 LinkedIn via web search | `personName` `companyName` `emailDomain` `jobTitle` | node 2 `$.structuredOutputs.fullName` · trigger company name field · node 3 `$.result.domain` · none available yet — **bound** (the source fed none of the four) |
| 8–12 email arms | email | trigger `$.fields[<email field>]` |
| 9 / 11 found? | `linkedin_url` | the arm's own URL path from Step 1 of `SKILL.md` |
| 13 Merge | see code, plus `min_web_confidence` static | `$.result["LinkedIn URL"]` (5) · `$.structuredOutputs.linkedin_url` and `.confidence` (7) · each arm's URL path |
| 14 Enrich person | `email`, `person_identifier` | trigger email · node 13 `$.linkedin_url` |
| 15 Resolve role | `org` `title` `experience` | node 14 `$.result.org` `.title` `.experience` |
| 16 Needs web lookup? | `needs_lookup`, `matched_linkedin_url` | node 15 `$.needs_lookup` · node 13 `$.linkedin_url` |
| 17 Find employer | `name` `linkedin_url` `email` `last_known_company` `role_end_date` | node 2 `$.structuredOutputs.fullName` — **bound**: the source pinned node 2 as `$.fullName`, while every other reader of node 2 uses `$.structuredOutputs.fullName` · node 13 · node 3 `$.result.address` · node 15 `$.company` · node 15 `$.role_end_date` |
| 18 Final | see code | node 15 `$.*` · node 17 `$.current_company` `$.current_title` `$.confidence` (the source read this agent's outputs without a `structuredOutputs` prefix) · node 14 `$.result.*` · node 3 `$.result.domain` and `.isLikelyCompanyEmail` · `stale_role_days` static |
| 19 Website missing? | `company_name`, `company_domain` | node 18 |
| 20 Company Domain | `Company Name` | node 18 `$.company` |
| 21 Resolved website | `company_name` `existing_domain` `lookup_domain`, plus `placeholder_domains` static | node 18 `$.company` · node 18 `$.company_domain` · node 20 `$.result.Domain` |
| 22 Write person | each destination field | name, first, last, title, company, city, state, country ← node 18 · LinkedIn URL and source ← node 13 · website ← node 21 · lookup `id` ← trigger `$.fields.id` |
| 23 Company resolved? | `company_name`, `company_domain` | node 18 `$.company` · node 21 `$.company_domain` |
| 24 Write company | lookup `domain`, record `domain` + `org_name` | node 21 `$.company_domain` · node 18 `$.company` |
| 25 Attach company | lookup `id`, `associations|accountId`, website | trigger `$.fields.id` · node 24 `$.result.entityId` · node 21 `$.company_domain` |

Node 7 had all four prompt variables unbound in the source, so its title input is honestly empty here
too. A title is not known until node 14 runs, and node 14 runs after node 7.

Node 22 writes with `always_write` per field and `removeNullValues: true`, as the source did. Company
name was the one field the source left on the default write mode.

## 2 · Normalize name — agent, web search off

Output fields: `fullName`, `firstName`, `lastName`, `nameAlternatives`, `is_generic_email`,
`email_pattern_category`, `is_personal_email`, `is_generic_name`, `name_pattern_category`,
`is_searchable`, `unsearchable_reason`, `name_completeness`, `reasoning`.

```
# Context

You are a name-extraction and normalization specialist. Your sole job is to derive the most complete, accurate human name from raw input fields — without any internet browsing or external lookups. You work entirely from the text provided.

# Objective

Extract, clean, and structure the best human name available from the name field, email address, and any supporting text. Return a fully populated JSON object with name components, flags, and metadata.

# Instructions

## Step 1 — Gather candidates

Collect all name signals:

- The raw name field (primary source)
- The email address local part (secondary source — parse patterns like `firstname.lastname`, `flastname`, `first_last`, `first.m.last`, etc.)
- The supporting text (tertiary source — scan for a human name near job titles, signatures, "Hi [Name]", etc.)

## Step 2 — Filter and clean

Discard or ignore:

- Placeholder / test values: "test", "user", "demo", "n/a", "unknown", "null", "none", "(blank)", "---", and similar
- Pure gibberish: random character strings, keyboard mash, nonsense tokens
- Organization / company names: anything that looks like a business entity rather than a person
- Role or title terms used alone: "admin", "info", "support", "sales", "contact", "billing", "hr", "noreply", "do-not-reply", etc.
- Emoji-only or symbol-only strings

Protect and keep:

- Plausible personal names, even short ones (e.g., "Bo", "Al", "Jo")
- Names with initials (e.g., "J. Smith", "Mary A. Jones")
- Partial names where only one component is present (e.g., only a first name)
- Names written in non-Latin scripts (Arabic, Chinese, Cyrillic, etc.) — preserve them as-is
- Hyphenated surnames, particles (de, van, von, da, bin, bint, etc.), and compound given names

## Step 3 — Select the best name

Rank the candidates and pick the most complete, highest-confidence human name:

1. Prefer the name field if it is clean and unambiguous
2. Fall back to the email-parsed name if the name field is empty, a placeholder, or clearly wrong
3. Use supporting text only when both primary and secondary sources fail or conflict and supporting text provides a clearer result
4. If multiple alternatives exist (e.g., a native-script name and a romanized version), list them all in `nameAlternatives` with the primary (most complete / most likely intended) first

## Step 4 — Normalize and derive components

- Normalize Latin-script names: proper title case (respect known lowercase particles: de, van, von, da, di, del, bin, bint, al-, el-)
- Derive `firstName` and `lastName` from the final `fullName`
- For mononyms (single-name persons), put the name in `firstName` and leave `lastName` as an empty string `""`
- Never invent or hallucinate a missing name component — if something cannot be determined, use `""` or `"Name Not Found"` as specified below
- If no valid human name can be found at all, set `fullName` to `"Name Not Found"`, `firstName` to `""`, `lastName` to `""`

## Step 5 — Populate flags and metadata

### Email flags

- `is_generic_email`: true if the local part is a role/function address (info@, support@, admin@, sales@, contact@, billing@, hr@, team@, hello@, noreply@, etc.)
- `email_pattern_category`: one of "first.last", "firstlast", "first_last", "flast", "firstl", "first.middle.last", "first", "last", "generic_role", "random_or_unknown", or "" when no email is provided
- `is_personal_email`: true if the email domain is a known personal/consumer provider (gmail, yahoo, hotmail, outlook.com, icloud, proton, aol, live, etc.)

### Name flags

- `is_generic_name`: true if the resolved name is a placeholder, role term, or otherwise not a real personal name
- `name_pattern_category`: one of "full_name", "first_only", "last_only", "initials_only", "mononym", "name_with_initial", "not_found"
- `is_searchable`: true if the name is specific enough that a person could likely be found via a search (requires at minimum a real first name + real last name, or a highly distinctive mononym)
- `unsearchable_reason`: if `is_searchable` is false, briefly explain why. Use "" if searchable.
- `name_completeness`: one of "full", "partial", "none"

### Reasoning

- `reasoning`: a concise explanation (1–4 sentences) of which source was used, why alternatives were discarded, and any noteworthy parsing decisions

### Alternatives

- `nameAlternatives`: an array of strings listing all alternative name forms found. Empty array [] if none. Primary alternative first.

## Sentinel and default conventions — preserve exactly

- Missing full name → `fullName: "Name Not Found"`
- Missing first or last name components → `""`
- No email provided → `email_pattern_category: ""`
- No alternatives → `nameAlternatives: []`

# Inputs

Name Field: {{nameField}}
Email Address: {{emailAddress}}
Supporting Text: {{supportingText}}
```

The `email_pattern_category` and `name_pattern_category` lists are condensed from the source's
bulleted examples onto one line each. The values are unchanged.

## 3a · Person behind it? — code (added for this skill)

```python
def handler(context):
    generic = str(context.get_input("is_generic_email") or "").strip().lower() in ("true", "yes", "1")
    domain = str(context.get_input("email_domain") or "").strip().lower()
    # declared input: masked-relay domains, comma-separated
    relays = {d.strip().lower() for d in str(context.get_input("relay_domains") or "").split(",") if d.strip()}
    relay = any(domain == r or domain.endswith("." + r) for r in relays)
    reason = "role_address" if generic else ("masked_relay" if relay else "")
    return {"skip": "yes" if reason else "no", "skip_reason": reason or "none"}
```

## 7 · LinkedIn via web search — agent, web search on

Output fields: `linkedin_url` (string, `Not found` when none), `confidence` (number 0–100),
`evidence` (one sentence).

```
# Context

You are a LinkedIn profile verification specialist. Your task is to locate and verify the correct LinkedIn profile for a specific individual using their name, company, email domain, and job title. You must distinguish between people who share similar names or roles, handle name variations and multilingual spellings, and reason carefully about corporate relationships.

# Objective

Find, evaluate, and verify the single most accurate LinkedIn profile URL for the target individual, then return a structured result with confidence score and supporting evidence.

# Instructions

## Step 1 — Primary Search (Company-Based)
1. Search LinkedIn for the person's full name combined with their company name.
2. Also try variations: search by company domain (e.g., site:linkedin.com "company domain"), and by job title + company.

## Step 2 — Fallback Search (Domain, Title, Related Companies)
If Step 1 yields no strong candidate:
1. Search using the email domain to infer the employer (e.g., look up the company behind the domain).
2. Search by job title + email domain or job title + inferred company name.
3. If the company is a subsidiary, parent, or affiliated entity, expand the search to related company names.

## Step 3 — Name Variation Handling
1. Try common first-name and last-name variations (e.g., nicknames, hyphens, initials, accented characters removed).
2. Consider multilingual or transliterated spellings for non-English names.

## Step 4 — Profile Evaluation
For each candidate profile found:
1. Visit the profile URL and extract: full name, current job title, employer, employment history, location.
2. Confirm name match (exact or acceptable variation).
3. Confirm company match against both the provided company name and the email domain.

## Step 5 — Employment Status Verification
1. Determine employment status exclusively from the profile's experience history — do NOT infer from headline alone.
2. Identify the start and end dates of each role at the target company.
3. Mark a person as currently employed only if a role at the target company shows no end date.
4. If multiple people share the same role at the same company, compare employment date ranges and any other distinguishing evidence to select the correct individual.

## Step 6 — Confidence Scoring
After selecting the best candidate, assign a confidence score (0–100) reflecting how many signals match (name, company, title, domain, employment dates), and a one-sentence evidence summary.

## Step 7 — Output
- If a verified profile is found, return the LinkedIn URL, confidence score and evidence summary.
- If no satisfactory profile is found after all search strategies are exhausted, set the LinkedIn URL to "Not found" and confidence to 0.

## General Rules
- Never guess or fabricate a LinkedIn URL. Only return URLs you have actually visited and verified.
- Do not confuse two people who share a name — always cross-check company, title, and employment dates.

# Inputs

Person Name: {{personName}}
Company Name: {{companyName}}
Email Domain: {{emailDomain}}
Job Title: {{jobTitle}}
```

The source's prompt also asked for a relationship classification, a full search log and an execution
time. None of the three was in its output schema, and nothing read them, so they are dropped here.

## 13 · Merge LinkedIn URL — code

```python
def handler(context):
    import re
    PROVIDERS = {
        "function_linkedin_url":   "Clay native waterfall",
        "contactout_linkedin_url": "ContactOut",
        "cpj_linkedin_url":        "CPJ",
        "pdl_linkedin_url":        "People Data Labs",
    }
    ORDER = ("function_linkedin_url", "claygent_linkedin_url",
             "contactout_linkedin_url", "cpj_linkedin_url", "pdl_linkedin_url")
    # declared input: the installer's minimum confidence for a web-search match.
    # The author's default is 70. The source workflow had no minimum.
    try:
        min_conf = float(context.get_input("min_web_confidence"))
    except (TypeError, ValueError):
        min_conf = None

    for field in ORDER:
        value = context.get_input(field)
        if not isinstance(value, str):
            continue
        value = value.strip()
        match = re.fullmatch(r"(?:https?://)?(?:www\.|[a-z]{2,3}\.)?linkedin\.com/in/([^/?#\s]+)(?:/)?(?:[?#][^\s]*)?", value, re.I)
        if not match:
            continue

        # A data provider matched the email deterministically -> name the provider.
        # A web search inferred it -> report its own confidence instead,
        # because the provider name tells you nothing about whether a guess is right.
        if field == "claygent_linkedin_url":
            score = context.get_input("claygent_confidence")
            try:
                score = int(round(float(score)))
            except (TypeError, ValueError):
                score = None
            if min_conf is not None and (score is None or score < min_conf):
                continue
            source = "Claygent (confidence %d/100)" % score if score is not None else "Claygent (confidence not reported)"
        else:
            source = PROVIDERS[field]

        return {
            "linkedin_url": "https://www.linkedin.com/in/" + match.group(1),
            "linkedin_source": source,
        }

    # null, not empty
    return {"linkedin_url": None, "linkedin_source": None}
```

## 15 · Resolve current role — code

Unchanged from the source except the empty `company` and `title` values become `None`. The
`needs_lookup` flag stays a string, because node 16 compares it to `yes`.

```python
def handler(context):
    org = str(context.get_input("org") or "").strip()
    title = str(context.get_input("title") or "").strip()
    exp = context.get_input("experience") or []
    if isinstance(exp, dict):
        exp = [exp]

    def out(c, t, src, end="", dom=""):
        return {"company": c or None, "job_title": t or None, "role_source": src,
                "role_end_date": end, "company_domain": dom,
                "needs_lookup": "yes" if src in ("none", "possibly_departed") else "no"}

    # tier 1 — the provider already resolved it.
    # still look up the domain from the experience rows, the writeback needs it as a key.
    if org and title:
        dom = ""
        for e in exp:
            if isinstance(e, dict) and str(e.get("company") or "").strip().lower() == org.strip().lower():
                dom = str(e.get("company_domain") or "").strip()
                if dom:
                    break
        return out(org, title, "provider_current", "", dom)

    rows = []
    for e in exp:
        if not isinstance(e, dict):
            continue
        c = str(e.get("company") or "").strip()
        if not c and not str(e.get("title") or "").strip():
            continue
        rows.append({
            "c": c,
            "t": str(e.get("title") or "").strip(),
            "end": str(e.get("end_date") or "").strip(),
            "start": str(e.get("start_date") or "").strip(),
            "dom": str(e.get("company_domain") or "").strip(),
            "cur": bool(e.get("is_current")),
        })

    if not rows:
        return out("", "", "none")

    # tier 2 — a role the provider marks current, or one with no end date
    for r in rows:
        if r["cur"] or not r["end"]:
            return out(r["c"], r["t"], "open_ended", "", r["dom"])

    # tier 3 — every role has an end date, so pick the latest and judge it
    best = sorted(rows, key=lambda r: (r["end"], r["start"]), reverse=True)[0]

    # start == end is a one-day role: a promotion recorded badly, not a departure
    if best["start"] and best["start"] == best["end"]:
        return out(best["c"], best["t"], "promotion_artifact", best["end"], best["dom"])

    # same employer as the role before it also points to a promotion chain
    same_employer = [r for r in rows if r["c"] and r["c"] == best["c"]]
    if len(same_employer) > 1:
        return out(best["c"], best["t"], "promotion_artifact", best["end"], best["dom"])

    return out(best["c"], best["t"], "possibly_departed", best["end"], best["dom"])
```

## 17 · Find current employer (web) — agent, web search on

Output fields: `current_company`, `current_title`, `profile_text_quoted`, `evidence`,
`confidence` (select: High / Medium / Low).

```
# Objective
Find where this person works **today** and their current job title. Clay's enrichment could not resolve it: either their profile had no employment history at all, or the most recent role carries an end date suggesting they have left.

# Person
- Name: {{name}}
- LinkedIn profile: {{linkedin_url}}
- Email: {{email}}
- Last known employer (may be former): {{last_known_company}}
- That role ended: {{role_end_date}}

# Method
1. Open {{linkedin_url}} and read the Experience section. The current role is the topmost entry with no end date.
2. Quote the literal current-position text you read into `profile_text_quoted`.
3. If the profile shows nothing current, search the web: the person's name with "joins", "joined", "appointed", "announces"; their name with the last known employer; team and about pages; press releases; podcast and event speaker bios.
4. Prefer sources dated after {{role_end_date}}. A source older than that cannot establish where they work now.

# Hard rules
- If `profile_text_quoted` is empty AND no dated source after {{role_end_date}} confirms an employer, return empty strings for company and title.
- Do not return {{last_known_company}} unless a source dated after {{role_end_date}} confirms they are still there.
- Never infer an employer from the email domain or from your own prior knowledge.
- An honest blank is correct. A confident wrong employer gets written to a customer record.
- `confidence` is High only when the company you report appears in `profile_text_quoted` or in a source you dated.

# Return
- current_company, current_title, profile_text_quoted, evidence (URL and date), confidence
```

## 18 · Final company + title — code

```python
def handler(context):
    import datetime
    rc = str(context.get_input("resolved_company") or "").strip()
    rt = str(context.get_input("resolved_title") or "").strip()
    src = str(context.get_input("role_source") or "none").strip()
    end = str(context.get_input("role_end_date") or "").strip()
    ac = str(context.get_input("agent_company") or "").strip()
    at = str(context.get_input("agent_title") or "").strip()
    aconf = str(context.get_input("agent_confidence") or "").strip()
    # declared input: the stale-role window. The author's default is 365; the source used 180.
    # It only bites on end-dated roles judged a promotion artifact: a possibly_departed
    # role is withheld at any age by the branch below.
    stale_days = int(context.get_input("stale_role_days"))

    stale = False
    if end[:10].count("-") == 2:
        try:
            stale = (datetime.date.today() - datetime.date.fromisoformat(end[:10])).days > stale_days
        except Exception:
            stale = False

    if ac and aconf in ("High", "Medium"):
        company, job_title, source = ac, (at or rt), "web_lookup_" + aconf.lower()
    elif src == "possibly_departed" or (stale and src != "provider_current"):
        company, job_title, source = "", "", "withheld_stale_role"
    else:
        company, job_title, source = rc, rt, src

    placeholders = {"undefined", "null", "none", "unknown", "n/a", "not found", "name not found"}
    def clean_component(value):
        value = str(value or "").strip()
        return "" if value.lower() in placeholders else value
    full = clean_component(context.get_input("enriched_name"))
    first = clean_component(context.get_input("enriched_first"))
    last = clean_component(context.get_input("enriched_last"))
    if any(token.lower() in placeholders for token in full.split()):
        full = " ".join(part for part in (first, last) if part)
    if full and not (first or last):
        bits = full.split()
        if len(bits) >= 2:
            first, last = bits[0], " ".join(bits[1:])

    # ---- location ----
    # the dedicated country field is authoritative; the location string is free text
    # and is often a metro name with no country in it ("Greater Boston").
    country = str(context.get_input("country") or "").strip()
    loc = str(context.get_input("location_name") or "").strip()
    city = state = ""
    loc_source = "none"
    if loc:
        parts = [p.strip() for p in loc.split(",") if p.strip()]
        if len(parts) >= 3:
            city, state = parts[0], parts[1]
            if not country:
                country = parts[-1]
            loc_source = "city_state_country"
        elif len(parts) == 2:
            city, state = parts[0], parts[1]
            loc_source = "city_state"
        elif len(parts) == 1:
            # a lone fragment is a city or metro area, never a country
            city = parts[0]
            loc_source = "metro_only"

    # never let a metro or region leak into country
    if country and city and country.lower() == city.lower():
        country = ""
    if country and len(country.split()) > 4:
        country = ""

    # ---- company domain ----
    # resolved here, after enrichment, so the domain matches the company we
    # actually settled on above. Chain: the experience row that matched the
    # company -> the person's own work-email domain. Never derive a domain
    # from a company name, and never emit one for a role we withheld.
    rd = str(context.get_input("resolved_domain") or "").strip().lower()
    ed = str(context.get_input("email_domain") or "").strip().lower()
    is_work = str(context.get_input("is_company_email") or "").strip().lower() in ("true", "yes", "1")

    company_domain = ""
    domain_source = "none"
    if company:
        # the experience-row domain belongs to the PROVIDER's company. If the web
        # agent overrode the employer, that domain is for a different company,
        # and pairing them keys one company's record on another's website.
        # Only trust it when the name came from the provider.
        if rd and not source.startswith("web_lookup"):
            company_domain, domain_source = rd, "experience_row"
        elif is_work and ed:
            # a work-email domain is the employer's domain, but only trust it as a
            # key for THIS company when the provider named the current role, or the
            # domain root actually shows up in the company name. Blank beats wrong:
            # the upsert keys on domain, so a mismatch mislabels a real company.
            root = ed.split(".")[0]
            squashed = "".join(ch for ch in company.lower() if ch.isalnum())
            if source in ("provider_current", "open_ended") or (len(root) > 2 and root in squashed):
                company_domain, domain_source = ed, "work_email"
            else:
                domain_source = "work_email_rejected_mismatch"

    if company_domain:
        company_domain = company_domain.replace("https://", "").replace("http://", "")
        company_domain = company_domain.split("/")[0].split("?")[0].strip()
        if company_domain.startswith("www."):
            company_domain = company_domain[4:]

    # null, not empty — for every value node 22 writes
    n = lambda v: v or None
    return {"company": n(company), "job_title": n(job_title), "source": source,
            "company_domain": n(company_domain), "company_domain_source": domain_source,
            "full_name": n(full), "first_name": n(first), "last_name": n(last),
            "city": n(city), "state": n(state), "country": n(country),
            "location_source": loc_source}
```

## 21 · Resolved website — code

```python
def handler(context):
    import re
    company = re.sub(r"[^a-z0-9]", "", str(context.get_input("company_name") or "").lower())
    # declared input: placeholder domains, comma-separated. The source hardcoded
    # example.com, example.org, example.net, unknown.com, notfound.com.
    placeholders = {d.strip().lower() for d in str(context.get_input("placeholder_domains") or "").split(",") if d.strip()}
    for field, source in (("existing_domain", "person_enrichment"), ("lookup_domain", "company_domain_lookup")):
        value = context.get_input(field)
        if not isinstance(value, str):
            continue
        value = value.strip().lower()
        value = re.sub(r"^https?://", "", value)
        value = value.split("/")[0].split("?")[0].split("#")[0].rstrip(".")
        if value.startswith("www."):
            value = value[4:]
        if value in placeholders:
            continue
        if value == "company.com" and company != "companycom":
            continue
        if len(value) <= 253 and re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", value):
            return {"company_domain": value, "domain_source": source}
    # null, not empty
    return {"company_domain": None, "domain_source": "unresolved"}
```

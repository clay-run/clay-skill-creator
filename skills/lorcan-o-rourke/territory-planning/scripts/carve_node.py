"""Carve node (Step 7). Deterministic, zero credits, rules-driven. One file, two modes.

This is the code node of the "Territory Carve" workflow in Clay, and the same functions run locally for
the zero-credit preview (`carve.py`) and the summary (`carve_summary.py`). The sandbox ships only `json`,
so nothing else is imported.

The workflow runs once per account, on the Audiences pool (segment trigger) or on a domain through the
manual trigger. Shape: read the account from Salesforce by Website -> GATES -> (pool only) read the
eligible peers of the same bucket -> DEAL -> write Proposed Owner, Segment, Sub-region, Carve Status and
Carve Reason to Salesforce (never Owner) -> mirror on the Audiences record.

Mode `gates` (inputs rules_json, reps_json, import_user, fields_csv, account_result, domain): exclusions,
size cap, minimum size, eligibility, protections, rep picks, segment and route, in the canonical order.
Returns `decided` true with a final status, or `decided` false with `peer_soql`, the query for every
account in this segment band and region (the superset the deal filters down).

Mode `deal` (inputs rules_json, reps_json, import_user, fields_csv, account_json, gate_json,
peers_result, named_overrides_json): re-applies the gates to every peer, keeps the ones in the same
bucket (segment, region, sub-region, pooled), sorts them by fit then Id, re-runs the whole bucket's deal
(`snake` | `round_robin` | `manager` | `dynamic` | `draft`) against each rep's remaining capacity, and
returns this account's own slot. Every run of the bucket computes the same deal from the same inputs, so
concurrent runs agree and the result is explainable: "snake deal, SA / US West, rank 7 of 38".

Accounts already `Assigned` (owner is a rep) count as that rep's load and are never re-dealt. Accounts
`Proposed` by an earlier pass are still owned by the pool owner, so they are re-dealt consistently.
Hierarchy: entity mode in Clay (the CRM employee count of the account itself); family roll-up is in the
local preview only, and the summary says so when ParentId data exists.

Local: `python3 carve_node.py` runs the self-test (synthetic reps and accounts; checks that every
account gets a status, that each account's own slot equals the whole-bucket deal, and that books are
balanced within one).
"""
import json

STATUS_PROPOSED, STATUS_PROTECTED, STATUS_EXCLUDED, STATUS_NOT_ELIGIBLE, STATUS_UNOWNED = (
    "Proposed", "Protected", "Excluded", "Not eligible", "Unowned")

WANT_FIELDS = ["Id", "Name", "Website", "Industry", "NumberOfEmployees", "BillingCity", "BillingState", "BillingStateCode",
               "BillingCountry", "BillingCountryCode", "Type", "OwnerId", "ParentId", "Account_Fit_Score__c",
               "Account_Fit_Grade__c", "Scoring_Status__c", "Entity_Type__c", "Tech_Stack__c", "Sales_Team_Headcount__c",
               "Ops_Team_Headcount__c", "Open_Opportunities__c", "Is_Competitor__c", "Carve_Status__c", "Carve_Reason__c",
               "Proposed_Owner__c", "Business_Model__c", "GTM_Motion__c", "Rubric_Version__c", "Segment__c", "Sub_Region__c",
               "Engagement_Score__c"]


# ---------- small helpers ----------

def _num(v, d=None):
    try:
        if v is None or v == "" or isinstance(v, bool):
            return d
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return d


def _dom(u):
    u = (u or "").strip().lower()
    for p in ("https://", "http://"):
        if u.startswith(p):
            u = u[len(p):]
    u = u.split("/")[0]
    return u[4:] if u.startswith("www.") else u


def as_dict(v):
    return v if isinstance(v, dict) else {}


def as_list(v):
    if v is None or v == "":
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def _lower_list(v):
    return [str(s).lower() for s in as_list(v) if s not in (None, "")]


def _obj(v):
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return None
    return v


def _records(result):
    r = _obj(result)
    if isinstance(r, dict):
        recs = r.get("records")
        if recs is None and "result" in r:
            recs = as_dict(r.get("result")).get("records")
        return [x for x in (recs or []) if isinstance(x, dict)]
    if isinstance(r, list):
        return [x for x in r if isinstance(x, dict)]
    return []


def _q(s):
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _ceil_div(a, b):
    return -(-int(a) // int(b)) if b else 0


def norm(acct):
    """Normalise one Salesforce row: bare domain, state, country, employee count, fit."""
    x = {k: v for k, v in acct.items() if k != "attributes"}
    x["domain"] = _dom(x.get("Website"))
    x["state"] = x.get("BillingStateCode") or x.get("BillingState") or ""
    x["country"] = x.get("BillingCountryCode") or x.get("BillingCountry") or ""
    x["emp"] = _num(x.get("NumberOfEmployees"), None)
    x["fit"] = _num(x.get("Account_Fit_Score__c"), None)
    return x


# ---------- rules ----------

def size_cap_rule(rules):
    sc = None
    for parent in ("overrides", "exclusions"):
        blk = as_dict(rules.get(parent)).get("size_cap")
        if isinstance(blk, dict):
            sc = blk
            break
    if not sc or sc.get("enabled") is False:
        return None
    cap = _num(sc.get("max_employees", sc.get("min_employees")), 0)
    if not cap or cap <= 0:
        return None
    treat = str(sc.get("treat_as") or sc.get("action") or "Not eligible").strip().lower()
    status = STATUS_EXCLUDED if treat in ("excluded", "exclude") else STATUS_NOT_ELIGIBLE
    return {"cap": int(cap), "status": status, "field": sc.get("field"),
            "reason": sc.get("reason") or ("too big: %d+ employees" % int(cap))}


def industry_group(x, rules):
    EL = as_dict(rules.get("eligibility")); EX = as_dict(rules.get("exclusions"))
    ind = (x.get("Industry") or "").lower()
    if any(e and e in ind for e in _lower_list(EX.get("industries"))):
        return "excluded"
    core = _lower_list(EL.get("core_industries"))
    return "core" if any(c and (c in ind or ind in c) for c in core) else "other"


def exclude(x, rules, have):
    EX = as_dict(rules.get("exclusions")); EL = as_dict(rules.get("eligibility"))
    et = (x.get("Entity_Type__c") or "").lower(); d = x["domain"]
    comp_field = EX.get("competitors_field") or "Is_Competitor__c"
    vendors = _lower_list(EL.get("competing_vendors") or EX.get("competitors") or [])
    if comp_field in have and x.get(comp_field) in (True, "true", "True"):
        return "direct competitor"
    if d and (d in vendors or any(v and v.split(".")[0] and v.split(".")[0] in d for v in vendors)):
        return "direct competitor"
    if d in {_dom(p) for p in as_list(EX.get("partner_list")) if p}:
        return "partner"
    teams_field = EX.get("other_teams_field"); other_teams = _lower_list(EX.get("other_teams"))
    if teams_field and teams_field in have and other_teams and str(x.get(teams_field) or "").lower() in other_teams:
        return "owned by another team"
    ct = EX.get("company_types")
    excl_types = _lower_list(as_dict(ct).get("entity_types") if isinstance(ct, dict) else ct)
    if et and et in excl_types:
        return "company type %s: another motion owns it" % et
    edu = EX.get("education")
    if edu and d and (d.endswith(".edu") or d.endswith(".ac.uk") or (str(edu) != "edu_only" and d.endswith(".org"))) and et != "operating_company":
        return "education / institution domain"
    if industry_group(x, rules) == "excluded":
        return "industry %s: excluded" % (x.get("Industry") or "")
    hit = region_hit(x, EX.get("regions"))
    if hit:
        return "non-sellable region (%s)" % hit
    ih = EX.get("india_heavy")
    if ih and (ih is True or (isinstance(ih, dict) and ih.get("enabled"))) and _country_codes(x) & {"IN"}:
        return "India-heavy (HQ)"
    ml = EX.get("manager_list"); ml = ml if isinstance(ml, dict) else {"domains": ml}
    if d in {_dom(m) for m in as_list(ml.get("domains")) if m}:
        soft = str(ml.get("block") or "soft").lower() == "soft"
        return "manager exclusion" + (" (soft block, approver decides)" if soft else "")
    return None


# Country names and codes the exclusion list may use. Imported accounts usually carry the ISO code
# (BillingCountryCode), the interview answer usually names the country or a region, so both must match.
COUNTRY_CODES = {"israel": "IL", "india": "IN", "united states": "US", "usa": "US", "united kingdom": "GB", "uk": "GB", "canada": "CA",
                 "germany": "DE", "france": "FR", "ireland": "IE", "netherlands": "NL", "spain": "ES", "italy": "IT", "sweden": "SE",
                 "russia": "RU", "belarus": "BY", "ukraine": "UA", "china": "CN", "turkey": "TR", "united arab emirates": "AE", "uae": "AE",
                 "saudi arabia": "SA", "qatar": "QA", "kuwait": "KW", "bahrain": "BH", "oman": "OM", "jordan": "JO", "lebanon": "LB",
                 "iraq": "IQ", "iran": "IR", "syria": "SY", "yemen": "YE", "egypt": "EG", "pakistan": "PK", "brazil": "BR", "mexico": "MX",
                 "australia": "AU", "japan": "JP", "singapore": "SG", "south africa": "ZA", "nigeria": "NG", "kenya": "KE"}
REGION_CODES = {"middle east": {"IL", "AE", "SA", "QA", "KW", "BH", "OM", "JO", "LB", "IQ", "IR", "SY", "YE", "PS"},
                "cis": {"RU", "BY", "KZ", "UZ", "KG", "TJ", "TM", "AM", "AZ", "MD"},
                "africa": {"EG", "ZA", "NG", "KE", "MA", "DZ", "TN", "LY", "ET", "GH", "TZ", "UG", "SN", "CI", "CM", "AO", "ZW", "ZM", "MZ", "RW", "SD"},
                "apac": {"CN", "JP", "KR", "SG", "AU", "NZ", "IN", "ID", "MY", "TH", "VN", "PH", "TW", "HK"}}


def _country_codes(x):
    """The ISO codes an account's country fields may stand for."""
    out = set()
    for v in (x.get("BillingCountryCode"), x.get("BillingCountry"), x.get("country")):
        if not v:
            continue
        v = str(v).strip()
        if len(v) == 2:
            out.add(v.upper())
        code = COUNTRY_CODES.get(v.lower())
        if code:
            out.add(code)
    return out


def region_hit(x, regions):
    """Name of the exclusion-list entry (country or region) this account falls in, or None."""
    codes = _country_codes(x)
    names = {str(v).strip().lower() for v in (x.get("BillingCountryCode"), x.get("BillingCountry"), x.get("country")) if v}
    for r in as_list(regions):
        key = str(r).strip().lower()
        if not key:
            continue
        if key in names or key.upper() in codes or COUNTRY_CODES.get(key) in codes or (REGION_CODES.get(key) or set()) & codes:
            return str(r)
    return None


def segments(rules):
    return [s for s in as_list(rules.get("segments")) if isinstance(s, dict) and s.get("name")]


def segment_of(emp, rules):
    if emp is None:
        return None
    for s in segments(rules):
        lo, hi = _num(s.get("min_employees"), 0), s.get("max_employees")
        if emp >= lo and (hi in (None, "") or emp < _num(hi, 0)):
            return s["name"]
    return None


def _pool_value(p):
    return p.get("sub_region_value") or ("Pooled: %s" % p.get("name"))


def route(x, rules):
    """(region, sub_region, pooled). Pool city lists first, then sub-region state lists, then the default."""
    ROUTE = as_dict(rules.get("routing"))
    st, cc, city = x["state"], x["country"], (x.get("BillingCity") or "").strip().lower()
    for rname, rdef in as_dict(ROUTE.get("regions")).items():
        rdef = as_dict(rdef); rname = str(rname)
        countries = _lower_list(rdef.get("countries") or (["us", "ca"] if rname.upper() == "NAMER" else []))
        if countries and cc.lower() not in countries and (x.get("BillingCountry") or "").lower() not in countries:
            continue
        pools = [p for p in as_list(rdef.get("pools")) if isinstance(p, dict)]
        if ROUTE.get("pools_first", True):
            for p in pools:
                if city and city in _lower_list(p.get("cities")):
                    return rname, _pool_value(p), True
        default = None
        for sub, states in as_dict(rdef.get("sub_regions")).items():
            if states == "default":
                default = sub
                continue
            if st and st in as_list(states):
                return rname, str(sub), False
        if default:
            return rname, str(default), False
        if pools:
            return rname, _pool_value(pools[-1]), True
        return rname, None, False
    return None, None, False


def region_countries(rules, region):
    rdef = as_dict(as_dict(as_dict(rules.get("routing")).get("regions")).get(region))
    return [str(c) for c in as_list(rdef.get("countries") or (["US", "CA"] if str(region).upper() == "NAMER" else []))]


def rep_region(rep, rules):
    sub = (rep.get("sub_region") or "").strip().lower()
    for rname, rdef in as_dict(as_dict(rules.get("routing")).get("regions")).items():
        rdef = as_dict(rdef)
        keys = [str(k).lower() for k in as_dict(rdef.get("sub_regions")).keys()]
        pools = [str(_pool_value(p)).lower() for p in as_list(rdef.get("pools")) if isinstance(p, dict)]
        if sub == str(rname).lower() or sub in keys or sub in pools:
            return str(rname)
    return None


def eligible(x, rules):
    EL = as_dict(rules.get("eligibility"))
    thr = _num(EL.get("threshold"), 60)
    if (x.get("Scoring_Status__c") or "") != "scored" or x["fit"] is None:
        return False, "not scored"
    if x["fit"] >= thr:
        return True, "fit %g >= %g" % (x["fit"], thr)
    RE = as_dict(as_dict(rules.get("engagement")).get("reentry"))   # Step 8: a hot pool account may come back below the floor
    min_e = _num(RE.get("min_engagement"), 0) if RE else 0
    if min_e:
        eng = _num(x.get("Engagement_Score__c"), 0); min_f = _num(RE.get("min_fit"), thr)
        if eng >= min_e and x["fit"] >= min_f:
            return True, "engagement %g >= %g with fit %g >= %g (re-entry)" % (eng, min_e, x["fit"], min_f)
    if industry_group(x, rules) == "other" and EL.get("other_industries_gate"):
        ops = _num(x.get("Ops_Team_Headcount__c"), 0); sales = _num(x.get("Sales_Team_Headcount__c"), 0); emp = x["emp"] or 0
        pct = 100.0 * sales / emp if emp else 0.0
        vendors = _lower_list(EL.get("competing_vendors"))
        comp = any(v and v.split(".")[0] in (x.get("Tech_Stack__c") or "").lower() for v in vendors)
        gate = str(EL.get("other_industries_gate") or "").lower()
        if ops >= 3 and (comp or "competing_vendor" not in gate) and (sales >= 50 or pct >= 5):
            return True, "other-industry gate"
    return False, "fit %g below %g" % (x["fit"], thr)


def rep_picks(reps, rules):
    mx = int(_num(as_dict(as_dict(rules.get("protections")).get("rep_picks")).get("max"), 0) or 0)
    out = {}
    for r in reps:
        picks = [_dom(d) for d in str(r.get("protected_domains") or "").split(";") if d.strip()]
        for d in (picks[:mx] if mx else picks):
            out.setdefault(d, r)
    return out


# ---------- gates ----------

def gates(acct, rules, reps, import_user, have):
    """Decide everything that does not need the rest of the bucket. acct: a normalised row (see norm)."""
    x = acct
    EX = as_dict(rules.get("exclusions")); PROT = as_dict(rules.get("protections"))
    region, sub_region, pooled = route(x, rules)
    seg = segment_of(x["emp"], rules)
    out = {"decided": True, "account_id": x.get("Id") or "", "domain": x["domain"], "fit": x["fit"],
           "segment": seg or "", "region": region or "", "sub_region": sub_region or "", "pooled": bool(pooled),
           "industry_group": industry_group(x, rules), "owner_id": "", "owner_name": "", "carve_status": "", "carve_reason": ""}

    def done(status, reason, owner_id="", owner_name=""):
        out.update(carve_status=status, carve_reason=reason, owner_id=owner_id or "", owner_name=owner_name or "")
        return out

    why = exclude(x, rules, have)
    if why:
        return done(STATUS_EXCLUDED, why)
    SC = size_cap_rule(rules)
    if SC:
        n = x["emp"]
        if n is None and SC.get("field") and SC["field"] in have:
            n = _num(x.get(SC["field"]), None)
        if n is not None and n >= SC["cap"]:
            return done(SC["status"], "%s (%d employees)" % (SC["reason"], int(n)))
    if (x["emp"] or 0) < _num(EX.get("min_employees"), 0) or not seg:
        return done(STATUS_NOT_ELIGIBLE, "below minimum size" if x["emp"] is not None else "no employee count")
    ok, why = eligible(x, rules)
    if not ok:
        return done(STATUS_NOT_ELIGIBLE, why)
    if import_user and x.get("OwnerId") and x.get("OwnerId") != import_user:
        return done(STATUS_PROTECTED, "existing owner", x.get("OwnerId"))
    if PROT.get("open_opportunity") and _num(x.get("Open_Opportunities__c"), 0) > 0:
        return done(STATUS_PROTECTED, "open opportunity", x.get("OwnerId"))
    cust = PROT.get("customer_owner")
    cust = cust if isinstance(cust, dict) else ({"enabled": True} if cust else None)
    if cust and cust.get("enabled", True) and (x.get(cust.get("field") or "Type") or "") == (cust.get("value") or "Customer"):
        return done(STATUS_PROTECTED, "existing customer", x.get("OwnerId"))
    picks = rep_picks(reps, rules)
    if x["domain"] in picks:
        r = picks[x["domain"]]
        return done(STATUS_PROPOSED, "rep pick", r.get("crm_user_id"), r.get("name"))
    if region is None:
        return done(STATUS_UNOWNED, "no routing match")
    out["decided"] = False
    return out


def peer_soql(gate, rules, have, reps=()):
    """Every scored account in this segment band and region: the superset the deal re-gates and deals as a whole, so every
    run in the superset computes the same books. When a rep of this segment has no sub-region (serves every region), the
    country filter is dropped so that rep's capacity is counted once."""
    seg = next((s for s in segments(rules) if s["name"] == gate["segment"]), None)
    region_wide = any((r.get("segment") or "") == gate["segment"] and not (r.get("sub_region") or "").strip() for r in reps)
    fields = [f for f in WANT_FIELDS if f in have]
    if "Id" not in fields:
        fields.insert(0, "Id")
    where = ["Territory_Plan__c = true", "Scoring_Status__c = 'scored'", "Account_Fit_Score__c != null"]
    if seg:
        where.append("NumberOfEmployees >= %d" % int(_num(seg.get("min_employees"), 0)))
        if seg.get("max_employees") not in (None, ""):
            where.append("NumberOfEmployees < %d" % int(_num(seg.get("max_employees"), 0)))
    countries = [] if region_wide else region_countries(rules, gate["region"])
    if countries:
        parts = []
        for f in ("BillingCountryCode", "BillingCountry"):
            if f in have:
                parts.append("%s IN (%s)" % (f, ", ".join(_q(c) for c in countries)))
        if parts:
            where.append("(" + " OR ".join(parts) + ")")
    return "SELECT %s FROM Account WHERE %s" % (", ".join(fields), " AND ".join(where))


# ---------- deal ----------

def candidates(gate, reps, rules):
    out = []
    for r in reps:
        if (r.get("segment") or "") != gate["segment"]:
            continue
        rsub = (r.get("sub_region") or "").strip()
        if rsub == "" or rsub.lower() == (gate["sub_region"] or "").lower():
            out.append(r)
        elif gate["pooled"] and rep_region(r, rules) == gate["region"]:
            out.append(r)
    return out


def capacity(rep, rules, n_cands, pool_size):
    if str(rep.get("capacity") or "").strip():
        return int(_num(rep["capacity"], 0))
    s = next((s for s in segments(rules) if s["name"] == rep.get("segment")), {})
    cap = int(_num(s.get("capacity"), 0)); rreg = (rep_region(rep, rules) or "").lower(); rsub = (rep.get("sub_region") or "").lower()
    for k, v in as_dict(s.get("capacity_bonus")).items():
        if str(k).lower() in rsub or str(k).lower() == rreg:
            cap += int(_num(v, 0))
    if cap:
        return cap
    return _ceil_div(pool_size, n_cands or 1)


def _bucket_key(g):
    return (g["segment"], g["region"], g["sub_region"], bool(g["pooled"]))


def deal(acct, gate, peers, rules, reps, import_user, have, overrides=None):
    """Re-run the deal for every bucket in the superset (same segment band and region), with one shared capacity ledger
    per rep, in the canonical order (pooled metros first, then segment, then sub-region), and return this account's slot.
    Every run over the same superset computes the same books, so concurrent runs agree."""
    ALLOC = as_dict(rules.get("allocation"))
    method = str(ALLOC.get("method") or "snake").lower()
    sort_key = ALLOC.get("sort_key") or "fit_score"
    overrides = as_dict(_obj(overrides))
    rows = {}
    for p in peers:
        n = norm(p)
        if n.get("Id"):
            rows[n["Id"]] = n
    rows[acct["Id"]] = acct
    load, groups, gate_of = {}, {}, {}
    for x in rows.values():
        g = gates(x, rules, reps, import_user, have)
        if (x.get("Carve_Status__c") or "") == "Assigned" and x.get("OwnerId"):
            load[x["OwnerId"]] = load.get(x["OwnerId"], 0) + 1
        if not g["decided"]:
            groups.setdefault(_bucket_key(g), []).append(x); gate_of[_bucket_key(g)] = g

    def sk(x):
        v = x["fit"] if sort_key == "fit_score" else _num(x.get(sort_key), 0)
        return (-(v or 0), x.get("Id") or "")

    def rid_of(r):
        return r.get("crm_user_id") or r.get("name")
    seg_pool = {}
    for k, items in groups.items():
        seg_pool[k[0]] = seg_pool.get(k[0], 0) + len(items)
    remaining = {}
    for r in reps:
        n_in_seg = sum(1 for q in reps if (q.get("segment") or "") == (r.get("segment") or "")) or 1
        remaining[rid_of(r)] = max(0, capacity(r, rules, n_in_seg, seg_pool.get(r.get("segment") or "", 0)) - load.get(rid_of(r), 0))
    my_key = _bucket_key(gate)
    out = {"carve_status": STATUS_UNOWNED, "carve_reason": "", "proposed_owner_id": "", "proposed_owner_name": "",
           "rank": 0, "bucket_size": len(groups.get(my_key, [])), "candidate_count": 0, "method": method}
    if my_key not in groups or acct["Id"] not in {x["Id"] for x in groups[my_key]}:
        out["carve_reason"] = "not in the bucket's pool (re-run the gates)"
        return out
    assigned = {}   # account Id -> (rep or None, reason)
    for key in sorted(groups, key=lambda k: (not k[3], str(k[0]), str(k[2]))):
        items = sorted(groups[key], key=sk)
        g = gate_of[key]; label = "%s / %s" % (g["segment"], g["sub_region"]); n = len(items)
        cands = candidates(g, reps, rules)
        if key == my_key:
            out["candidate_count"] = len(cands)
            out["rank"] = next((i + 1 for i, x in enumerate(items) if x["Id"] == acct["Id"]), 0)
        if not cands:
            for x in items:
                assigned[x["Id"]] = (None, "no rep for segment / region")
            continue
        if method == "draft":
            for i, x in enumerate(items):
                assigned[x["Id"]] = (None, "awaiting draft pick (pick %d of %d, %s)" % (i + 1, n, label))
            continue
        rest = items; method_rest = method; offset = 0
        if method == "manager":
            top_n = int(_num(as_dict(ALLOC.get("named_accounts")).get("top_n"), 0) or 0)
            for x in items[:top_n]:
                want = overrides.get(x["domain"])
                r = next((c for c in cands if rid_of(c) == want), None) or cands[0]
                if remaining.get(rid_of(r), 0) > 0:
                    remaining[rid_of(r)] -= 1; assigned[x["Id"]] = (r, "named account, manager allocation")
                else:
                    assigned[x["Id"]] = (None, "named account, no rep with capacity")
            rest = items[top_n:]; method_rest = "round_robin"; offset = min(top_n, n)
        if method_rest == "dynamic":
            for x in rest:
                best = None
                for r in cands:
                    if remaining.get(rid_of(r), 0) > 0 and (best is None or remaining[rid_of(r)] > remaining[rid_of(best)]):
                        best = r
                if best is None:
                    assigned[x["Id"]] = (None, "over capacity")
                else:
                    remaining[rid_of(best)] -= 1; assigned[x["Id"]] = (best, "dynamic deal, %s: rep with the most room" % label)
            continue
        order = list(cands); i = 0; direction = 1
        for idx, x in enumerate(rest):
            placed = None
            for _ in range(len(order) * 2):
                r = order[i]
                if placed is None and remaining.get(rid_of(r), 0) > 0:
                    remaining[rid_of(r)] -= 1; placed = r
                if method_rest == "snake" and len(order) > 1:
                    if direction == 1 and i == len(order) - 1:
                        direction = -1
                    elif direction == -1 and i == 0:
                        direction = 1
                    else:
                        i += direction
                else:
                    i = (i + 1) % len(order)
                if placed is not None:
                    break
            assigned[x["Id"]] = (placed, "%s deal, %s, rank %d of %d" % (method_rest, label, idx + 1 + offset, n)) if placed is not None else (None, "over capacity")
    r, reason = assigned.get(acct["Id"], (None, "over capacity"))
    out["carve_reason"] = reason
    if r is not None:
        out.update(carve_status=STATUS_PROPOSED, proposed_owner_id=r.get("crm_user_id") or "", proposed_owner_name=r.get("name") or "")
    return out


# ---------- Clay code node ----------

def handler(context):
    mode = (context.get_input("mode") or "gates").strip().lower()
    rules = as_dict(_obj(context.get_input("rules_json")))
    reps = [r for r in (as_list(_obj(context.get_input("reps_json"))) or []) if isinstance(r, dict)]
    import_user = (context.get_input("import_user") or "").strip()
    have = set(f.strip() for f in str(context.get_input("fields_csv") or "").split(",") if f.strip()) or set(WANT_FIELDS)
    if mode == "gates":
        recs = _records(context.get_input("account_result"))
        domain = _dom(context.get_input("domain"))
        if not recs:
            return {"decided": True, "account_id": "", "domain": domain, "fit": None, "segment": "", "region": "", "sub_region": "",
                    "pooled": False, "industry_group": "", "owner_id": "", "owner_name": "", "carve_status": STATUS_NOT_ELIGIBLE,
                    "carve_reason": "account not found in Salesforce (Website lookup on %s)" % domain, "peer_soql": "",
                    "account_json": "", "gate_json": ""}
        acct = norm(recs[0])
        g = gates(acct, rules, reps, import_user, have)
        g["peer_soql"] = "" if g["decided"] else peer_soql(g, rules, have, reps)
        g["account_json"] = json.dumps(acct)
        g["gate_json"] = json.dumps({k: v for k, v in g.items() if k not in ("account_json", "gate_json", "peer_soql")})
        return g
    if mode == "deal":
        acct = as_dict(_obj(context.get_input("account_json")))
        gate = as_dict(_obj(context.get_input("gate_json")))
        if not acct or not gate:
            return {"carve_status": STATUS_UNOWNED, "carve_reason": "deal node received no account", "proposed_owner_id": "",
                    "proposed_owner_name": "", "rank": 0, "bucket_size": 0, "candidate_count": 0, "method": ""}
        peers = _records(context.get_input("peers_result"))
        return deal(acct, gate, peers, rules, reps, import_user, have, context.get_input("named_overrides_json"))
    raise ValueError("mode must be gates or deal")


# ---------- local preview over a whole universe ----------

def carve_all(accts, rules, reps, import_user, have, overrides=None):
    """Run gates on every account, then the deal per bucket (the local equivalent of one workflow run per account).
    Returns the accounts with carve_status, carve_reason, segment, sub_region, region, pooled, owner_id, rep, rank."""
    rows = [norm(a) for a in accts]
    out = []
    for x in rows:
        g = gates(x, rules, reps, import_user, have)
        x.update(segment=g["segment"], region=g["region"], sub_region=g["sub_region"], pooled=g["pooled"], industry_group=g["industry_group"])
        if (x.get("Carve_Status__c") or "") == "Assigned" and x.get("OwnerId") and x.get("OwnerId") != import_user:
            # approved in an earlier run: keep it as Assigned (the Clay node sees it as Protected / existing owner, same effect)
            x.update(carve_status="Assigned", carve_reason=x.get("Carve_Reason__c") or "assigned in an earlier run", owner_id=x["OwnerId"],
                     rep=next((r.get("name") for r in reps if r.get("crm_user_id") == x["OwnerId"]), ""), rank=0)
        elif g["decided"]:
            x.update(carve_status=g["carve_status"], carve_reason=g["carve_reason"], owner_id=g["owner_id"] or "", rep=g["owner_name"] or "", rank=0)
        else:
            d = deal(x, g, rows, rules, reps, import_user, have, overrides)
            x.update(carve_status=d["carve_status"], carve_reason=d["carve_reason"], owner_id=d["proposed_owner_id"], rep=d["proposed_owner_name"], rank=d["rank"])
        out.append(x)
    return out


def _self_test():
    rules = {"version": "t", "exclusions": {"industries": ["Retail"], "regions": ["Israel"], "min_employees": 50,
                                            "company_types": {"entity_types": ["vc_pe", "agency"]}},
             "eligibility": {"threshold": 60, "core_industries": ["Technology"]},
             "protections": {"open_opportunity": {"field": "Open_Opportunities__c"}, "customer_owner": {"enabled": True, "field": "Type", "value": "Customer"},
                             "rep_picks": {"max": 5}},
             "segments": [{"name": "SA", "min_employees": 50, "max_employees": 350, "capacity": 60},
                          {"name": "SL1/SL2", "min_employees": 350, "max_employees": 3000, "capacity": 50},
                          {"name": "SL3", "min_employees": 3000, "capacity": 45}],
             "routing": {"pools_first": True, "regions": {"NAMER": {"countries": ["US", "CA"], "sub_regions": {"US West": ["WA", "OR", "CA", "CO"], "US East": "default"},
                                                                    "pools": [{"name": "SF Bay Area", "sub_region_value": "Pooled: SF Bay Area", "cities": ["San Francisco", "Oakland"]}]},
                                                          "EMEA": {"countries": ["GB", "DE"], "sub_regions": {"Rest of EMEA": "default"}}}},
             "allocation": {"method": "snake", "sort_key": "fit_score"}}
    reps = [{"name": "Maya", "crm_user_id": "005A", "segment": "SA", "sub_region": "US West", "capacity": "", "protected_domains": "pick.io"},
            {"name": "Priya", "crm_user_id": "005B", "segment": "SA", "sub_region": "US East", "capacity": "", "protected_domains": ""},
            {"name": "Jordan", "crm_user_id": "005C", "segment": "SL1/SL2", "sub_region": "US West", "capacity": "3", "protected_domains": ""},
            {"name": "Taylor", "crm_user_id": "005D", "segment": "SL1/SL2", "sub_region": "US East", "capacity": "3", "protected_domains": ""}]
    IMP = "005IMPORT"
    states = ["CA", "WA", "NY", "MA", "TX", "CO", "FL", "OR"]
    accts = []
    for i in range(60):
        emp = [120, 200, 500, 900, 80, 1500][i % 6]
        acct = {"Id": "001%03d" % i, "Name": "Co %d" % i, "Website": "https://co%d.com" % i, "Industry": "Technology" if i % 7 else "Retail",
                "NumberOfEmployees": emp, "BillingCity": "San Francisco" if i % 9 == 0 else "Other", "BillingStateCode": states[i % len(states)],
                "BillingCountryCode": "IL" if i == 13 else "US", "Type": "Customer" if i == 5 else "Prospect", "OwnerId": "005REP" if i == 6 else IMP,
                "Account_Fit_Score__c": 40 + (i * 37) % 60, "Scoring_Status__c": "scored", "Open_Opportunities__c": 1 if i == 8 else 0}
        if i in (5, 8):   # the customer and the open-opportunity cases must pass the fit floor to reach the protections
            acct["Account_Fit_Score__c"] = 88
        accts.append(acct)
    accts.append({"Id": "001PICK", "Name": "Pick", "Website": "https://pick.io", "Industry": "Technology", "NumberOfEmployees": 100, "BillingCity": "Other",
                  "BillingStateCode": "NY", "BillingCountryCode": "US", "Type": "Prospect", "OwnerId": IMP, "Account_Fit_Score__c": 70, "Scoring_Status__c": "scored", "Open_Opportunities__c": 0})
    have = set(accts[0].keys()) | {"Open_Opportunities__c"}
    res = carve_all(accts, rules, reps, IMP, have)
    assert all(x["carve_status"] for x in res), "every account gets a status"
    by = {}
    for x in res:
        by[x["carve_status"]] = by.get(x["carve_status"], 0) + 1
    pick = next(x for x in res if x["Id"] == "001PICK"); assert pick["carve_status"] == "Proposed" and pick["rep"] == "Maya", pick
    assert next(x for x in res if x["Id"] == "001005")["carve_reason"] == "existing customer"
    assert next(x for x in res if x["Id"] == "001006")["carve_reason"] == "existing owner"
    assert next(x for x in res if x["Id"] == "001008")["carve_reason"] == "open opportunity"
    assert next(x for x in res if x["Id"] == "001013")["carve_status"] == "Excluded"
    # per-account slot equals the whole-bucket deal, and concurrent runs agree
    rows = [norm(a) for a in accts]
    for x in res:
        if x["carve_status"] in ("Proposed", "Unowned") and x["carve_reason"] != "no routing match":
            g = gates(x, rules, reps, IMP, have)
            if g["decided"]:
                continue
            d = deal(x, g, rows, rules, reps, IMP, have)
            assert d["proposed_owner_id"] == x["owner_id"], (x["Id"], d, x["owner_id"])
    books = {}
    for x in res:
        if x["carve_status"] == "Proposed" and x["carve_reason"] != "rep pick":
            k = (x["segment"], x["sub_region"]); books.setdefault(k, {}); books[k][x["rep"]] = books[k].get(x["rep"], 0) + 1
    for k, b in books.items():
        if len(b) > 1:
            assert max(b.values()) - min(b.values()) <= 1, (k, b)
    sl_caps = sum(1 for x in res if x["segment"] == "SL1/SL2" and x["carve_status"] == "Proposed")
    assert sl_caps <= 6, "capacity 3 per SL rep is respected"
    print("self-test ok:", by, "| SL1/SL2 proposed", sl_caps, "| books", {"%s/%s" % k: v for k, v in books.items()})
    # a second method: dynamic
    rules2 = dict(rules); rules2["allocation"] = {"method": "dynamic", "sort_key": "fit_score"}
    res2 = carve_all(accts, rules2, reps, IMP, have)
    print("dynamic ok:", sum(1 for x in res2 if x["carve_status"] == "Proposed"), "proposed")
    # peer SOQL shape
    g = gates(norm(accts[0]), rules, reps, IMP, have)
    print("peer soql:", peer_soql(g, rules, have, reps)[:160] + "...")


if __name__ == "__main__":
    _self_test()

#!/usr/bin/env python3
"""Step 8: engagement after the carve. Three Clay Signals watch the assigned books (and the pool); every event adds points
to an Engagement Score next to the fit score, in Salesforce and in Audiences; a weekly decay keeps the number about this
week; `health` turns it into book health and pool candidates. Nothing here writes an Owner. Run from the project root
after Step 7's books are approved (the fields come from Step 5; `sf_setup.py fields` is idempotent and adds them).

  python3 engagement.py build  --org <alias> --rules territory-rules.md [--carve ./carve] [--out ./engagement] [--app-account aa_...] [--no-decay] [--dry]
  python3 engagement.py test   --org <alias> --out ./engagement --domain <domain> [--type NewHire|News|JobPost] [--headline "..."] [--points N]
  python3 engagement.py resume --out ./engagement --yes          # start the signals: events cost data credits
  python3 engagement.py pause  --out ./engagement
  python3 engagement.py status --org <alias> --out ./engagement
  python3 engagement.py health --org <alias> --rules territory-rules.md --reps reps.csv [--out ./engagement]

build is idempotent (state in <out>/engagement.json) and creates, all as drafts:
  - Audiences fields Engagement Score (number), Last Signal (text), Last Signal Date (text)
  - the segment "Territory books (assigned)": domain not empty, Carve Status = Assigned
  - one signal per enabled type in the rules file's `engagement` block, PAUSED, watching the assigned segment and the
    Eligible pool segment from <carve>/carve-workflow.json (engagement.watch_pool)
  - "Territory Engagement": manual trigger (domain, signal_type, headline, points) for tests + one audience_signal trigger
    per signal -> Pick the event -> Salesforce: read the account -> Score the event -> In the plan? -> Salesforce: write
    the engagement score -> Audiences: mirror the engagement score
  - "Territory Engagement Decay": one audience_scheduled trigger (weekly) per watched segment -> Pick the record ->
    Salesforce: read the account -> Decay -> In the plan? -> the same two writers, score only
Publishing a workflow is the user's call (`clay workflows publish <wf>`); a draft trigger fires nothing. Measured on the CLI:
an audience_signal trigger node outputs $.fields (the Audience record by display name) and $.signal
(signalEventId, signalId, signalType, emittedAt, activityTime, data); audience_scheduled takes segmentId, entityType and a
simple weekly scheduleConfig and outputs $.fields.
"""
import argparse, datetime, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import carve_workflow as cw          # noqa: E402  (clay/sf wrappers, package ids, node helpers)
import carve_node                    # noqa: E402
from carve_node import as_dict, as_list, _num as num, _dom as dom   # noqa: E402

clay, sf, records, src, ref, static, create_node, binop = cw.clay, cw.sf, cw.records, cw.src, cw.ref, cw.static, cw.create_node, cw.binop

SF_FIELDS = ["Engagement_Score__c", "Last_Signal__c", "Last_Signal_Date__c"]
AUD = {"engagement": ("Engagement Score", "number"), "last_signal": ("Last Signal", "text"), "last_signal_date": ("Last Signal Date", "text"),
       "sfdc_id": ("Salesforce Account Id", "text")}
NAMES = {"pick": "Pick the event", "read": "Salesforce: read the account", "score": "Score the event", "cond": "In the plan?",
         "write": "Salesforce: write the engagement score (never Owner)", "mirror": "Audiences: mirror the engagement score", "skip": "Not in the plan",
         "d_pick": "Pick the record", "d_decay": "Decay"}
DEFAULTS = {
    "segment_name": "Territory books (assigned)", "watch_pool": True, "cap": 100, "manual_points": 20,
    "signals": {
        "news": {"enabled": True, "type": "News", "points": 25, "schedule": "weekly", "name": "Territory books: company news and funding",
                 "max_per_domain": 3, "lookback_days": 30,
                 "topics": ["Fundraising", "Investment", "Merger & Acquisition", "Executive Appointment", "Executive Change", "Business Expansion",
                            "New Product Launch", "Initial Public Offering"]},
        "gtm_hires": {"enabled": True, "type": "NewHire", "points": 30, "schedule": "weekly", "name": "Territory books: GTM leadership hires",
                      "seniority_floor": "director", "limit_per_company": 5, "lookback_months": 3,
                      "titles": ["VP Sales", "VP of Sales", "Head of Sales", "Chief Revenue Officer", "CRO", "VP Revenue Operations",
                                 "Head of Revenue Operations", "Director of Sales", "GTM Engineer", "Head of Growth"]},
        "job_posts": {"enabled": True, "type": "JobPost", "points": 15, "schedule": "weekly", "name": "Territory books: sales and RevOps job postings",
                      "limit_per_company": 5, "max_days_since_posted": 30,
                      "titles": ["SDR", "BDR", "Sales Development Representative", "Business Development Representative", "Account Executive",
                                 "Revenue Operations", "RevOps", "GTM Engineer", "Sales Operations"]}},
    "decay": {"enabled": True, "every": "weekly", "keep": 0.75, "timezone": "Europe/London"},
    "reentry": {"min_engagement": 40, "min_fit": 50},
}

# The exact input shapes the three signal types take, read back from working signals with `clay signals get`
# (--input takes the same shape). Only the keys the rules file names are changed.
SIGNAL_TEMPLATES = json.loads(r'''{"NewHire":{"type":"NewHire","filters":{"start_from_method":"query","company_identifier":[],"company_record_id":[],"company_table_id":"","include_company_filter_identifier_count":0,"exclude_entities_configuration":[],"languages":[],"certification_keywords":[],"school_names":[],"names":[],"profile_keywords":[],"headline_keywords":[],"about_keywords":[],"include_past_experiences":false,"exclude_people_identifiers_mixed":[],"job_title_mode":"contain","job_functions":[],"job_title_seniority_levels":[],"job_title_seniority_levels_v2":[],"job_title_seniority_match_mode":"floor","job_title_seniority_floor_level":"director","locations":[],"locations_exclude":[],"location_cities_exclude":[],"location_cities_include":[],"location_countries_exclude":[],"location_countries_include":[],"location_regions_exclude":[],"location_regions_include":[],"search_raw_location":false,"location_states_exclude":[],"location_states_include":[],"company_sizes":[],"company_annual_revenues":[],"company_industries_exclude":[],"company_industries_include":[],"company_description_keywords_exclude":[],"company_description_keywords":[],"limit_per_company":5,"job_title_exclude_keywords":[],"job_title_keywords":["VP Sales","VP of Sales","Head of Sales","Chief Revenue Officer","CRO","VP Revenue Operations","Head of Revenue Operations","Director of Sales","GTM Engineer","Head of Growth"],"job_description_keywords":[]},"lookBackTimeWindowInMonths":3,"entityType":"ACCOUNT"},"JobPost":{"type":"JobPost","filters":{"exclude_job_identifiers":[],"startFrom":"ClayTableOfCompanies","company_identifier":[],"company_record_id":[],"company_table_id":"","locations":[],"locations_exclude":[],"limit_per_company":5,"employment_type":["Full-time"],"seniority":[],"has_recruiter":false,"job_title_exclude_keywords":[],"job_title_keywords":["SDR","BDR","Sales Development Representative","Business Development Representative","Account Executive","Revenue Operations","RevOps","GTM Engineer","Sales Operations"],"max_num_days_since_posted":30,"job_description_keywords":[]},"entityType":"ACCOUNT"},"News":{"type":"News","filters":{"topics":["Fundraising","Investment","Merger & Acquisition","Executive Appointment","Executive Change","Business Expansion","New Product Launch","Initial Public Offering"],"maxNewsPerDomain":3,"earliestPublishDate":"2026-09-15","autoAdvanceEarliestPublishDate":true},"entityType":"ACCOUNT"}}''')


# ---------- config and state ----------

def merge(a, b):
    out = json.loads(json.dumps(a))
    for k, v in as_dict(b).items():
        out[k] = merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def eng_cfg(rules):
    return merge(DEFAULTS, rules.get("engagement"))


def state_path(out):
    return os.path.join(out, "engagement.json")


def load_state(out):
    p = state_path(out)
    return json.load(open(p)) if os.path.exists(p) else {}


def save_state(out, st):
    os.makedirs(out, exist_ok=True)
    json.dump(st, open(state_path(out), "w"), indent=1)


def have_fields(org):
    return {f["name"] for f in (sf("sobject", "describe", "-s", "Account", "-o", org).get("result") or {}).get("fields", [])}


def aud_fields(create_missing=True):
    d = clay("audiences", "fields", "list", "--entity-type", "companies", quiet=True)
    items = d.get("data") if isinstance(d, dict) else d
    by = {str(f.get("name") or "").strip().lower(): f.get("id") for f in (items or []) if isinstance(f, dict)}
    out = {}
    for key, (name, dtype) in AUD.items():
        fid = by.get(name.lower())
        if not fid and create_missing and key != "sfdc_id":
            c = clay("audiences", "fields", "create", "--entity-type", "companies", "--name", name, "--data-type", dtype)
            fid = c.get("id"); print("created Audiences field", c.get("name") or name, fid)
        out[key] = fid
    out["carve_status"] = by.get("carve status"); out["fit"] = by.get("account fit score")
    return out


def forms_soql(extra_fields=()):
    forms = " OR ".join("Website = '%s://%s{{domain}}'" % (scheme, www) for scheme in ("https", "http") for www in ("", "www."))
    cols = ["Id", "Name", "OwnerId", "Carve_Status__c"] + list(extra_fields)
    return "SELECT %s FROM Account WHERE Territory_Plan__c = true AND (%s) LIMIT 1" % (", ".join(cols), forms)


# ---------- signals ----------

def signal_input(key, s, segment_ids):
    t = s.get("type") or DEFAULTS["signals"].get(key, {}).get("type")
    if t not in SIGNAL_TEMPLATES:
        sys.exit("engagement.signals.%s: type %r is not one of %s" % (key, t, sorted(SIGNAL_TEMPLATES)))
    tpl = json.loads(json.dumps(SIGNAL_TEMPLATES[t])); f = tpl.setdefault("filters", {})
    if t == "News":
        f["topics"] = [str(x) for x in as_list(s.get("topics"))] or f.get("topics") or []
        f["maxNewsPerDomain"] = int(num(s.get("max_per_domain"), f.get("maxNewsPerDomain") or 3))
        f["earliestPublishDate"] = (datetime.date.today() - datetime.timedelta(days=int(num(s.get("lookback_days"), 30)))).isoformat()
        f["autoAdvanceEarliestPublishDate"] = True
    elif t == "NewHire":
        f["job_title_keywords"] = [str(x) for x in as_list(s.get("titles"))] or f.get("job_title_keywords") or []
        if s.get("seniority_floor"):
            f["job_title_seniority_match_mode"] = "floor"; f["job_title_seniority_floor_level"] = str(s["seniority_floor"])
        f["limit_per_company"] = int(num(s.get("limit_per_company"), f.get("limit_per_company") or 5))
        tpl["lookBackTimeWindowInMonths"] = int(num(s.get("lookback_months"), tpl.get("lookBackTimeWindowInMonths") or 3))
    elif t == "JobPost":
        f["job_title_keywords"] = [str(x) for x in as_list(s.get("titles"))] or f.get("job_title_keywords") or []
        f["max_num_days_since_posted"] = int(num(s.get("max_days_since_posted"), f.get("max_num_days_since_posted") or 30))
        f["limit_per_company"] = int(num(s.get("limit_per_company"), f.get("limit_per_company") or 5))
    tpl["type"] = t; tpl["entityType"] = "ACCOUNT"; tpl["segmentIds"] = list(segment_ids)
    return tpl


def enabled_signals(cfg):
    out = []
    for key, s in as_dict(cfg.get("signals")).items():
        s = merge(DEFAULTS["signals"].get(key, {}), s)
        if s.get("enabled", True):
            out.append((key, s))
    return out


# ---------- node code ----------

def baked(code, cfg):
    return code.replace("__CONFIG__", json.dumps(json.dumps(cfg)))


PICK_CODE = '''import json, datetime

CONFIG = json.loads(__CONFIG__)   # baked by engagement.py build: points per signal type, manual_points


def _s(v):
    return "" if v is None or isinstance(v, (dict, list)) else str(v).strip()


def _domain(v):
    v = _s(v).lower()
    for p in ("https://", "http://"):
        if v.startswith(p):
            v = v[len(p):]
    v = v.split("/")[0]
    return v[4:] if v.startswith("www.") else v


def _headline(data, depth=0):
    """A short human line for Last Signal. Signal payloads nest the event under a type-specific object
    (news: data.newsData.newsTitle + publisher; hires and jobs: a person or job object), so look inside first."""
    if not isinstance(data, dict) or depth > 3:
        return ""
    for sub in ("newsData", "hireData", "jobData", "personData", "news", "hire", "job", "person", "event", "payload"):
        if isinstance(data.get(sub), dict):
            h = _headline(data[sub], depth + 1)
            if h and not h.startswith("{"):
                return h
    for keys in (("newsTitle", "publisher"), ("title", "publisher"), ("title",), ("headline",), ("person_name", "job_title"),
                 ("personName", "jobTitle"), ("full_name", "job_title"), ("fullName", "jobTitle"), ("name", "job_title"),
                 ("name", "jobTitle"), ("job_title", "company_name"), ("jobTitle",), ("job_title",), ("name",), ("summary",), ("description",)):
        vals = [_s(data.get(k)) for k in keys if _s(data.get(k))]
        if vals:
            return " - ".join(vals)[:200]
    for v in data.values():
        if isinstance(v, dict):
            h = _headline(v, depth + 1)
            if h and not h.startswith("{"):
                return h
    return json.dumps(data)[:200]


def handler(context):
    today = datetime.date.today().isoformat()
    m_domain = _domain(context.get_input("m_domain"))
    if m_domain:
        t = _s(context.get_input("m_type")) or "Manual"
        pts = _s(context.get_input("m_points"))
        pts = float(pts) if pts else float(CONFIG["points"].get(t, CONFIG["manual_points"]))
        return {"domain": m_domain, "signal_type": t, "headline": _s(context.get_input("m_headline")) or ("%s (manual test)" % t),
                "activity_date": today, "points": pts}
    for i in range(1, 9):
        f = context.get_input("e%d_fields" % i); s = context.get_input("e%d_signal" % i)
        if not isinstance(f, dict) and not isinstance(s, dict):
            continue
        f = f if isinstance(f, dict) else {}; s = s if isinstance(s, dict) else {}
        d = _domain(f.get("Domain") or f.get("domain") or f.get("Normalized domain"))
        if not d:
            continue
        t = _s(s.get("signalType")) or "Signal"
        when = (_s(s.get("activityTime")) or _s(s.get("emittedAt")))[:10] or today
        return {"domain": d, "signal_type": t, "headline": _headline(s.get("data")) or t, "activity_date": when,
                "points": float(CONFIG["points"].get(t, CONFIG["manual_points"]))}
    return {"domain": "", "signal_type": "", "headline": "", "activity_date": today, "points": 0.0}
'''

SCORE_CODE = '''import json

CONFIG = json.loads(__CONFIG__)   # baked by engagement.py build: cap


def _records(res):
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            return []
    if isinstance(res, dict):
        recs = res.get("records")
        if recs is None and isinstance(res.get("result"), dict):
            recs = res["result"].get("records")
        return [r for r in (recs or []) if isinstance(r, dict)]
    return [r for r in res if isinstance(r, dict)] if isinstance(res, list) else []


def handler(context):
    recs = _records(context.get_input("result"))
    empty = {"found": False, "account_id": "", "account_name": "", "old_score": 0.0, "new_score": 0.0, "last_signal": "", "last_signal_date": ""}
    if not recs or not recs[0].get("Id"):
        return empty
    r = recs[0]
    old = float(r.get("Engagement_Score__c") or 0)
    pts = float(context.get_input("points") or 0)
    new = min(float(CONFIG["cap"]), round(old + pts, 1))
    t = str(context.get_input("signal_type") or "Signal"); h = str(context.get_input("headline") or t)
    when = str(context.get_input("activity_date") or "")[:10]
    return {"found": True, "account_id": r.get("Id"), "account_name": r.get("Name") or "", "old_score": old, "new_score": new,
            "last_signal": ("%s: %s (+%g)" % (t, h, pts))[:255], "last_signal_date": when}
'''

DECAY_PICK_CODE = '''def handler(context):
    def _s(v):
        return "" if v is None or isinstance(v, (dict, list)) else str(v).strip()
    def _domain(v):
        v = _s(v).lower()
        for p in ("https://", "http://"):
            if v.startswith(p):
                v = v[len(p):]
        v = v.split("/")[0]
        return v[4:] if v.startswith("www.") else v
    for i in range(1, 9):
        f = context.get_input("e%d_fields" % i)
        if isinstance(f, dict):
            d = _domain(f.get("Domain") or f.get("domain") or f.get("Normalized domain"))
            if d:
                return {"domain": d, "audience_score": f.get("Engagement Score")}
    return {"domain": "", "audience_score": None}
'''

DECAY_CODE = '''import json

CONFIG = json.loads(__CONFIG__)   # baked by engagement.py build: keep


def _records(res):
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            return []
    if isinstance(res, dict):
        recs = res.get("records")
        if recs is None and isinstance(res.get("result"), dict):
            recs = res["result"].get("records")
        return [r for r in (recs or []) if isinstance(r, dict)]
    return [r for r in res if isinstance(r, dict)] if isinstance(res, list) else []


def handler(context):
    recs = _records(context.get_input("result"))
    if not recs or not recs[0].get("Id"):
        return {"found": False, "account_id": "", "old_score": 0.0, "new_score": 0.0}
    r = recs[0]; old = float(r.get("Engagement_Score__c") or 0)
    if old <= 0:
        return {"found": False, "account_id": r.get("Id"), "old_score": old, "new_score": 0.0}
    new = round(old * float(CONFIG["keep"]), 1)
    return {"found": True, "account_id": r.get("Id"), "old_score": old, "new_score": new if new >= 1 else 0.0}
'''

COND_CODE = '''def handler(context):
    f = context.get_input("found")
    if f is True or str(f).lower() == "true":
        return context.transition_to(%s, "write")
    return context.transition_to(%s, "skip")
''' % (json.dumps(NAMES["write"]), json.dumps(NAMES["skip"]))

SKIP_CODE = '''def handler(context):
    return {"note": "not a Territory Plan account in Salesforce, or no engagement to write: %s" % (context.get_input("domain") or "")}
'''


# ---------- build ----------

def manual_trigger(WF):
    props = {"domain": {"type": "string", "description": "Account domain, e.g. vercel.com (matched on Website, Territory Plan = true)"},
             "signal_type": {"type": "string", "description": "News | NewHire | JobPost | anything; sets the points"},
             "headline": {"type": "string", "description": "What happened, written to Last Signal"},
             "points": {"type": "number", "description": "Override the points for this event"}}
    t = clay("workflows", "triggers", "create", WF, inp={"triggerType": "manual", "inputSchema": {"type": "object", "properties": props, "required": ["domain"]}})
    tid = t.get("resourceId"); node = clay("workflows", "triggers", "get", tid).get("workflowNodeId") if tid else None
    if not node:
        sys.exit("manual trigger failed: %s" % json.dumps(t)[:600])
    return tid, node


def writers(WF, pk, acct, aud, after, props, fields_sf, fields_aud, dry):
    """Salesforce update-object then the Audiences mirror; fields_sf: {api: '{{var}}'}, fields_aud: {aud key: '{{var}}'}."""
    wmap = {"recordId": ref("{{account_id}}"), "object_type": static("Account"), "removeNullValues": static(True), "object_fields|disableAutoAssignmentRules": static(True)}
    for api, expr in fields_sf.items():
        wmap["object_fields|" + api] = ref(expr)
    w = create_node(WF, {"nodeType": "tool", "name": NAMES["write"], "inputSchema": {"type": "object", "properties": props},
                         "tools": [{"toolType": "clay_action", "actionKey": "update-object", "actionPackageId": pk["sf"], "appAccountId": acct, "inputMappingConfig": wmap}],
                         "incomingEdges": after}, "write", dry)
    rf = {aud.get(k): expr for k, expr in fields_aud.items() if aud.get(k)}
    mmap = {"entityType": static("ACCOUNT"), "lookupFields|selectedLookupFields": static(["domain"]), "lookupFields|domain": ref("{{domain}}"),
            "recordFields|selectedRecordFields": static(list(rf.keys())), "recordFields|removeNullValues": static(True)}
    for k, expr in rf.items():
        mmap["recordFields|" + k] = ref(expr)
    m = create_node(WF, {"nodeType": "tool", "name": NAMES["mirror"], "inputSchema": {"type": "object", "properties": props},
                         "tools": [{"toolType": "clay_action", "actionKey": "upsert-audiences-record", "actionPackageId": pk["aud"], "inputMappingConfig": mmap}],
                         "incomingEdges": [{"sourceNode": w}]}, "mirror", dry)
    return w, m


def next_monday_iso(hour=8):
    d = datetime.date.today(); d = d + datetime.timedelta(days=(7 - d.weekday()) % 7 or 7)
    return "%sT%02d:00:00.000Z" % (d.isoformat(), hour)


def cmd_build(a):
    rules = cw.load_rules(a.rules); cfg = eng_cfg(rules)
    st = load_state(a.out)
    if st.get("workflow") and not a.dry:
        print("already built: %s names workflow %s (%s). `test` fires one event; `resume --yes` starts the signals; `status` reports; "
              "delete the file only to build a second set." % (state_path(a.out), st["workflow"]["id"], st["workflow"]["name"]))
        return
    carve = cw.load_state(a.carve) if a.carve else {}
    pk = carve.get("packages") or cw.package_ids()
    acct = a.app_account or carve.get("app_account") or cw.discover_app_account(pk["sf"])
    if not acct and not a.dry:
        sys.exit("no Salesforce connection id found on any workflow; pass --app-account aa_... (read it off the scoring workflow's Salesforce node)")
    have = have_fields(a.org)
    missing = [f for f in SF_FIELDS if f not in have]
    if missing and not a.dry:
        sys.exit("the org has no %s yet: run Step 5 again (sf_setup.py fields is idempotent and adds the engagement fields)" % ", ".join(missing))
    if missing:
        print("dry run: the org has no %s yet (Step 5 adds them); continuing" % ", ".join(missing))
    aud = aud_fields(create_missing=not a.dry)
    if not a.dry and not all(aud.get(k) for k in ("engagement", "last_signal", "last_signal_date")):
        sys.exit("could not create the Audiences fields: %s" % json.dumps(aud))
    sigs_cfg = enabled_signals(cfg)
    print("engagement: %d signals %s | cap %g | decay %s keep %g | re-entry engagement >= %g with fit >= %g | Salesforce connection %s" % (
        len(sigs_cfg), [s["type"] for _, s in sigs_cfg], num(cfg.get("cap"), 100), "on" if as_dict(cfg.get("decay")).get("enabled", True) and not a.no_decay else "off",
        num(as_dict(cfg.get("decay")).get("keep"), 0.75), num(as_dict(cfg.get("reentry")).get("min_engagement"), 0), num(as_dict(cfg.get("reentry")).get("min_fit"), 0), acct))
    st = {"rules": os.path.abspath(a.rules), "carve": os.path.abspath(a.carve) if a.carve else None, "app_account": acct, "packages": pk, "audience_fields": aud,
          "config": cfg, "built_at": datetime.datetime.now().isoformat(timespec="seconds")}

    # 1. the assigned segment
    seg_name = str(cfg.get("segment_name") or DEFAULTS["segment_name"])
    if a.dry:
        seg_id = "audseg_DRY"
    else:
        flt = {"type": "GroupOp", "combinationMode": "And", "items": [binop("domain", "NotEmpty"), binop(aud["carve_status"], "Equal", "Assigned")]}
        seg = clay("audiences", "create", "--entity-type", "companies", "--name", seg_name, "--description",
                   "Accounts with an approved owner (Carve Status = Assigned). The signals watch it; the decay runs over it.", "--filter", json.dumps(flt))
        seg_id = seg.get("id") or sys.exit("segment create failed: %s" % json.dumps(seg)[:500])
        seg_name = seg.get("name") or seg_name
    print("segment", seg_id, seg_name)
    watched = [seg_id]
    pool_id = carve.get("segment_id") if cfg.get("watch_pool", True) else None
    if pool_id:
        watched.append(pool_id); print("also watching the pool segment", pool_id)
    elif cfg.get("watch_pool", True):
        print("note: no Eligible pool segment in %s yet (carve_workflow.py segment creates it); the signals watch the books only" % (a.carve or "--carve"))
    st.update(segment_id=seg_id, segment_name=seg_name, pool_segment_id=pool_id, watched_segments=watched)

    # 2. the signals, paused
    sigs = []
    for key, s in sigs_cfg:
        inp = signal_input(key, s, watched)
        if a.dry:
            print("-- signal", key, s["type"], json.dumps(inp)[:200]); sigs.append({"key": key, "type": s["type"], "id": "td_DRY_" + key, "signal_id": "sig_DRY_" + key, "name": s.get("name"), "points": s.get("points")}); continue
        c = clay("signals", "create", "--type", s["type"], "--name", str(s.get("name") or s["type"]), "--schedule", str(s.get("schedule") or "weekly"), inp=inp)
        if not c.get("id"):
            sys.exit("signal %s failed: %s" % (key, json.dumps(c)[:800]))
        sigs.append({"key": key, "type": s["type"], "id": c["id"], "signal_id": (c.get("signal") or {}).get("id"), "name": c.get("name"), "points": s.get("points"), "runStatus": c.get("runStatus")})
        print("signal %-10s %s %s (%s)" % (key, c["id"], c.get("name"), c.get("runStatus")))
    st["signals"] = sigs

    # 3. the engagement workflow
    name = a.name or "Territory Engagement"
    if a.dry:
        WF = "wf_DRY"; tid, trig = None, "wfn_DRY_trigger"; url = None
        strig = [dict(s, trigger_id=None, node="wfn_DRY_" + s["key"]) for s in sigs]
    else:
        w = clay("workflows", "create", "--name", name); WF = w.get("id") or sys.exit("workflow create failed: %s" % json.dumps(w)[:600]); url = w.get("url")
        tid, trig = manual_trigger(WF)
        strig = []
        for s in sigs:
            t = clay("workflows", "triggers", "create", WF, inp={"triggerType": "audience_signal", "signalId": s["signal_id"], "entityType": "ACCOUNT"})
            rid = t.get("resourceId"); node = clay("workflows", "triggers", "get", rid).get("workflowNodeId") if rid else None
            if not node:
                sys.exit("signal trigger for %s failed: %s" % (s["key"], json.dumps(t)[:600]))
            strig.append(dict(s, trigger_id=rid, node=node)); print("trigger %-10s %s" % (s["key"], rid))
    points = {s["type"]: float(num(s.get("points"), cfg["manual_points"])) for s in sigs}
    N = {}
    pprops = {"m_domain": src(trig, "$.domain"), "m_type": src(trig, "$.signal_type"), "m_headline": src(trig, "$.headline"), "m_points": src(trig, "$.points", "number")}
    edges = [{"sourceNode": trig}]
    for i, s in enumerate(strig, 1):
        pprops["e%d_fields" % i] = src(s["node"], "$.fields", "object"); pprops["e%d_signal" % i] = src(s["node"], "$.signal", "object"); edges.append({"sourceNode": s["node"]})
    N["pick"] = create_node(WF, {"nodeType": "code", "name": NAMES["pick"], "code": baked(PICK_CODE, {"points": points, "manual_points": float(num(cfg.get("manual_points"), 20))}),
                                 "inputSchema": {"type": "object", "properties": pprops}, "incomingEdges": edges}, "pick", a.dry)
    N["read"] = create_node(WF, {"nodeType": "tool", "name": NAMES["read"], "inputSchema": {"type": "object", "properties": {"domain": src(N["pick"], "$.domain")}},
                                 "tools": [{"toolType": "clay_action", "actionKey": "salesforce-lookup-via-soql", "actionPackageId": pk["sf"], "appAccountId": acct,
                                            "inputMappingConfig": {"soql_query": ref(forms_soql(["Engagement_Score__c", "Last_Signal_Date__c"]))}}],
                                 "incomingEdges": [{"sourceNode": N["pick"]}]}, "read", a.dry)
    sprops = {"result": src(N["read"], "$.result", "object"), "points": src(N["pick"], "$.points", "number"), "signal_type": src(N["pick"], "$.signal_type"),
              "headline": src(N["pick"], "$.headline"), "activity_date": src(N["pick"], "$.activity_date")}
    N["score"] = create_node(WF, {"nodeType": "code", "name": NAMES["score"], "code": baked(SCORE_CODE, {"cap": float(num(cfg.get("cap"), 100))}),
                                  "inputSchema": {"type": "object", "properties": sprops}, "incomingEdges": [{"sourceNode": N["read"]}]}, "score", a.dry)
    N["cond"] = create_node(WF, {"nodeType": "conditional", "name": NAMES["cond"], "conditionalMode": "code", "code": COND_CODE,
                                 "inputSchema": {"type": "object", "properties": {"found": src(N["score"], "$.found", "boolean")}}, "incomingEdges": [{"sourceNode": N["score"]}]}, "cond", a.dry)
    wprops = {"account_id": src(N["score"], "$.account_id"), "new_score": src(N["score"], "$.new_score", "number"), "last_signal": src(N["score"], "$.last_signal"),
              "last_signal_date": src(N["score"], "$.last_signal_date"), "domain": src(N["pick"], "$.domain")}
    N["write"], N["mirror"] = writers(WF, pk, acct, aud, [{"sourceNode": N["cond"], "transitionId": "write"}], wprops,
                                      {"Engagement_Score__c": "{{new_score}}", "Last_Signal__c": "{{last_signal}}", "Last_Signal_Date__c": "{{last_signal_date}}"},
                                      {"engagement": "{{new_score}}", "last_signal": "{{last_signal}}", "last_signal_date": "{{last_signal_date}}", "sfdc_id": "{{account_id}}"}, a.dry)
    N["skip"] = create_node(WF, {"nodeType": "code", "name": NAMES["skip"], "code": SKIP_CODE,
                                 "inputSchema": {"type": "object", "properties": {"domain": src(N["pick"], "$.domain")}},
                                 "incomingEdges": [{"sourceNode": N["cond"], "transitionId": "skip"}]}, "skip", a.dry)
    st["workflow"] = {"id": WF, "name": name, "url": url, "trigger_id": tid, "trigger_node": trig, "signal_triggers": strig, "nodes": N}
    if not a.dry:
        v = clay("workflows", "graph", "validate", WF)
        st["workflow"]["validate"] = {"valid": v.get("valid"), "errors": v.get("errors")}
        print("validate:", v.get("valid"), "errors:", json.dumps(v.get("errors"))[:600], "warnings:", len(v.get("warnings", [])))

    # 4. the weekly decay workflow
    dec = as_dict(cfg.get("decay"))
    if dec.get("enabled", True) and not a.no_decay:
        dname = "%s Decay" % name; keep = float(num(dec.get("keep"), 0.75))
        if a.dry:
            DW = "wf_DRY_decay"; durl = None; dtrig = [{"segment": s, "trigger_id": None, "node": "wfn_DRY_sched_%d" % i} for i, s in enumerate(watched)]
        else:
            w = clay("workflows", "create", "--name", dname); DW = w.get("id") or sys.exit("decay workflow create failed: %s" % json.dumps(w)[:600]); durl = w.get("url")
            dtrig = []
            for s in watched:
                sc = {"recurrenceType": "simple", "value": {"periodUnit": str(dec.get("every") or "weekly"), "startDate": next_monday_iso(), "timezone": str(dec.get("timezone") or "UTC")}}
                t = clay("workflows", "triggers", "create", DW, inp={"triggerType": "audience_scheduled", "segmentId": s, "entityType": "ACCOUNT", "scheduleConfig": sc})
                rid = t.get("resourceId"); node = clay("workflows", "triggers", "get", rid).get("workflowNodeId") if rid else None
                if not node:
                    sys.exit("scheduled trigger on %s failed: %s" % (s, json.dumps(t)[:600]))
                dtrig.append({"segment": s, "trigger_id": rid, "node": node})
        D = {}
        dprops = {"e%d_fields" % i: src(t["node"], "$.fields", "object") for i, t in enumerate(dtrig, 1)}
        D["pick"] = create_node(DW, {"nodeType": "code", "name": NAMES["d_pick"], "code": DECAY_PICK_CODE,
                                     "inputSchema": {"type": "object", "properties": dprops}, "incomingEdges": [{"sourceNode": t["node"]} for t in dtrig]}, "d_pick", a.dry)
        D["read"] = create_node(DW, {"nodeType": "tool", "name": NAMES["read"], "inputSchema": {"type": "object", "properties": {"domain": src(D["pick"], "$.domain")}},
                                     "tools": [{"toolType": "clay_action", "actionKey": "salesforce-lookup-via-soql", "actionPackageId": pk["sf"], "appAccountId": acct,
                                                "inputMappingConfig": {"soql_query": ref(forms_soql(["Engagement_Score__c"]))}}],
                                     "incomingEdges": [{"sourceNode": D["pick"]}]}, "d_read", a.dry)
        D["decay"] = create_node(DW, {"nodeType": "code", "name": NAMES["d_decay"], "code": baked(DECAY_CODE, {"keep": keep}),
                                      "inputSchema": {"type": "object", "properties": {"result": src(D["read"], "$.result", "object")}}, "incomingEdges": [{"sourceNode": D["read"]}]}, "d_decay", a.dry)
        D["cond"] = create_node(DW, {"nodeType": "conditional", "name": NAMES["cond"], "conditionalMode": "code", "code": COND_CODE,
                                     "inputSchema": {"type": "object", "properties": {"found": src(D["decay"], "$.found", "boolean")}}, "incomingEdges": [{"sourceNode": D["decay"]}]}, "d_cond", a.dry)
        dw = {"account_id": src(D["decay"], "$.account_id"), "new_score": src(D["decay"], "$.new_score", "number"), "domain": src(D["pick"], "$.domain")}
        D["write"], D["mirror"] = writers(DW, pk, acct, aud, [{"sourceNode": D["cond"], "transitionId": "write"}], dw,
                                          {"Engagement_Score__c": "{{new_score}}"}, {"engagement": "{{new_score}}", "sfdc_id": "{{account_id}}"}, a.dry)
        D["skip"] = create_node(DW, {"nodeType": "code", "name": NAMES["skip"], "code": SKIP_CODE,
                                     "inputSchema": {"type": "object", "properties": {"domain": src(D["pick"], "$.domain")}},
                                     "incomingEdges": [{"sourceNode": D["cond"], "transitionId": "skip"}]}, "d_skip", a.dry)
        st["decay"] = {"id": DW, "name": dname, "url": durl, "keep": keep, "triggers": dtrig, "nodes": D}
        if not a.dry:
            v = clay("workflows", "graph", "validate", DW)
            st["decay"]["validate"] = {"valid": v.get("valid"), "errors": v.get("errors")}
            print("decay validate:", v.get("valid"), "errors:", json.dumps(v.get("errors"))[:600])
    if a.dry:
        print("dry run: nothing created"); return
    save_state(a.out, st)
    print("saved", state_path(a.out))
    print("next: one test event on a plan account the user picks, zero data credits (it writes the two fields for real):\n"
          "  python3 %s test --org %s --out %s --domain <domain> --type NewHire --headline \"VP Sales joined\"\n"
          "then the gate, then `clay workflows publish %s` and `python3 %s resume --out %s --yes`" % (os.path.abspath(__file__), a.org, a.out, WF, os.path.abspath(__file__), a.out))


# ---------- test / resume / pause / status ----------

def read_back(org, domain):
    forms = ", ".join("'%s://%s%s'" % (sch, www, domain) for sch in ("https", "http") for www in ("", "www."))
    q = "SELECT Id, Name, Owner.Name, Carve_Status__c, Account_Fit_Score__c, Engagement_Score__c, Last_Signal__c, Last_Signal_Date__c FROM Account WHERE Territory_Plan__c = true AND Website IN (%s) LIMIT 1" % forms
    recs = records(sf("data", "query", "-q", q, "-o", org))
    return recs[0] if recs else None


def show(r, label):
    if not r:
        print("%s: no Territory Plan account with that domain" % label); return
    print("%s: %s | owner %s | carve %s | fit %s | engagement %s | last signal %s (%s)" % (
        label, r.get("Name"), (r.get("Owner") or {}).get("Name"), r.get("Carve_Status__c"), r.get("Account_Fit_Score__c"),
        r.get("Engagement_Score__c"), r.get("Last_Signal__c"), r.get("Last_Signal_Date__c")))


def cmd_test(a):
    st = load_state(a.out); wf = (st.get("workflow") or {}).get("id") or sys.exit("no %s; run build first" % state_path(a.out))
    d = dom(a.domain) or sys.exit("--domain is required")
    before = read_back(a.org, d); show(before, "before")
    if not before:
        sys.exit("pick a domain that is a Territory Plan account in %s" % a.org)
    inputs = {"domain": d, "signal_type": a.type or "NewHire", "headline": a.headline or "%s (manual test)" % (a.type or "NewHire")}
    if a.points is not None:
        inputs["points"] = a.points
    r = clay("workflows", "runs", "test", wf, inputs=inputs)
    rid = r.get("runId") or sys.exit("run did not start: %s" % json.dumps(r)[:500])
    print("run", rid, "started; waiting")
    done = cw.wait_runs(wf, [rid], timeout=300).get(rid) or {}
    print("run status:", done.get("status"), "| error:", (done.get("error") or "")[:300], "| data credits:", done.get("dataCreditsUsed"), "action credits:", done.get("actionCreditsUsed"))
    after = read_back(a.org, d); show(after, "after")
    if after and before and (after.get("Owner") or {}).get("Name") != (before.get("Owner") or {}).get("Name"):
        print("WARNING: the owner changed; that must not happen")
    print("Audiences: open the record for %s and check Engagement Score, Last Signal, Last Signal Date read the same." % d)


def watched_count(st):
    n = 0
    for s in st.get("watched_segments") or []:
        c = clay("audiences", "records", "search-count", "--audience-id", s, "--entity-type", "companies", quiet=True)
        n += int(num(c.get("count") if isinstance(c, dict) else None, 0))
    return n


def cmd_resume(a):
    st = load_state(a.out); sigs = st.get("signals") or sys.exit("no signals in %s; run build first" % state_path(a.out))
    n = watched_count(st)
    print("%d signals over %d watched accounts (%s). Each weekly check bills data credits per event found, as Clay Signals do; the Engagement "
          "workflow %s must be published for events to score." % (len(sigs), n, ", ".join(st.get("watched_segments") or []), (st.get("workflow") or {}).get("id")))
    if not a.yes:
        sys.exit("rerun with --yes after the user's \"Start the signals\"")
    for s in sigs:
        r = clay("signals", "resume", s["id"]); print("resume %-10s %s -> %s" % (s["key"], s["id"], r.get("runStatus") or json.dumps(r.get("error"))[:200]))


def cmd_pause(a):
    st = load_state(a.out)
    for s in st.get("signals") or []:
        r = clay("signals", "pause", s["id"]); print("pause %-10s %s -> %s" % (s["key"], s["id"], r.get("runStatus") or json.dumps(r.get("error"))[:200]))


def cmd_status(a):
    st = load_state(a.out)
    for s in st.get("signals") or []:
        g = clay("signals", "get", s["id"], quiet=True)
        print("signal %-10s %-45s %-8s last run %s %s" % (s["key"], g.get("name") or s.get("name"), g.get("runStatus"), g.get("lastRunAt") or "-", ("ERROR " + str((g.get("error") or {}).get("userFriendlyMessage") or g.get("error"))) if g.get("error") else ""))
    for k in ("workflow", "decay"):
        w = st.get(k)
        if w:
            print("%-9s %s %s  %s" % (k, w["id"], w["name"], w.get("url") or ""))
    if a.org:
        have = have_fields(a.org)
        if "Engagement_Score__c" in have:
            tot = records(sf("data", "query", "-q", "SELECT COUNT(Id) n, SUM(Engagement_Score__c) s FROM Account WHERE Territory_Plan__c = true AND Engagement_Score__c > 0", "-o", a.org))
            print("accounts with engagement:", (tot or [{}])[0].get("n"), "| total points:", (tot or [{}])[0].get("s"))
            for r in records(sf("data", "query", "-q", "SELECT Name, Owner.Name, Carve_Status__c, Account_Fit_Score__c, Engagement_Score__c, Last_Signal__c, Last_Signal_Date__c FROM Account WHERE Territory_Plan__c = true AND Engagement_Score__c > 0 ORDER BY Engagement_Score__c DESC, Account_Fit_Score__c DESC LIMIT 15", "-o", a.org)):
                print("  %-28s %5s  fit %5s  %-12s %-16s %s %s" % (r["Name"], r.get("Engagement_Score__c"), r.get("Account_Fit_Score__c"), r.get("Carve_Status__c") or "-", (r.get("Owner") or {}).get("Name"), r.get("Last_Signal_Date__c") or "", (r.get("Last_Signal__c") or "")[:70]))


# ---------- book health ----------

def cmd_health(a):
    rules = cw.load_rules(a.rules); cfg = eng_cfg(rules); reps = cw.load_reps(a.reps); imp = cw.import_user_id(a.org, a.import_user)
    thr = num(as_dict(rules.get("eligibility")).get("threshold"), 60)
    RE = as_dict(cfg.get("reentry")); min_e = num(RE.get("min_engagement"), 40); min_f = num(RE.get("min_fit"), 50)
    have = have_fields(a.org)
    eng_ok = "Engagement_Score__c" in have
    cols = ["Id", "Name", "Website", "OwnerId", "Carve_Status__c", "Carve_Reason__c", "Segment__c", "Sub_Region__c", "Account_Fit_Score__c", "Account_Fit_Grade__c",
            "Scoring_Status__c", "NumberOfEmployees", "BillingCity", "BillingState", "BillingStateCode", "BillingCountry", "BillingCountryCode", "Industry", "Type"]
    cols = [c for c in cols if c in have or "__c" not in c] + (["Engagement_Score__c", "Last_Signal__c", "Last_Signal_Date__c"] if eng_ok else [])
    rows = [carve_node.norm(r) for r in records(sf("data", "query", "-q", "SELECT %s FROM Account WHERE Territory_Plan__c = true" % ", ".join(cols), "-o", a.org))]
    for x in rows:
        x["eng"] = num(x.get("Engagement_Score__c"), 0) if eng_ok else 0
        x["segment"] = x.get("Segment__c") or carve_node.segment_of(x["emp"], rules) or ""
        reg, sub, pooled = carve_node.route(x, rules) if x.get("country") or x.get("state") else (None, None, False)
        x["region"] = reg or ""; x["sub_region"] = x.get("Sub_Region__c") or sub or ""
    by_owner = {}
    for x in rows:
        by_owner.setdefault(x.get("OwnerId"), []).append(x)
    L = ["# Book health", "", "Read from Salesforce %s. Fit floor %g. Re-entry: engagement >= %g with fit >= %g. Capacity precedence as the carve." % (
        datetime.date.today().isoformat(), thr, min_e, min_f), ""]
    if not eng_ok:
        L += ["No Engagement_Score__c in the org yet (Step 5 `fields` adds it); engagement columns read 0.", ""]
    L += ["## Books", "", "| Rep | Segment / sub-region | Capacity | Assigned | Room | Mean fit | Mean engagement | Most engagement |", "|---|---|---|---|---|---|---|---|"]
    pool = [x for x in rows if x.get("OwnerId") == imp and (x.get("Carve_Status__c") or "") in ("", "Unowned", "Not eligible", "Proposed")]
    room = {}
    for r in reps:
        book = [x for x in by_owner.get(r.get("crm_user_id"), []) if (x.get("Carve_Status__c") or "") in ("Assigned", "Protected", "Proposed") or x.get("Carve_Status__c") is None]
        book = [x for x in book if x.get("Carve_Status__c")]
        cap = carve_node.capacity(r, rules, len(reps), len(pool))
        fits = [x["fit"] for x in book if x["fit"] is not None]; heats = [x["eng"] for x in book]
        hot = sorted(book, key=lambda x: (-x["eng"], -(x["fit"] or 0)))[:3]
        room[r["name"]] = (cap - len(book), r)
        L.append("| %s | %s / %s | %d | %d | %d | %s | %s | %s |" % (r["name"], r.get("segment", ""), r.get("sub_region", ""), cap, len(book), cap - len(book),
                 ("%.1f" % (sum(fits) / len(fits))) if fits else "-", ("%.1f" % (sum(heats) / len(heats))) if heats else "-",
                 "; ".join("%s %g" % (x["Name"], x["eng"]) for x in hot if x["eng"] > 0) or "-"))
    L += ["", "## Pool candidates", "", "Unassigned accounts (owned by the import user) that clear the re-entry rule or the fit floor, most engagement first. "
          "Candidates, not assignments: `carve_workflow.py run --only-pool`, the summary and the approval assign them.", "",
          "| Account | Fit | Engagement | Last signal | Status today | Segment / region | Rep with room |", "|---|---|---|---|---|---|---|"]
    cands = [x for x in pool if (x["eng"] >= min_e and (x["fit"] or 0) >= min_f) or (x["fit"] or 0) >= thr]
    cands.sort(key=lambda x: (-x["eng"], -(x["fit"] or 0)))
    for x in cands[:25]:
        fit_reps = [(rm, r) for name, (rm, r) in room.items() if r.get("segment") == x["segment"] and (carve_node.rep_region(r, rules) or "") == x["region"]]
        fit_reps.sort(key=lambda t: (0 if (t[1].get("sub_region") or "").strip().lower() == (x["sub_region"] or "").strip().lower() else 1, -t[0]))
        who = ("%s (%d room)" % (fit_reps[0][1]["name"], fit_reps[0][0])) if fit_reps and fit_reps[0][0] > 0 else ("no rep with room" if fit_reps else "no rep for %s / %s" % (x["segment"] or "?", x["region"] or "?"))
        L.append("| %s | %s | %g | %s | %s | %s / %s | %s |" % (x["Name"], x["fit"] if x["fit"] is not None else "-", x["eng"], (x.get("Last_Signal__c") or "-")[:60],
                 "%s: %s" % (x.get("Carve_Status__c") or "not carved", (x.get("Carve_Reason__c") or "")[:40]) if x.get("Carve_Status__c") else "not carved",
                 x["segment"] or "-", x["region"] or "-", who))
    if not cands:
        L.append("| (none) | | | | | | |")
    L += ["", "%d pool accounts, %d candidates, %d reps with room (%s)." % (len(pool), len(cands), sum(1 for rm, _ in room.values() if rm > 0),
          ", ".join("%s %d" % (n, rm) for n, (rm, _) in room.items() if rm > 0) or "none"), ""]
    os.makedirs(a.out, exist_ok=True); p = os.path.join(a.out, "book-health.md"); open(p, "w").write("\n".join(L))
    print("\n".join(L)); print("\nwritten", p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["build", "test", "resume", "pause", "status", "health"])
    ap.add_argument("--org"); ap.add_argument("--rules"); ap.add_argument("--reps"); ap.add_argument("--carve", default="./carve"); ap.add_argument("--out", default="./engagement")
    ap.add_argument("--app-account"); ap.add_argument("--name"); ap.add_argument("--import-user"); ap.add_argument("--no-decay", action="store_true"); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--domain"); ap.add_argument("--type"); ap.add_argument("--headline"); ap.add_argument("--points", type=float); ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    need = {"build": ["org", "rules"], "test": ["org", "domain"], "resume": [], "pause": [], "status": [], "health": ["org", "rules", "reps"]}[a.command]
    for n in need:
        if not getattr(a, n):
            sys.exit("--%s is required for %s" % (n.replace("_", "-"), a.command))
    {"build": cmd_build, "test": cmd_test, "resume": cmd_resume, "pause": cmd_pause, "status": cmd_status, "health": cmd_health}[a.command](a)


if __name__ == "__main__":
    main()

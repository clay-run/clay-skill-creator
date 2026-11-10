#!/usr/bin/env python3
"""Build and run the "Territory Carve" workflow in Clay (Step 7). Stdlib only; drives the `clay` and `sf` CLIs.

  python3 carve_workflow.py build   --org <alias> --rules territory-rules.md --reps reps.csv [--out ./carve]
                                    [--import-user 005...] [--app-account aa_...] [--name "Territory Carve"] [--named-overrides overrides.json] [--dry]
  python3 carve_workflow.py update  --org <alias> --rules territory-rules.md --reps reps.csv [--out ./carve]   # push edited rules/reps into the two code nodes
  python3 carve_workflow.py run     --org <alias> [--out ./carve] [--batch 25] [--live] [--only-pool] [--limit N] [--domains file]
  python3 carve_workflow.py segment --org <alias> --rules territory-rules.md [--out ./carve] [--name "Eligible pool"]   # Audiences pool + draft trigger
  python3 carve_workflow.py writer  [--out ./carve] [--name "Territory Write Owners"]        # the two-node Write Owners workflow (unpublished)
  python3 carve_workflow.py status  --org <alias>
  python3 carve_workflow.py reset-proposals --org <alias> --yes                             # clear every non-Assigned proposal before a re-carve

What `build` creates, as a draft (nothing runs until `run`, and nothing is published):
  manual trigger {domain}
  -> Pick domain (code)                       first non-empty of the manual domain and the segment record's domain, bare form
  -> Salesforce: read the account (SOQL)      by Website in four URL forms, Territory Plan true, the fields the org has
  -> Carve gates (code, scripts/carve_node.py, mode gates)   exclusions, size, eligibility, protections, rep picks, segment, route
  -> decided? (conditional)                   yes -> write; no -> deal
  -> Salesforce: eligible peers (SOQL)        every scored account in the same segment band and region (zero credits)
  -> Carve deal (code, mode deal)             re-runs the whole superset's deal with shared capacity; returns this account's slot
  -> Salesforce: write the proposal           Segment, Sub-region, Carve Status, Carve Reason, Proposed Owner. NEVER Owner.
  -> Audiences: mirror the proposal           same fields on the company record, by domain
The rules YAML, reps.csv, the pool owner and the field list are baked into the two code nodes as CONFIG, so a rules change is
`update`, not a rebuild. Both Salesforce actions are free; a full 200-account carve costs action credits only.

`run` carves through the manual trigger: every scored plan account that is not already Assigned (or `--only-pool` for the
unassigned eligible set), 25 domains at a time, polling each batch to completion and logging to <out>/carve-runs.jsonl.
`segment` creates the "Eligible pool" Audiences segment (scored, fit >= threshold, Carve Status empty or Unowned) and an
audience_segment trigger on the carve workflow as a DRAFT; publishing the workflow then makes it live and carves every record
in the segment, which is the always-on top-up. Say that before anyone publishes.
"""
import argparse, csv, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import miniyaml      # noqa: E402
import carve_node    # noqa: E402

SF_PKG_FALLBACK = "d0c0a70d-7c1e-40de-b214-9d8d82672770"
AUD_PKG_FALLBACK = "b1ab3d5d-b0db-4b30-9251-3f32d8b103c1"
AUD_FIELDS = {"segment": "Segment", "sub_region": "Sub-region", "carve_status": "Carve Status", "carve_reason": "Carve Reason",
              "sfdc_id": "Salesforce Account Id", "proposed_owner": "Proposed Owner"}
NAMES = {"pick": "Pick domain", "read": "Salesforce: read the account", "gates": "Carve gates", "decided": "Decided before the deal?",
         "peers": "Salesforce: eligible peers in the bucket", "deal": "Carve deal", "write": "Salesforce: write the proposal (never Owner)",
         "mirror": "Audiences: mirror the proposal"}


# ---------- CLIs ----------

def clay(*a, inp=None, inputs=None, quiet=False):
    cmd = ["clay", *a]
    if inp is not None:
        cmd += ["--input", json.dumps(inp)]
    if inputs is not None:
        cmd += ["--inputs", json.dumps(inputs)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout.strip() or r.stderr.strip()
    try:
        d = json.loads(out)
    except Exception:
        d = {"error": {"message": out[-1500:]}}
    if "error" in d and not quiet:
        print("clay", " ".join(a[:3]), "->", json.dumps(d["error"])[:600])
    return d


def sf(*args):
    r = subprocess.run(["sf", *args, "--json"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        sys.exit("sf failed: %s\n%s" % (" ".join(args), (r.stdout + r.stderr)[-800:]))


def records(d):
    return (d.get("result") or {}).get("records", []) if isinstance(d, dict) else []


# ---------- inputs ----------

def load_rules(path):
    rules = miniyaml.load_rules(path)
    if not isinstance(rules, dict) or not rules:
        sys.exit("%s: no YAML machine spec found" % path)
    return rules


def load_reps(path):
    reps = list(csv.DictReader(open(path, newline="")))
    bad = [r.get("name") for r in reps if not re.match(r"^005\w{12,15}$", (r.get("crm_user_id") or "").strip())]
    if bad:
        sys.exit("reps without a Salesforce user id (run sf_setup.py reps first): %s" % bad)
    keep = ["name", "crm_user_id", "email", "segment", "sub_region", "capacity", "protected_domains", "region"]
    return [{k: (r.get(k) or "").strip() for k in keep if k in r} for r in reps]


def import_user_id(org, given=None):
    if given:
        return given
    me = (sf("org", "display", "-o", org).get("result") or {}).get("username")
    recs = records(sf("data", "query", "-q", "SELECT Id FROM User WHERE Username = '%s'" % me, "-o", org))
    if not recs:
        sys.exit("could not determine the import user; pass --import-user 005...")
    return recs[0]["Id"]


def account_fields(org, rules):
    have = {f["name"] for f in (sf("sobject", "describe", "-s", "Account", "-o", org).get("result") or {}).get("fields", [])}
    want = list(carve_node.WANT_FIELDS)
    EX = carve_node.as_dict(rules.get("exclusions")); PROT = carve_node.as_dict(rules.get("protections"))
    for f in [EX.get("competitors_field"), EX.get("other_teams_field")]:
        if f:
            want.append(f)
    for p in PROT.values():
        if isinstance(p, dict):
            want += ([p.get("field")] if p.get("field") else []) + carve_node.as_list(p.get("fields"))
    sc = carve_node.size_cap_rule(rules)
    if sc and sc.get("field"):
        want.append(sc["field"])
    fields = [f for f in dict.fromkeys(want) if f and f in have]
    if "Territory_Plan__c" not in have or "Account_Fit_Score__c" not in have:
        sys.exit("the org has no Territory_Plan__c / Account_Fit_Score__c yet: run Step 5 (sf_setup.py fields) first")
    return fields, have


def state_path(out):
    return os.path.join(out, "carve-workflow.json")


def load_state(out):
    p = state_path(out)
    return json.load(open(p)) if os.path.exists(p) else {}


def save_state(out, st):
    os.makedirs(out, exist_ok=True)
    json.dump(st, open(state_path(out), "w"), indent=1)


# ---------- Clay discovery ----------

def package_ids():
    d = clay("workflows", "actions", "list", quiet=True)
    found = {}
    def scan(o):
        if isinstance(o, dict):
            k = o.get("actionKey") or o.get("key")
            if k in ("salesforce-lookup-via-soql", "update-object", "upsert-audiences-record") and (o.get("packageId") or o.get("package_id")):
                found.setdefault(k, o.get("packageId") or o.get("package_id"))
            for v in o.values():
                scan(v)
        elif isinstance(o, list):
            for v in o:
                scan(v)
    scan(d)
    return {"sf": found.get("salesforce-lookup-via-soql") or found.get("update-object") or SF_PKG_FALLBACK,
            "aud": found.get("upsert-audiences-record") or AUD_PKG_FALLBACK}


def discover_app_account(sf_pkg):
    """The Salesforce connection id: read off any workflow node that already uses a Salesforce action (the scoring workflow),
    else from the catalog's availableAppAccounts on the Salesforce actions (a fresh workspace with the connection just added)."""
    for w in (clay("workflows", "list", quiet=True).get("data") or []):
        g = clay("workflows", "graph", "get", w.get("id") or w.get("workflowId"), "--mode", "full", quiet=True)
        for n in g.get("nodes") or []:
            for t in (n.get("tools") or []):
                if t.get("actionPackageId") == sf_pkg and t.get("appAccountId"):
                    return t["appAccountId"]
    found = []
    def scan(o):
        if isinstance(o, dict):
            if o.get("packageId") == sf_pkg:
                for a in (o.get("availableAppAccounts") or []):
                    if isinstance(a, dict) and a.get("id") and a["id"] not in found:
                        found.append(a["id"])
            for v in o.values():
                scan(v)
        elif isinstance(o, list):
            for v in o:
                scan(v)
    scan(clay("workflows", "actions", "list", quiet=True))
    if len(found) > 1:
        print("note: %d Salesforce connections in the workspace (%s); using the first, pass --app-account to choose" % (len(found), ", ".join(found)))
    return found[0] if found else None


def audience_field_ids(create_missing=True):
    d = clay("audiences", "fields", "list", "--entity-type", "companies", quiet=True)
    items = d.get("data") if isinstance(d, dict) else d
    by = {str(f.get("name") or "").strip().lower(): f.get("id") for f in (items or []) if isinstance(f, dict)}
    out = {}
    for key, name in AUD_FIELDS.items():
        fid = by.get(name.lower())
        if not fid and create_missing:
            c = clay("audiences", "fields", "create", "--entity-type", "companies", "--name", name, "--data-type", "text")
            fid = c.get("id")
            print("created Audiences field", name, fid)
        out[key] = fid
    out["fit"] = by.get("account fit score"); out["scoring_status"] = by.get("scoring status")
    return out


# ---------- node code ----------

def node_code(mode, rules, reps, import_user, fields, overrides=None):
    """carve_node.py without its module docstring and self-test (smaller node), plus the baked CONFIG.
    overrides: the --named-overrides JSON (domain -> rep user id) for the manager method; baked into the deal node."""
    src = open(os.path.join(HERE, "carve_node.py")).read()
    if src.startswith('"""'):
        src = src[src.index('"""', 3) + 3:].lstrip("\n")
    src = src.split("\n# ---------- local preview over a whole universe ----------")[0].rstrip() + "\n"
    cfg = {"mode": mode, "rules_json": json.dumps(rules), "reps_json": json.dumps(reps), "import_user": import_user, "fields_csv": ",".join(fields)}
    if mode == "deal":
        cfg["named_overrides_json"] = json.dumps(overrides or {})
    trailer = '''

# ---- baked by carve_workflow.py build/update; edit the rules file and run `update`, do not edit here ----
CONFIG = json.loads(%s)
_node_handler = handler


class _Ctx:
    def __init__(self, c):
        self._c = c

    def get_input(self, k):
        if k in CONFIG:
            return CONFIG[k]
        return self._c.get_input(k)


def handler(context):
    return _node_handler(_Ctx(context))
''' % json.dumps(json.dumps(cfg))
    return src + trailer


PICK_CODE = '''def handler(context):
    import json
    cands = [context.get_input("m_domain"), context.get_input("s_domain"), context.get_input("s_website")]
    for v in cands:
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        v = (v or "").strip().lower() if isinstance(v, str) else ""
        if not v:
            continue
        for p in ("https://", "http://"):
            if v.startswith(p):
                v = v[len(p):]
        v = v.split("/")[0]
        if v.startswith("www."):
            v = v[4:]
        if v:
            return {"domain": v}
    return {"domain": ""}
'''

DECIDED_CODE = '''def handler(context):
    d = context.get_input("decided")
    if d is True or str(d).lower() == "true":
        return context.transition_to(%s, "write")
    return context.transition_to(%s, "deal")
''' % (json.dumps(NAMES["write"]), json.dumps(NAMES["peers"]))


def src(nid, path, t="string"):
    return {"type": t, "sourceNodeId": nid, "sourcePath": path}


def ref(expr):
    return {"type": "reference", "expression": expr}


def static(v):
    return {"type": "static", "value": v}


def coalesce(*exprs):
    return {"type": "coalesce", "candidates": [ref(e) for e in exprs]}


# ---------- build ----------

def create_node(wf, spec, key, dry=False):
    spec = {k: v for k, v in spec.items() if k != "codeTimeoutMs"}   # some workspaces reject the key (validation_error); the default timeout is fine
    if dry:
        print("--", key, json.dumps(spec)[:300]); return "wfn_DRY_" + key
    out = clay("workflows", "nodes", "create", wf, inp=spec)
    nid = out.get("nodeId")
    fails = [u for u in out.get("appliedUpdates", []) if not u.get("success")]
    print("%-10s %s %s" % (key, nid, ("FAIL " + json.dumps(fails)[:400]) if fails else "ok"))
    if not nid:
        sys.exit("node %s failed: %s" % (key, json.dumps(out)[:1200]))
    return nid


def load_overrides(path):
    if not path:
        return {}
    d = json.load(open(path))
    if not isinstance(d, dict):
        sys.exit("--named-overrides must be a JSON object of domain -> rep crm_user_id")
    return d


def cmd_build(a):
    rules = load_rules(a.rules); reps = load_reps(a.reps); overrides = load_overrides(a.named_overrides)
    st = load_state(a.out)
    if st.get("workflow") and not a.dry:
        print("already built: %s names workflow %s (%s). Nothing to do. `update` pushes an edited rules file or reps.csv into it; `run` carves; "
              "delete the file only to build a second workflow." % (state_path(a.out), st["workflow"], st.get("name")))
        return
    imp = import_user_id(a.org, a.import_user)
    fields, have = account_fields(a.org, rules)
    pk = package_ids()
    acct = a.app_account or discover_app_account(pk["sf"])
    if not acct and not a.dry:
        sys.exit("no Salesforce connection id found on any workflow; pass --app-account aa_... (read it off the scoring workflow's Salesforce node with `clay workflows graph get <wf> --mode full`)")
    aud = audience_field_ids(create_missing=not a.dry)
    name = a.name or "Territory Carve"
    print("workflow %r | pool owner %s | %d account fields | Salesforce connection %s" % (name, imp, len(fields), acct))
    if a.dry:
        WF = "wf_DRY"; trig = "wfn_DRY_trigger"
    else:
        w = clay("workflows", "create", "--name", name); WF = w.get("id")
        if not WF:
            sys.exit("workflow create failed: %s" % json.dumps(w)[:600])
        t = clay("workflows", "triggers", "create", WF, inp={"triggerType": "manual", "inputSchema": {"type": "object", "properties": {
            "domain": {"type": "string", "description": "Account domain, e.g. vercel.com (matched on Website, Territory Plan = true)"}}, "required": ["domain"]}})
        tid = t.get("resourceId"); trig = clay("workflows", "triggers", "get", tid).get("workflowNodeId")
        if not trig:
            sys.exit("manual trigger failed: %s" % json.dumps(t)[:600])
    ids = {"workflow": WF, "name": name, "trigger_id": None if a.dry else tid, "trigger_node": trig, "import_user": imp, "fields": fields,
           "app_account": acct, "packages": pk, "audience_fields": aud, "rules": os.path.abspath(a.rules), "reps": os.path.abspath(a.reps),
           "named_overrides": os.path.abspath(a.named_overrides) if a.named_overrides else None}
    N = ids["nodes"] = {}
    N["pick"] = create_node(WF, {"nodeType": "code", "name": NAMES["pick"], "code": PICK_CODE, "codeTimeoutMs": 10000,
        "inputSchema": {"type": "object", "properties": {"m_domain": src(trig, "$.domain")}}, "incomingEdges": [{"sourceNode": trig}]}, "pick", a.dry)
    forms = " OR ".join("Website = '%s://%s{{domain}}'" % (scheme, www) for scheme in ("https", "http") for www in ("", "www."))
    q = "SELECT %s FROM Account WHERE Territory_Plan__c = true AND (%s) LIMIT 1" % (", ".join(fields), forms)
    N["read"] = create_node(WF, {"nodeType": "tool", "name": NAMES["read"], "inputSchema": {"type": "object", "properties": {"domain": src(N["pick"], "$.domain")}},
        "tools": [{"toolType": "clay_action", "actionKey": "salesforce-lookup-via-soql", "actionPackageId": pk["sf"], "appAccountId": acct,
                   "inputMappingConfig": {"soql_query": ref(q)}}], "incomingEdges": [{"sourceNode": N["pick"]}]}, "read", a.dry)
    N["gates"] = create_node(WF, {"nodeType": "code", "name": NAMES["gates"], "code": node_code("gates", rules, reps, imp, fields), "codeTimeoutMs": 30000,
        "inputSchema": {"type": "object", "properties": {"account_result": src(N["read"], "$.result", "object"), "domain": src(N["pick"], "$.domain")}},
        "incomingEdges": [{"sourceNode": N["read"]}]}, "gates", a.dry)
    N["decided"] = create_node(WF, {"nodeType": "conditional", "name": NAMES["decided"], "conditionalMode": "code", "code": DECIDED_CODE,
        "inputSchema": {"type": "object", "properties": {"decided": src(N["gates"], "$.decided", "boolean")}}, "incomingEdges": [{"sourceNode": N["gates"]}]}, "decided", a.dry)
    N["peers"] = create_node(WF, {"nodeType": "tool", "name": NAMES["peers"], "inputSchema": {"type": "object", "properties": {"peer_soql": src(N["gates"], "$.peer_soql")}},
        "tools": [{"toolType": "clay_action", "actionKey": "salesforce-lookup-via-soql", "actionPackageId": pk["sf"], "appAccountId": acct,
                   "inputMappingConfig": {"soql_query": ref("{{peer_soql}}")}}], "incomingEdges": [{"sourceNode": N["decided"], "transitionId": "deal"}]}, "peers", a.dry)
    N["deal"] = create_node(WF, {"nodeType": "code", "name": NAMES["deal"], "code": node_code("deal", rules, reps, imp, fields, overrides), "codeTimeoutMs": 30000,
        "inputSchema": {"type": "object", "properties": {"account_json": src(N["gates"], "$.account_json"), "gate_json": src(N["gates"], "$.gate_json"),
                                                         "peers_result": src(N["peers"], "$.result", "object")}},
        "incomingEdges": [{"sourceNode": N["peers"]}]}, "deal", a.dry)
    wprops = {"account_id": src(N["gates"], "$.account_id"), "segment": src(N["gates"], "$.segment"), "sub_region": src(N["gates"], "$.sub_region"),
              "g_status": src(N["gates"], "$.carve_status"), "g_reason": src(N["gates"], "$.carve_reason"), "g_owner": src(N["gates"], "$.owner_id"),
              "g_owner_name": src(N["gates"], "$.owner_name"), "d_status": src(N["deal"], "$.carve_status"), "d_reason": src(N["deal"], "$.carve_reason"),
              "d_owner": src(N["deal"], "$.proposed_owner_id"), "d_owner_name": src(N["deal"], "$.proposed_owner_name"), "domain": src(N["pick"], "$.domain")}
    wmap = {"recordId": ref("{{account_id}}"), "object_type": static("Account"), "removeNullValues": static(True), "object_fields|disableAutoAssignmentRules": static(True),
            "object_fields|Segment__c": ref("{{segment}}"), "object_fields|Sub_Region__c": ref("{{sub_region}}"),
            "object_fields|Carve_Status__c": coalesce("{{d_status}}", "{{g_status}}"), "object_fields|Carve_Reason__c": coalesce("{{d_reason}}", "{{g_reason}}")}
    if "Proposed_Owner__c" in have:
        wmap["object_fields|Proposed_Owner__c"] = coalesce("{{d_owner}}", "{{g_owner}}")
    else:
        print("note: Proposed_Owner__c is not in the org; the proposal is written as Carve Status + Reason only (sf_setup.py fields adds the lookup)")
    N["write"] = create_node(WF, {"nodeType": "tool", "name": NAMES["write"], "inputSchema": {"type": "object", "properties": wprops},
        "tools": [{"toolType": "clay_action", "actionKey": "update-object", "actionPackageId": pk["sf"], "appAccountId": acct, "inputMappingConfig": wmap}],
        "incomingEdges": [{"sourceNode": N["decided"], "transitionId": "write"}, {"sourceNode": N["deal"]}]}, "write", a.dry)
    fid = aud
    rf = {fid["segment"]: ref("{{segment}}"), fid["sub_region"]: ref("{{sub_region}}"), fid["carve_status"]: coalesce("{{d_status}}", "{{g_status}}"),
          fid["carve_reason"]: coalesce("{{d_reason}}", "{{g_reason}}"), fid["proposed_owner"]: coalesce("{{d_owner_name}}", "{{g_owner_name}}"), fid["sfdc_id"]: ref("{{account_id}}")}
    rf = {k: v for k, v in rf.items() if k}
    mmap = {"entityType": static("ACCOUNT"), "lookupFields|selectedLookupFields": static(["domain"]), "lookupFields|domain": ref("{{domain}}"),
            "recordFields|selectedRecordFields": static(list(rf.keys())), "recordFields|removeNullValues": static(True)}
    for k, v in rf.items():
        mmap["recordFields|" + k] = v
    N["mirror"] = create_node(WF, {"nodeType": "tool", "name": NAMES["mirror"], "inputSchema": {"type": "object", "properties": wprops},
        "tools": [{"toolType": "clay_action", "actionKey": "upsert-audiences-record", "actionPackageId": pk["aud"], "inputMappingConfig": mmap}],
        "incomingEdges": [{"sourceNode": N["write"]}]}, "mirror", a.dry)
    if not a.dry:
        v = clay("workflows", "graph", "validate", WF)
        ids["validate"] = {"valid": v.get("valid"), "errors": v.get("errors"), "warnings": [(w.get("code"), w.get("nodeId"), w.get("inputPath") or w.get("message")) for w in v.get("warnings", [])]}
        print("validate:", v.get("valid"), "errors:", json.dumps(v.get("errors"))[:800], "warnings:", len(v.get("warnings", [])))
        ids["url"] = w.get("url")
    save_state(a.out, ids)
    print("saved", state_path(a.out))
    print("next: one test run, zero credits: python3 %s run --org %s --out %s --domains <file with one known domain>  (or `clay workflows runs test %s --inputs '{\"domain\":\"vercel.com\"}'`)" % (os.path.abspath(__file__), a.org, a.out, WF))


def cmd_update(a):
    st = load_state(a.out)
    if not st.get("workflow"):
        sys.exit("no %s; run build first" % state_path(a.out))
    rules = load_rules(a.rules or st["rules"]); reps = load_reps(a.reps or st["reps"])
    overrides = load_overrides(a.named_overrides or st.get("named_overrides"))
    imp = st["import_user"]; fields = st["fields"]
    if a.named_overrides:
        st["named_overrides"] = os.path.abspath(a.named_overrides); save_state(a.out, st)
    for key, mode in (("gates", "gates"), ("deal", "deal")):
        out = clay("workflows", "nodes", "update", st["workflow"], st["nodes"][key], inp={"code": node_code(mode, rules, reps, imp, fields, overrides)})
        fails = [u for u in out.get("appliedUpdates", []) if not u.get("success")]
        print("update", key, "FAIL " + json.dumps(fails)[:300] if fails else "ok")
    v = clay("workflows", "graph", "validate", st["workflow"]); print("validate:", v.get("valid"), json.dumps(v.get("errors"))[:400])
    print("the draft now carries the new rules; `run` uses the draft unless --live, and a published version needs `clay workflows publish` to pick it up")


# ---------- run ----------

def carve_candidates(org, only_pool, import_user=None):
    where = "Territory_Plan__c = true AND Scoring_Status__c = 'scored' AND Website != null"
    if only_pool:
        where += " AND (Carve_Status__c = null OR Carve_Status__c IN ('Unowned', 'Proposed', 'Not eligible'))"
        if import_user:
            where += " AND OwnerId = '%s'" % import_user
    else:
        where += " AND (Carve_Status__c = null OR Carve_Status__c != 'Assigned')"
    recs = records(sf("data", "query", "-q", "SELECT Id, Website, Account_Fit_Score__c FROM Account WHERE %s ORDER BY Account_Fit_Score__c DESC NULLS LAST" % where, "-o", org))
    doms = []
    for r in recs:
        d = carve_node._dom(r.get("Website"))
        if d and d not in doms:
            doms.append(d)
    return doms


def wait_runs(wf, run_ids, timeout=900):
    t0 = time.time(); done = {}
    while len(done) < len(run_ids) and time.time() - t0 < timeout:
        for rid in run_ids:
            if rid in done:
                continue
            g = clay("workflows", "runs", "get", wf, rid, quiet=True)
            if g.get("status") in ("completed", "failed", "cancelled"):
                done[rid] = g
        if len(done) < len(run_ids):
            time.sleep(4)
    return done


def cmd_run(a):
    st = load_state(a.out)
    wf = st.get("workflow") or sys.exit("no %s; run build first" % state_path(a.out))
    if a.domains:
        doms = [l.strip() for l in open(a.domains) if l.strip() and not l.startswith("#")]
    else:
        doms = carve_candidates(a.org, a.only_pool, st.get("import_user"))
    if a.limit:
        doms = doms[:a.limit]
    if not doms:
        sys.exit("nothing to carve: no scored plan accounts match")
    print("%d accounts to carve through %s (%s), batches of %d" % (len(doms), wf, "live" if a.live else "draft", a.batch))
    log = open(os.path.join(a.out, "carve-runs.jsonl"), "a")
    tot = {"completed": 0, "failed": 0, "data_credits": 0.0, "action_credits": 0.0}
    for b in range(0, len(doms), a.batch):
        batch = doms[b:b + a.batch]; started = time.time(); runs = {}
        for d in batch:
            args = ["workflows", "runs", "test", wf] + (["--live"] if a.live else [])
            r = clay(*args, inputs={"domain": d}, quiet=True)
            if r.get("runId"):
                runs[r["runId"]] = d
            else:
                print("  start failed", d, json.dumps(r.get("error"))[:200]); tot["failed"] += 1
        done = wait_runs(wf, list(runs))
        for rid, g in done.items():
            ok = g.get("status") == "completed"
            tot["completed" if ok else "failed"] += 1
            tot["data_credits"] += float(g.get("dataCreditsUsed") or 0); tot["action_credits"] += float(g.get("actionCreditsUsed") or 0)
            log.write(json.dumps({"run": rid, "domain": runs[rid], "status": g.get("status"), "error": g.get("error"), "data_credits": g.get("dataCreditsUsed"),
                                  "action_credits": g.get("actionCreditsUsed"), "duration": g.get("duration")}) + "\n")
            if not ok:
                print("  FAILED", runs[rid], (g.get("error") or "")[:200])
        missing = set(runs) - set(done)
        if missing:
            print("  %d runs still active after the wait; check `clay workflows runs list %s`" % (len(missing), wf))
        print("batch %d: %d/%d completed in %ds | credits so far data %.0f action %.0f" % (b // a.batch + 1, sum(1 for g in done.values() if g.get("status") == "completed"), len(batch), time.time() - started, tot["data_credits"], tot["action_credits"]))
    log.close()
    print("done:", json.dumps(tot), "| log", os.path.join(a.out, "carve-runs.jsonl"))
    print("next: python3 %s --org %s ... (books, balance, exclusions, patch doc) then the approval" % (os.path.join(HERE, "carve_summary.py"), a.org))


# ---------- segment + trigger ----------

def binop(fid, op, value=None):
    b = {"type": "BinOp", "key": fid, "dataPath": ["account_entity_field_values", "field", fid], "operator": op, "entityType": "ACCOUNT"}
    if value is not None:
        b["value"] = value
    return b


def cmd_segment(a):
    st = load_state(a.out)
    wf = st.get("workflow") or sys.exit("no %s; run build first" % state_path(a.out))
    rules = load_rules(a.rules or st["rules"])
    thr = carve_node._num(carve_node.as_dict(rules.get("eligibility")).get("threshold"), 60)
    aud = st.get("audience_fields") or audience_field_ids(create_missing=False)
    if not aud.get("fit") or not aud.get("scoring_status") or not aud.get("carve_status"):
        sys.exit("Audiences fields missing (Account Fit Score / Scoring Status / Carve Status); the scoring workflow's upserts create them")
    flt = {"type": "GroupOp", "combinationMode": "And", "items": [
        binop("domain", "NotEmpty"), binop(aud["scoring_status"], "Equal", "scored"), binop(aud["fit"], "GreaterThanOrEqual", thr),
        {"type": "GroupOp", "combinationMode": "Or", "items": [binop(aud["carve_status"], "Empty"), binop(aud["carve_status"], "Equal", "Unowned")]}]}
    seg = clay("audiences", "create", "--entity-type", "companies", "--name", a.name or "Eligible pool", "--description",
               "Scored, fit >= %g, not yet proposed or assigned. The carve workflow's trigger." % thr, "--filter", json.dumps(flt))
    sid = seg.get("id") or sys.exit("segment create failed: %s" % json.dumps(seg)[:500])
    print("segment", sid, seg.get("name"))
    t = clay("workflows", "triggers", "create", wf, inp={"triggerType": "audience_segment", "segmentId": sid, "entityType": "ACCOUNT"})
    tid = t.get("resourceId"); tg = clay("workflows", "triggers", "get", tid) if tid else {}
    tnode = tg.get("workflowNodeId")
    st.update(segment_id=sid, segment_trigger_id=tid, segment_trigger_node=tnode, segment_trigger=tg)
    if tnode:
        # the Pick domain node also reads the segment record's domain, so one graph serves both triggers
        props = {"m_domain": src(st["trigger_node"], "$.domain"), "s_domain": src(tnode, "$.domain"), "s_website": src(tnode, "$.website")}
        out = clay("workflows", "nodes", "update", wf, st["nodes"]["pick"], inp={"inputSchema": {"type": "object", "properties": props},
                                                                                  "incomingEdges": [{"sourceNode": st["trigger_node"]}, {"sourceNode": tnode}]})
        fails = [u for u in out.get("appliedUpdates", []) if not u.get("success")]
        print("pick node wired to the segment trigger:", "FAIL " + json.dumps(fails)[:300] if fails else "ok")
        print("segment trigger output keys:", list((tg.get("outputSchema") or {}).get("properties", {}).keys())[:20] or "(not exposed; test with runs test --audience-segment --record-ids and read the Pick domain output)")
    save_state(a.out, st)
    v = clay("workflows", "graph", "validate", wf); print("validate:", v.get("valid"), json.dumps(v.get("errors"))[:400])
    print("The trigger is a DRAFT. `clay workflows publish %s` makes it live and carves every record in '%s' at once (zero data credits);"
          " say so, and publish only when the team wants the always-on top-up. Test first: clay workflows runs test %s --audience-segment %s --limit 2" % (wf, seg.get("name"), wf, sid))


# ---------- Write Owners workflow ----------

def cmd_writer(a):
    st = load_state(a.out)
    pk = st.get("packages") or package_ids(); acct = st.get("app_account") or a.app_account or discover_app_account(pk["sf"])
    aud = st.get("audience_fields") or audience_field_ids(create_missing=False)
    if not acct:
        sys.exit("no Salesforce connection id; pass --app-account")
    name = a.name or "Territory Write Owners"
    w = clay("workflows", "create", "--name", name); WF = w.get("id") or sys.exit("create failed")
    props = {k: {"type": "string", "description": d} for k, d in [("account_id", "Salesforce Account Id"), ("domain", "company domain (Audiences lookup)"),
             ("owner_id", "rep Salesforce user id; empty leaves the owner unchanged"), ("segment", "Segment__c"), ("sub_region", "Sub_Region__c"),
             ("carve_status", "Assigned | Protected | Excluded | Not eligible | Unowned"), ("carve_reason", "Carve_Reason__c")]}
    t = clay("workflows", "triggers", "create", WF, inp={"triggerType": "manual", "inputSchema": {"type": "object", "properties": props, "required": ["account_id", "domain", "carve_status", "carve_reason"]}})
    trig = clay("workflows", "triggers", "get", t.get("resourceId")).get("workflowNodeId")
    tp = {k: src(trig, "$." + k) for k in props}
    sfn = create_node(WF, {"nodeType": "tool", "name": "Salesforce: write owner, segment, sub-region, carve status, reason", "inputSchema": {"type": "object", "properties": tp},
        "tools": [{"toolType": "clay_action", "actionKey": "update-object", "actionPackageId": pk["sf"], "appAccountId": acct, "inputMappingConfig": {
            "recordId": ref("{{account_id}}"), "object_type": static("Account"), "removeNullValues": static(True), "object_fields|disableAutoAssignmentRules": static(True),
            "object_fields|OwnerId": ref("{{owner_id}}"), "object_fields|Segment__c": ref("{{segment}}"), "object_fields|Sub_Region__c": ref("{{sub_region}}"),
            "object_fields|Carve_Status__c": ref("{{carve_status}}"), "object_fields|Carve_Reason__c": ref("{{carve_reason}}")}}],
        "incomingEdges": [{"sourceNode": trig}]}, "sf")
    rf = {aud.get("segment"): "{{segment}}", aud.get("sub_region"): "{{sub_region}}", aud.get("carve_status"): "{{carve_status}}", aud.get("carve_reason"): "{{carve_reason}}",
          aud.get("sfdc_id"): "{{account_id}}", "sfdc_owner_id": "{{owner_id}}"}
    rf = {k: v for k, v in rf.items() if k}
    mmap = {"entityType": static("ACCOUNT"), "lookupFields|selectedLookupFields": static(["domain"]), "lookupFields|domain": ref("{{domain}}"),
            "recordFields|selectedRecordFields": static(list(rf.keys())), "recordFields|removeNullValues": static(True)}
    for k, v in rf.items():
        mmap["recordFields|" + k] = ref(v)
    create_node(WF, {"nodeType": "tool", "name": "Audiences: mirror owner, segment, sub-region, carve status, reason", "inputSchema": {"type": "object", "properties": tp},
        "tools": [{"toolType": "clay_action", "actionKey": "upsert-audiences-record", "actionPackageId": pk["aud"], "inputMappingConfig": mmap}], "incomingEdges": [{"sourceNode": sfn}]}, "aud")
    v = clay("workflows", "graph", "validate", WF); print("validate:", v.get("valid"), json.dumps(v.get("errors"))[:400])
    st["writer"] = {"workflow": WF, "name": name, "trigger_id": t.get("resourceId"), "url": w.get("url")}
    save_state(a.out, st)
    print("Write Owners workflow", WF, "built as a draft; leave it unpublished until the books are approved. Then, as three separate commands:")
    print("  clay workflows publish %s\n  clay routines create workflow %s\n  clay routines runs start <routine> --bulk %s" % (WF, WF, os.path.join(a.out, "write-owners.jsonl")))


# ---------- status / reset ----------

def cmd_status(a):
    org = a.org
    print("by carve status:")
    for r in records(sf("data", "query", "-q", "SELECT Carve_Status__c s, COUNT(Id) n FROM Account WHERE Territory_Plan__c = true GROUP BY Carve_Status__c", "-o", org)):
        print("  %-14s %s" % (r.get("s") or "(blank)", r.get("n")))
    have = {f["name"] for f in (sf("sobject", "describe", "-s", "Account", "-o", org).get("result") or {}).get("fields", [])}
    if "Proposed_Owner__c" in have:
        print("proposed books (Proposed + Assigned, by proposed owner):")
        for r in records(sf("data", "query", "-q", "SELECT Segment__c g, Proposed_Owner__r.Name o, COUNT(Id) n, AVG(Account_Fit_Score__c) f FROM Account WHERE Territory_Plan__c = true AND Carve_Status__c IN ('Proposed','Assigned') GROUP BY Segment__c, Proposed_Owner__r.Name ORDER BY Segment__c", "-o", org)):
            print("  %-10s %-20s %3s  mean fit %.1f" % (r.get("g") or "-", r.get("o") or "(none)", r.get("n"), float(r.get("f") or 0)))


def cmd_reset_proposals(a):
    if not a.yes:
        sys.exit("--yes required: this clears Carve Status, Carve Reason and Proposed Owner on every plan account that is not Assigned")
    org = a.org
    have = {f["name"] for f in (sf("sobject", "describe", "-s", "Account", "-o", org).get("result") or {}).get("fields", [])}
    recs = records(sf("data", "query", "-q", "SELECT Id FROM Account WHERE Territory_Plan__c = true AND Carve_Status__c != null AND Carve_Status__c != 'Assigned'", "-o", org))
    if not recs:
        print("nothing to clear"); return
    os.makedirs(a.out, exist_ok=True)
    p = os.path.join(a.out, "reset-proposals.csv")
    cols = ["Id", "Carve_Status__c", "Carve_Reason__c"] + (["Proposed_Owner__c"] if "Proposed_Owner__c" in have else [])
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(cols)
        for r in recs:
            w.writerow([r["Id"]] + ["#N/A"] * (len(cols) - 1))
    out = sf("data", "update", "bulk", "--sobject", "Account", "--file", p, "--wait", "10", "-o", org)
    print("cleared %d accounts (bulk job %s); the Audiences mirror refreshes on the next carve run" % (len(recs), (out.get("result") or {}).get("jobInfo", {}).get("id", "?")))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["build", "update", "run", "segment", "writer", "status", "reset-proposals"])
    ap.add_argument("--org"); ap.add_argument("--rules"); ap.add_argument("--reps"); ap.add_argument("--out", default="./carve")
    ap.add_argument("--import-user"); ap.add_argument("--app-account"); ap.add_argument("--name"); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--batch", type=int, default=25); ap.add_argument("--live", action="store_true"); ap.add_argument("--only-pool", action="store_true")
    ap.add_argument("--limit", type=int); ap.add_argument("--domains"); ap.add_argument("--yes", action="store_true")
    ap.add_argument("--named-overrides", help="build/update: JSON object of domain -> rep crm_user_id for the manager method; baked into the deal node")
    a = ap.parse_args()
    if a.command in ("build", "update", "run", "status", "reset-proposals", "segment") and not a.org:
        sys.exit("--org <alias> is required")
    if a.command == "build" and not (a.rules and a.reps):
        sys.exit("build needs --rules and --reps")
    {"build": cmd_build, "update": cmd_update, "run": cmd_run, "segment": cmd_segment, "writer": cmd_writer, "status": cmd_status,
     "reset-proposals": cmd_reset_proposals}[a.command](a)

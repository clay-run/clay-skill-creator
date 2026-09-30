#!/usr/bin/env python3
"""
Build (or update) and publish "Person Active At Company (Jev)" in Clay, and optionally its
Audiences twin.

    python3 build_workflow.py --provider typesafe --plan                  # what would be built; changes nothing
    python3 build_workflow.py --provider typesafe                         # the table / webhook workflow
    python3 build_workflow.py --provider typesafe --audience <id> --show-audience-map
    python3 build_workflow.py --provider typesafe --audience <id> [--url-field "LinkedIn URL"]
                              [--profile-field "<field>"] [--name-field "Name"] [--schedule weekly|monthly|quarterly]
    python3 build_workflow.py backfill --audience <id> --plan             # how many are left and the most it can cost; sends nothing
    python3 build_workflow.py backfill --audience <id> [--limit N]        # check members already there (all by default)
    python3 build_workflow.py readback --audience <id>                    # the "Active …" fields of members this script sent

The table / webhook workflow:

  webhook (+ any table that invokes it)
    → 1 Intake (code)              is there a company, a profile, or only a LinkedIn URL?  [holds the Jev key]
    → 2 Need a profile?            yes → 2a ; no → 2r
    → 2a Enrich person             Clay's own "Enrich person" from the LinkedIn URL (0.5 credits)
    → 2p Enrichment ran            both outcomes → 2r  (so 2r never waits on a lane that was not taken)
    → 2r Prepare (code)            which roles could be at the company; one Jev request, a few questions per role
    → 3 Anything to ask Jev?       yes → 4 ; no → 3b
    → 3b Verdict without Jev (code, terminal)
    → 4 Ask Jev (HTTP, no Clay connection: headers from 1 Intake)
    → 5 Verdict (code, terminal)

The Audiences workflow runs for people in one saved audience (when they join, or on a schedule),
finds their linked company with a free Audiences lookup, runs the same steps, and writes the
verdict onto the person's own "Active …" fields. A failed Jev call writes nothing, so an outage
never overwrites an earlier verdict.

The Jev key goes into the first code step of each workflow (see the TODO there): Clay's CLI can
neither create an HTTP connection nor bind one to a step. Every HTTP step is written with an
EMPTY connection id and read back; a step Clay attached any connection to keeps its workflow
unpublished (exit 6), because that connection's own headers would go out with the key.

Idempotent and resumable: every node id is written to build-state.json the moment it exists, a
node left by an interrupted run is adopted by name, and a re-run changes only what differs.
"""
import argparse
import json
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import active_lib as L  # noqa: E402

HTTP_KEY = "http-api-v2"
LOOKUP_KEY = "lookup-in-audiences"
UPDATE_KEY = "update-audiences-record"
AUD_WORKFLOW = L.WORKFLOW_NAME + " · Audiences"

# Fields the Audiences workflow writes on people records (display name, output key, type).
# Adopted by display name if they exist; a create with a taken name gets a suffix.
AUDIENCE_FIELDS = (("Active at company", "active_at_company", "text"),
                   ("Active relationship", "relationship", "text"),
                   ("Active company checked", "company_checked", "text"),
                   ("Active evidence", "evidence", "text"),
                   ("Active confidence", "verdict_confidence", "number"),
                   ("Active needs review", "needs_review", "text"),
                   ("Active last attempt", "check_status", "text"),
                   ("Active last attempt note", "check_note", "text"),
                   ("Active checked at", "checked_at", "date"))
NOT_CHECKED_FIELDS = ("check_status", "check_note")   # a person who could not be checked: the last-attempt
                                                      # fields only; the verdict fields keep the last real check


# ======================================================================= connections: none

def bind_tool(tool, existing=None):
    """The tool as written. Keeps the node's own `toolId` (an update without it makes a new tool,
    which re-attaches the workspace default). An HTTP tool gets `appAccountId: ""`, the one form
    that leaves it with NO connection: written without the field, Clay attaches whatever HTTP
    connection the workspace has, and that connection's headers go out too."""
    out = {k: v for k, v in tool.items() if k not in ("unbound", "appAccountName")}
    if existing and existing.get("toolId") and existing.get("actionKey") == tool.get("actionKey"):
        out["toolId"] = existing["toolId"]
    if tool.get("unbound"):
        out["appAccountId"] = ""
    return out


def binding_problem(tool, back):
    if not tool.get("unbound"):
        return None
    b = back or {}
    return b.get("appAccountName") or b.get("appAccountId") or None


def connection_report(wrong):
    lines = ["%d step(s) came back with a Clay connection attached, so this build published NEITHER workflow "
             "(a version published earlier, if any, is still the live one):" % len(wrong)]
    lines += ["  - %s → %s: connection %r" % w for w in wrong]
    lines += ["Those steps send the Jev key from the workflow's first step; an attached connection would "
              "send its own key as well.",
              "Fix, in Clay: open each step above, clear its connection (no account), save. Then run this "
              "build again: it keeps the step as it is, checks again, and publishes."]
    return "\n".join(lines)


# ======================================================================= graph plumbing

class Graph:
    """One workflow's nodes, persisted in build-state.json under workflows[<key>]."""

    def __init__(self, st_path, key, name):
        self.st_path, self.key, self.name = st_path, key, name
        self._pkg, self._catalog = {}, None
        self.problems = []

    def state(self):
        return L.load(self.st_path, {"workflows": {}})

    def rec(self):
        return self.state()["workflows"].get(self.key) or {"nodes": {}, "tooltypes": {}}

    def put(self, **kv):
        s = self.state()
        w = s["workflows"].setdefault(self.key, {"nodes": {}, "tooltypes": {}})
        w.update(kv)
        L.save(self.st_path, s)

    def put_node(self, k, nid, tooltype=None):
        s = self.state()
        w = s["workflows"].setdefault(self.key, {"nodes": {}, "tooltypes": {}})
        if nid is None:
            w["nodes"].pop(k, None)
            w["tooltypes"].pop(k, None)
        else:
            w["nodes"][k] = nid
            if tooltype:
                w["tooltypes"][k] = tooltype
        L.save(self.st_path, s)

    @property
    def wf(self):
        return self.rec()["id"]

    def node(self, k):
        return self.rec()["nodes"][k]

    def ensure_workflow(self):
        if self.rec().get("id"):
            return False
        for w in L.paged("workflows", "list", limit=200):
            if str(w.get("name", "")).strip().lower() == self.name.lower():
                L.fail("A workflow named %r already exists but this workspace's build state has no record of "
                       "it, so its nodes cannot be told apart. Rename or delete it in Clay, then re-run; "
                       "refusing to create a second one." % self.name)
        self.put(id=L.clay("workflows", "create", "--name", self.name)["id"])
        L.say("  + workflow %s" % self.name)
        return True

    def reconcile(self):
        g = L.clay("workflows", "graph", "get", self.wf)
        live = {n["id"] for n in (g.get("summary") or {}).get("nodes") or []}
        for k, nid in list(self.rec()["nodes"].items()):
            if nid not in live:
                self.put_node(k, None)
                L.say("  ! %s was deleted in Clay; recreating" % k)

    def ensure_trigger(self, body, refresh):
        """Create the trigger once; on later runs re-send `refresh` (a webhook's schema must be
        complete every time, or fields added since are stripped at intake)."""
        r = self.rec()
        if not r.get("trigger_id"):
            t = L.clay("workflows", "triggers", "create", self.wf, inp=body)
            tid = t.get("resourceId") or t.get("id")
            got = L.clay("workflows", "triggers", "get", tid)
            self.put(trigger_id=tid, trigger_node=got.get("workflowNodeId"), webhook_url=got.get("webhookUrl"))
        elif refresh:
            L.clay("workflows", "triggers", "update", r["trigger_id"], inp=refresh)
        return L.clay("workflows", "triggers", "get", self.rec()["trigger_id"])

    def trigger_nodes(self):
        """EVERY trigger node: a table invoking the workflow adds its own, and wiring only ours
        would sever it on the next rebuild."""
        nodes = [self.rec()["trigger_node"]]
        g = L.clay("workflows", "graph", "get", self.wf)
        for t in (g.get("summary") or {}).get("triggers") or []:
            nid = L.clay("workflows", "triggers", "get", t["id"]).get("workflowNodeId")
            if nid and nid not in nodes:
                nodes.append(nid)
        return nodes

    def catalog(self):
        if self._catalog is None:
            c = L.clay("workflows", "actions", "list")
            self._catalog = c.get("data") if isinstance(c, dict) else c
        return self._catalog or []

    def pkg(self, action_key):
        if action_key not in self._pkg:
            for a in self.catalog():
                if a.get("actionKey") == action_key:
                    self._pkg[action_key] = a.get("packageId")
                    break
            else:
                L.fail("Action %r is not in this workspace's catalogue; refusing to guess its package." % action_key)
        return self._pkg[action_key]

    def adopt(self, name):
        """A node already in Clay under this name but not in build state: a create whose response
        was lost. Keep the wired one, delete unwired duplicates this build left."""
        g = (L.clay("workflows", "graph", "get", self.wf).get("summary") or {})
        claimed = set(self.rec()["nodes"].values())
        same = [n["id"] for n in g.get("nodes") or [] if n.get("name") == name and n["id"] not in claimed
                and n.get("nodeType") != "trigger"]
        if not same:
            return None
        edges = g.get("edges") or []
        wired = [nid for nid in same if any(e.get("targetNodeId") == nid for e in edges)]
        keep = (wired or same)[0]
        for nid in same:
            if nid != keep and not any(nid in (e.get("sourceNodeId"), e.get("targetNodeId")) for e in edges):
                L.clay("workflows", "nodes", "delete", self.wf, nid, allow_fail=True)
        L.say("  = adopted %r, created by an earlier run" % name)
        return keep

    def ensure(self, k, spec):
        want = ((spec.get("tools") or [{}])[0] or {}).get("toolType")
        r = self.rec()
        if k in r["nodes"]:
            if want == r["tooltypes"].get(k):
                return r["nodes"][k]
            L.clay("workflows", "nodes", "delete", self.wf, r["nodes"][k], allow_fail=True)
            self.put_node(k, None)
        found = self.adopt(spec.get("name"))
        if found:
            self.put_node(k, found, want)
            return found
        body = {kk: v for kk, v in spec.items() if kk not in ("inputSchema", "incomingEdges")}
        if spec.get("tools"):
            body["tools"] = [bind_tool(t) for t in spec["tools"]]
        out = L.clay("workflows", "nodes", "create", self.wf, inp=body, allow_fail=True, retries=0)
        nid = out.get("nodeId") or out.get("id") or self.adopt(spec.get("name"))
        if not nid:
            L.fail("Creating %r in %s failed: %s" % (spec.get("name"), self.name, out.get("error")))
        self.put_node(k, nid, want)
        return nid

    def pin(self, src, path, typ="string"):
        nid = src if str(src).startswith("wfn_") else self.node(src)
        return {"type": typ, "sourceNodeId": nid, "sourcePath": path}

    def wire(self, k, spec, pins=None, edges=()):
        """Write the whole spec (every pin, every edge) and READ IT BACK: a partial schema write
        reports success and drops what it omitted, and a tool can land on a connection without
        any error."""
        inc = []
        for e in edges:
            if isinstance(e, str):
                inc.append({"sourceNode": e if e.startswith("wfn_") else self.node(e)})
            else:
                inc.append({"sourceNode": self.node(e["from"]), "ruleId": e["rule"],
                            "ruleName": e.get("name", e["rule"])})
        body = dict(spec)
        body["inputSchema"] = {"type": "object", "properties": pins or {}}
        body["incomingEdges"] = inc
        nid = self.ensure(k, spec)
        if spec.get("tools"):
            have = L.clay("workflows", "nodes", "get", self.wf, nid)["node"].get("tools") or []
            body["tools"] = [bind_tool(t, have[i] if i < len(have) else None) for i, t in enumerate(spec["tools"])]
        L.clay("workflows", "nodes", "update", self.wf, nid, inp=body)
        back = L.clay("workflows", "nodes", "get", self.wf, nid)["node"]
        got = {kk for kk, v in ((back.get("inputSchema") or {}).get("properties") or {}).items()
               if isinstance(v, dict) and v.get("sourceNodeId")}
        want = {kk for kk, v in (pins or {}).items() if isinstance(v, dict) and v.get("sourceNodeId")}
        lost = want - got
        if lost:
            L.fail("Pins lost on %s (%s): %s" % (self.name, k, sorted(lost)))
        back_tools = back.get("tools") or []
        for i, t in enumerate(spec.get("tools") or []):
            on = binding_problem(t, back_tools[i] if i < len(back_tools) else None)
            if on:
                self.problems.append((self.name, spec.get("name") or k, on))
        return nid

    def prune(self, keep):
        stale = [(k, nid) for k, nid in self.rec()["nodes"].items() if k not in keep]
        for k, nid in stale:
            L.clay("workflows", "nodes", "update", self.wf, nid, inp={"incomingEdges": []}, allow_fail=True)
        for k, nid in stale:
            out = L.clay("workflows", "nodes", "delete", self.wf, nid, allow_fail=True)
            if isinstance(out, dict) and out.get("error"):
                L.say("  ! could not remove %s: %s" % (k, out["error"]))
                continue
            self.put_node(k, None)
            L.say("  - removed %s (no longer in the design)" % k)

    def publish(self):
        if self.problems:
            return False
        L.clay("workflows", "publish", self.wf)
        return True


# ======================================================================= node specs

def code_spec(name, src):
    return {"nodeType": "code", "name": name, "codeTimeoutMs": 30000, "code": src}


def rules_spec(name, rules):
    """A conditional where EVERY value has a rule: a conditional with no matching rule fails the run."""
    return {"nodeType": "conditional", "name": name, "conditionalMode": "rules",
            "rulesConditionalConfig": {"rules": [
                {"id": rid, "name": label, "condition": {"type": "GroupOp", "combinationMode": "And", "items": [
                    {"type": "BinOp", "dataPath": [path], "operator": op, "value": val}]}}
                for rid, label, path, op, val in rules]}}


def pass_spec(name):
    """After a tool step: two rules to the same next step, so the step after it has only
    conditional parents. A PLAIN edge into a step with several parents hangs the run whenever
    a sibling lane was not taken."""
    return rules_spec(name, [("rule_found", "ran", "ran", "Equal", True),
                             ("rule_empty", "continue anyway", "ran", "NotEqual", True)])


def http_spec(g):
    """4 Ask Jev. URL, body and headers by reference (headers MUST be a reference to an object:
    a static JSON string is sent one header per character, a static object is rejected). No
    Clay connection. returnResponseMetadata makes a 4xx data rather than a failed run, so
    5 Verdict can say why."""
    imc = {"method": {"type": "static", "value": "POST"},
           "url": {"type": "reference", "expression": "{{jev_url}}"},
           "body": {"type": "reference", "expression": "{{jev_body}}"},
           "headers": {"type": "reference", "expression": "{{jev_headers}}"},
           "returnResponseMetadata": {"type": "static", "value": True}}
    return {"nodeType": "tool", "name": "4 Ask Jev",
            "tools": [{"toolType": "clay_action", "actionKey": HTTP_KEY, "actionPackageId": g.pkg(HTTP_KEY),
                       "unbound": True, "inputMappingConfig": imc}]}


def enrich_spec(g):
    imc = {"person_identifier": {"type": "reference", "expression": "{{linkedin_url}}"}}
    return {"nodeType": "tool", "name": "2a Enrich person (0.5 credits)",
            "tools": [{"toolType": "clay_action", "actionKey": L.ENRICH_ACTION,
                       "actionPackageId": g.pkg(L.ENRICH_ACTION), "inputMappingConfig": imc}]}


def build_core(g, provider, ix_node, head_node, ix_edges):
    """The steps both workflows share, from 'Need a profile?' to the two verdicts. `ix_node` is
    the step whose output is the intake record; `head_node` carries the Jev headers."""
    g.wire("gate", rules_spec("2 Need a profile?", [
        ("rule_need", "enrich from LinkedIn", "need_enrichment", "Equal", True),
        ("rule_have", "profile in hand, or nothing to enrich", "need_enrichment", "NotEqual", True)]),
        {"need_enrichment": g.pin(ix_node, "$.need_enrichment", "boolean")}, ix_edges)
    g.wire("enrich", enrich_spec(g), {"linkedin_url": g.pin(ix_node, "$.linkedin_url")},
           [{"from": "gate", "rule": "rule_need", "name": "enrich from LinkedIn"}])
    g.wire("enrich_pass", pass_spec("2p Enrichment ran"), {"ran": {"type": "boolean"}}, ["enrich"])
    g.wire("prep", code_spec("2r Prepare", L.render(L.PREPARE_HANDLER, provider)),
           {"intake": g.pin(ix_node, "$", "object"), "found": g.pin("enrich", "$.result", "object")},
           [{"from": "enrich_pass", "rule": "rule_found", "name": "ran"},
            {"from": "enrich_pass", "rule": "rule_empty", "name": "continue anyway"},
            {"from": "gate", "rule": "rule_have", "name": "profile in hand, or nothing to enrich"}])
    g.wire("ask_gate", rules_spec("3 Anything to ask Jev?", [
        ("rule_ask", "ask Jev", "ask", "Equal", True), ("rule_skip", "nothing to ask", "ask", "NotEqual", True)]),
        {"ask": g.pin("prep", "$.ask", "boolean")}, ["prep"])
    g.wire("nojev", code_spec("3b Verdict without Jev", L.render(L.NOJEV_HANDLER, provider)),
           {"prep": g.pin("prep", "$", "object")}, [{"from": "ask_gate", "rule": "rule_skip", "name": "nothing to ask"}])
    g.wire("ask", http_spec(g),
           {"jev_url": g.pin("prep", "$.jev_url"), "jev_body": g.pin("prep", "$.jev_body"),
            "jev_headers": g.pin(head_node, "$.jev_headers", "object")},
           [{"from": "ask_gate", "rule": "rule_ask", "name": "ask Jev"}])
    g.wire("verdict", code_spec("5 Verdict", L.render(L.VERDICT_HANDLER, provider)),
           {"prep": g.pin("prep", "$", "object"),
            "status_code": g.pin("ask", "$.result.statusCode", "number"),
            "body": g.pin("ask", "$.result.body", "object")}, ["ask"])
    return {"gate", "enrich", "enrich_pass", "prep", "ask_gate", "nojev", "ask", "verdict"}


# ======================================================================= the table / webhook workflow

def build_table(st_path, provider, headers):
    g = Graph(st_path, "table", L.WORKFLOW_NAME)
    g.ensure_workflow()
    g.reconcile()
    props = dict((k, {"type": "string"}) for k in L.INPUT_KEYS)
    schema = {"inputSchema": {"type": "object", "properties": props}}
    g.ensure_trigger(dict(triggerType="webhook", **schema), schema)
    triggers = g.trigger_nodes()
    pins = dict(("in_" + k, g.pin(triggers[0], "$." + k)) for k in L.INPUT_KEYS)
    g.wire("intake", code_spec("1 Intake", L.render(L.INTAKE_HANDLER, provider, headers)), pins, triggers)
    keep = {"intake"} | build_core(g, provider, "intake", "intake", ["intake"])
    g.prune(keep)
    g.put(provider=provider, built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    L.say("  = %s: built" % g.name)
    return g


# ======================================================================= the Audiences workflow

def people_fields():
    f = L.clay("audiences", "fields", "list", "--entity-type", "people")
    f = f.get("data") or f.get("fields") or (f if isinstance(f, list) else [])
    return [{"id": x.get("id") or x.get("fieldId"), "name": x.get("name") or x.get("displayName"),
             "dataType": x.get("dataType")} for x in f]


def ensure_fields(columns):
    """The "Active …" fields: adopted by display name, created if absent. `fields create`
    suffixes a taken name, so adopting first is what keeps a rebuild from multiplying them."""
    by_name = dict((str(c["name"]).strip().lower(), c) for c in columns if c.get("name"))
    out = {}
    for name, key, dtype in AUDIENCE_FIELDS:
        c = by_name.get(name.lower())
        if c:
            if c.get("dataType") and str(c["dataType"]).lower() != dtype:
                L.fail("Audiences already has a people field %r of type %s, but it must be %s. Rename that "
                       "field in Clay, then re-run." % (name, c["dataType"], dtype))
            out[key] = c["id"]
            continue
        made = L.clay("audiences", "fields", "create", "--entity-type", "people", "--name", name, "--data-type", dtype)
        out[key] = made["id"]
        L.say("  + people field %r (%s)" % (made.get("name") or name, dtype))
    return out


def schedule_config(every):
    return {"recurrenceType": "simple", "value": {
        "periodUnit": every, "timezone": "UTC",
        "startDate": time.strftime("%Y-%m-%dT09:00:00.000Z", time.gmtime(time.time() + 86400))}}


def pick_field(columns, wanted, default_names):
    names = [c["name"] for c in columns if c.get("name")]
    if wanted:
        hit = next((n for n in names if n.lower() == wanted.lower()), None)
        if not hit:
            L.fail("No people field called %r. Fields: %s" % (wanted, ", ".join(names)[:800]), code=2)
        return hit
    return next((n for n in names if n.lower() in default_names), None)


def members(audience_id, limit=None):
    ids = L.paged("audiences", "records", "search-ids", "--audience-id", audience_id, "--entity-type", "people",
                  limit=100 if limit is None else min(100, limit))
    return [str(i) for i in ids][:limit] if limit else [str(i) for i in ids]


def find_profile_field(audience_id, columns):
    """A people field that already holds a work history, found by CONTENT on up to ten members.
    Using it saves 0.5 credits a person; missing it would buy every profile again."""
    ids = members(audience_id, 10)
    if not ids:
        return None
    recs = L.clay("audiences", "records", "get", "--entity-type", "people", "--ids", ",".join(ids)).get("data") or []
    core = L.load_core("typesafe")
    names = dict((c["id"], c["name"]) for c in columns)
    for fid in sorted(set(k for r in recs for k in (r.get("fields") or {}))):
        for r in recs:
            v = (r.get("fields") or {}).get(fid)
            roles = core["read_profile"](core["_obj"](v))[0] if v else []
            if any(x["company"] for x in roles):
                return names.get(fid)
    return None


def build_audience(st_path, provider, headers, audience_id, url_field, profile_field, every, show_only,
                   name_field=None):
    g = Graph(st_path, "audience", AUD_WORKFLOW)
    columns = people_fields()
    url_name = pick_field(columns, url_field, ("linkedin url", "linkedin", "linkedin profile"))
    name_name = pick_field(columns, name_field, ("name", "full name"))
    prof_name = pick_field(columns, profile_field, ()) if profile_field else find_profile_field(audience_id, columns)
    L.say("Audiences mapping: LinkedIn URL ← %r; name ← %r; profile ← %s; company ← the person's first linked company."
          % (url_name, name_name, repr(prof_name) if prof_name else
             "none found on ten members (every person's profile is bought from LinkedIn)"))
    if show_only:
        print(json.dumps({"url_field": url_name, "name_field": name_name, "profile_field": prof_name,
                          "members": len(members(audience_id))}))
        return None
    if not url_name and not prof_name:
        L.fail("No people field holds a LinkedIn URL; name it with --url-field.", code=2)

    g.ensure_workflow()
    g.reconcile()
    fields = ensure_fields(columns)
    trig = {"triggerType": "audience_scheduled" if every else "audience_segment", "segmentId": audience_id,
            "entityType": "CONTACT"}
    if every:
        trig["scheduleConfig"] = schedule_config(every)
    prior = g.rec()
    if prior.get("trigger_id") and prior.get("trigger_kind") != trig["triggerType"]:
        L.fail("This audience workflow's trigger is %s and you asked for %s. Clay cannot change a trigger's "
               "type in place; delete the trigger in Clay (or the workflow), then re-run."
               % (prior.get("trigger_kind"), trig["triggerType"]))
    got = g.ensure_trigger(trig, {k: v for k, v in trig.items() if k != "triggerType"})
    g.put(trigger_kind=trig["triggerType"])
    paths = set((((got.get("outputSchema") or {}).get("properties")) or {}).keys())
    if not {"fields", "accounts"} <= paths:
        L.fail("The audience trigger's output has no %s, so the person or their company cannot be read. "
               "Found: %s" % (" and ".join(sorted({"fields", "accounts"} - paths)), ", ".join(sorted(paths))))
    tnodes = g.trigger_nodes()
    g.wire("intake", code_spec("1 Intake", L.render(L.AUD_INTAKE_HANDLER, provider, headers,
                                                   URL_FIELD=url_name or "", PROFILE_FIELD=prof_name or "",
                                                   NAME_FIELD=name_name or "")),
           {"fields": g.pin(tnodes[0], "$.fields", "object"), "accounts": g.pin(tnodes[0], "$.accounts", "array")},
           tnodes)
    g.wire("co_gate", rules_spec("1g Linked to a company?", [
        ("rule_need", "look up the company", "has_account", "Equal", True),
        ("rule_have", "no linked company", "has_account", "NotEqual", True)]),
        {"has_account": g.pin("intake", "$.has_account", "boolean")}, ["intake"])
    imc = {"entityType": {"type": "static", "value": "ACCOUNT"},
           "fields|fieldsToFilterBy": {"type": "static", "value": ["__entity_id__"]},
           "fields|__entity_id__": {"type": "reference", "expression": "{{account_id}}"},
           "dataToInclude": {"type": "static", "value": ["fields"]},
           "limit": {"type": "static", "value": 1}}
    g.wire("co_lookup", {"nodeType": "tool", "name": "1a Look up the company",
                         "tools": [{"toolType": "clay_action", "actionKey": LOOKUP_KEY,
                                    "actionPackageId": g.pkg(LOOKUP_KEY), "inputMappingConfig": imc}]},
           {"account_id": g.pin("intake", "$.account_id")},
           [{"from": "co_gate", "rule": "rule_need", "name": "look up the company"}])
    g.wire("co_pass", pass_spec("1p Lookup ran"), {"ran": {"type": "boolean"}}, ["co_lookup"])
    g.wire("company", code_spec("1r Company", L.render(L.AUD_COMPANY_HANDLER, provider)),
           {"a": g.pin("intake", "$", "object"), "found": g.pin("co_lookup", "$.result", "object")},
           [{"from": "co_pass", "rule": "rule_found", "name": "ran"},
            {"from": "co_pass", "rule": "rule_empty", "name": "continue anyway"},
            {"from": "co_gate", "rule": "rule_have", "name": "no linked company"}])
    keep = {"intake", "co_gate", "co_lookup", "co_pass", "company"}
    keep |= build_core(g, provider, "company", "intake", ["company"])

    def writer(k, name, src, edges, keys):
        fids = [fields[key] for _, key, _ in AUDIENCE_FIELDS if key in keys]
        imc = {"entityType": {"type": "static", "value": "CONTACT"},
               "entityId": {"type": "reference", "expression": "{{record_id}}"},
               "recordFields|selectedRecordFields": {"type": "static", "value": fids},
               "recordFields|removeNullValues": {"type": "static", "value": True}}
        wp = {"record_id": g.pin("intake", "$.record_id")}
        for n, (_, key, _) in enumerate(AUDIENCE_FIELDS):
            if key not in keys:
                continue
            imc["recordFields|" + fields[key]] = {"type": "reference", "expression": "{{v_%d}}" % n}
            wp["v_%d" % n] = g.pin(src, "$." + key)
        g.wire(k, {"nodeType": "tool", "name": name,
                   "tools": [{"toolType": "clay_action", "actionKey": UPDATE_KEY, "actionPackageId": g.pkg(UPDATE_KEY),
                              "inputMappingConfig": imc}]}, wp, edges)

    all_keys = [key for _, key, _ in AUDIENCE_FIELDS]
    # 3b's lane: a verdict reached without Jev (nothing at the company) is saved in full; "not
    # checked" (no profile, no company) saves only its status and note, never over an earlier verdict.
    g.wire("route_b", rules_spec("3c Save which?", [
        ("rule_full", "verdict", "check_status", "Equal", "checked"),
        ("rule_note", "not checked: status only", "check_status", "NotEqual", "checked")]),
        {"check_status": g.pin("nojev", "$.check_status")}, ["nojev"])
    writer("save_b", "3d Save verdict", "nojev", [{"from": "route_b", "rule": "rule_full", "name": "verdict"}], all_keys)
    writer("note_b", "3e Save status only", "nojev",
           [{"from": "route_b", "rule": "rule_note", "name": "not checked: status only"}], NOT_CHECKED_FIELDS)
    g.wire("route_v", rules_spec("6 Save it?", [
        ("rule_full", "verdict", "check_status", "Equal", "checked"),
        ("rule_keep", "Jev failed: keep the earlier verdict", "check_status", "NotEqual", "checked")]),
        {"check_status": g.pin("verdict", "$.check_status")}, ["verdict"])
    writer("save_v", "6a Save verdict", "verdict", [{"from": "route_v", "rule": "rule_full", "name": "verdict"}], all_keys)
    g.wire("not_saved", code_spec("6b Not saved (Jev failed)",
                                  "def handler(context):\n    return {'saved': False, 'isTerminal': True}\n"),
           {"prev": g.pin("verdict", "$", "object")},
           [{"from": "route_v", "rule": "rule_keep", "name": "Jev failed: keep the earlier verdict"}])
    keep |= {"route_b", "save_b", "note_b", "route_v", "save_v", "not_saved"}
    g.prune(keep)
    g.put(provider=provider, audience={"segment_id": audience_id, "url_field": url_name, "name_field": name_name,
                                       "profile_field": prof_name, "every": every or "", "fields": fields})
    L.say("  = %s: built" % g.name)
    return g


def _ledger(st_path, audience_id):
    return os.path.join(os.path.dirname(st_path), "backfill-%s.jsonl" % audience_id)


def _read_ledger(path):
    out = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    out[str(d["id"])] = d.get("at", 0)
                except Exception:
                    continue
    return out


def _attempted(ids, field_id):
    """{id: last-attempt value} read back from Clay: what the workflow actually wrote."""
    got = {}
    for n in range(0, len(ids), 100):
        recs = L.clay("audiences", "records", "get", "--entity-type", "people", "--ids", ",".join(ids[n:n + 100]),
                      allow_fail=True).get("data") or []
        for r in recs:
            got[str(r.get("recordId"))] = (r.get("fields") or {}).get(field_id)
    return got


def backfill(st_path, audience_id, limit, dry=False, settle_after=900):
    """Check members already in the audience (the trigger only fires for people who join).

    What is left is recomputed from CLAY, not from memory: a member counts as done once the
    workflow wrote its "Active last attempt" field. A member sent more than `settle_after`
    seconds ago with nothing written (Jev rate limit or outage: a failed check writes nothing)
    goes back in the work set. Sends in batches of up to 50 through the published workflow, each
    id appended to a ledger the moment its batch is accepted."""
    rec = L.load(st_path, {"workflows": {}})["workflows"].get("audience") or {}
    if not rec.get("id"):
        L.fail("Build the Audiences workflow first (--audience).")
    field = ((rec.get("audience") or {}).get("fields") or {}).get("check_status")
    path = _ledger(st_path, audience_id)
    sent = _read_ledger(path)
    ids = members(audience_id)
    done = _attempted([i for i in ids if i in sent], field) if sent and field else {}
    now = time.time()
    settled = set(i for i, v in done.items() if v)
    waiting = set(i for i in sent if i not in settled and now - sent[i] < settle_after)
    todo = [i for i in ids if i not in settled and i not in waiting]
    if limit:
        todo = todo[:limit]
    L.say("%d members: %d checked, %d sent in the last %d minutes (not yet settled), %d to send now (%.1f credits "
          "at most)." % (len(ids), len(settled), len(waiting), settle_after // 60, len(todo), len(todo) * L.ENRICH_CREDITS))
    if dry:
        print(json.dumps({"members": len(ids), "checked": len(settled), "waiting": len(waiting), "would_send": len(todo),
                          "max_credits": len(todo) * L.ENRICH_CREDITS}))
        return
    for n in range(0, len(todo), 50):
        batch = todo[n:n + 50]
        out = L.clay("workflows", "runs", "test", rec["id"], "--audience-segment", audience_id,
                     "--record-ids", ",".join(batch), "--live", allow_fail=True)
        if isinstance(out, dict) and out.get("error"):
            L.fail("Batch starting at %s was refused: %s. Re-run to continue; nothing sent is lost." % (batch[0], out["error"]))
        with open(path, "a") as f:
            for i in batch:
                f.write(json.dumps({"id": i, "at": time.time()}) + "\n")
        L.say("  sent %d" % (n + len(batch)))
    print(json.dumps({"members": len(ids), "checked": len(settled), "waiting": len(waiting), "sent_now": len(todo)}))


def readback(st_path, audience_id):
    """The "Active …" fields of every member this script has sent, as a table: the Audiences
    preview (Step 6)."""
    rec = L.load(st_path, {"workflows": {}})["workflows"].get("audience") or {}
    fields = (rec.get("audience") or {}).get("fields") or {}
    sent = list(_read_ledger(_ledger(st_path, audience_id)))
    if not sent:
        L.fail("Nothing sent yet: run backfill first (Step 6 sends ten with --limit 10).")
    rows = []
    for n in range(0, len(sent), 100):
        rows += L.clay("audiences", "records", "get", "--entity-type", "people", "--ids",
                       ",".join(sent[n:n + 100])).get("data") or []
    keys = ("active_at_company", "relationship", "verdict_confidence", "check_status", "evidence")
    for r in rows:
        f = r.get("fields") or {}
        v = dict((k, f.get(fields.get(k))) for k in keys)
        shown = v["active_at_company"] or ("(not checked)" if v["check_status"] else "(pending)")
        L.say("  %-12s %-13s %-16s %4s  %-22s %s" % (r.get("recordId"), shown,
                                                  v["relationship"] or "", v["verdict_confidence"] or "",
                                                  v["check_status"] or "", str(v["evidence"] or "")[:110]))
    tally = {}
    for r in rows:
        rf = r.get("fields") or {}
        k = rf.get(fields.get("active_at_company")) or ("(not checked)" if rf.get(fields.get("check_status")) else "(pending)")
        tally[k] = tally.get(k, 0) + 1
    L.say("%d members: %s" % (len(rows), ", ".join("%s %d" % kv for kv in sorted(tally.items()))))


# ======================================================================= main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", nargs="?", default="build", choices=("build", "backfill", "readback"))
    ap.add_argument("--provider", choices=sorted(L.PROVIDERS))
    ap.add_argument("--audience", help="a saved audience of people: also build the Audiences workflow")
    ap.add_argument("--url-field", help="the people field holding the LinkedIn URL (default: 'LinkedIn URL')")
    ap.add_argument("--profile-field", help="a people field holding an enriched profile (default: found by content)")
    ap.add_argument("--name-field", help="the people field holding the person's name (default: 'Name')")
    ap.add_argument("--schedule", choices=("weekly", "monthly", "quarterly"),
                    help="re-check the whole audience on this schedule instead of when people join")
    ap.add_argument("--show-audience-map", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="backfill: at most this many members this run (default: all)")
    a = ap.parse_args()

    L.check_cli()
    ws = L.workspace()
    st_path = os.path.join(L.state_dir(ws["id"]), "build-state.json")
    if a.action in ("backfill", "readback"):
        if not a.audience:
            L.fail("%s needs --audience" % a.action, code=2)
        if a.action == "backfill":
            backfill(st_path, a.audience, a.limit, dry=a.plan)
        else:
            readback(st_path, a.audience)
        return
    prior = L.load(st_path, {"workflows": {}})["workflows"]
    provider = a.provider or (prior.get("table") or {}).get("provider")
    if not provider:
        L.fail("Say which provider holds the key: --provider openrouter|typesafe", code=2)
    aud = a.audience or ((prior.get("audience") or {}).get("audience") or {}).get("segment_id")
    P = L.PROVIDERS[provider]

    if a.plan or a.show_audience_map:
        L.say("Would build in Clay workspace %s:" % (ws["name"] or ws["id"]))
        L.say("  %s   (webhook; a table can invoke it)" % L.WORKFLOW_NAME)
        if aud:
            L.say("  %s   (audience %s: %s; writes %s)" % (
                AUD_WORKFLOW, aud, "re-checks every member %s" % {"weekly": "every week", "monthly": "every month",
                                                                   "quarterly": "every quarter"}[a.schedule]
                if a.schedule else "checks people as they join", ", ".join(n for n, _, _ in AUDIENCE_FIELDS)))
            if a.schedule:
                n = len(members(aud))
                L.say("  FIRST SCHEDULED RUN: %s UTC, all %d current members, up to %.1f credits; then the same "
                      "every %s." % (schedule_config(a.schedule)["value"]["startDate"][:16].replace("T", " "), n,
                                    n * L.ENRICH_CREDITS, a.schedule[:-2] if a.schedule != "monthly" else "month"))
        L.say("  '4 Ask Jev' calls %s (%s); the key is written into each workflow's first step." % (P["label"], P["model"]))
        L.say("  '2a Enrich person' costs %s Clay credits, only for a person sent with no profile." % L.ENRICH_CREDITS)
        if a.show_audience_map and aud:
            build_audience(st_path, provider, None, aud, a.url_field, a.profile_field, a.schedule, True, a.name_field)
        return

    headers = L.jev_headers(provider)
    L.say("Building in Clay workspace %s" % (ws["name"] or ws["id"]))
    graphs = [build_table(st_path, provider, headers)]
    if aud:
        prev = (prior.get("audience") or {}).get("audience") or {}
        graphs.append(build_audience(st_path, provider, headers, aud, a.url_field or prev.get("url_field"),
                                     a.profile_field or prev.get("profile_field"),
                                     a.schedule or prev.get("every") or None, False,
                                     a.name_field or prev.get("name_field")))
    wrong = [w for g in graphs for w in g.problems]
    # One decision for both: publish all or none, so a workflow is never live beside a sibling
    # that was held back. A version published earlier stays live either way.
    if not wrong:
        for g in graphs:
            g.publish()
            L.say("  = %s: published" % g.name)
    out = {"webhook_url": graphs[0].rec().get("webhook_url"), "workflow_id": graphs[0].wf, "published": not wrong}
    if len(graphs) > 1:
        out["audience_workflow_id"] = graphs[1].wf
    print(json.dumps(out))
    if wrong:
        L.fail(connection_report(wrong), code=6)


if __name__ == "__main__":
    main()

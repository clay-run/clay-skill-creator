#!/usr/bin/env python3
"""
Build (or update) the Clay workflow that scores one record with a saved rubric, and publish it.

    python3 build_scorer.py --provider openrouter --plan                 # what would be built; changes nothing
    python3 build_scorer.py --provider openrouter [--connection "Jev (OpenRouter)"] [--connection-id <connection id>]
    python3 build_scorer.py --provider openrouter --reattach     # after making the Jev connection Clay's default
    python3 build_scorer.py --provider openrouter --audience <audience id> --show-audience-map
    python3 build_scorer.py --provider openrouter --audience <audience id> [--map key=Field …]
    python3 build_scorer.py backfill --audience <audience id> [--limit 500]   # score existing members

The table/webhook workflow, "Jev lead score: <entity> · <rubric>":

  webhook (+ any table bound to it in Clay's UI)
    → 1 Intake (code)             rules worked out in code; which questions have their data; the request
    → 2 Anything to ask Jev?      yes → 3 ; no → 2b
    → 2b Score without Jev (code, terminal)     disqualified by a rule, a required input missing, or nothing to ask
    → 3 Ask Jev (HTTP, the Clay connection holds the key)
    → 4 Score (code, terminal)

With --audience, a second workflow, "… (audience)", is triggered by members of that saved audience
and writes the verdict onto each record's own "Jev …" fields (created if missing, adopted by name
if they exist). A failed Jev call writes nothing, so an outage never overwrites an earlier score.

The key lives in a Clay connection (HTTP API with headers). Clay attaches a connection to a step by
id, never by name, and its CLI lists no HTTP connection ids, so: the build binds by id when it can
find one (or --connection-id), otherwise writes the step, gets the workspace's default connection,
and READS IT BACK. If the step landed on any connection other than the one named, that workflow is
not published and the build stops (exit 6) printing the fixes: --connection-id, or make the Jev
connection Clay's default and re-run with --reattach.

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
import jev_lib as L  # noqa: E402

HTTP_KEY = "http-api-v2"
UPDATE_KEY = "update-audiences-record"


# ======================================================================= connections

def same_name(a, b):
    return str(a or "").strip().lower() == str(b or "").strip().lower() != ""


def find_account_id(catalog, action_key, name):
    """The id of the connection called `name`, when Clay's catalogue happens to list it. The HTTP
    action usually lists none, so None is a normal answer; the read-back then decides."""
    for a in catalog or []:
        if a.get("actionKey") != action_key:
            continue
        for acc in a.get("availableAppAccounts") or []:
            if same_name(acc.get("name"), name) and (acc.get("abilities") or {}).get("canAccess") is not False:
                return acc.get("id")
        for t in a.get("configuredTools") or []:
            if same_name(t.get("appAccountName"), name) and t.get("appAccountId"):
                return t["appAccountId"]
    return None


REATTACH = False     # --reattach: write connection steps as new tools, so Clay attaches its current default


def bind_tool(tool, existing=None, account_id=None):
    """The tool as written to Clay. Keeps the node's own `toolId` (an update without it makes a
    NEW tool, which re-attaches the workspace default and undoes a connection chosen in the UI);
    binds by id when known."""
    out = {k: v for k, v in tool.items() if k not in ("connection", "appAccountName")}
    keep = not (REATTACH and tool.get("connection"))
    if keep and existing and existing.get("toolId") and existing.get("actionKey") == tool.get("actionKey"):
        out["toolId"] = existing["toolId"]
    if tool.get("connection") and account_id:
        out["appAccountId"] = account_id
    return out


def binding_problem(tool, back):
    """None when the step read back from Clay is on the connection it needs; otherwise the
    connection it is actually on ("(none)" when it has none)."""
    want = tool.get("connection")
    if not want:
        return None
    got = (back or {}).get("appAccountName") or (back or {}).get("appAccountId")
    return None if same_name(got, want) else (got or "(none)")


def connection_report(wrong):
    lines = ["%d step(s) are not on the right Clay connection; the workflow(s) below were NOT published:" % len(wrong)]
    lines += ["  - %s → step '%s': on %r, needs %r" % w for w in wrong]
    lines += ["Clay attaches a connection to a step by id, never by name, and its CLI cannot list HTTP "
              "connection ids, so Clay picked a different one (or none).",
              "Fix it one of these ways, then re-run; the build checks every step again and publishes:",
              "  1. --connection-id <connection id> binds by id, when you can read the connection's id.",
              "  2. In Clay: Settings → Connections → the Jev connection's … menu → Set as default. Re-run this "
              "build with --reattach, which rewrites the step so Clay attaches its default. Then set the "
              "connection named 'on' above back as default, so new HTTP steps elsewhere don't get the Jev key.",
              "  3. In the workflow's draft, click the step, pick the connection, Save, and re-run. (This "
              "did not persist in testing; if the re-run still reports it, use 1 or 2.)"]
    return "\n".join(lines)


# ======================================================================= graph plumbing

def action_catalog():
    c = L.clay("workflows", "actions", "list")
    return (c.get("data") if isinstance(c, dict) else c) or []


class Graph:
    """One workflow's nodes, persisted in build-state.json under workflows[<key>]."""

    def __init__(self, st_path, key, name):
        self.st_path, self.key, self.name = st_path, key, name
        self._pkg, self._catalog = {}, None
        self.problems = []          # (workflow, step, is_on, needs)
        self.account_id = None

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
        got = L.clay("workflows", "triggers", "get", self.rec()["trigger_id"])
        if refresh:
            want = set(((refresh.get("inputSchema") or {}).get("properties") or {}))
            have = set(((got.get("inputSchema") or {}).get("properties") or {}))
            if have and want - have:
                L.fail("The trigger's input schema is missing %s after the update; inputs not in it are "
                       "dropped at intake. Re-run the build." % sorted(want - have))
        return got

    def trigger_nodes(self):
        """EVERY trigger node: binding a table in Clay's UI adds its own, and wiring only ours would
        sever that binding on the next rebuild."""
        nodes = [self.rec()["trigger_node"]]
        g = L.clay("workflows", "graph", "get", self.wf)
        for t in (g.get("summary") or {}).get("triggers") or []:
            nid = L.clay("workflows", "triggers", "get", t["id"]).get("workflowNodeId")
            if nid and nid not in nodes:
                nodes.append(nid)
        return nodes

    def catalog(self):
        if self._catalog is None:
            self._catalog = action_catalog()
        return self._catalog

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
            body["tools"] = [bind_tool(t, None, self.account_id) for t in spec["tools"]]
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
        reports success and drops what it omitted, and a tool can land on the wrong connection
        without any error."""
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
            body["tools"] = [bind_tool(t, have[i] if i < len(have) else None, self.account_id)
                             for i, t in enumerate(spec["tools"])]
        L.clay("workflows", "nodes", "update", self.wf, nid, inp=body)
        back = L.clay("workflows", "nodes", "get", self.wf, nid)["node"]
        got = {kk for kk, v in ((back.get("inputSchema") or {}).get("properties") or {}).items()
               if isinstance(v, dict) and v.get("sourceNodeId")}
        lost = set(pins or {}) - got
        if lost:
            L.fail("Pins lost on %s (%s): %s" % (self.name, k, sorted(lost)))
        back_tools = back.get("tools") or []
        for i, t in enumerate(spec.get("tools") or []):
            on = binding_problem(t, back_tools[i] if i < len(back_tools) else None)
            if on:
                self.problems.append((self.name, spec.get("name") or k, on, t.get("connection")))
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
    return {"nodeType": "conditional", "name": name, "conditionalMode": "rules",
            "rulesConditionalConfig": {"rules": [
                {"id": rid, "name": label, "condition": {"type": "GroupOp", "combinationMode": "And", "items": [
                    {"type": "BinOp", "dataPath": [path], "operator": op, "value": val}]}}
                for rid, label, path, op, val in rules]}}


def http_spec(g, connection):
    """3 Ask Jev. URL, body and headers by reference from 1 Intake (headers MUST be a reference to
    an object: a static JSON string is sent one header per character, a static object is
    rejected). The key comes from the Clay connection, never from the workflow's own text.
    returnResponseMetadata makes a 4xx data rather than a failed run, so 4 Score can say why."""
    imc = {"method": {"type": "static", "value": "POST"},
           "url": {"type": "reference", "expression": "{{jev_url}}"},
           "body": {"type": "reference", "expression": "{{jev_body}}"},
           "headers": {"type": "reference", "expression": "{{jev_headers}}"},
           "returnResponseMetadata": {"type": "static", "value": True}}
    # NO shouldRetry / retryOptions: with them set, the step failed every live run with
    # ERROR_ACTION_RUNTIME_ERROR before calling Jev; without them, every run passed (2026-09-29).
    return {"nodeType": "tool", "name": "3 Ask Jev",
            "tools": [{"toolType": "clay_action", "actionKey": HTTP_KEY, "actionPackageId": g.pkg(HTTP_KEY),
                       "connection": connection, "inputMappingConfig": imc}]}


def build_core(g, rubric, provider, connection, intake_pins, triggers):
    """The four scoring nodes both workflows share. Returns the node keys built."""
    g.wire("intake", code_spec("1 Intake", L.render(L.INTAKE_HANDLER, rubric, provider)), intake_pins, triggers)
    g.wire("gate", rules_spec("2 Anything to ask Jev?", [
        ("rule_ask", "ask Jev", "ask", "Equal", True), ("rule_skip", "nothing to ask", "ask", "NotEqual", True)]),
           {"ask": g.pin("intake", "$.ask", "boolean")}, ["intake"])
    g.wire("nojev", code_spec("2b Score without Jev", L.render(L.NOJEV_HANDLER, rubric, provider)),
           {"intake": g.pin("intake", "$", "object")}, [{"from": "gate", "rule": "rule_skip", "name": "nothing to ask"}])
    g.wire("ask", http_spec(g, connection),
           {"jev_url": g.pin("intake", "$.jev_url"), "jev_body": g.pin("intake", "$.jev_body"),
            "jev_headers": g.pin("intake", "$.jev_headers", "object")},
           [{"from": "gate", "rule": "rule_ask", "name": "ask Jev"}])
    g.wire("score", code_spec("4 Score", L.render(L.SCORE_HANDLER, rubric, provider)),
           {"intake": g.pin("intake", "$", "object"),
            "status_code": g.pin("ask", "$.result.statusCode", "number"),
            "body": g.pin("ask", "$.result.body", "object")}, ["ask"])
    return {"intake", "gate", "nojev", "ask", "score"}


# ======================================================================= the table / webhook workflow

def wf_name(rubric, audience=False):
    return "Jev lead score: %s · %s%s" % (L.NOUNS, rubric["name"], " (audience)" if audience else "")


def build_table(st_path, rubric, provider, connection, account_id):
    key = L.slug(rubric["name"])
    g = Graph(st_path, key, wf_name(rubric))
    g.account_id = account_id
    g.ensure_workflow()
    g.reconcile()
    props = dict((k, {"type": "string"}) for k in list(rubric["inputs"]) + ["source_ref"])
    schema = {"inputSchema": {"type": "object", "properties": props}}
    g.ensure_trigger(dict(triggerType="webhook", **schema), schema)
    triggers = g.trigger_nodes()
    pins = dict(("in_" + k, g.pin(triggers[0], "$." + k)) for k in list(rubric["inputs"]) + ["source_ref"])
    keep = build_core(g, rubric, provider, connection, pins, triggers)
    g.prune(keep)
    ok = g.publish()
    g.put(rubric_version=rubric["version"], provider=provider, connection=connection)
    L.say("  = %s: %s" % (g.name, "built and published" if ok else "built, NOT published (connection)"))
    return g


# ======================================================================= the audience workflow

def audience_columns():
    f = L.clay("audiences", "fields", "list", "--entity-type", L.AUDIENCE_FLAG)
    f = f.get("data") or f.get("fields") or (f if isinstance(f, list) else [])
    return [{"id": x.get("id") or x.get("fieldId"), "name": x.get("name") or x.get("displayName"),
             "dataType": x.get("dataType")} for x in f]


def schema_paths(schema, prefix=""):
    """Every dotted path an outputSchema declares."""
    out = set()
    props = (schema or {}).get("properties") or {}
    for k, v in props.items():
        p = prefix + k
        out.add(p)
        if isinstance(v, dict) and v.get("properties"):
            out |= schema_paths(v, p + ".")
    return out


def resolve_path(paths, candidates):
    for c in candidates:
        if c and c in paths:
            return "$." + c
    return None


def ensure_score_fields(columns):
    """The "Jev …" fields the audience workflow writes: adopted by display name, created if absent.
    `fields create` suffixes a taken name, so adopting first is what keeps this idempotent."""
    by_name = dict((str(c["name"]).strip().lower(), c) for c in columns if c.get("name"))
    out = {}
    for name, key, dtype in L.AUDIENCE_FIELDS:
        c = by_name.get(name.lower())
        if c:
            if c.get("dataType") and str(c["dataType"]).lower() != dtype:
                L.fail("Audiences already has a field %r of type %s, but it must be %s for this workflow. "
                       "Rename that field in Clay, then re-run." % (name, c["dataType"], dtype))
            out[key] = c["id"]
            continue
        made = L.clay("audiences", "fields", "create", "--entity-type", L.AUDIENCE_FLAG, "--name", name,
                      "--data-type", dtype)
        out[key] = made["id"]
        L.say("  + Audiences field %r (%s)" % (made.get("name") or name, dtype))
    return out


def build_audience(st_path, rubric, provider, connection, account_id, audience_id, overrides, show_only):
    key = L.slug(rubric["name"]) + "__audience"
    g = Graph(st_path, key, wf_name(rubric, True))
    g.account_id = account_id
    columns = audience_columns()
    prior = (g.rec().get("audience") or {})
    mapping = L.propose_map(rubric["inputs"], columns)
    if prior.get("segment_id") == audience_id:
        mapping.update((k, v) for k, v in (prior.get("map") or {}).items() if k in mapping)
    mapping = L.apply_overrides(mapping, columns, overrides)
    L.say(L.mapping_card(rubric["inputs"], mapping, columns))
    missing = [k for k, s in rubric["inputs"].items() if s["required"] and not mapping.get(k)]
    if show_only:
        print(json.dumps({"mapping": mapping, "unmapped": [k for k in mapping if not mapping[k]]}))
        return None
    if missing:
        L.fail("Required input(s) have no audience field: %s. Map them with --map key=Field." % ", ".join(missing), code=2)

    g.ensure_workflow()
    g.reconcile()
    fields = ensure_score_fields(columns)
    trig = g.ensure_trigger({"triggerType": "audience_segment", "segmentId": audience_id,
                             "entityType": L.AUDIENCE_TYPE}, None)
    if str(trig.get("segmentId") or audience_id) != str(audience_id):
        L.clay("workflows", "triggers", "update", g.rec()["trigger_id"], inp={"segmentId": audience_id})
    paths = schema_paths(trig.get("outputSchema") or {})
    if not paths:
        L.fail("Clay did not return an output schema for the audience trigger, so the field paths cannot be "
               "read, and this build does not guess them. Open the workflow in Clay once, then re-run.")
    names = dict((c["id"], c["name"]) for c in columns)
    pins = {}
    tnode = g.rec()["trigger_node"]
    for k, fid in mapping.items():
        if not fid:
            continue
        p = resolve_path(paths, ["fields." + str(fid), "fields." + str(names.get(fid) or ""), str(fid),
                                 str(names.get(fid) or "")])
        if not p:
            L.fail("The audience trigger does not expose field %r (%s). Available: %s"
                   % (names.get(fid), fid, ", ".join(sorted(paths))[:600]))
        pins["in_" + k] = g.pin(tnode, p)
    rid = resolve_path(paths, ["fields.id", "id", "recordId", "entityId"])
    if not rid:
        L.fail("The audience trigger exposes no record id (looked for fields.id, id). Available: %s"
               % ", ".join(sorted(paths))[:600])
    pins["in_record_id"] = g.pin(tnode, rid)
    keep = build_core(g, rubric, provider, connection, pins, g.trigger_nodes())

    def writer(k, name, src, edges):
        fids = [fields[key] for _, key, _ in L.AUDIENCE_FIELDS]
        imc = {"entityType": {"type": "static", "value": L.AUDIENCE_TYPE},
               "entityId": {"type": "reference", "expression": "{{record_id}}"},
               "recordFields|selectedRecordFields": {"type": "static", "value": fids},
               "recordFields|removeNullValues": {"type": "static", "value": True}}
        wp = {"record_id": g.pin("intake", "$.record_id")}
        for n, (_, key, _) in enumerate(L.AUDIENCE_FIELDS):
            imc["recordFields|" + fields[key]] = {"type": "reference", "expression": "{{v_%d}}" % n}
            wp["v_%d" % n] = g.pin(src, "$." + key)
        g.wire(k, {"nodeType": "tool", "name": name,
                   "tools": [{"toolType": "clay_action", "actionKey": UPDATE_KEY, "actionPackageId": g.pkg(UPDATE_KEY),
                              "inputMappingConfig": imc}]}, wp, edges)

    writer("write_nojev", "2c Save to Audiences", "nojev", ["nojev"])
    g.wire("save_gate", rules_spec("5 Save it?", [
        ("rule_save", "save", "score_status", "NotEqual", "failed"),
        ("rule_keep", "Jev failed: keep the old score", "score_status", "Equal", "failed")]),
           {"score_status": g.pin("score", "$.score_status")}, ["score"])
    writer("write", "6 Save to Audiences", "score", [{"from": "save_gate", "rule": "rule_save", "name": "save"}])
    g.wire("not_saved", code_spec("5b Not saved (Jev failed)",
                                  "def handler(context):\n    return {'saved': False, 'isTerminal': True}\n"),
           {"prev": g.pin("score", "$", "object")},
           [{"from": "save_gate", "rule": "rule_keep", "name": "Jev failed: keep the old score"}])
    keep |= {"write_nojev", "save_gate", "write", "not_saved"}
    g.prune(keep)
    ok = g.publish()
    g.put(rubric_version=rubric["version"], provider=provider, connection=connection,
          audience={"segment_id": audience_id, "map": mapping, "fields": fields})
    L.say("  = %s: %s" % (g.name, "built and published" if ok else "built, NOT published (connection)"))
    return g


def backfill(st_path, rubric, audience_id, limit):
    """Score members already in the audience (the trigger handles members as they join).

    What is left is DERIVED from Clay, not remembered: a member is done when its "Jev score rubric"
    field already reads this rubric's "name vN". So a re-run after an interruption, a Jev outage
    (failed runs write nothing) or a new rubric version submits exactly the members still owed,
    and nothing is double-counted. Members submitted in the last 30 minutes are skipped once, so a
    quick re-run does not resubmit runs that are still in flight."""
    st = L.load(st_path, {"workflows": {}})
    rec = st["workflows"].get(L.slug(rubric["name"]) + "__audience") or {}
    fid = ((rec.get("audience") or {}).get("fields") or {}).get("rubric")
    if not rec.get("id") or not fid:
        L.fail("Build the audience workflow first (--audience).")
    want = "%s v%d" % (rubric["name"], rubric["version"])
    ids = [str(i) for i in L.paged("audiences", "records", "search-ids", "--audience-id", audience_id,
                                     "--entity-type", L.AUDIENCE_FLAG, limit=2000)]
    done = set()
    for n in range(0, len(ids), 100):
        got = L.clay("audiences", "records", "get", "--entity-type", L.AUDIENCE_FLAG,
                     "--ids", ",".join(ids[n:n + 100])).get("data") or []
        done |= {str(r.get("recordId")) for r in got if (r.get("fields") or {}).get(fid) == want}
    ledger = os.path.join(os.path.dirname(st_path), "backfill-inflight.json")
    inflight = L.load(ledger, {})
    now = time.time()
    recent = {i for i, t in inflight.get(want, {}).items() if now - t < 1800}
    todo = [i for i in ids if i not in done and i not in recent][:limit]
    L.say("%d members: %d already scored with %s, %d submitted in the last 30 minutes, submitting %d now."
          % (len(ids), len(done), want, len(recent), len(todo)))
    for n in range(0, len(todo), 50):
        batch = todo[n:n + 50]
        out = L.clay("workflows", "runs", "test", rec["id"], "--audience-segment", audience_id,
                     "--record-ids", ",".join(batch), "--live", allow_fail=True)
        if isinstance(out, dict) and out.get("error"):
            L.fail("Batch starting at %s was refused: %s" % (batch[0], out["error"]))
        inflight.setdefault(want, {}).update((i, now) for i in batch)
        L.save(ledger, inflight)
        L.say("  submitted %d" % (n + len(batch)))
    L.say("Submitted. Each score lands on the record's 'Jev …' fields as its run finishes; run this again "
          "later to see what is left (failed runs write nothing and are picked up again).")


# ======================================================================= main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", nargs="?", default="build", choices=("build", "backfill"))
    ap.add_argument("--rubric")
    ap.add_argument("--provider", choices=sorted(L.PROVIDERS))
    ap.add_argument("--connection", help="the Clay connection holding the key (default: 'Jev (<provider>)')")
    ap.add_argument("--connection-id", help="bind that connection by its id, when you can read it")
    ap.add_argument("--audience", help="a saved audience id: also build the audience workflow")
    ap.add_argument("--map", action="append", default=[], help="key=Field for the audience workflow")
    ap.add_argument("--show-audience-map", action="store_true")
    ap.add_argument("--reattach", action="store_true",
                    help="rewrite the Jev step as a new tool so Clay attaches its current default connection")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--limit", type=int, default=500, help="backfill: at most this many members this run")
    a = ap.parse_args()

    global REATTACH
    REATTACH = a.reattach
    L.check_cli()
    ws = L.workspace()
    rubric = L.load_rubric(a.rubric, ws["id"])
    st_path = os.path.join(L.state_dir(ws["id"]), "build-state.json")

    if a.action == "backfill":
        if not a.audience:
            L.fail("backfill needs --audience", code=2)
        backfill(st_path, rubric, a.audience, a.limit)
        return

    prior = L.load(st_path, {"workflows": {}})["workflows"].get(L.slug(rubric["name"])) or {}
    provider = a.provider or prior.get("provider")
    if not provider:
        L.fail("Say which provider holds the key: --provider openrouter|typesafe", code=2)
    same_provider = prior.get("provider") == provider
    connection = a.connection or (prior.get("connection") if same_provider else None) or L.PROVIDERS[provider]["connection"]

    if a.plan or a.show_audience_map:
        L.say("Would build in Clay workspace %s:" % (ws["name"] or ws["id"]))
        L.say("  %s   (webhook; bind a table to '1 Intake')" % wf_name(rubric))
        if a.audience:
            L.say("  %s   (runs for members of audience %s; writes %s)" % (
                wf_name(rubric, True), a.audience, ", ".join(n for n, _, _ in L.AUDIENCE_FIELDS)))
        L.say("  '3 Ask Jev' calls %s (%s) with the key from the Clay connection %r."
              % (L.PROVIDERS[provider]["label"], L.PROVIDERS[provider]["model"], connection))
        L.say("  Rubric %s v%d: %d rules, %d Jev questions." % (rubric["name"], rubric["version"],
                                                               len(rubric["rules"]), len(rubric["questions"])))
        if a.show_audience_map and a.audience:
            build_audience(st_path, rubric, provider, connection, None, a.audience, a.map, True)
        return

    L.say("Building in Clay workspace %s" % (ws["name"] or ws["id"]))
    account_id = a.connection_id or find_account_id(action_catalog(), HTTP_KEY, connection)
    graphs = [build_table(st_path, rubric, provider, connection, account_id)]
    aud = a.audience or ((L.load(st_path, {"workflows": {}})["workflows"].get(L.slug(rubric["name"]) + "__audience")
                          or {}).get("audience") or {}).get("segment_id")
    if aud:
        graphs.append(build_audience(st_path, rubric, provider, connection, account_id, aud, a.map, False))
    wrong = [(w, step, on, needs) for g in graphs for (w, step, on, needs) in g.problems]
    out = {"webhook_url": graphs[0].rec().get("webhook_url"), "workflow_id": graphs[0].wf,
           "published": not wrong}
    if len(graphs) > 1:
        out["audience_workflow_id"] = graphs[1].wf
    print(json.dumps(out))
    if wrong:
        L.fail(connection_report(wrong), code=6)


if __name__ == "__main__":
    main()

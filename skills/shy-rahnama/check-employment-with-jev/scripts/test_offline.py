#!/usr/bin/env python3
"""
Everything checkable with no Clay, no network and no key.

    python3 test_offline.py            # run the checks (exit 0 = all pass)
    python3 test_offline.py --record   # maintainers: re-record jev_answers.json from live Jev (needs a key)

1. Every generated code step compiles, and only the first step carries the key.
2. The verdict code runs with `datetime`, `_strptime` and `calendar` made unimportable, the way
   Clay's code runtime has them (a green run elsewhere proved nothing once: every date failed live).
3. The invented cases in fixtures.json, replayed against Jev answers recorded from a live run,
   give the verdict each case expects. A changed question set is caught, not silently replayed.
4. Output keys are always all present, and every verdict value is from its fixed set.
5. Jev failures (401, 429, a malformed body) come back `failed`, never as a verdict.
6. Company matching and date reading, case by case.
7. The builder, against a fake Clay: the Jev step has no connection and headers by reference,
   no step with several parents has a plain edge into it, every pin is sent, and the key is in
   no step but the first.
"""
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import active_lib as L  # noqa: E402

ANSWERS = os.path.join(HERE, "jev_answers.json")
MARK = "test-marker-not-a-key"
FAKE_HEADERS = {"Content-Type": "application/json", "X-Test": MARK}
passed, failed = [0], []


def check(name, cond, detail=""):
    if cond:
        passed[0] += 1
    else:
        failed.append("%s %s" % (name, detail))


def cases():
    return json.load(open(os.path.join(HERE, "fixtures.json")))["cases"]


class Blocked:
    """Make modules unimportable for the duration, as Clay's code runtime does."""
    NAMES = ("datetime", "_strptime", "calendar", "_datetime", "re")

    def __enter__(self):
        self.saved = dict((n, sys.modules.get(n)) for n in self.NAMES)
        for n in self.NAMES:
            sys.modules[n] = None
        return self

    def __exit__(self, *a):
        for n, m in self.saved.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m


def replay(record_file):
    store = json.load(open(record_file)) if os.path.exists(record_file) else {}

    def make(cid):
        def call(body):
            rec = store.get(cid)
            if not rec:
                raise AssertionError("no recorded Jev answer for %s: run test_offline.py --record" % cid)
            if sorted(rec["questions"]) != sorted(body["questions"]):
                raise AssertionError("%s asks different questions than were recorded (%s vs %s): re-record"
                                     % (cid, sorted(body["questions"]), sorted(rec["questions"])))
            return 200, rec["response"]
        return call
    return make


def record():
    store = {}
    for c in cases():
        def call(body, cid=c["id"]):
            st, resp = L.call_jev("typesafe" if L.find_key("typesafe") else "openrouter", body)
            store[cid] = {"questions": sorted(body["questions"]), "response": resp}
            return st, resp
        L.check_record("typesafe", c["record"], call=call)
    json.dump(store, open(ANSWERS, "w"), indent=1, sort_keys=True)
    print("recorded %d cases into %s" % (len(store), ANSWERS))


# ---------------------------------------------------------------------------- 1

def test_render():
    for name in ("INTAKE_HANDLER", "PREPARE_HANDLER", "VERDICT_HANDLER", "NOJEV_HANDLER", "AUD_COMPANY_HANDLER"):
        src = L.render(getattr(L, name), "typesafe", FAKE_HEADERS if name == "INTAKE_HANDLER" else None)
        try:
            compile(src, name, "exec")
            ok = True
        except SyntaxError as e:
            ok, src = False, str(e)
        check("compiles " + name, ok, src[:200])
        check("no unfilled slot in " + name, "__" not in src.replace("__name__", "").replace("__init__", ""), "")
        has_key = MARK in src
        check("key only in the first step (%s)" % name, has_key == (name == "INTAKE_HANDLER"))
        for mod in ("datetime", "urllib", "hashlib", "base64", "calendar", "uuid"):
            check("%s does not import %s" % (name, mod), ("import " + mod) not in src)
    src = L.render(L.AUD_INTAKE_HANDLER, "typesafe", FAKE_HEADERS, URL_FIELD="LinkedIn URL", PROFILE_FIELD="",
                   NAME_FIELD="Name")
    compile(src, "aud", "exec")
    check("audience intake carries the key", MARK in src)
    check("audience intake has the TODO to move the key", "TODO(move to a Clay connection)" in src)


# ---------------------------------------------------------------------------- 2, 3, 4

def test_fixtures():
    make = replay(ANSWERS)
    with Blocked():
        core = L.load_core("typesafe")
        check("dates work without datetime", core["_days_since"]("2020-01-01") is not None)
        for c in cases():
            try:
                v = L.check_record("typesafe", c["record"], call=make(c["id"]))
            except AssertionError as e:
                check("replay " + c["id"], False, str(e))
                continue
            for k, want in c["expect"].items():
                check("%s: %s" % (c["id"], k), v.get(k) == want, "got %r want %r" % (v.get(k), want))
            check("%s: all keys" % c["id"], set(L.OUTPUT_KEYS) <= set(v), sorted(set(L.OUTPUT_KEYS) - set(v)))
            check("%s: active value" % c["id"], v["active_at_company"] in L.ACTIVE_VALUES, v["active_at_company"])
            check("%s: relationship value" % c["id"], v["relationship"] in L.RELATIONSHIPS, v["relationship"])
            check("%s: status value" % c["id"], v["check_status"] in L.CHECK_STATUSES, v["check_status"])
            check("%s: never blank evidence" % c["id"], bool(v["evidence"]) and bool(v["needs_review"]))
            check("%s: no key in output" % c["id"], MARK not in json.dumps(v) and "jev_headers" not in v)


# ---------------------------------------------------------------------------- 5

def test_failures():
    c = cases()[0]["record"]
    for code, body in ((401, {"error": "bad key"}), (429, {}), (200, {"answers": {}}), (200, "not json"), (0, None)):
        v = L.check_record("typesafe", c, call=lambda b, code=code, body=body: (code, body))
        check("Jev %s is failed" % code, v["check_status"] == "failed" and v["active_at_company"] == "not_checked",
              "%s %s" % (v["check_status"], v["active_at_company"]))
        check("Jev %s says why" % code, bool(v["error"]))


# ---------------------------------------------------------------------------- 6

def test_matching_and_dates():
    core = L.load_core("typesafe")
    t = core["target_of"]({"company_name": "Northwind Supply Inc.", "company_domain": "https://www.northwind.example/about"})

    def role(**kw):
        base = {"company": "", "domain": "", "linkedin": ""}
        base.update(kw)
        return base
    ident = core["identity"]
    check("subdomain matches", ident(role(company="x", domain="shop.northwind.example"), t)[0] == "confirmed")
    check("legal suffix ignored", ident(role(company="Northwind Supply, LLC"), t)[0] == "name_match")
    check("name overlap asks Jev", ident(role(company="Northwind"), t)[0] == "name_overlap")
    check("other company is none", ident(role(company="Contoso"), t)[0] == "none")
    check("same name, other website: Jev decides",
          ident(role(company="Northwind Supply", domain="northwind-supply.example"), t)[0] == "id_conflict")
    t2 = core["target_of"]({"company_linkedin_url": "https://www.linkedin.com/company/northwind-supply-example/"})
    check("LinkedIn page matches", ident(role(company="NW", linkedin="northwind-supply-example"), t2)[0] == "confirmed")
    t3 = core["target_of"]({"company_domain": "fabrikam-example.co.uk"})
    check("co.uk root", core["_root"]("mail.fabrikam-example.co.uk") == "fabrikam-example.co.uk")
    check("domain label is a name", ident(role(company="Fabrikam Example Ltd"), t3)[0] == "name_match")
    d = core["_date"]
    for raw, want in (("2021-03-01", "2021-03-01"), ("Mar 2021", "2021-03"), ("March 2021", "2021-03"),
                      ("2021", "2021"), ({"year": 2021, "month": 3}, "2021-03"), ("Present", ""), (None, "")):
        check("date %r" % (raw,), d(raw) == want, "got %r" % d(raw))
    r = core["_role"]({"company": "X", "title": "Y", "start_date": "2020-01", "end_date": "2021-01", "is_current": None})
    check("ended role is not open", r["open"] is False)
    r = core["_role"]({"company": "X", "title": "Y", "start_date": "2020-01", "end_date": None})
    check("no end date is open", r["open"] is True)
    ix = core["intake"]({"company_name": "X", "linkedin_url": "https://linkedin.com/company/x"})
    check("company URL is not a person URL", not ix["need_enrichment"] and "not a LinkedIn profile" in ix["blocked"])
    ix = core["intake"]({"company_name": "X", "linkedin_url": "https://www.linkedin.com/in/x", "skip_enrichment": "true"})
    check("skip_enrichment is honoured", not ix["need_enrichment"])
    old = {"last_refresh": "2020-01-01", "experience": [{"company": "X", "title": "Y", "is_current": True}]}
    ix = core["intake"]({"company_name": "X", "profile": old, "linkedin_url": "https://www.linkedin.com/in/x",
                         "max_profile_age_days": "365"})
    check("old supplied profile is re-bought when asked", ix["need_enrichment"] and ix["stale_supplied"])
    ix = core["intake"]({"company_name": "X", "profile": old, "linkedin_url": "https://www.linkedin.com/in/x"})
    check("old supplied profile is used when not asked", not ix["need_enrichment"])


# ---------------------------------------------------------------------------- audience handlers

def test_audience_handlers():
    ns = {}
    exec(compile(L.render(L.AUD_INTAKE_HANDLER, "typesafe", FAKE_HEADERS, URL_FIELD="LinkedIn URL",
                          PROFILE_FIELD="", NAME_FIELD="Full name"), "a", "exec"), ns)

    class Ctx:
        def __init__(self, d):
            self.d = d

        def get_input(self, k):
            return self.d.get(k)
    a = ns["handler"](Ctx({"fields": {"id": 1000001.0, "Full name": "Dana Ruiz", "LinkedIn URL": "https://www.linkedin.com/in/x"},
                           "accounts": [{"id": 2000002, "name": "Northwind Supply"}]}))
    check("record id is an integer string", a["record_id"] == "1000001", a["record_id"])
    check("first linked company", a["account_id"] == "2000002" and a["has_account"])
    check("name read from the named field", a["full_name"] == "Dana Ruiz")
    ns2 = {}
    exec(compile(L.render(L.AUD_COMPANY_HANDLER, "typesafe"), "c", "exec"), ns2)
    ix = ns2["handler"](Ctx({"a": a, "found": {"records": [{"fields": {"Domain": "northwind.example",
                                                                          "Company name": "Northwind Supply"}}]}}))
    check("company website from the lookup", ix["inp"]["company_domain"] == "northwind.example")
    check("URL-only person is enriched", ix["need_enrichment"])
    ix = ns2["handler"](Ctx({"a": dict(a, account_name="Northwind Supply"), "found": None}))
    check("lookup not run: linked company name still used", ix["inp"]["company_name"] == "Northwind Supply")


# ---------------------------------------------------------------------------- 7 the builder

def test_builder():
    import build_workflow as B
    calls, nodes, seq, owner = [], {}, [0], {}

    def fake_clay(*args, inp=None, allow_fail=False, retries=2):
        calls.append((args, inp))
        a = list(args)
        if a[:2] == ["workflows", "create"]:
            seq[0] += 1
            return {"id": "wf_test%d" % seq[0]}
        if a[:2] == ["workflows", "list"]:
            return {"data": []}
        if a[:3] == ["workflows", "graph", "get"]:
            return {"summary": {"nodes": [{"id": n, "name": v.get("name")} for n, v in nodes.items()
                                          if owner.get(n) == a[3]], "triggers": []}}
        if a[:3] == ["workflows", "triggers", "create"]:
            return {"resourceId": "trg_1"}
        if a[:3] == ["workflows", "triggers", "get"]:
            return {"workflowNodeId": "wfn_trigger", "webhookUrl": "https://example.invalid/hook",
                    "outputSchema": {"properties": {"fields": {}, "accounts": {}}}}
        if a[:3] == ["workflows", "actions", "list"]:
            return {"data": [{"actionKey": k, "packageId": "pkg_" + k} for k in
                             (B.HTTP_KEY, B.LOOKUP_KEY, B.UPDATE_KEY, L.ENRICH_ACTION)]}
        if a[:3] == ["workflows", "nodes", "create"]:
            seq[0] += 1
            nid = "wfn_%d" % seq[0]
            nodes[nid] = dict(inp)
            owner[nid] = a[3]
            return {"nodeId": nid}
        if a[:3] == ["workflows", "nodes", "update"]:
            nodes[a[4]].update(inp)
            return {}
        if a[:3] == ["workflows", "nodes", "get"]:
            n = nodes[a[4]]
            tools = [dict(t, toolId="tool_" + a[4]) for t in (n.get("tools") or [])]
            return {"node": dict(n, tools=tools)}
        if a[:3] == ["audiences", "fields", "list"]:
            return {"data": [{"id": "linkedin_url", "name": "LinkedIn URL", "dataType": "url"}]}
        if a[:3] == ["audiences", "fields", "create"]:
            return {"id": "audf_" + a[a.index("--name") + 1].replace(" ", "_"), "name": a[a.index("--name") + 1]}
        return {}
    real = L.clay
    L.clay = fake_clay
    L.paged = lambda *a, **k: []
    tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), "active-test-build-state.json")
    if os.path.exists(tmp):
        os.remove(tmp)
    try:
        g = B.build_table(tmp, "typesafe", FAKE_HEADERS)
        check("builder does not publish on its own", not any(c[0][:2] == ("workflows", "publish") for c in calls))
        ga = B.build_audience(tmp, "typesafe", FAKE_HEADERS, "audseg_test", None, None, None, False)
        check("no connection problems", not g.problems and not ga.problems)
    finally:
        L.clay = real
    check("no step adopted across workflows", len(nodes) == 9 + 19, len(nodes))
    by_name = dict((v.get("name"), v) for v in nodes.values())
    ask = by_name.get("4 Ask Jev") or {}
    tool = (ask.get("tools") or [{}])[0]
    check("Jev step has NO connection", tool.get("appAccountId") == "", tool.get("appAccountId"))
    imc = tool.get("inputMappingConfig") or {}
    check("headers by reference", (imc.get("headers") or {}).get("type") == "reference")
    check("Jev step keeps its toolId on update", bool(tool.get("toolId")))
    for name, n in by_name.items():
        code = n.get("code") or ""
        check("key only in 1 Intake (%s)" % name, (MARK in code) == (name == "1 Intake"))
        edges = n.get("incomingEdges") or []
        if len(edges) > 1:
            check("no plain edge into %s" % name, all(e.get("ruleId") for e in edges), edges)
        for t in n.get("tools") or []:
            refs = json.dumps(t.get("inputMappingConfig") or {})
            for pin in (n.get("inputSchema") or {}).get("properties") or {}:
                if (n["inputSchema"]["properties"][pin] or {}).get("sourceNodeId"):
                    check("pin %s used by %s" % (pin, name), "{{%s}}" % pin in refs)
    trig = [c[1] for c in calls if c[0][:3] == ("workflows", "triggers", "create")][0]
    check("webhook schema has every input", set(L.INPUT_KEYS) <= set(trig["inputSchema"]["properties"]))
    writers = [v for v in nodes.values() if (v.get("tools") or [{}])[0].get("actionKey") == B.UPDATE_KEY]
    check("three Audiences writers", len(writers) == 3, len(writers))
    status_only = [w for w in writers if len(w["tools"][0]["inputMappingConfig"]["recordFields|selectedRecordFields"]["value"]) == 2]
    check("a not-checked person writes status and note only", len(status_only) == 1)
    names = [n for n, _, _ in B.AUDIENCE_FIELDS]
    check("last-attempt fields are named as such", "Active last attempt" in names and "Active last attempt note" in names)
    # the connection report must never claim a live workflow was held back
    check("exit 6 text says neither was published", "NEITHER" in B.connection_report([("w", "s", "c")]))
    os.remove(tmp)


def test_tie_and_rival():
    """Two certain current roles at the company: the evidence names the newer one. A side role
    elsewhere is never named as a rival main job."""
    rec = {"company_domain": "northwind.example", "profile": {"experience": [
        {"company": "Northwind Supply", "title": "SVP Stores", "start_date": "2015-01-01", "is_current": True,
         "company_domain": "northwind.example"},
        {"company": "Northwind Supply", "title": "CEO, Stores", "start_date": "2022-07-01", "is_current": True,
         "company_domain": "northwind.example"},
        {"company": "Contoso Robotics", "title": "Board Member", "start_date": "2020-01-01", "is_current": True,
         "company_domain": "contoso.example"}]}}
    core = L.load_core("typesafe")
    pr = core["prepare"](core["intake"](rec))
    emp = {"type": "choice", "choice": "employee", "confidence": 1.0,
           "probabilities": {"employee": 1.0}}
    emp_99 = {"type": "choice", "choice": "employee", "confidence": 0.98,
              "probabilities": {"employee": 0.99, "contractor": 0.01}}
    board = {"type": "choice", "choice": "advisor_or_board", "confidence": 1.0,
             "probabilities": {"advisor_or_board": 1.0}}
    answers = {}
    for q in json.loads(pr["jev_body"])["questions"]:
        answers[q] = board if q.startswith("other_") else (emp if q.startswith("kind_") else {"type": "noul", "noul": 0.9})
    # the newer role scored a hair lower, as Jev did live (0.99 against 1.00): still a tie
    newer = next(i for i, r in enumerate(pr["roles"]) if r["title"] == "CEO, Stores")
    answers["kind_%d" % newer] = emp_99
    v = core["verdict"](pr, 200, {"model": "jev-1.13.0", "answers": answers, "usage": {"input_tokens": 1}})
    check("tie goes to the newer role", v["role_title"] == "CEO, Stores", v["role_title"])
    rows = json.loads(v["roles_json"])
    check("a board seat is never a rival job", all(r["rival_job"] == "" for r in rows), [r["rival_job"] for r in rows])
    check("still primary", v["relationship"] == "primary_job", v["relationship"])


def test_backfill_dry_run():
    """backfill --plan counts what is left and must never start a run."""
    import build_workflow as B
    calls = []
    real_clay, real_paged = L.clay, L.paged
    L.clay = lambda *a, **k: calls.append(a) or {"data": []}
    L.paged = lambda *a, **k: [101, 102, 103]
    tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), "active-test-backfill-state.json")
    L.save(tmp, {"workflows": {"audience": {"id": "wf_x", "audience": {"fields": {"check_status": "f1"}}}}})
    try:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            B.backfill(tmp, "seg", 0, dry=True)
    finally:
        L.clay, L.paged = real_clay, real_paged
        os.remove(tmp)
    check("backfill --plan starts no run", not any(c[:3] == ("workflows", "runs", "test") for c in calls), calls)


def main():
    L.say = lambda *_a, **_k: None          # the builder's progress lines are noise here
    if "--record" in sys.argv:
        record()
        return
    for t in (test_render, test_fixtures, test_failures, test_matching_and_dates, test_audience_handlers, test_builder,
              test_backfill_dry_run, test_tie_and_rival):
        try:
            t()
        except Exception as e:  # a crash is a failure, named
            failed.append("%s crashed: %r" % (t.__name__, e))
    print("%d checks passed, %d failed" % (passed[0], len(failed)))
    for f in failed:
        print("  FAIL " + f)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Offline checks: no Clay, no network, no key. Runs every generated Clay code step on fixtures, the
scoring arithmetic, the rubric checks, the .env handling, and the builder against a fake Clay.

    python3 -B test_offline.py        # exit 0 when every check passes
"""
import ast
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jev_lib as L  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print("ok   " + name)
    else:
        print("FAIL " + name + ("  " + str(detail) if detail else ""))
        FAILS.append(name)


def raises(fn):
    try:
        fn()
    except SystemExit:
        return True
    return False


EXAMPLE = json.load(open(os.path.join(HERE, "rubric.example.json")))
R = L.validate_rubric(EXAMPLE)
check("example rubric validates for this skill's entity (%s)" % L.ENTITY, R["entity"] == L.ENTITY)


# ------------------------------------------------------------------ generated code steps

for label, h in (("intake", L.INTAKE_HANDLER), ("score", L.SCORE_HANDLER), ("no-jev", L.NOJEV_HANDLER)):
    for prov in L.PROVIDERS:
        src = L.render(h, R, prov)
        tree = ast.parse(src)
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module)
        check("%s step (%s) imports only json and time" % (label, prov), mods <= {"json", "time"}, mods)
        check("%s step (%s) defines handler" % (label, prov),
              any(isinstance(n, ast.FunctionDef) and n.name == "handler" for n in tree.body))
        check("%s step (%s) holds no key-shaped text" % (label, prov), "Bearer" not in src and "Authorization" not in src)

core = L.load_core(R, "openrouter")
num = core["_num"]
check("number: '1,200' -> 1200", num("1,200") == 1200)
check("number: '51-200' -> midpoint", num("51-200") == 125.5)
check("number: '1,001-5,000' -> midpoint", num("1,001-5,000") == 3000.5)
check("number: '10k' -> 10000", num("10k") == 10000)
check("number: '2.5M' -> 2500000", num("2.5M") == 2500000)
check("number: 'unknown' -> None", num("unknown") is None)
check("number: '$3.4bn' -> 3.4e9", num("$3.4bn") == 3.4e9)
check("number: '5 million' -> 5e6", num("5 million") == 5e6)
check("number: '1.2B' -> 1.2e9", num("1.2B") == 1.2e9)
check("days since: garbage -> None", core["_days_since"]("soon") is None)


# Clay's runtime: only json and time. time.strptime imports _strptime -> datetime/calendar behind
# the scenes, which the runtime lacks, so run the rendered steps with every other import refused
# AND with those helpers unavailable.
import builtins  # noqa: E402
import time as _t  # noqa: E402

_real_import = builtins.__import__


def _clay_import(name, *a, **k):
    if name.split(".")[0] not in ("json", "time"):
        raise ImportError("not in Clay's runtime: " + name)
    return _real_import(name, *a, **k)


def in_clay_runtime(fn):
    saved = (_t.strptime, _t.mktime)
    builtins.__import__ = _clay_import
    _t.strptime = _t.mktime = lambda *a, **k: (_ for _ in ()).throw(ImportError("strptime/mktime unavailable"))
    try:
        return fn()
    finally:
        builtins.__import__ = _real_import
        _t.strptime, _t.mktime = saved


for label, h in (("intake", L.INTAKE_HANDLER), ("score", L.SCORE_HANDLER)):
    src = L.render(h, R, "openrouter")
    check("%s step uses no strptime/mktime" % label, "strptime(" not in src and "mktime(" not in src)
ago400 = _t.strftime("%Y-%m-%d", _t.gmtime(_t.time() - 400 * 86400))
rt_days = in_clay_runtime(lambda: L.load_core(R, "openrouter")["_days_since"](ago400))
check("days since works under Clay's imports (400 days)", rt_days in (399, 400, 401), rt_days)
check("days since: 1970-01-01 is today's day count", core["_days_since"]("1970-01-01") == int(_t.time() // 86400))
check("days since: YYYY-MM and YYYY read", core["_days_since"]("2020-02") is not None and core["_days_since"]("2020") is not None)
check("days since: impossible date -> None", core["_days_since"]("2020-13-45") is None)


class Ctx:
    def __init__(self, d):
        self.d = d

    def get_input(self, k):
        if k not in self.d:
            raise KeyError(k)
        return self.d[k]


def run_node(handler, rubric, inputs):
    ns = {}
    exec(compile(L.render(handler, rubric, "openrouter"), "<node>", "exec"), ns)
    return json.loads(json.dumps(ns["handler"](Ctx(inputs))))   # JSON round trip, as Clay passes it


# a record every rubric input is filled for
inputs = {}
for k, spec in R["inputs"].items():
    inputs[k] = "250" if spec["type"] == "number" else ("2026-01-01" if spec["type"] == "date" else "Example value for " + k)


def fake_answers(rubric, probs_first=0.9):
    ans = {}
    for q in rubric["questions"]:
        if q["kind"] == "noul":
            ans[q["id"]] = {"type": "noul", "noul": probs_first}
        elif q["kind"] == "choice":
            keys = list(q["options"])
            p = dict((k, 0.0) for k in keys)
            p[keys[0]] = probs_first
            p[keys[1]] = round(1 - probs_first, 4)
            ans[q["id"]] = {"type": "choice", "choice": keys[0], "confidence": probs_first, "probabilities": p}
        else:
            ans[q["id"]] = {"type": "score", "score": len(q["levels"]) - 1, "confidence": 0.9}
    return {"model": "typesafe/jev-1.13-20260917", "answers": ans, "usage": {"input_tokens": 800, "cost": 3.4e-05}}


ix = run_node(L.INTAKE_HANDLER, R, dict(("in_" + k, v) for k, v in inputs.items()))
check("intake: asks Jev when data is present", ix["ask"] is True)
body = json.loads(ix["jev_body"])
check("intake: one request carries every question", set(body["questions"]) == {q["id"] for q in R["questions"]})
check("intake: question types are Jev's (noul/choice/score)",
      all(v["type"] in ("noul", "choice", "score") for v in body["questions"].values()))
check("intake: every choice offers not_enough_information",
      all("not_enough_information" in v["criteria"] for v in body["questions"].values() if v["type"] == "choice"))
check("intake: state holds only fields a question reads",
      set(body["state"]) <= {k for q in R["questions"] for k in q["reads"]})
check("intake: pinned model sent", body["model"] == L.PROVIDERS["openrouter"]["model"])
check("intake: headers are an object with no key", ix["jev_headers"] == {"Content-Type": "application/json"})

out = run_node(L.SCORE_HANDLER, R, {"intake": ix, "status_code": 200, "body": fake_answers(R)})
check("score: every output key present", all(k in out for k in L.OUTPUT_KEYS), [k for k in L.OUTPUT_KEYS if k not in out])
check("score: marked terminal", out["isTerminal"] is True)
check("score: 0-100 integer", isinstance(out["lead_score"], int) and 0 <= out["lead_score"] <= 100)
check("score: status is one of the fixed set", out["score_status"] in L.STATUSES)
check("score: reasons name points", "(+" in out["score_reasons"])
check("score: cost read from usage.cost", out["jev_cost_usd"] == 3.4e-05)

# parity: the local path gives the same verdict as the Clay steps
local = L.score_record(R, "openrouter", inputs, lambda b: (200, fake_answers(R)))
check("parity: local preview == Clay steps", (local["lead_score"], local["lead_tier"], local["criteria_json"]) ==
      (out["lead_score"], out["lead_tier"], out["criteria_json"]))

# expected points: a less sure answer moves the score less
sure = L.score_record(R, "openrouter", inputs, lambda b: (200, fake_answers(R, 0.95)))
unsure = L.score_record(R, "openrouter", inputs, lambda b: (200, fake_answers(R, 0.55)))
check("expected points: unsure answers score lower than sure ones", unsure["lead_score"] < sure["lead_score"])
check("needs_review lists low-confidence answers", unsure["needs_review"] != "none" and sure["needs_review"] == "none")

# failures
for code, word in ((401, "401"), (429, "rate limit"), (529, "overloaded"), (500, "HTTP 500")):
    f = L.score_record(R, "openrouter", inputs, lambda b, c=code: (c, {"error": "x"}))
    check("failure %s: status failed, reason says so" % code, f["score_status"] == "failed" and word in f["error"], f["error"])
    check("failure %s: keys still all present" % code, all(k in f for k in L.OUTPUT_KEYS))
f = L.score_record(R, "openrouter", inputs, lambda b: (200, {"answers": {}}))
check("200 with no answers is a failure, not a zero", f["score_status"] == "failed")


def never(_b):
    raise AssertionError("Jev must not be called")


# nothing to ask / required missing / rule disqualifies: no Jev call
req = [k for k, s in R["inputs"].items() if s["required"]]
if req:
    nr = dict(inputs)
    nr[req[0]] = ""
    x = L.score_record(R, "openrouter", nr, never)
    check("missing required input: not_scored, no Jev call", x["score_status"] == "not_scored" and x["jev_model"] == "not called")
dq_rules = [r for r in R["rules"] if r["kind"] == "match" and r["disqualify"]]
if dq_rules:
    d = dict(inputs)
    d[dq_rules[0]["input"]] = "".join(["https", "://", "www", ".", dq_rules[0]["values"][0], "/"])   # URL form, scheme and www stripped
    x = L.score_record(R, "openrouter", d, never)
    check("rule disqualifier: disqualified before any Jev call", x["score_status"] == "disqualified" and x["jev_model"] == "not called")
thin = dict((k, "") for k in inputs)
for k in req:
    thin[k] = "Only this"


def shrug(body):
    """Jev on a record with almost nothing in it: every choice lands on not_enough_information."""
    ans = {}
    for qid, q in body["questions"].items():
        if q["type"] == "choice":
            p = dict((k, 0.0) for k in q["criteria"])
            p["not_enough_information"] = 0.9
            ans[qid] = {"type": "choice", "choice": "not_enough_information", "confidence": 0.85, "probabilities": p}
        elif q["type"] == "noul":
            ans[qid] = {"type": "noul", "noul": 0.1}
        else:
            ans[qid] = {"type": "score", "score": 0.0, "confidence": 0.9}
    return 200, {"model": "typesafe/jev-1.13", "answers": ans, "usage": {"input_tokens": 300}}


x = L.score_record(R, "openrouter", thin, shrug)
check("thin record: insufficient_data, never a low tier", x["lead_tier"] == "insufficient_data", x["lead_tier"])
check("thin record: says what had no data", "No data for" in x["score_reasons"])

# abstaining answers do not count as coverage
abst = fake_answers(R)
for q in R["questions"]:
    if q["kind"] == "choice":
        p = dict((k, 0.0) for k in q["options"])
        p["not_enough_information"] = 0.9
        abst["answers"][q["id"]] = {"type": "choice", "choice": "not_enough_information", "confidence": 0.9, "probabilities": p}
a1 = L.score_record(R, "openrouter", inputs, lambda b: (200, fake_answers(R)))
a2 = L.score_record(R, "openrouter", inputs, lambda b: (200, abst))
if any(q["kind"] == "choice" for q in R["questions"]):
    check("abstained choice lowers coverage", a2["coverage_pct"] < a1["coverage_pct"])

for q in R["questions"]:
    if q["kind"] == "choice":
        ab = fake_answers(R)
        p = dict((k, 0.0) for k in q["options"])
        p["not_enough_information"] = 0.6
        p[list(q["options"])[0]] = 0.4
        ab["answers"][q["id"]] = {"type": "choice", "choice": "not_enough_information", "confidence": 0.5, "probabilities": p}
        x = L.score_record(R, "openrouter", inputs, lambda b: (200, ab))
        pts = [c["points"] for c in json.loads(x["criteria_json"]) if c["id"] == q["id"]][0]
        check("abstained choice earns no points", pts == 0, pts)
        break
x = L.score_record(R, "openrouter", inputs, lambda b: ("200.0", fake_answers(R)))
check("status code as '200.0' is still a 200", x["score_status"] != "failed", x["error"])
x = L.score_record(R, "openrouter", inputs, lambda b: (500, {"raw": "x" * 5000}))
check("reasons and review stay short for Audiences text fields", len(x["score_reasons"]) <= 500 and len(x["needs_review"]) <= 500)
x = run_node(L.INTAKE_HANDLER, R, dict(("in_" + k, v) for k, v in inputs.items()))
full = in_clay_runtime(lambda: run_node(L.SCORE_HANDLER, R, {"intake": x, "status_code": 200, "body": fake_answers(R)}))
check("whole scoring path runs under Clay's imports", full["score_status"] in L.STATUSES and not full["error"], full.get("error"))

# a noul or choice disqualifier fires on probability
for q in R["questions"]:
    if q["kind"] == "choice" and any(o["disqualify"] for o in q["options"].values()):
        opt = next(k for k, o in q["options"].items() if o["disqualify"])
        ans = fake_answers(R)
        p = dict((k, 0.0) for k in q["options"])
        p[opt] = 0.85
        p["not_enough_information"] = 0.15
        ans["answers"][q["id"]] = {"type": "choice", "choice": opt, "confidence": 0.8, "probabilities": p}
        x = L.score_record(R, "openrouter", inputs, lambda b: (200, ans))
        check("choice disqualifier at 85%% (%s)" % opt, x["score_status"] == "disqualified")
        break

# reasons: what counted for the record, and what pulled it down
nq = [q for q in R["questions"] if q["kind"] == "noul" and q["points"]["yes"] > q["points"]["no"]]
if nq:
    q = nq[0]
    ans = fake_answers(R)
    ans["answers"][q["id"]] = {"type": "noul", "noul": 0.08}
    x = L.score_record(R, "openrouter", inputs, lambda b: (200, ans))
    want = "%s: %s (%d of %d)" % (q["label"], q["says_no"] or "no", round(0.08 * q["points"]["yes"]), round(q["points"]["yes"]))
    check("a 'no' that earned points through Jev's doubt reads as a shortfall, not a win", want in x["score_reasons"],
          x["score_reasons"])
    check("... and is never shown as (+N)", "%s: %s (+" % (q["label"], q["says_no"] or "no") not in x["score_reasons"])
cq = [q for q in R["questions"] if q["kind"] == "choice"]
if cq:
    q = cq[0]
    zero = [k for k, o in q["options"].items() if o["points"] == 0 and k != "not_enough_information" and not o["disqualify"]]
    if zero:
        ans = fake_answers(R)
        p = dict((k, 0.0) for k in q["options"])
        p[zero[0]] = 0.95
        p["not_enough_information"] = 0.05
        ans["answers"][q["id"]] = {"type": "choice", "choice": zero[0], "confidence": 0.9, "probabilities": p}
        x = L.score_record(R, "openrouter", inputs, lambda b: (200, ans))
        want = "%s: %s (0 of %d)" % (q["label"], q["options"][zero[0]]["says"], round(L.item_max(q)))
        check("a zero-point answer that dragged the score down is named", want in x["score_reasons"], x["score_reasons"])

# ------------------------------------------------------------------ rubric checks

bad = [("wrong entity", dict(EXAMPLE, entity="contact" if L.ENTITY == "account" else "account")),
       ("unknown input in reads", dict(EXAMPLE, questions=[dict(EXAMPLE["questions"][0], reads=["nope"])])),
       ("tiers not reaching 0", dict(EXAMPLE, tiers=[{"tier": "A", "min": 50}])),
       ("tier named like a status", dict(EXAMPLE, tiers=[{"tier": "failed", "min": 0}])),
       ("no name", dict(EXAMPLE, name="")),
       ("score with 11 levels", dict(EXAMPLE, rules=[], questions=[{"id": "s", "kind": "score", "reads": [list(EXAMPLE["inputs"])[0]],
                                                                    "instructions": "x", "levels": list("abcdefghijk"), "points": 5}])),
       ("bands out of order", dict(EXAMPLE, questions=[], rules=[{"id": "b", "kind": "bands", "input": list(EXAMPLE["inputs"])[0],
                                                                "bands": [{"below": 50, "points": 1}, {"below": 10, "points": 2}]}])),
       ("duplicate ids", dict(EXAMPLE, rules=EXAMPLE["rules"][:1] * 2)),
       ("min_coverage as a percent", dict(EXAMPLE, min_coverage=50)),
       ("confidence_floor as a percent", dict(EXAMPLE, confidence_floor=60)),
       ("infinite points", dict(EXAMPLE, rules=[{"id": "b", "kind": "bands", "input": list(EXAMPLE["inputs"])[0],
                                                  "bands": [{"points": "inf"}]}])),
       ("choice disqualify_at 0", dict(EXAMPLE, questions=[{"id": "c", "kind": "choice", "reads": [list(EXAMPLE["inputs"])[0]],
                                                             "instructions": "x", "options": {"a": 1, "b": 2}, "disqualify_at": 0}]))]
for name, doc in bad:
    buf = io.StringIO()
    with redirect_stdout(buf):
        refused = raises(lambda d=doc: L.validate_rubric(json.loads(json.dumps(d))))
    check("rubric check rejects: " + name, refused)
lk = json.loads(json.dumps(EXAMPLE))
first = list(lk["inputs"])[0]
lk["rules"] = [{"id": "lk", "label": "Tier", "kind": "lookup", "input": first,
                "table": {"A": {"points": 25, "says": "tier A account"}, "b": 15}, "miss_points": 0}]
LK = L.validate_rubric(lk)
lk_core = L.load_core(LK, "openrouter")
check("lookup rule: case-insensitive hit", lk_core["apply_rule"](dict(LK["rules"][0], _max=25), {first: "a"})["points"] == 25)
check("lookup rule: miss gets miss_points", lk_core["apply_rule"](dict(LK["rules"][0], _max=25), {first: "Z"})["points"] == 0)
check("lookup rule: max is the best value", L.item_max(LK["rules"][0]) == 25)
card = L.rubric_card(R, "openrouter")
check("rubric card prices the run and never says 'a account'", "per 1,000" in card and "a account" not in card)

# ------------------------------------------------------------------ keys and .env

with tempfile.TemporaryDirectory() as t:
    p = os.path.join(t, "cfg", ".env")
    L.write_env(p, "OPENROUTER_API_KEY", "sk-test-value")
    L.write_env(p, "OPENROUTER_API_KEY", "sk-test-value-2")
    check(".env: key replaced, not duplicated", open(p).read().count("OPENROUTER_API_KEY") == 1)
    check(".env: file is 0600", (os.stat(p).st_mode & 0o777) == 0o600)
    check(".env: parsed back", L.parse_env(p)["OPENROUTER_API_KEY"] == "sk-test-value-2")
    with open(os.path.join(t, "q.env"), "w") as f:
        f.write('# c\nexport TYPESAFE_API_KEY="abc"\nX=1\n')
    with open(os.path.join(t, "c.env"), "w") as f:
        f.write("OPENROUTER_API_KEY=sk-abc # prod key\n")
    check(".env: inline comment dropped", L.parse_env(os.path.join(t, "c.env"))["OPENROUTER_API_KEY"] == "sk-abc")
    check(".env: export and quotes stripped", L.parse_env(os.path.join(t, "q.env"))["TYPESAFE_API_KEY"] == "abc")
    old = (os.environ.get("XDG_CONFIG_HOME"), os.getcwd(), os.environ.pop("OPENROUTER_API_KEY", None))
    os.environ["XDG_CONFIG_HOME"] = os.path.join(t, "xdg")
    os.chdir(t)
    L.write_env(L.default_env_file(), "OPENROUTER_API_KEY", "sk-shared")
    w = L.find_key("openrouter")
    check("find_key: shared file found, location only", w == (L.default_env_file(), "OPENROUTER_API_KEY"))
    with open(os.path.join(t, ".env"), "w") as f:
        f.write("OPENROUTER_API_KEY=sk-project\n")
    check("find_key: ./.env wins over the shared file", L.find_key("openrouter")[0] == os.path.join(os.path.realpath(t), ".env")
          or L.find_key("openrouter")[0] == os.path.join(t, ".env"))
    os.environ["OPENROUTER_API_KEY"] = "sk-env"
    check("find_key: environment wins", L.find_key("openrouter") == ("environment", "OPENROUTER_API_KEY"))
    buf = io.StringIO()
    import jev_key as K
    with redirect_stdout(buf):
        K.cmd_find(None)
    check("jev_key find never prints a value", "sk-" not in buf.getvalue())
    os.environ.pop("OPENROUTER_API_KEY")
    os.chdir(old[1])
    if old[0] is None:
        os.environ.pop("XDG_CONFIG_HOME", None)
    else:
        os.environ["XDG_CONFIG_HOME"] = old[0]
    if old[2] is not None:
        os.environ["OPENROUTER_API_KEY"] = old[2]

with tempfile.TemporaryDirectory() as t:
    import subprocess
    if subprocess.run(["git", "-C", t, "init", "-q"], capture_output=True).returncode == 0:
        check("git risk: a not-yet-existing folder inside a repo is still checked",
              L.git_tracks_risk(os.path.join(t, "new", "sub", ".env")) is True)
        with open(os.path.join(t, ".gitignore"), "w") as f:
            f.write(".env\n")
        check("git risk: an ignored .env is safe", L.git_tracks_risk(os.path.join(t, ".env")) is False)

# ------------------------------------------------------------------ mapping

cols = [{"id": "c1", "name": "Company Name"}, {"id": "c2", "name": "Description"}, {"id": "c3", "name": "Website domain"}]
m = L.propose_map({"company_name": {"label": "Company name"}, "description": {"label": "What it does"},
                   "domain": {"label": "Website domain"}, "industry": {"label": "Industry"}}, cols)
check("mapping: exact and label matches", m == {"company_name": "c1", "description": "c2", "domain": "c3", "industry": None}, m)
m3 = L.propose_map({"started_role_on": {"label": "Started current role"}, "title": {"label": "Job title"},
                    "headline": {"label": "Profile headline or summary"}},
                   [{"id": "x1", "name": "Started role"}, {"id": "x2", "name": "Job title"}, {"id": "x3", "name": "Headline"},
                    {"id": "x4", "name": "Role notes"}])
m4 = L.propose_map({"description": {"label": "What the company does"}}, [{"id": "c", "name": "Company"}])
check("mapping: one shared label word is not a match", m4 == {"description": None}, m4)
check("mapping: close names match (Started role, Headline)", m3 == {"started_role_on": "x1", "title": "x2", "headline": "x3"}, m3)
m2 = L.apply_overrides(dict(m), cols, ["industry=Description"])
check("mapping: --map override by column name", m2["industry"] == "c2")
check("mapping: unknown column stops", raises(lambda: L.apply_overrides(dict(m), cols, ["industry=Nope"])))

# ------------------------------------------------------------------ builder against a fake Clay

import build_scorer as B  # noqa: E402


class FakeClay:
    """Clay's binding rule as seen live (2026-09-28): a tool written without an account id lands
    on the workspace's default account; a tool updated with its toolId keeps what it has."""
    DEFAULT = "some-other-connection"

    def __init__(self):
        self.nodes, self.n, self.published = {}, 0, False

    def _tool(self, t, old=None):
        out = dict(t)
        out.setdefault("toolId", "tool_%d" % self.n)
        if t.get("appAccountId"):
            out["appAccountName"] = self.accounts.get(t["appAccountId"])
        elif old and old.get("appAccountName") is not None:
            out["appAccountName"] = old["appAccountName"]
        else:
            out["appAccountName"] = self.DEFAULT
        return out

    accounts = {"conn-jev": "Jev (OpenRouter)"}

    def __call__(self, *args, inp=None, allow_fail=False, retries=2):
        a = list(args)
        if a[:2] == ["workflows", "list"]:
            return {"data": []}
        if a[:2] == ["workflows", "create"]:
            return {"id": "wf-test"}
        if a[:2] == ["workflows", "actions"]:
            return {"data": [{"actionKey": "http-api-v2", "packageId": "pkg_http"},
                             {"actionKey": "update-audiences-record", "packageId": "pkg_aud"}]}
        if a[:3] == ["workflows", "triggers", "create"]:
            return {"resourceId": "trg_1"}
        if a[:3] == ["workflows", "triggers", "get"]:
            return {"workflowNodeId": "wfn_trigger", "webhookUrl": "https://hooks.example/abc"}
        if a[:3] == ["workflows", "triggers", "update"]:
            return {}
        if a[:3] == ["workflows", "graph", "get"]:
            return {"summary": {"nodes": [{"id": k, "name": v.get("name")} for k, v in self.nodes.items()],
                                "edges": [], "triggers": [{"id": "trg_1"}]}}
        if a[:3] == ["workflows", "nodes", "create"]:
            self.n += 1
            nid = "wfn_%d" % self.n
            node = dict(inp)
            node["tools"] = [self._tool(t) for t in inp.get("tools") or []]
            self.nodes[nid] = node
            return {"nodeId": nid}
        if a[:3] == ["workflows", "nodes", "update"]:
            nid = a[4]
            old = self.nodes[nid]
            new = dict(old)
            new.update(inp)
            if "tools" in inp:
                new["tools"] = [self._tool(t, (old.get("tools") or [None])[i] if i < len(old.get("tools") or []) else None)
                                for i, t in enumerate(inp["tools"])]
            self.nodes[nid] = new
            return {}
        if a[:3] == ["workflows", "nodes", "get"]:
            return {"node": self.nodes[a[4]]}
        if a[:2] == ["workflows", "publish"]:
            self.published = True
            return {}
        raise AssertionError("unexpected clay call %s" % a)


with tempfile.TemporaryDirectory() as t:
    fake = FakeClay()
    real = L.clay
    L.clay = fake
    try:
        st = os.path.join(t, "build-state.json")
        with redirect_stdout(io.StringIO()):
            g = B.build_table(st, R, "openrouter", "Jev (OpenRouter)", None)
        check("build: 5 nodes (intake, gate, no-Jev, ask, score)", len(fake.nodes) == 5, len(fake.nodes))
        check("build: a step on the wrong connection blocks publishing", g.problems and not fake.published, g.problems)
        ask = next(n for n in fake.nodes.values() if n.get("name") == "3 Ask Jev")
        imc = ask["tools"][0]["inputMappingConfig"]
        check("build: headers go by reference, never static", imc["headers"]["type"] == "reference")
        check("build: 4xx comes back as data", imc["returnResponseMetadata"]["value"] is True)
        check("build: no retry options on the Jev step (they break it at run time)",
              not any("etry" in k for k in imc))
        check("build: no key in any node", "Bearer" not in json.dumps(fake.nodes))
        check("build: every pin written survived", all(
            all(v.get("sourceNodeId") for v in (n.get("inputSchema") or {}).get("properties", {}).values())
            for n in fake.nodes.values()))
        # the installer picks the right connection in Clay's UI, then re-runs
        ask["tools"][0]["appAccountName"] = "Jev (OpenRouter)"
        with redirect_stdout(io.StringIO()):
            g2 = B.build_table(st, R, "openrouter", "Jev (OpenRouter)", None)
        check("rebuild: keeps the connection chosen in the UI, publishes", not g2.problems and fake.published, g2.problems)
        check("rebuild: no duplicate nodes", len(fake.nodes) == 5, len(fake.nodes))
        B.REATTACH = True
        check("--reattach drops the Jev step's toolId so Clay attaches its default",
              "toolId" not in B.bind_tool({"actionKey": "http-api-v2", "connection": "X"}, {"toolId": "t", "actionKey": "http-api-v2"})
              and "toolId" in B.bind_tool({"actionKey": "update-audiences-record"}, {"toolId": "t", "actionKey": "update-audiences-record"}))
        B.REATTACH = False
        # binding by id works first time
        fake2 = FakeClay()
        L.clay = fake2
        with redirect_stdout(io.StringIO()):
            g3 = B.build_table(os.path.join(t, "s2.json"), R, "openrouter", "Jev (OpenRouter)", "conn-jev")
        check("build with a connection id: right connection, published", not g3.problems and fake2.published)
        check("connection report names step and connection",
              "3 Ask Jev" in B.connection_report([("wf", "3 Ask Jev", "x", "Jev (OpenRouter)")]))
    finally:
        L.clay = real

check("schema paths walk nested properties",
      B.schema_paths({"properties": {"fields": {"properties": {"id": {}, "f_1": {}}}}}) == {"fields", "fields.id", "fields.f_1"})
check("resolve path prefers fields.<id>", B.resolve_path({"fields.f_1", "f_1"}, ["fields.f_1", "f_1"]) == "$.fields.f_1")

print("")
print("%d failed" % len(FAILS) if FAILS else "all checks passed")
sys.exit(1 if FAILS else 0)

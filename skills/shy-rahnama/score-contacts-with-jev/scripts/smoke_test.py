#!/usr/bin/env python3
"""
Send ONE record through the published workflow in Clay and score the same record locally, then
compare. Agreement proves the wiring, the Clay connection's key and the published rubric in one go.

    python3 smoke_test.py --record '{"company_name": "…", "description": "…"}'
    python3 smoke_test.py --from-preview        # the first record of the latest local preview
    python3 smoke_test.py --audience            # one member of the built audience workflow's audience,
                                                # then its "Jev …" fields read back from Audiences

Jev's probabilities can move slightly between two calls on the same input, so the scores are
compared within 3 points; the status and every confident answer must match, and the tier must
match unless the score sits within 3 points of a cut-off. Costs two Jev
requests (a fraction of a cent) and one Clay workflow run.
"""
import argparse
import glob
import json
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev_lib as L  # noqa: E402


def settle(wf, run_id, budget=180, every=4):
    """Poll until a TERMINAL step completes. Settle on `isTerminal`, never on a node's name."""
    waited = 0
    while waited < budget:
        time.sleep(every)
        waited += every
        steps = L.clay("workflows", "runs", "steps", wf, run_id, allow_fail=True)
        steps = steps.get("data") or [] if isinstance(steps, dict) else []
        for s in steps:
            out = s.get("stepOutputs") or {}
            res = out if "lead_score" in out else (out.get("result") if isinstance(out.get("result"), dict) else {})
            if (out.get("isTerminal") or res.get("isTerminal")) and s.get("status") == "completed":
                return "completed", res or out
        bad = [s for s in steps if s.get("status") == "failed"]
        if bad:
            errs = [e for s in bad for e in (s.get("errors") or [])]
            return "failed", {"error": str(errs[0] if errs else bad[0])[:400], "step": node_name(wf, bad[0].get("nodeId"))}
    return "timeout", {}


def node_name(wf, nid):
    g = L.clay("workflows", "graph", "get", wf, allow_fail=True)
    for n in ((g.get("summary") or {}).get("nodes") or []) if isinstance(g, dict) else []:
        if n.get("id") == nid:
            return n.get("name") or nid
    return nid


def audience_smoke(rubric, st):
    """One member through the published audience workflow; then read its Jev fields back from
    Audiences and compare with a local score of the same record."""
    rec = st["workflows"].get(L.slug(rubric["name"]) + "__audience") or {}
    aud = rec.get("audience") or {}
    if not rec.get("id") or not aud.get("segment_id"):
        L.fail("The audience workflow is not built yet: build_scorer.py --audience <id>")
    fields = aud["fields"]
    ids = L.clay("audiences", "records", "search-ids", "--audience-id", aud["segment_id"], "--entity-type",
                 L.AUDIENCE_FLAG, "--limit", "100").get("data") or []
    if not ids:
        L.fail("The audience has no members to test with.")
    got = L.clay("audiences", "records", "get", "--entity-type", L.AUDIENCE_FLAG,
                 "--ids", ",".join(str(i) for i in ids)).get("data") or []
    mapping = aud.get("map") or {}
    # prefer a member whose data gives Jev something to answer, so the test exercises the Jev call
    # through the Clay connection, not just the free path
    core = L.load_core(rubric, rec["provider"])

    def as_record(r):
        f = r.get("fields") or {}
        return dict((k, str(f.get(c))) for k, c in mapping.items() if c and f.get(c) not in (None, ""))
    pick = next((r for r in got if core["intake"](as_record(r))["ask"]), None)
    if pick is None:
        L.say("None of the first %d members has data for any Jev question; testing the no-Jev path only." % len(got))
        pick = got[0]
    f = pick.get("fields") or {}
    record = as_record(pick)
    rid = str(pick.get("recordId"))
    before = f.get(fields["scored_at"])
    local = L.score_record(rubric, rec["provider"], record)
    run = L.clay("workflows", "runs", "test", rec["id"], "--audience-segment", aud["segment_id"],
                 "--record-ids", rid, "--live", allow_fail=True)
    if isinstance(run, dict) and run.get("error"):
        L.fail("Clay would not start the audience run: %s" % run["error"])
    L.say("Member %s sent through the audience workflow; waiting for its Jev fields to change…" % rid)
    back = {}
    for _ in range(45):
        time.sleep(4)
        r = L.clay("audiences", "records", "get", "--entity-type", L.AUDIENCE_FLAG, "--ids", rid, allow_fail=True)
        rows = r.get("data") or [] if isinstance(r, dict) else []
        back = (rows[0].get("fields") or {}) if rows else {}
        if back.get(fields["scored_at"]) and back.get(fields["scored_at"]) != before:
            break
    else:
        L.fail("The record's 'Jev scored at' never changed. Check the audience workflow's latest run in Clay.", code=5)
    if local["jev_model"] == "not called":
        L.say("  (this member needed no Jev call, so the Clay connection's key was not exercised)")
    remote = {"lead_score": back.get(fields["lead_score"]), "lead_tier": back.get(fields["lead_tier"]),
              "score_status": back.get(fields["score_status"]), "rubric": back.get(fields["rubric"])}
    L.say("  local    : %s, %s" % (local["lead_score"], local["lead_tier"]))
    L.say("  Audiences: %s, %s (%s)" % (remote["lead_score"], remote["lead_tier"], remote["rubric"]))
    problems = []
    if remote["rubric"] != local["rubric"]:
        problems.append("the record carries rubric %r, expected %r" % (remote["rubric"], local["rubric"]))
    if remote["score_status"] != local["score_status"]:
        problems.append("status differs")
    try:
        if abs(float(remote["lead_score"]) - float(local["lead_score"])) > 3:
            problems.append("scores differ by more than 3")
    except (TypeError, ValueError):
        problems.append("no score on the record")
    print(json.dumps({"ok": not problems, "record": rid, "local": local["lead_score"],
                      "audiences": remote["lead_score"], "problems": problems}))
    if problems:
        L.fail("Local and Audiences disagree: " + "; ".join(problems), code=5)
    L.say("Match: the audience workflow wrote the score the preview shows onto the record.")


def answers(res, floor=0.6):
    """Each criterion's answer, leaving out the ones Jev was unsure of: a 49%/51% yes/no can
    legitimately flip between two calls on the same input."""
    try:
        return dict((c["id"], c["answer"]) for c in json.loads(res.get("criteria_json") or "[]")
                    if c.get("confidence") is None or c["confidence"] >= floor)
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rubric")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--record", help="the record as JSON, keyed by the rubric's input names")
    src.add_argument("--from-preview", action="store_true")
    src.add_argument("--audience", action="store_true", help="test the audience workflow instead")
    a = ap.parse_args()

    ws = L.workspace()
    rubric = L.load_rubric(a.rubric, ws["id"])
    st = L.load(os.path.join(L.state_dir(ws["id"]), "build-state.json"), {"workflows": {}})
    if a.audience:
        return audience_smoke(rubric, st)
    rec = st["workflows"].get(L.slug(rubric["name"])) or {}
    if not rec.get("id"):
        L.fail("The workflow for %r is not built yet: build_scorer.py" % rubric["name"])
    if rec.get("rubric_version") != rubric["version"]:
        L.fail("The workflow was built from v%s of this rubric and the saved rubric is v%d. Re-run "
               "build_scorer.py first." % (rec.get("rubric_version"), rubric["version"]))
    provider = rec["provider"]

    if a.from_preview:
        files = sorted(glob.glob(os.path.join(L.state_dir(ws["id"]), "previews", L.slug(rubric["name"]) + "-*.jsonl")),
                       key=os.path.getmtime)
        if not files:
            L.fail("No local preview yet: score_local.py")
        with open(files[-1]) as f:
            record = json.loads(f.readline())["input"]
    else:
        record = json.loads(a.record)
    # every value as text: the workflow's inputs are declared as strings
    record = dict((k, str(v)) for k, v in record.items() if v not in (None, "") and k in list(rubric["inputs"]) + ["source_ref"])
    record.setdefault("source_ref", "smoke-test")

    L.say("Scoring one %s locally and through the published workflow in Clay…" % L.NOUN)
    local = L.score_record(rubric, provider, record)
    run = L.clay("workflows", "runs", "test", rec["id"], "--inputs", json.dumps(record), "--live", allow_fail=True)
    if run.get("error"):
        L.fail("Clay would not start a run of the published workflow: %s" % run["error"])
    status, remote = settle(rec["id"], run["runId"])
    L.say("  local : %s, %s, %s" % (local["lead_score"], local["lead_tier"], local["score_reasons"][:120]))
    if status != "completed":
        L.say("  clay  : run %s %s %s" % (run["runId"], status, json.dumps(remote)[:300]))
        L.fail("The Clay run did not finish cleanly; the step and error are above.", code=5)
    L.say("  clay  : %s, %s, %s" % (remote.get("lead_score"), remote.get("lead_tier"), str(remote.get("score_reasons"))[:120]))
    problems = []
    if remote.get("error"):
        problems.append("Clay's run reports: %s" % remote["error"])
    near_cut = any(abs(float(local["lead_score"]) - t["min"]) <= 3 for t in rubric["tiers"] if t["min"] > 0)
    if remote.get("score_status") != local["score_status"] or (
            remote.get("lead_tier") != local["lead_tier"] and not near_cut):
        problems.append("tier/status differ")
    try:
        if abs(int(remote.get("lead_score")) - int(local["lead_score"])) > 3:
            problems.append("scores differ by more than 3")
    except (TypeError, ValueError):
        problems.append("Clay returned no score")
    fl = rubric["confidence_floor"]
    if answers(remote, fl) != answers(local, fl):
        problems.append("criterion answers differ: %s vs %s" % (answers(remote, fl), answers(local, fl)))
    print(json.dumps({"ok": not problems, "local": local["lead_score"], "clay": remote.get("lead_score"),
                      "problems": problems}))
    if problems:
        L.fail("Local and Clay disagree: " + "; ".join(problems), code=5)
    L.say("Match: the workflow in Clay returns what the preview showed.")


if __name__ == "__main__":
    main()

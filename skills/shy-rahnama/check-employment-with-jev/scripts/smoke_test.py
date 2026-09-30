#!/usr/bin/env python3
"""
Prove the PUBLISHED workflow gives the same verdict as the local preview, person by person.

    python3 smoke_test.py --provider typesafe --from-preview        # the first person of the last preview
    python3 smoke_test.py --provider typesafe --fixtures            # every invented case in fixtures.json
    python3 smoke_test.py --provider typesafe --fixtures --only stale_current_role
    python3 smoke_test.py --provider typesafe --record person.json  # one record you supply (JSON object)

Each record goes to the workflow's webhook (the published version) with a unique source_ref, the
run carrying that source_ref is found and its verdict read, and the same record is checked
locally with the exact code the workflow runs. A record sent with only a LinkedIn URL makes Clay
buy the profile (0.5 credits); the local check then reuses the profile Clay bought, so both sides
judge the same work history.

Match means the wiring, the key in the first step and the published code all work. Jev's
probabilities move slightly between calls, so a confidence can differ by a few points; the
verdict and the relationship must not.
"""
import argparse
import json
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import active_lib as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def terminal_outputs(wf, since, want_refs, limit=180):
    """{source_ref: (verdict, run)} for runs created after `since`, polling until every ref is in."""
    found, end = {}, time.time() + limit
    while time.time() < end and len(found) < len(want_refs):
        runs = L.clay("workflows", "runs", "list", wf, "--limit", "50").get("data") or []
        for r in runs:
            if r.get("createdAt", "") < since or r["runId"] in [v[1]["runId"] for v in found.values()]:
                continue
            if r.get("status") not in ("completed", "failed"):
                continue
            got = L.clay("workflows", "runs", "get", wf, r["runId"], "--verbose", allow_fail=True)
            nodes = got.get("nodes") or []
            prep = {}
            for n in nodes:
                out = n.get("outputs") or n.get("output") or {}
                if isinstance(out, dict) and "roles" in out and "ask" in out:
                    prep = out
                if isinstance(out, dict) and out.get("isTerminal") and "active_at_company" in out:
                    found[out.get("source_ref")] = (out, got, prep)
            if r.get("status") == "failed":
                found.setdefault("__failed__" + r["runId"], ({"error": "run failed"}, got, prep))
        if len(found) < len(want_refs):
            time.sleep(4)
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=sorted(L.PROVIDERS), required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--fixtures", action="store_true")
    g.add_argument("--from-preview", action="store_true")
    g.add_argument("--record", help="a JSON file holding one record")
    ap.add_argument("--only", action="append", default=[], help="with --fixtures: just these case ids")
    a = ap.parse_args()

    ws = L.workspace()
    st = L.load(os.path.join(L.state_dir(ws["id"]), "build-state.json"), {"workflows": {}})
    t = st["workflows"].get("table") or {}
    if not t.get("webhook_url"):
        L.fail("The workflow is not built yet: run build_workflow.py first.")

    if a.fixtures:
        cases = [(c["id"], c["record"], c.get("expect") or {})
                 for c in json.load(open(os.path.join(HERE, "fixtures.json")))["cases"]
                 if not a.only or c["id"] in a.only]
    elif a.record:
        cases = [("record", json.load(open(a.record)), {})]
    else:
        prev = L.load(os.path.join(L.state_dir(ws["id"]), "last-preview.json"), {})
        if not prev.get("records"):
            L.fail("No preview has run yet: run check_local.py first, or use --fixtures.")
        cases = [("preview-1", prev["records"][0], {})]

    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    since = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 5))
    refs = {}
    for i, (cid, rec, _) in enumerate(cases):
        body = dict(rec, source_ref="smoke-%s-%d" % (stamp, i))
        status, resp = L.http("POST", t["webhook_url"], None, body)
        if status != 200:
            L.fail("The webhook refused %s: HTTP %s %s" % (cid, status, resp))
        refs[body["source_ref"]] = (cid, body)
    L.say("Sent %d record(s) to the published workflow; waiting for the runs." % len(refs))
    got = terminal_outputs(t["id"], since, refs)

    bad = 0
    rows = []
    for ref, (cid, body) in refs.items():
        hit = got.get(ref)
        exp = next(c[2] for c in cases if c[0] == cid)
        if not hit:
            bad += 1
            rows.append((cid, "no run found", "", ""))
            continue
        clay_v, _run, prep = hit
        enriched = prep.get("source") == "enriched"

        def enrich(_url):
            return {"experience": [dict(company=r["company"], title=r["title"], start_date=r["start"],
                                        end_date=r["end"] or None, is_current=r["is_current"],
                                        company_domain=r["domain"], summary=r["description"],
                                        location_type=r["work_type"],
                                        url=("https://www.linkedin.com/company/" + r["linkedin"]) if r["linkedin"] else "")
                                   for r in prep.get("profile_roles") or []]}
        local = L.check_record(a.provider, body, enrich=enrich if enriched else None)
        same = all(clay_v.get(k) == local.get(k) for k in ("active_at_company", "relationship", "check_status"))
        meets = all(clay_v.get(k) == v for k, v in exp.items())
        if not (same and meets):
            bad += 1
        rows.append((cid, "%s / %s (%s%%)" % (clay_v.get("active_at_company"), clay_v.get("relationship"),
                                             clay_v.get("verdict_confidence")),
                     "match" if same else "DIFFERS: local %s / %s" % (local["active_at_company"], local["relationship"]),
                     "" if not exp else ("as expected" if meets else "EXPECTED %s" % exp)))
    for r in rows:
        L.say("  %-28s Clay: %-34s %s  %s" % r)
    print(json.dumps({"checked": len(rows), "problems": bad}))
    raise SystemExit(0 if not bad else 5)


if __name__ == "__main__":
    main()

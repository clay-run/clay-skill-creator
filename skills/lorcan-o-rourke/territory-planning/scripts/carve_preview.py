"""Optional entity-level proposal only. No CRM, network, or record mutation.

Every account must arrive with reviewed eligibility/protection and an explicit bucket.
This engine never infers a region, segment, family root, or commercial exclusion.
A single frozen population and shared capacity ledger replace per-account peer queries.
"""
import json
import math


def integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(name + " must be a nonnegative integer")
    return value


def carve(snapshot):
    if snapshot.get("grain") != "entity":
        raise ValueError("only entity-level preview is supported; no implicit family rollup")
    if not snapshot.get("snapshot_id") or not snapshot.get("rules_version"):
        raise ValueError("snapshot_id and rules_version required")
    if snapshot.get("method") not in ("snake", "round_robin"):
        raise ValueError("only snake and round_robin are supported")
    accts, reps = snapshot.get("accounts"), snapshot.get("reps")
    if not isinstance(accts, list) or not isinstance(reps, list) or not reps:
        raise ValueError("accounts list and nonempty reps list required")
    if len(accts) > 2000:
        raise ValueError("preview is capped at 2000 entities; do not silently split a shared ledger")
    rep_by_id, remaining, load, groups, out = {}, {}, {}, {}, {}
    for r in reps:
        rid = r.get("rep_id")
        if not isinstance(rid, str) or not rid.strip() or rid in rep_by_id:
            raise ValueError("unique rep_id required")
        cap = integer(r.get("capacity"), "capacity")
        existing = integer(r.get("existing_load_outside_snapshot"), "existing load")
        buckets = r.get("buckets")
        if not isinstance(buckets, list) or not buckets or any(not isinstance(b, str) or not b for b in buckets):
            raise ValueError("explicit nonempty rep buckets required")
        rep_by_id[rid] = r
        load[rid] = existing
        remaining[rid] = max(0, cap - existing)
    seen = set()
    for a in accts:
        aid = a.get("account_id")
        if not isinstance(aid, str) or not aid.strip() or aid in seen:
            raise ValueError("unique account_id required; duplicate input is not dropped")
        seen.add(aid)
        for field in ("eligible", "protected", "excluded"):
            if not isinstance(a.get(field), bool):
                raise ValueError("explicit boolean required: " + field)
        existing = a.get("current_owner_id", "")
        if existing in load:
            load[existing] += 1
            remaining[existing] = max(0, remaining[existing] - 1)
        row = {"account_id": aid, "current_owner_id": existing, "proposed_owner_id": "",
               "status": "unowned", "reason": "", "bucket": a.get("bucket", "")}
        out[aid] = row
        # Protection is a no-move rule regardless of current score or eligibility.
        if a["protected"] or existing:
            if existing and not a["protected"]:
                raise ValueError("existing owner must be explicitly protected before a preview")
            if not existing:
                raise ValueError("protected account requires a current owner")
            row.update(status="protected", reason=a.get("protection_reason") or "existing owner retained")
        elif a["excluded"]:
            row.update(status="excluded", reason=a.get("exclusion_reason") or "excluded by reviewed rules")
        elif a.get("scoring_status") != "scored" or not a["eligible"]:
            row.update(status="not_eligible", reason="not scored or outside reviewed eligibility")
        else:
            score = a.get("account_fit_score")
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 100:
                raise ValueError("eligible account requires finite fit score in 0..100")
            if not isinstance(a.get("bucket"), str) or not a["bucket"]:
                row.update(reason="no reviewed routing bucket")
            else:
                groups.setdefault(a["bucket"], []).append(a)
    # All existing/protected accounts are counted before any new proposal.
    for bucket in sorted(groups):
        items = sorted(groups[bucket], key=lambda a: (-a["account_fit_score"], a["account_id"]))
        cands = sorted([rid for rid, r in rep_by_id.items() if bucket in r["buckets"]])
        pos, direction = 0, 1
        for a in items:
            row = out[a["account_id"]]
            preferred = a.get("requested_rep_id")
            if preferred:
                if preferred not in cands:
                    row["reason"] = "requested rep cannot serve bucket"
                    continue
                if not remaining[preferred]:
                    row["reason"] = "requested rep has no capacity"
                    continue
                picked = preferred
            else:
                picked = None
                for _ in range(len(cands) * 2):
                    rid = cands[pos]
                    if remaining[rid] > 0:
                        picked = rid
                    if snapshot["method"] == "snake" and len(cands) > 1:
                        if direction == 1 and pos == len(cands) - 1:
                            direction = -1
                        elif direction == -1 and pos == 0:
                            direction = 1
                        else:
                            pos += direction
                    elif cands:
                        pos = (pos + 1) % len(cands)
                    if picked:
                        break
            if picked:
                remaining[picked] -= 1
                load[picked] += 1
                row.update(status="proposed", proposed_owner_id=picked,
                           reason=snapshot["method"] + ", reviewed bucket " + bucket)
            else:
                row["reason"] = "no eligible rep with remaining capacity"
    return {"snapshot_id": snapshot["snapshot_id"], "rules_version": snapshot["rules_version"],
            "grain": "entity", "proposal_only": True, "accounts": [out[k] for k in sorted(out)],
            "books": [{"rep_id": rid, "total_load": load[rid], "capacity": rep_by_id[rid]["capacity"],
                       "over_capacity": max(0, load[rid] - rep_by_id[rid]["capacity"]),
                       "proposed": sum(r["proposed_owner_id"] == rid for r in out.values())}
                      for rid in sorted(rep_by_id)]}


def handler(context):
    data = context.get_input("snapshot_json")
    result = carve(json.loads(data) if isinstance(data, str) else data)
    return {"proposal_json": json.dumps(result, allow_nan=False, sort_keys=True)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: carve_preview.py snapshot.json")
    with open(sys.argv[1], encoding="utf-8") as f:
        print(json.dumps(carve(json.load(f)), indent=2, allow_nan=False))

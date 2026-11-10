"""Reference scoring node. Rubric-driven, deterministic, zero credits.

Paste into a Clay code node (Python, `handler(ctx)`), or import locally to re-score saved research
outputs. Inputs: the rubric JSON (from the ```json block in rubric.md) as `rubric_json`, plus
`<factor>_value`, `<factor>_status`, `<factor>_evidence` for every factor the rubric lists.
See references/scoring-rules.md for the contract and the evidence rules.

Local use:
    python3 score_account.py rubric.md saved_outputs.json   # rubric.md or a plain .json rubric
    python3 score_account.py                                # runs the built-in self-test

Stdlib only, and only `json` and `time`: the Clay code-node sandbox does not ship `datetime`, so
`months_since` below is written against `time` for builders to copy into their derive step.
"""
import json
import time

GRADES = [(80, "Best Fit"), (65, "Good Fit"), (50, "Moderate Fit"), (0, "Low Fit")]
STATUSES = ("found", "none", "failed", "capped")
MONTHS = {m: i + 1 for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}


def _num(v, default=None):
    try:
        if v is None or v == "" or isinstance(v, bool):
            return default
        return float(str(v).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return default


def factor_score(spec, value):
    """Score one factor from its spec. Returns None if the value cannot be read."""
    kind = spec.get("kind", "map")
    if kind == "map":
        key = str(value or "none").strip().lower()
        base = spec["map"].get(key, spec["map"].get("none"))
    elif kind == "bands":
        n = _num(value)
        if n is None:
            return None
        # Bands are read top down, first match wins. Sort by min descending so an ascending list
        # typed by hand ("0 to 9, 10 to 49, 50+") does not send every value to its first band.
        bands = sorted(spec["bands"], key=lambda b: b[0], reverse=True)
        base = next((s for lo, s in bands if n >= lo), bands[-1][1])
    elif kind == "linear":
        n = _num(value)
        if n is None:
            return None
        lo, hi, cap = spec.get("from", 0), spec["to"], spec.get("cap", 100)
        base = max(0.0, min(cap, (n - lo) / (hi - lo) * 100.0))
    else:
        raise ValueError(f"unknown kind {kind}")
    return base


def apply_modifiers(spec, base, flags):
    """flags: comma-separated modifier keys emitted by research, e.g. 'saas,ai_native'."""
    mods = spec.get("modifiers") or {}
    for f in str(flags or "").lower().replace(";", ",").split(","):
        f = f.strip()
        if f in mods:
            base += mods[f]
    return max(0.0, min(100.0, base))


def grade(score):
    return next(g for lo, g in GRADES if score >= lo)


def score(rubric, inputs):
    """rubric: parsed rubric JSON. inputs: dict of <factor>_value/_status/_evidence/_flags."""
    out = {"rubric_version": rubric.get("version")}
    total_weight = sum(f["weight"] for f in rubric["factors"])
    if round(total_weight) != 100:
        raise ValueError(f"weights sum to {total_weight}, not 100; fix the rubric, do not divide here")
    weighted, parts = 0.0, []
    for f in rubric["factors"]:
        fid, w = f["id"], f["weight"]
        raw_status = inputs.get(f"{fid}_status")
        status = str(raw_status).strip().lower() if raw_status not in (None, "") else ""
        evidence = str(inputs.get(f"{fid}_evidence") or "").strip()
        if w == 0:                                   # rule 5: retired factors never block
            out[f"{fid}_score"] = None
            continue
        if status not in STATUSES:                   # rule 4: unknown status is a wiring error
            status, why = "failed", f"status not wired ({raw_status!r})"
        else:
            why = f"data source {status}"
        if status in ("failed", "capped"):           # rules 2 and 3: hold the account
            for g in rubric["factors"]:              # rule 8: a held account writes no component scores
                out.pop(f"{g['id']}_score", None)
            out.update(account_fit_score=None, account_fit_grade=None,
                       scoring_status=f"Held: {f['name']} {status}",
                       account_fit_reason=f"Held: {f['name']} {why}; rerun before scoring.")
            return out
        value = inputs.get(f"{fid}_value") if status == "found" else "none"   # rule 1: none band
        s = factor_score(f, value)
        if s is None:
            s = factor_score(f, "none") if f.get("kind", "map") == "map" else f.get("none_score", 0)
        s = apply_modifiers(f, s, inputs.get(f"{fid}_flags"))
        out[f"{fid}_score"] = round(s)
        weighted += s * w / 100.0
        if not evidence:                             # never a blank where evidence goes
            evidence = "nothing found" if status == "none" else "(no evidence recorded)"
        parts.append((s, f["name"], evidence))
    fit = round(weighted, 1)
    strongest = max(parts, key=lambda p: p[0])
    weakest = min(parts, key=lambda p: p[0])
    g = grade(fit)
    wrap = lambda e: e if e.startswith("(") else f"({e})"   # "(no evidence recorded)" is already wrapped
    out.update(
        account_fit_score=fit, account_fit_grade=g, scoring_status="scored",
        account_fit_reason=(f"{g} ({fit}). Strongest: {strongest[1]} {wrap(strongest[2])}. "
                            f"Weakest: {weakest[1]} {wrap(weakest[2])}."),
    )
    return out


DEFAULT_OVERRIDES = {
    # Clay Ops Rules section 4: entity types another motion owns never land in a rep's book. The component
    # scores are kept for transparency; the total is capped under the eligibility threshold and the reason
    # says why. The carve excludes the same types again, so neither rule alone decides.
    "education": {"exclude": True},
    "vc_pe": {"exclude": True},
    "agency": {"exclude": True},
}
EXCLUDE_CAP = 40.0


def apply_overrides(result, entity_type, rules=None):
    """Grade overrides, applied after the weighted score (rubric-template.md, rules file `overrides:`).

    `rules` is the rules file's overrides block keyed by entity type. Three forms:
    - `{"exclude": true}` (the default for education, vc_pe and agency): keep the component scores, cap the
      total at 40 (`cap` to change it), grade Low Fit, prefix the reason with "Excluded by rule".
    - a bare grade string (`education: Bad Fit`): set the grade, keep the score.
    - `{"min_grade": "Best Fit", "unless_factor_zero": true}`: the opt-in lift for a seller to whom VC
      firms or agencies are real customers; the rules file's exclusions still keep them out of the carve.
    A held account (no score) is left alone.
    """
    if result.get("account_fit_score") is None:
        return result
    rules = DEFAULT_OVERRIDES if rules is None else rules
    rule = rules.get(str(entity_type or "").strip().lower())
    if rule is None:
        return result
    if isinstance(rule, str):                        # e.g. education: Bad Fit
        result["account_fit_grade"] = rule
        result["account_fit_reason"] = f"{rule} (override: {entity_type}). " + result["account_fit_reason"]
        return result
    if rule.get("exclude"):
        raw = result["account_fit_score"]
        result["account_fit_score"] = min(float(raw), float(rule.get("cap", EXCLUDE_CAP)))
        result["account_fit_grade"] = "Low Fit"
        result["account_fit_reason"] = (f"Excluded by rule ({entity_type}): not carved into a territory. "
                                        f"Unadjusted score {raw}. " + result["account_fit_reason"])
        return result
    min_grade = rule.get("min_grade", "Best Fit")
    if rule.get("unless_factor_zero", True):
        # A factor score of 0 is a real zero; `(score or 1) > 0` would turn it into 1 and fire the
        # override on exactly the account the rubric meant to keep out. Retired factors have no score.
        for k, v in result.items():
            if k.endswith("_score") and k != "account_fit_score" and v is not None and v == 0:
                return result
    rank = {g: i for i, (_, g) in enumerate(GRADES)}  # 0 = best
    if rank.get(result["account_fit_grade"], 99) > rank.get(min_grade, 0):
        result["account_fit_grade"] = min_grade
        result["account_fit_reason"] = (f"{min_grade} (override: {entity_type}, no factor scored 0). "
                                        + result["account_fit_reason"])
    return result


def _days_from_civil(y, m, d):
    """Days since 1970-01-01 for a Y/M/D date, no datetime module needed (the sandbox lacks it)."""
    y2 = y - (1 if m <= 2 else 0)
    era = (y2 if y2 >= 0 else y2 - 399) // 400
    yoe = y2 - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def months_since(date_str, now=None):
    """Whole months between `date_str` and today, or None if the date cannot be read.

    Accepts "YYYY-MM-DD", "YYYY-MM", "YYYY" and "Month YYYY" ("June 2025", "Jun 2025"). Missing month
    or day defaults to the first. Uses `time` only, so it can be pasted into a Clay code node as is.
    Typical use in the derive step: `fundraising_value = amount if months_since(d) <= 18 else 1`.
    """
    s = str(date_str or "").strip()
    if not s:
        return None
    y = m = d = None
    try:
        if s[:4].isdigit() and (len(s) == 4 or s[4] in "-/"):
            parts = s.replace("/", "-").split("-")
            y = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 and parts[1] else 1
            d = int(parts[2][:2]) if len(parts) > 2 and parts[2] else 1
        else:                                        # "June 2025", "Jun 2025", "June, 2025"
            words = s.replace(",", " ").split()
            if len(words) >= 2 and words[0][:3].lower() in MONTHS and words[-1].isdigit():
                y, m, d = int(words[-1]), MONTHS[words[0][:3].lower()], 1
        if y is None or not (1 <= m <= 12 and 1 <= d <= 31):
            return None
        days = _days_from_civil(y, m, d)
    except (ValueError, TypeError, IndexError):
        return None
    today_days = int((time.time() if now is None else now) // 86400)
    return int((today_days - days) // 30.44)


def handler(ctx):
    """Clay code-node entry point."""
    rubric = ctx.get_input("rubric_json")
    rubric = json.loads(rubric) if isinstance(rubric, str) else rubric
    inputs = {}
    for f in rubric["factors"]:
        for suffix in ("value", "status", "evidence", "flags"):
            inputs[f"{f['id']}_{suffix}"] = ctx.get_input(f"{f['id']}_{suffix}")
    rules = ctx.get_input("overrides_json")              # optional: the rules file's `overrides:` block as JSON
    if isinstance(rules, str):
        rules = json.loads(rules) if rules.strip() else None
    elif not isinstance(rules, dict):
        rules = None
    return apply_overrides(score(rubric, inputs), ctx.get_input("entity_type"), rules)


def load_rubric(path):
    """A plain .json rubric, or a rubric.md whose rubric lives in a ```json block (same as sf_setup.py)."""
    text = open(path).read()
    if path.endswith(".md"):
        start = text.find("```json")
        end = text.find("```", start + 7) if start >= 0 else -1
        if start < 0 or end < 0:
            raise SystemExit(f"{path}: no ```json block found")
        text = text[start + 7:end]
    return json.loads(text)


def _self_test():
    rubric = {"version": "t", "factors": [
        {"id": "a", "name": "A", "weight": 60, "kind": "map", "map": {"yes": 100, "no": 0, "none": 20}},
        {"id": "b", "name": "B", "weight": 40, "kind": "bands",
         "bands": [[0, 10], [1, 40], [10, 70], [50, 100]], "none_score": 10},   # ascending on purpose
        {"id": "r", "name": "Retired", "weight": 0, "kind": "map", "map": {"none": 0}},
    ]}
    found = {"a_status": "found", "a_value": "yes", "a_evidence": "", "b_status": "found", "b_value": 60,
             "b_evidence": "60 reps"}
    o = score(rubric, found)
    assert o["b_score"] == 100, o                                  # bands sorted before lookup
    assert o["account_fit_score"] == 100.0 and o["account_fit_grade"] == "Best Fit", o
    assert "(no evidence recorded)" in o["account_fit_reason"], o  # empty evidence never blank
    assert o["r_score"] is None, o                                 # retired factor: no score, no block
    o = score(rubric, dict(found, b_status="failed"))
    assert o["account_fit_score"] is None and "a_score" not in o and "b_score" not in o, o  # no partials
    o = score(rubric, dict(found, b_status=None))
    assert o["scoring_status"] == "Held: B failed" and "status not wired" in o["account_fit_reason"], o
    o = score(rubric, dict(found, b_status="success"))
    assert "status not wired" in o["account_fit_reason"], o
    o = apply_overrides(score(rubric, found), "education")          # default: excluded, capped, Low Fit
    assert o["account_fit_score"] == 40.0 and o["account_fit_grade"] == "Low Fit", o
    assert o["account_fit_reason"].startswith("Excluded by rule (education)") and "Unadjusted score 100.0" in o["account_fit_reason"], o
    assert o["a_score"] == 100, o                                   # component scores survive the cap
    low = dict(found, a_value="none", b_value=5)                    # a=20, b=40 -> 28, Low Fit
    o = apply_overrides(score(rubric, low), "vc_pe")
    assert o["account_fit_score"] == 28.0 and o["account_fit_grade"] == "Low Fit" and "Excluded by rule" in o["account_fit_reason"], o
    o = apply_overrides(score(rubric, found), "education", {"education": "Bad Fit"})   # string form
    assert o["account_fit_grade"] == "Bad Fit" and o["account_fit_score"] == 100.0, o
    lift = {"vc_pe": {"min_grade": "Best Fit", "unless_factor_zero": True},
            "agency": {"min_grade": "Best Fit", "unless_factor_zero": True}}            # opt-in lift
    o = apply_overrides(score(rubric, low), "vc_pe", lift)
    assert o["account_fit_grade"] == "Best Fit", o
    zero = dict(found, a_value="no")                                # a=0 is a real zero
    o = apply_overrides(score(rubric, zero), "agency", lift)
    assert o["a_score"] == 0 and "override" not in o["account_fit_reason"], o
    o = apply_overrides(score(rubric, dict(found, b_status="failed")), "vc_pe")
    assert o["account_fit_grade"] is None, o                        # held accounts are left alone
    o = apply_overrides(score(rubric, found), "saas")               # no rule for the type: untouched
    assert o["account_fit_grade"] == "Best Fit" and "Excluded" not in o["account_fit_reason"], o
    now = _days_from_civil(2026, 10, 2) * 86400
    assert months_since("2025-06-15", now) == 15, months_since("2025-06-15", now)
    assert months_since("2025-06", now) == 16 and months_since("2025", now) == 20
    assert months_since("June 2025", now) == 16 and months_since("Jun 2025", now) == 16
    assert months_since("", now) is None and months_since("unknown", now) is None
    assert months_since(None) is None
    print("self-test ok")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        _self_test()
        sys.exit(0)
    rubric = load_rubric(sys.argv[1])                      # rubric.md (```json block) or rubric.json
    rows = json.load(open(sys.argv[2]))                    # [{"domain": ..., "<factor>_value": ...}, ...]
    for r in rows:
        o = apply_overrides(score(rubric, r), r.get("entity_type"))
        print(f"{r.get('domain', '?'):28s} {str(o.get('account_fit_score')):6s} {o.get('account_fit_grade') or o['scoring_status']}")

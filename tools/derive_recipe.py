#!/usr/bin/env python3
"""Adapter (a) recipe derivation — INDEPENDENT of the acceptance harness.

The harness has its own `derive_evidence_from_config`. This module deliberately does NOT
call it: if the converter and the grader share extraction code, agreement is tautological
and proves only that one function equals itself. Disagreement between two independent
implementations is the signal.

Reads config only, via RULE 0b's four-command allowlist, or from an exported payload.
Never reads a cell, never runs a column, never writes.

Usage:
  derive_recipe.py live   <tableId>
  derive_recipe.py config <export.json> [--table-id <id>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys

VERSION = "derive-recipe/1.0.0"

# The low-yield boundary. Calibrated on the 12-table measurement (2026-08-15), not chosen for
# roundness — real prompts ran 9k–16k chars, so 200 excludes stubs and nothing real; and one
# derivable column is a lookup rather than a workflow, already served by an existing task skill.
# Sample caveat: one workspace, skewed to content/SEO tooling. Re-derive on a second workspace.
INTENT_MIN_CHARS = 200
MECHANICS_MIN_COLUMNS = 2

# RULE 0b — the ENTIRE Clay surface. An allowlist, because a denylist fails the moment
# Clay ships a verb (and `clay tables update` is a config WRITE that reads like a setting).
ALLOWED = {
    ("whoami",),
    ("tables", "list"),
    ("tables", "columns", "list"),
    ("tables", "columns", "get"),
}

# Clay system columns carry SEMANTIC ids; user columns carry random ~19-char ids.
SYSTEM_ID = re.compile(r"^f_[a-z][a-z0-9_]*$")
# A column reference inside a formula/binding.
COLREF = re.compile(r"\{\{\s*(f_[A-Za-z0-9_]+)\s*\}\}")
# Workspace-scoped auth handles.
AUTH_HANDLE = re.compile(r"\baa_[A-Za-z0-9]{6,}\b")

# Binding key sets are DISJOINT structural fingerprints, so action type never
# depends on a human-editable column name.
FINGERPRINT = {
    "ai": {"claygentId", "answerSchemaType", "metaprompt", "systemPrompt", "useCase"},
    "http": {"method", "url", "followRedirects", "retryOptions", "maxRetries", "headers"},
}
# Cost-determining knobs. Identity and price are absent from column config; these
# are not. An unset knob is an explicit unknown, never a zero.
COST_KNOBS = ("model", "maxTokens", "maxCostInCents", "runBudget", "reasoningLevel", "temperature")

# ── Which binding carries the rules that actually RUN ──────────────────────────────
# An AI column can hold two different rule statements. `prompt` is the compiled runtime text;
# `metaprompt` is the human-authored spec the compiler was fed, retained afterwards and NOT
# sent. They diverge routinely — and sometimes contradict: one REF table's URL-comparison
# column instructs "normalize, ignore http vs https" in its metaprompt and "judge the /in/
# slug, do NOT compare URL syntax" in its prompt. Those are different behaviours.
#
# The mechanical tell (not a guess): the compiled text interpolates real column references —
# `Clay.formatForAIPrompt({{f_…}})` — while the spec carries human placeholders (`{{prompt}}`).
#
# So decision facts come from the RULE binding only. Extracting from the union of bindings
# mixes live rules with dead ones and then demands the draft transcribe both, which converts
# stale config into a false blocking finding.
RULE_BINDINGS = ("prompt",)
SPEC_BINDINGS = ("metaprompt",)
# `systemPrompt` on these columns holds the JSON answer schema, not a system message: it
# constrains output SHAPE, and its `enum` arrays are a declared output value set.
SCHEMA_BINDINGS = ("systemPrompt", "answerSchemaType")
COMPILED_REF = re.compile(r"Clay\.formatForAIPrompt\(")

# ── Decision-fact extraction ─────────────────────────────────────────────────────────────
# The claim comparison asks whether the DRAFT's rules are the SOURCE's rules. It can only ask that if the
# derivation hands it the source's rules, keyed per action so a gap is attributable.
#
# INDEPENDENCE NOTE, stated because someone will otherwise cite agreement as corroboration:
# the harness has its own extractor, and this one was written AFTER reading it. On thresholds
# the two now converge by construction, so matching threshold sets are NOT independent
# evidence. The shapes below that are genuinely mine — schema-enum harvesting, newline-list
# output sets, numeric-output ranges, and rule/spec scoping — are where disagreement is still
# informative.
_INSTRUCT = r"(?:return|output|respond\s+with|reply\s+with|answer\s+with|classify\s+as|emit|set)"
# "one of: A, B, or C" / "one of the exact strings: A, B, or C"
_INLINE_SET = re.compile(
    rf"(?is)\b{_INSTRUCT}\b[^.\n]{{0,90}}?\bone\s+of\b[^:\n]{{0,60}}:?\s*(?P<vals>[^.\n]{{4,200}})")
# A colon ending a line, then short label lines. This is how a hand-written classifier states
# its label set, and an "one of" matcher never sees it.
_LIST_SET = re.compile(
    rf"(?im)^.*\b{_INSTRUCT}\b[^\n]{{0,80}}:\s*$\n(?P<vals>(?:[ \t]*[*\-]?\s*[A-Z][^\n]{{0,60}}\n?){{2,8}})")
# A numeric output declaration is a decision rule too — it just decides a number.
_NUMERIC_OUT = re.compile(
    rf"(?is)\b{_INSTRUCT}\b[^.\n]{{0,80}}?\b(?:single\s+)?(?:integer|number|score)\b"
    r"[^.\n]{0,40}?(?:between\s+|from\s+)?(?P<lo>\d{1,3})\s*(?:-|–|—|\bto\b|\band\b)\s*(?P<hi>\d{1,3})")
_ENUM_ARRAY = re.compile(r'"enum"\s*:\s*\[(?P<vals>[^\]]{2,400})\]')
# A multi-field object verdict. This is the line between a SCORER and an ANALYZER, and it is
# the difference between a band ladder that gates and one that is a sub-field's scale: the
# analyzer in the reference table declares "exactly one JSON object with these camelCase
# fields" and contains `Return as a number from 1 to 10` for ONE of fifteen fields. Marking
# that action banded made A9b block on its instruction numbering — cry wolf, on the check
# whose whole value is being read.
_OBJECT_OUT = re.compile(
    r"(?i)\breturn\b[^\n]{0,60}?\b(?:json\s+object|object\s+with|these\s+(?:camelCase\s+)?"
    r"(?:fields|keys)|following\s+(?:fields|keys))\b")
# Comparators are unambiguous anywhere. Bands and `N+` need a scoring context, or ordinary
# prose numbers flood the set.
_CMP = re.compile(
    r"(?ix)(?:>=|<=|≥|≤|>|<|at\s+least|at\s+most|no\s+more\s+than|above|below|under|over|"
    r"fewer\s+than|more\s+than)\s*(?P<n>\d+(?:\.\d+)?)|top-(?P<t>\d+)")
_BAND = re.compile(r"(?P<lo>\d{1,3})\s*(?:–|—|-|\bto\b)\s*(?P<hi>\d{1,3})(?![\d%])|(?P<plus>\d{1,3})\+(?!\d)")
_SCORING = re.compile(r"(?i)\b(scor\w+|band|tier|threshold|rating|percentile|grade|rank\w*)\b")
_LIST_NUM = re.compile(r"(?m)^\s*\d+[.)]\s")
# A band LADDER: consecutive lines that each open with a band and a colon. Structural, so it
# does not depend on how far the ladder has drifted from the word "scoring" — which is how the
# first version silently dropped the bottom two bands of a four-band scale (reach is
# contract). A ladder is self-evidencing; two band-shaped lines in a row are not prose.
_LADDER_LINE = re.compile(
    r"(?m)^[ \t]*(?:[-*•]|\d+[.)])?[ \t]*(?:\d{1,3}\s*(?:–|—|-|\bto\b)\s*\d{1,3}|\d{1,3}\s*\+)\s*(?::|—|-|\bpoints?\b)")
# A number governed by a LENGTH or FORMAT constraint is not a cut point. "keep reason concise
# (<= 140 characters)" and "1-2 words max" are output hygiene; treating them as decision
# thresholds and then demanding a draft restate them is the cry-wolf failure in miniature.
_FORMAT_WORD = re.compile(
    r"(?i)\b(char|chars|character|characters|word|words|token|tokens|sentence|sentences|"
    r"paragraph|paragraphs|line|lines|byte|bytes|item|items|decimal|decimals)\b")
# `field: Exactly one of ["A","B"]` — a per-FIELD label set, not the action's verdict.
_FIELD_ENUM = re.compile(
    r"(?im)^[^\n]{0,40}?\b(?P<field>[A-Za-z][A-Za-z0-9_]{2,40})\b[^\n:]{0,40}:"
    r"[^\n\[]{0,60}?\b(?:exactly\s+one\s+of|one\s+of|must\s+be\s+one\s+of)\b[^\[\n]{0,40}\n?"
    r"\s*\[(?P<vals>[^\]]{4,600})\]")
_IDENT = re.compile(r"\b(?P<id>[a-z]+(?:[A-Z][a-z]+){1,4})\b")
_NOISE = {"format", "output", "input", "field", "fields", "value", "values", "object", "string",
          "json", "please", "return", "prompt", "context", "objective", "instructions",
          "example", "examples", "explanation", "text", "only", "none", "true", "false",
          "expected", "yes", "no", "and", "or", "if", "then"}


def is_system_column(col_id: str) -> bool:
    """Independent implementation of the system-column id rule (harness exports its own)."""
    return bool(SYSTEM_ID.match(col_id))


def _run(*args: str) -> dict:
    if tuple(a for a in args if not a.startswith("-"))[: len(max(ALLOWED, key=len))] and \
            not any(tuple(args[: len(p)]) == p for p in ALLOWED):
        raise PermissionError(f"RULE 0b: `clay {' '.join(args)}` is not in the four-command allowlist")
    p = subprocess.run(["clay", *args], capture_output=True, text=True)
    body = json.loads(p.stdout or "{}")
    if isinstance(body, dict) and body.get("error"):
        err = body["error"]
        # A cross-workspace table id returns not_found at exit 0, indistinguishable
        # from a typo. Say which it probably is instead of passing the raw error through.
        if err.get("code") == "not_found" and "columns" in args:
            raise LookupError(
                f"{err.get('message')} — NOTE: a table in a DIFFERENT workspace also reports "
                "'not_found'. Check `clay whoami`'s workspace id against the table's home "
                "workspace, and re-pin with `clay login` if they differ (the pin cannot be "
                "changed non-interactively)."
            )
        raise RuntimeError(f"clay {' '.join(args)} → {err}")
    return body


def _binding(settings: dict) -> dict:
    """Flatten inputsBinding's [{name, formulaText}] into {name: formulaText}."""
    out = {}
    for item in (settings or {}).get("inputsBinding") or []:
        if isinstance(item, dict) and "name" in item:
            out[item["name"]] = item.get("formulaText")
    return out


def _enums(text: str) -> dict[str, list[str]]:
    """Extract closed label sets from prompt text. Intentionally broader than the harness's
    single phrasing — a converter that only recognizes one way of writing an enum will
    silently truncate somebody's label set, which the label-set check exists to catch."""
    found: dict[str, list[str]] = {}
    try:
        text = text.encode().decode("unicode_escape", errors="ignore")
    except Exception:
        pass
    patterns = (
        r'(\w+)\s*:\s*(?:Exactly one of|exactly one of|one of|must be one of|choose one of)\s*\[(.*?)\]',
        r'"(\w+)"\s*:\s*\{[^}]*?"enum"\s*:\s*\[(.*?)\]',
        r'(\w+)\s*(?:must be|is)\s*(?:exactly )?one of\s*:?\s*\[(.*?)\]',
    )
    for pat in patterns:
        for m in re.finditer(pat, text, re.S):
            vals = re.findall(r'"([^"]+)"', m.group(2))
            if len(vals) > 1:
                found.setdefault(m.group(1), vals)
    return found


def _clean(text: str) -> str:
    """Real newlines, and no `+ Clay.formulaCall(...) +` scaffolding left in the prose.

    Only the two-char escapes — not `unicode_escape`, which mangles the en-dashes that band
    ranges (`50–79`) are written with, and a mangled dash is a threshold silently lost.
    """
    t = str(text or "").replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    return re.sub(r"Clay\.\w+\(\s*\{\{[A-Za-z0-9_]+\}\}\s*\)", " <ref> ", t)


def _label_values(raw: str) -> list[str]:
    """A comma/or/newline separated enumeration → its labels, or [] if it is really prose."""
    parts = [p.strip(" \t`\"'*-–—.") for p in re.split(r",|\bor\b|\n", raw)]
    out = []
    for p in parts:
        if not p or len(p) > 40 or p.lower() in _NOISE:
            continue
        # A label is a short capitalised phrase. Instructional tails ("with no punctuation or
        # extra text") split into fragments that fail this, which is the point.
        if not re.fullmatch(r"[A-Z][A-Za-z0-9][A-Za-z0-9 /&'’_-]*", p):
            continue
        if len(p.split()) > 4:
            continue
        out.append(p)
    return out if len(out) >= 2 else []


def decision_facts(rule_text: str, schema_text: str = "") -> dict:
    """The facts a faithful transcription must carry. Extracted from the RULE binding only."""
    t = _clean(rule_text)
    values: list[str] = []

    # 1. A declared answer schema enum is the strongest signal there is — it is machine-read
    #    at runtime, so it cannot be stale relative to the prompt.
    for m in _ENUM_ARRAY.finditer(_clean(schema_text) + "\n" + t):
        vals = re.findall(r'"([^"\n]{1,40})"', m.group("vals"))
        if len(vals) >= 2:
            values = vals
            break
    # 2. Otherwise an instruction clause: inline list first, then the newline-list form.
    if not values:
        for pat in (_INLINE_SET, _LIST_SET):
            for m in pat.finditer(t):
                quoted = re.findall(r'"([^"\n]{1,40})"', m.group("vals"))
                got = quoted if len(quoted) >= 2 else _label_values(m.group("vals"))
                if got:
                    values = got
                    break
            if values:
                break

    # A numeric verdict is a decision too. Recorded separately: it is NOT a label set, and
    # claiming it is one would make A9a demand that a number appear as a quoted string.
    nm = _NUMERIC_OUT.search(t)
    numeric = [float(nm.group("lo")), float(nm.group("hi"))] if nm else []

    # Per-FIELD label sets are a different animal from the action's verdict: a nine-field
    # classifier declares six of them, and flattening those into `output_values` would make
    # every one of its formatting numbers a blocking threshold. Kept keyed, reported, and left
    # to the enum check — but recorded so nobody reads `output_values: []` as "no label sets".
    field_enums: dict[str, list[str]] = {}
    for m in _FIELD_ENUM.finditer(t):
        vals = re.findall(r'"([^"\n]{1,60})"', m.group("vals"))
        if len(vals) >= 2:
            field_enums.setdefault(m.group("field"), vals)
    # Keyed sets, so a gap is attributable to the set that dropped it rather than to the action.
    value_sets = dict(field_enums)
    if values:
        value_sets["verdict"] = values

    # Thresholds. Ordered-list numbering is stripped FIRST — `3. Scoring guide` is not a cut
    # point, and a threshold set padded with instruction numbers is one nobody reads.
    body = _LIST_NUM.sub("  ", t)

    def _is_format(pos: int) -> bool:
        return bool(_FORMAT_WORD.search(body[max(0, pos - 40): pos + 60]))

    found = {float(g) for m in _CMP.finditer(body) if not _is_format(m.start())
             for g in m.groups() if g}
    for cm in _SCORING.finditer(body):
        window = body[max(0, cm.start() - 240): cm.end() + 240]
        for m in _BAND.finditer(window):
            if not _is_format(cm.start() - 240 + m.start() if cm.start() > 240 else m.start()):
                found |= {float(g) for g in m.groups() if g}
    # …and a band ladder counts wherever it is, keyword or no keyword.
    ladder = 0
    for m in _LADDER_LINE.finditer(body):
        ladder += 1
        for bm in _BAND.finditer(m.group(0)):
            found |= {float(g) for g in bm.groups() if g}
    found |= set(numeric)

    counts: dict[str, int] = {}
    for m in _IDENT.finditer(t):
        counts[m.group("id")] = counts.get(m.group("id"), 0) + 1
    inputs = sorted(k for k, n in counts.items() if n >= 2 and k.lower() not in _NOISE)

    # `banded` is the grader's DECISIVE trigger for a label-free scorer. Emitted because a
    # trigger key read with `.get()` treats absent as false — so an adapter that omits it
    # silently disables the check rather than failing it. Two ladder lines minimum: one band on
    # its own is a bound, a run of them is a scale.
    facts = {"output_values": values, "value_sets": value_sets,
             # BANDED = the action's own verdict is a banded scalar score. Requires all three:
             # a ladder (a scale, not a lone bound), a declared numeric verdict, and NO
             # multi-field object output. Loosening any one of them re-broke the analyzer.
             "banded": bool(ladder >= 2 and numeric and not _OBJECT_OUT.search(t)),
             "thresholds": sorted(found), "decision_inputs": inputs}
    if numeric:
        facts["numeric_output_range"] = numeric
    if field_enums:
        # NOT inside the claim-graded pair. An action whose only decision facts are per-field enums
        # gives the comparison nothing to assert, and emitting an empty-but-present facts blob would turn a
        # SKIP into a vacuous PASS — worse than an ungraded check, because it reads as covered.
        facts["_output_field_enums"] = field_enums
    return facts


def _spec_divergence(rule_text: str, spec_text: str) -> dict | None:
    """Does the retained spec state DIFFERENT rules from the compiled prompt?

    Reported, never used as rules. A creator whose column carries two contradictory rule
    statements should be told which one runs — that is a finding about their artifact, and
    silently transcribing whichever one an extractor happened to reach is how that defect happened.
    """
    if not spec_text:
        return None
    a = decision_facts(rule_text)
    b = decision_facts(spec_text)
    diff = {}
    if set(b["output_values"]) - set(a["output_values"]):
        diff["spec_only_output_values"] = sorted(set(b["output_values"]) - set(a["output_values"]))
    if set(b["thresholds"]) - set(a["thresholds"]):
        diff["spec_only_thresholds"] = sorted(set(b["thresholds"]) - set(a["thresholds"]))
    if not diff:
        return None
    diff["note"] = ("the retained spec (`metaprompt`) states rules the compiled `prompt` does "
                    "not; the compiled prompt is what runs — do NOT transcribe these")
    return diff


CLAIM_VERSION = "claim-block/1.0.0"

# A comparator against a literal, in either operand order. Formulas are code, not prose, so this
# is a scan over a formal language — NOT the regex-over-English that costs a check its right to
# block. `>=` before `>` matters: alternation is ordered and `>` would shadow it.
_F_CMP_RIGHT = re.compile(r"(?P<cmp>>=|<=|==|!=|>|<)\s*(?P<val>-?\d+(?:\.\d+)?)")
_F_CMP_LEFT = re.compile(r"(?P<val>-?\d+(?:\.\d+)?)\s*(?P<cmp>>=|<=|==|!=|>|<)")
# `x >= 50` and `50 <= x` are the same claim. Normalising means a creator who writes the operands
# either way gets one canonical claim, and the comparison cannot fail on spelling.
_MIRROR = {">=": "<=", "<=": ">=", ">": "<", "<": ">", "==": "==", "!=": "!="}
# Templates, not bare words: English puts some comparators before the number ("more than 50") and
# some after ("50 or more"). A single word map produced "1,000 more than" — and because this is the
# ONLY place prose is generated, that one bug would have appeared in every skill this adapter ever
# emits. Hence case H's renderer coverage in the acceptance suite.
_CMP_TEMPLATE = {">=": "{v} or more", ">": "more than {v}", "<=": "{v} or fewer",
                 "<": "fewer than {v}", "==": "exactly {v}", "!=": "other than {v}"}
# The subject of a comparison is the operand, not the column the formula lives in: in
# `if({{f_headcount}} >= 50, …)` inside a "Tier" column, the claim is about headcount. Bounded
# look-back so a reference three clauses away is not misattributed.
_SUBJECT_BACK = 40


def _formula_sites(settings: dict) -> list[tuple[str, str]]:
    """Every place a formula can live, as (site, text). Named sites, because a threshold in a
    conditional gate is a different claim from one in the column's own formula."""
    out: list[tuple[str, str]] = []
    if t := settings.get("formulaText"):
        out.append(("formula", str(t)))
    if t := settings.get("conditionalRunFormulaText"):
        out.append(("gate", str(t)))
    for b in settings.get("inputsBinding") or []:
        if isinstance(b, dict) and (t := b.get("formulaText")):
            out.append((f"input:{b.get('name') or '?'}", str(t)))
    return out


def source_claims(cols: list[dict]) -> dict:
    """GROUND TRUTH: deterministic claims extracted from formulaText, with a digest per site.

    This is the reference side of the comparison, never the asserted side. Extracting the block
    from the formula and then 'comparing' the two would be a tautology — one field restated, a
    check that cannot fail (the provider-semantics notes). The asserted side must come from the
    drafting step.

    The digest pins WHICH formula produced a claim without shipping the formula, which is what
    keeps the package free of workspace-specific content while still being auditable.
    """
    claims, digests, sites_seen = [], {}, 0
    names = {c.get("id", ""): c.get("name") or c.get("id", "") for c in cols}
    for c in cols:
        cid = c.get("id", "")
        if is_system_column(cid):
            continue
        settings = c.get("settings") or {}
        for site, text in _formula_sites(settings):
            sites_seen += 1
            key = f"{c.get('name') or cid}:{site}"
            digests[key] = "sha256:" + hashlib.sha256(text.encode()).hexdigest()[:12]
            found = []
            for m in _F_CMP_RIGHT.finditer(text):
                found.append((m.group("cmp"), m.group("val"), m.start()))
            for m in _F_CMP_LEFT.finditer(text):
                found.append((_MIRROR[m.group("cmp")], m.group("val"), m.start()))
            for cmp_, val, at in found:
                # Resolve the operand to a column NAME, never an id — an id is a workspace handle
                # and the abstraction step exists to remove it. Unresolvable → None, not a guess.
                back = text[max(0, at - _SUBJECT_BACK):at]
                refs = COLREF.findall(back)
                subject = names.get(refs[-1]) if refs else None
                claim = {
                    "kind": "threshold",
                    "applies_to": c.get("name") or "(unnamed column)",
                    "subject": subject,
                    "site": site,
                    "comparator": cmp_,
                    "value": float(val) if "." in val else int(val),
                    "source": {"evidence": "formula", "digest": digests[key]},
                }
                if claim not in claims:
                    claims.append(claim)
    return {
        "schema": CLAIM_VERSION,
        "claims": claims,
        "digests": digests,
        # Coverage is reported so an empty set is legible as "nothing to check" rather than
        # silently indistinguishable from "everything checked out" (work-order item 12).
        "coverage": {"formula_sites": sites_seen, "claims_found": len(claims)},
    }


def render_threshold(claim: dict) -> str:
    """THE single renderer. Prose is generated from the block, in one direction only.

    Extracting `>= 50` back out of "at least 50" / "50+" / "fifty" is a regex over English, and a
    hard block on that class of evidence is what the codebase's own severity rule forbids.
    Generating one way makes the extraction problem not exist: prose and block cannot diverge
    because the prose is not independently maintained.
    """
    v = claim["value"]
    v = f"{v:g}" if isinstance(v, float) else f"{v:,}"
    phrase = _CMP_TEMPLATE.get(claim["comparator"], f"{claim['comparator']} {{v}}").format(v=v)
    subj = claim.get("subject")
    return f"{subj} {phrase}" if subj else phrase


def _ckey(c: dict) -> tuple:
    # `subject` is deliberately NOT part of the key. It is a rendering aid resolved by a bounded
    # look-back, so a drafting step that omits or rewords it must not read as a threshold
    # mismatch — the comparison exists to catch wrong NUMBERS, not wrong labels.
    return (c.get("applies_to"), c.get("site"), c.get("comparator"), c.get("value"))


def compare_claims(asserted: list[dict], source: dict) -> dict:
    """Deterministic on BOTH sides: structured assertions against structured source claims.

    Fails in both directions on purpose. A wrong threshold and a silently DROPPED threshold are
    the same defect to an installer — the skill does something the table did not — and a
    one-directional check would pass the second.
    """
    src = {_ckey(c): c for c in source.get("claims", [])}
    ast = {_ckey(c): c for c in asserted}
    wrong_value, unsupported, omitted = [], [], []

    for k, c in ast.items():
        if k in src:
            continue
        # Same target and site, different comparator or value → a transcription error, which is
        # more actionable to report than a bare "unsupported claim".
        near = [s for s in src if s[0] == k[0] and s[1] == k[1]]
        (wrong_value if near else unsupported).append(
            {"asserted": c, "source_candidates": [src[n] for n in near]})
    for k, c in src.items():
        if k not in ast:
            omitted.append(c)

    ok = not (wrong_value or unsupported or omitted)
    # THREE verdicts, not two. A boolean `empty_comparison_set` beside `verdict: match` still lets
    # a caller that reads only the verdict record a pass over zero evidence — the same
    # one-field-two-questions defect. `no_claims_to_compare` cannot be misread (item 12).
    verdict = ("mismatch" if not ok else "no_claims_to_compare" if not src else "match")
    return {
        "schema": CLAIM_VERSION,
        "compared": len(src),
        "asserted": len(ast),
        "verdict": verdict,
        "wrong_value": wrong_value,
        "unsupported": unsupported,
        "omitted": omitted,
        "empty_comparison_set": not src,
        "_matched": [src[k] for k in ast if k in src],
    }


def proof(comparison: dict, gate: dict, interview_derived: bool = False,
          source_omitted: bool = True) -> dict:
    """Emit against the rev-4 contract — NOT a parallel schema.

    `proof_status` ∈ complete|partial|not_exercised and `proof_gaps[]` of `{stage, reason}`,
    non-empty exactly when status is not `complete`, per the deployed constraints in
    20260814a_eval_run_rev4_additive.sql. Inventing a second vocabulary makes the two unjoinable,
    which is the whole reason work-order item 10 exists.

    For adapter (a) `source_omitted` is always True, so **a table-derived package is always
    `partial`** — the formula does not ship, therefore local proof cannot be complete, by
    construction rather than by circumstance. The parameter exists because adapter (b) works from
    evidence that DOES ship with the package and can legitimately reach `complete`; hard-coding
    the gap here would have left a `complete` branch that no caller could ever take, which reads
    as reachable to the next person and is not.
    """
    # A mismatch must FAIL GENERATION, so reaching here with one means the caller skipped the
    # gate. Refuse rather than emit: on a wrong-value mismatch this function would otherwise
    # return a well-formed proof block listing the claims that DID match, which reads as a
    # partially-verified package when the correct outcome is no package at all.
    if comparison.get("verdict") == "mismatch":
        raise ValueError(
            "refusing to emit proof for a mismatched comparison — generation must fail first "
            f"(wrong_value={len(comparison.get('wrong_value') or [])}, "
            f"unsupported={len(comparison.get('unsupported') or [])}, "
            f"omitted={len(comparison.get('omitted') or [])})")

    gaps: list[dict] = []
    if comparison.get("verdict") == "no_claims_to_compare":
        gaps.append({"stage": "stage_p", "reason":
                     "No deterministic claims existed to compare, so no threshold was verified — "
                     "this skill's logic is not arithmetic transcribed from formulas."})
    if interview_derived or gate.get("verdict") == "interview_fallback":
        gaps.append({"stage": "stage_p", "reason":
                     "Logic came from the creator interview, which has no ground truth in the "
                     "table — it is the creator's stated intent, not a verified mechanism."})
    if source_omitted:
        gaps.append({"stage": "intake", "reason":
                     "The source formula is omitted from the package, so intake cannot "
                     "independently replay the comparison, and the check cannot see edits made "
                     "after generation."})
    return {
        "proof_status": "complete" if not gaps else "partial",
        "proof_gaps": gaps,
        "proven_claims": [
            {k: v for k, v in c.items() if k != "source"} | {"digest": c["source"]["digest"]}
            for c in (comparison.get("_matched") or [])
        ],
        "source_evidence_summary": {
            "claims_compared": comparison.get("compared", 0),
            "claims_asserted": comparison.get("asserted", 0),
            "comparison_verdict": comparison.get("verdict"),
            "intent_prompt_chars": gate.get("intent_prompt_chars"),
            "mechanics_columns": gate.get("mechanics_columns"),
            "yield_verdict": gate.get("verdict"),
        },
    }


def topo_steps(by_id: dict, refs_out: dict, user_ids: set) -> list[dict]:
    """Procedural order from the dependency graph — never spatial column order.

    A table is spatial: columns sit wherever the creator added them, so a correction column at the
    far right is a step-2 operation in the last position. Ties break on column id so repeated
    builds number steps identically; non-deterministic ordering would fail manifest equality for
    reasons that have nothing to do with content.
    """
    pend = {c: {r for r in refs_out[c] if r in user_ids} for c in user_ids}
    steps, done = [], set()
    while pend:
        ready = sorted(c for c, deps in pend.items() if not (deps - done))
        if not ready:
            # A cycle is a system failure. Dropping an edge to force an ordering would turn a
            # converter bug into a confidently-wrong skill.
            return [{"system_failure": "dependency cycle",
                     "columns": sorted(by_id[c]["name"] for c in pend)}]
        for c in ready:
            steps.append({"step": len(steps) + 1, "column": by_id[c]["name"],
                          "depends_on_steps": sorted(
                              s["step"] for s in steps
                              if s["column"] in {by_id[r]["name"] for r in refs_out[c] & user_ids})})
            done.add(c)
            del pend[c]
    return steps


def yield_gate(cols: list[dict]) -> dict:
    """The low-yield boundary — two axes, computed AND reported.

    Shortfall on either axis routes to the interview adapter. Reported with both values because
    "nothing recoverable here" without a number is indistinguishable from a broken converter.
    """
    prompt_chars, mech = 0, 0
    for c in cols:
        if is_system_column(c.get("id", "")):
            continue
        settings = c.get("settings") or {}
        b = _binding(settings)
        for k in ("metaprompt", "systemPrompt", "formulaPrompt", "prompt"):
            for src in (b, settings):
                if isinstance(src.get(k), str):
                    prompt_chars = max(prompt_chars, len(_clean(src[k])))
        keys = set(b)
        derivable = any(keys & sig for sig in FINGERPRINT.values()) or bool(
            settings.get("formulaText")) or (c.get("type") == "action")
        mech += 1 if derivable else 0
    intent_ok = prompt_chars >= INTENT_MIN_CHARS
    mech_ok = mech >= MECHANICS_MIN_COLUMNS
    return {
        "intent_prompt_chars": prompt_chars, "intent_threshold": INTENT_MIN_CHARS,
        "mechanics_columns": mech, "mechanics_threshold": MECHANICS_MIN_COLUMNS,
        "intent_ok": intent_ok, "mechanics_ok": mech_ok,
        "verdict": "proceed" if (intent_ok and mech_ok) else "interview_fallback",
        "shortfall": [] if (intent_ok and mech_ok) else
                     ([] if intent_ok else ["intent"]) + ([] if mech_ok else ["mechanics"]),
    }


def derive(table_id: str, cols: list[dict]) -> dict:
    by_id = {c["id"]: c for c in cols}
    user_ids = {cid for cid in by_id if not is_system_column(cid)}

    # Dependency graph from binding/formula references (the only liveness signal that
    # always exists — a known issue record counts for non-source columns).
    refs_out: dict[str, set[str]] = {}
    handles: set[str] = {table_id}
    for cid, c in by_id.items():
        blob = json.dumps(c.get("settings") or {})
        refs_out[cid] = set(COLREF.findall(blob))
        handles |= set(AUTH_HANDLE.findall(blob))
    handles |= user_ids
    referenced = {r for rs in refs_out.values() for r in rs}

    actions, hosts, enums = {}, set(), {}
    for cid in user_ids:
        c = by_id[cid]
        if c.get("type") != "action":
            continue
        b = _binding(c.get("settings") or {})
        keys = set(b)
        kind = next((k for k, sig in FINGERPRINT.items() if keys & sig), "unknown")
        knobs = {k: b[k] for k in COST_KNOBS if b.get(k) not in (None, "")}
        # Declare side effects. FAIL-CLOSED: a non-GET/HEAD method or a mutating verb in
        # the column name counts as side-effecting, because under-declaring a write is worse.
        method = str(b.get("method") or "").strip('"\'').upper()
        mutating_name = bool(re.search(r"(?i)\b(patch|update|upsert|create|delete|post|write|sync|send)\b", c["name"]))
        writes = bool((method and method not in ("GET", "HEAD")) or mutating_name)
        # …but SAY WHICH KIND. A POST that generates a completion sends the installer's data
        # to a vendor; a PATCH to their CMS edits the installer's own records. Same fail-closed
        # flag, two different disclosures — collapsing them puts two risk classes in one bucket.
        write_kind = ("mutates_installer_data" if method in ("PATCH", "PUT", "DELETE")
                      else "third_party_call" if writes else None)
        # Conditional execution. A gated action does not always run, so summing every
        # action overstates cost; and the gate IS logic, so a chain transcribed without it tells
        # the installer to run every step.
        cond = str((c.get("settings") or {}).get("conditionalRunFormulaText") or "").strip()
        # Publish state for a CMS-shaped write. Fail closed: unset is `unknown`, never
        # `draft` — assuming the safe meaning is how an unsafe write ships with a calm caption.
        flag = str(b.get("isDraft") or "").strip('"\'').lower()
        publish_state = ("draft" if flag == "true" else "live" if flag == "false"
                         else "unknown" if writes and any(
                             k == "collection" or k.startswith("fields|") for k in b)
                         else None)
        actions[c["name"]] = {
            # The action's IDENTITY, carried through verbatim. The table has it on every action
            # column; dropping it is what made a wrong input field unverifiable — a parameter name
            # with no owner cannot be looked up, so `clay workflows actions schema <packageId>
            # <actionKey>` has no arguments and `cost_basis: needs_catalog_lookup` below asks for a
            # lookup that has been made impossible. NEVER synthesise a pair: absent means `null`,
            # and the caller reports it unverified rather than guessing a packageId.
            "action_key": (c.get("settings") or {}).get("actionKey"),
            "action_package_id": (c.get("settings") or {}).get("actionPackageId"),
            "action_version": (c.get("settings") or {}).get("actionVersion"),
            # The parameter names as the TABLE spells them — one side of the schema comparison.
            # Clay's UI writes a shotgun of aliases per action (one source column mapped to every
            # plausible name so whichever the provider reads lands), so this is a candidate set,
            # never a contract. Only the action's schema says which of them is real.
            "input_parameter_names": sorted(keys),
            "kind": kind,
            "cost_knobs": knobs,
            # HTTP cost sits with the callee, so it is unavailable — NEVER zero.
            # `unknown` is a managed/catalog action — the ONE class with an exact
            # declared price. It TRIGGERS a catalog lookup; it is never a terminal verdict.
            # `unavailable` is reserved for HTTP, where cost genuinely sits with the callee.
            "cost_basis": ("unavailable" if kind == "http"
                           else "declared" if knobs
                           else "needs_catalog_lookup"),
            "unset_knobs": [k for k in COST_KNOBS if k in b and b.get(k) in (None, "")],
            "writes": writes,
            "write_kind": write_kind,
            "conditional": bool(cond),
            "condition_refs": sorted(set(COLREF.findall(cond))),
            "publish_state": publish_state,
        }
        # Decision facts, from the rule binding only. An action with no rule binding
        # (HTTP, managed) contributes none — and the comparison then has nothing to grade on it, which is
        # the honest state, not a pass.
        rule_text = "\n".join(_clean(b[k]) for k in RULE_BINDINGS if b.get(k))
        spec_text = "\n".join(_clean(b[k]) for k in SPEC_BINDINGS if b.get(k))
        schema_text = "\n".join(_clean(b[k]) for k in SCHEMA_BINDINGS if b.get(k))
        facts = (decision_facts(rule_text or spec_text, schema_text) if (rule_text or spec_text)
                 else {"output_values": [], "thresholds": [], "decision_inputs": []})
        if fe := facts.pop("_output_field_enums", None):
            actions[c["name"]]["output_field_enums"] = fe
        # ALWAYS emit the key, empty or not. Emitting only when non-empty makes
        # `field_absent` indistinguishable from `field_present_and_empty`, and the grader then
        # SKIPS instead of failing — a check dodged by omission from the side it grades.
        actions[c["name"]]["decision_facts"] = facts
        if rule_text or spec_text:
            actions[c["name"]]["rule_source"] = (
                "prompt" if rule_text else "metaprompt (no compiled prompt on this column)")
        if rule_text and spec_text:
            actions[c["name"]]["compiled_rule_binding"] = bool(COMPILED_REF.search(rule_text))
            div = _spec_divergence(rule_text, spec_text)
            if div:
                actions[c["name"]]["spec_divergence"] = div
        for v in b.values():
            if not isinstance(v, str):
                continue
            if kind == "http":
                hosts |= {h.rsplit(":", 1)[0] for h in re.findall(r"https?://([^/\"'\s{]+)", v)}
            enums.update({k: v2 for k, v2 in _enums(v).items() if k not in enums})

    return {
        "derivation": VERSION,
        "table_id": table_id,
        "column_count": len(cols),
        "action_count": sum(1 for c in cols if c.get("type") == "action"),
        "system_columns_excluded": sorted(cid for cid in by_id if is_system_column(cid)),
        "handles": sorted(handles),
        # Root inputs: reference nothing, referenced by something → the installer supplies them.
        "declared_inputs": sorted(by_id[c]["name"] for c in user_ids
                                  if not refs_out[c] and c in referenced),
        # Orphans: referenced by nothing. CANDIDATES only — a graph walk cannot tell an
        # abandoned experiment from an optional input never filled. Played back, never pruned.
        "dead_candidates": sorted(by_id[c]["name"] for c in user_ids
                                  if not refs_out[c] and c not in referenced),
        # Terminal outputs: reference something, referenced by nothing → what the table PRODUCES.
        # The two branches above both require `not refs_out[c]`, so terminals fell into neither and
        # the outputs were never computed at all. Root → terminal is the use case, from config:
        # on the table this was found against, "Personal Email" in, "Work Email" out.
        # It also separates a dead-end OUTPUT from an orphan: a column that consumes earlier work
        # and is consumed by nothing is a second output, which `dead_candidates` cannot express.
        "terminal_outputs": sorted(by_id[c]["name"] for c in user_ids
                                   if refs_out[c] and c not in referenced),
        "actions": actions,
        "external_hosts": sorted(hosts),
        "enums": enums,
        # Procedural order, from the graph above — the step sequence a skill body renders from.
        "steps": topo_steps(by_id, refs_out, user_ids),
        # The gate. Callers must honour `verdict: interview_fallback` and NOT draft: a skill
        # inferred from column names is fluent, plausible and unfounded.
        "yield_gate": yield_gate(cols),
        # Ground truth for the comparison. The asserted side comes from the drafting step; these
        # two are never the same object, or the check is a tautology.
        "source_claims": source_claims(cols),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    lv = sub.add_parser("live"); lv.add_argument("table_id")
    cf = sub.add_parser("config"); cf.add_argument("export"); cf.add_argument("--table-id", default="t_unknown")
    cm = sub.add_parser("compare", help="asserted claim block vs source claims; exit 3 on mismatch")
    cm.add_argument("export"); cm.add_argument("asserted")
    a = ap.parse_args()

    if a.mode == "compare":
        cols = (lambda p: p.get("data", p))(json.load(open(a.export)))
        asserted = json.load(open(a.asserted))
        if isinstance(asserted, dict):
            asserted = asserted.get("deterministic_claims") or asserted.get("claims") or []
        src = source_claims(cols)
        res = compare_claims(asserted, src)
        res["rendered"] = [render_threshold(c) for c in src["claims"]]
        print(json.dumps(res, indent=1))
        # Exit 3 = generation must fail. A mismatch is deterministic evidence on both sides, so
        # it legitimately blocks; an empty comparison set does NOT block, it downgrades proof.
        return 3 if res["verdict"] == "mismatch" else 0

    if a.mode == "live":
        me = _run("whoami")
        my_id = str((me.get("user") or {}).get("id", ""))
        # RULE 0 — owner-scope BEFORE reading columns; a bare list discloses other people's
        # table names, and `owner` comes back null on list rows so it cannot be fixed after.
        owned = {r["id"] for r in _run("tables", "list", "--filter", f"owner.id={my_id}").get("data", [])}
        if a.table_id not in owned:
            print(json.dumps({"error": f"RULE 0: {a.table_id} is not owned by user {my_id} "
                                       "(or the table is not in the workspace this CLI session is logged into)"}), file=sys.stderr)
            return 2
        cols = _run("tables", "columns", "get", a.table_id)["data"]
        print(json.dumps(derive(a.table_id, cols), indent=1))
    else:
        payload = json.load(open(a.export))
        cols = payload.get("data", payload)
        tid = a.table_id
        print(json.dumps(derive(tid, cols), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

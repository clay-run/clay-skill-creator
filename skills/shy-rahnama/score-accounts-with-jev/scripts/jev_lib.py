"""
Shared helpers for the Jev lead-score skills: the rubric, the scoring code that runs inside Clay,
where keys and state live, and how Clay is driven.

The two sibling packages (accounts and contacts) ship the same scripts. Only the two constants
below differ, and every script reads them from here.

Rules this file keeps, each paid for once in an earlier skill:

  * Jev decides, code counts. Jev answers Choice, Noul and Score questions; every number, date,
    list lookup, weight and cut-off is computed in the code step. Jev's own documentation says it
    is weak at arithmetic, dates and counting, so nothing numeric is ever asked of it.
  * The scoring code is ONE source (CORE below). The Clay code steps run it, and the local
    preview execs the very same rendered text, so a preview score is the score the workflow
    returns for the same record. test_offline.py checks both paths agree.
  * Code steps import only `json` and `time`: Clay's runtime has no datetime, urllib, hashlib,
    base64 (and its code-test sandbox is more permissive than the runtime, so a green sandbox run
    proves nothing).
  * Keys are never printed, logged or returned to stdout. The agent driving these scripts must
    never see a key value.
  * State lives at a path this library COMPUTES from the Clay workspace, never one an agent
    composes per run.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

SKILL = "score-accounts-with-jev"
ENTITY = "account"          # "account" | "contact"

MIN_CLI = (1, 0, 0)
ENTITY_WORDS = {"account": ("account", "accounts", "ACCOUNT", "companies"),
                "contact": ("contact", "contacts", "CONTACT", "people")}
NOUN, NOUNS, AUDIENCE_TYPE, AUDIENCE_FLAG = ENTITY_WORDS[ENTITY]
A_NOUN = ("an " if NOUN[0] in "aeiou" else "a ") + NOUN

# Where Jev is reached. Versions are PINNED, not aliased: tier cut-offs are tuned against one
# model version, and TypeSafe's own docs say an alias moves when a release ships.
PROVIDERS = {
    "openrouter": {"label": "OpenRouter", "env": "OPENROUTER_API_KEY",
                   "url": "https://openrouter.ai/api/alpha/decisions", "model": "typesafe/jev-1.13",
                   "price_per_mtok": 0.042, "keys_at": "https://openrouter.ai/settings/keys",
                   "connection": "Jev (OpenRouter)"},
    "typesafe": {"label": "TypeSafe", "env": "TYPESAFE_API_KEY",
                 "url": "https://api.typesafe.ai/v1/systemone", "model": "jev-1.13.0",
                 "price_per_mtok": 0.042, "keys_at": "https://console.typesafe.ai/keys",
                 "connection": "Jev (TypeSafe)"},
}

# The output every scoring run returns. Keys are guaranteed present; blank is a value.
OUTPUT_KEYS = ("lead_score", "lead_tier", "score_status", "score_reasons", "needs_review",
               "coverage_pct", "criteria_json", "rubric", "jev_model", "jev_cost_usd", "error",
               "source_ref", "scored_at", "record_id", "isTerminal")
STATUSES = ("scored", "disqualified", "insufficient_data", "not_scored", "failed")

# Audiences fields the audience workflow writes (display name, output key, field type).
AUDIENCE_FIELDS = (("Jev lead score", "lead_score", "number"),
                   ("Jev lead tier", "lead_tier", "text"),
                   ("Jev score status", "score_status", "text"),
                   ("Jev score reasons", "score_reasons", "text"),
                   ("Jev score needs review", "needs_review", "text"),
                   ("Jev score rubric", "rubric", "text"),
                   ("Jev scored at", "scored_at", "date"))

RESERVED_INPUTS = ("source_ref", "record_id")


# ---------------------------------------------------------------- output

def say(msg):
    """Progress for the agent to relay. Plain words; never a key."""
    print(msg, flush=True)


def fail(msg, code=1):
    print("STOP: " + msg, file=sys.stderr, flush=True)
    raise SystemExit(code)


# ---------------------------------------------------------------- clay CLI

def clay(*args, inp=None, allow_fail=False, retries=2):
    """Run the clay CLI, JSON in and out. Retries a network timeout; a timed-out CREATE may still
    have landed, so creators look before re-creating."""
    cmd = ["clay", *args]
    if inp is not None:
        cmd += ["--input", inp if isinstance(inp, str) else json.dumps(inp)]
    last = None
    for attempt in range(retries + 1):
        r = subprocess.run(cmd, capture_output=True, text=True)
        out = r.stdout or ""
        try:
            data = json.loads(out) if out.strip() else {}
        except json.JSONDecodeError:
            data = {"raw": out}
        err = (data.get("error") or {}) if isinstance(data, dict) else {}
        if r.returncode == 0:
            return data
        last = (r.returncode, err or (r.stderr or out)[:600])
        if isinstance(err, dict) and err.get("code") == "network_timeout" and attempt < retries:
            time.sleep(3)
            continue
        break
    if allow_fail:
        return {"error": last[1], "exit": last[0]}
    fail("clay %s failed (exit %s): %s" % (" ".join(args[:3]), last[0], last[1]))


def paged(*args, limit=100):
    """Walk every page. A single page silently misses anything past it (a live bug once)."""
    rows, cursor = [], None
    for _ in range(200):
        call = list(args) + ["--limit", str(limit)]
        if cursor:
            call += ["--cursor", cursor]
        d = clay(*call)
        rows.extend(d.get("data") or [])
        cursor = d.get("cursor") or d.get("nextCursor")
        if not cursor:
            break
    return rows


def check_cli():
    r = subprocess.run(["clay", "--version"], capture_output=True, text=True)
    if r.returncode != 0:
        fail("The `clay` CLI is not on PATH. Install the Clay plugin and run its setup, then re-run.")
    raw = (r.stdout or "").strip()
    try:
        got = tuple(int(x) for x in raw.split("+")[0].split(".")[:3])
        if got < MIN_CLI:
            fail("clay %s is older than this skill needs. Run `clay update`, then re-run." % raw)
    except ValueError:
        pass
    return raw


def workspace():
    who = clay("whoami")
    ws = who.get("workspace") or {}
    if not ws.get("id"):
        fail("`clay whoami` did not return a workspace. Sign in with `clay login`, then re-run.")
    return {"id": str(ws["id"]), "name": ws.get("name")}


# ---------------------------------------------------------------- state

def state_dir(workspace_id=None):
    """~/.local/state/<skill>/<clay-workspace-id>/ — computed, never composed by the caller."""
    wid = str(workspace_id or workspace()["id"])
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    d = os.path.join(base, SKILL, wid)
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def load(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def slug(text):
    out, dash = [], False
    for ch in (text or "").lower():
        if ch.isalnum():
            out.append(ch)
            dash = False
        elif not dash and out:
            out.append("-")
            dash = True
    return "".join(out).strip("-")[:60] or "rubric"


def rubric_path(name, workspace_id=None):
    d = os.path.join(state_dir(workspace_id), "rubrics")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return os.path.join(d, slug(name) + ".json")


def list_rubrics(workspace_id=None):
    d = os.path.join(state_dir(workspace_id), "rubrics")
    if not os.path.isdir(d):
        return []
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))


def load_rubric(name=None, workspace_id=None):
    """The saved rubric by name; with no name, the only one there is."""
    names = list_rubrics(workspace_id)
    if not name:
        if len(names) == 1:
            name = names[0]
        elif not names:
            fail("No rubric saved for this workspace yet. Save one first: rubric_tool.py save <file>")
        else:
            fail("Several rubrics are saved (%s); say which with --rubric." % ", ".join(names))
    p = rubric_path(name, workspace_id)
    if not os.path.exists(p):
        fail("No rubric called %r. Saved: %s" % (name, ", ".join(names) or "none"))
    return validate_rubric(load(p, {}))


# ---------------------------------------------------------------- keys (.env)

def config_dir():
    """Shared by both Jev skills, so a key saved for one is found by the other."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "jev-lead-score")


def default_env_file():
    return os.path.join(config_dir(), ".env")


def env_files():
    """Where a key may already be, in the order they are honoured."""
    seen, out = set(), []
    for p in (os.path.join(os.getcwd(), ".env"), default_env_file()):
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            out.append(ap)
    return out


def parse_env(path):
    """KEY=value lines; `export ` and matching quotes stripped. Values are never printed."""
    out = {}
    try:
        with open(path) as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                if s.startswith("export "):
                    s = s[7:].strip()
                k, v = s.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                elif " #" in v:
                    v = v.split(" #", 1)[0].rstrip()
                out[k.strip()] = v
    except OSError:
        pass
    return out


def find_key(provider):
    """Where this provider's key is, without the value: ("environment", var) or (path, var), or
    None. The process environment wins, then ./.env, then the shared config file."""
    var = PROVIDERS[provider]["env"]
    if os.environ.get(var, "").strip():
        return ("environment", var)
    for p in env_files():
        if parse_env(p).get(var, "").strip():
            return (p, var)
    return None


def _key_value(provider):
    """Internal only: the value, for an HTTP call made in this process. Never returned to stdout."""
    where = find_key(provider)
    if not where:
        return None
    if where[0] == "environment":
        return os.environ[where[1]].strip()
    return parse_env(where[0])[where[1]].strip()


def write_env(path, var, value):
    """Set var=value in an env file (creating it 0600), replacing an earlier line for var."""
    value = (value or "").strip()
    if not value:
        fail("No key given; nothing saved.")
    if any(c in value for c in "\n\r"):
        fail("That key contains a line break; nothing saved.")
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    lines = []
    if os.path.exists(path):
        with open(path) as f:
            lines = [l.rstrip("\n") for l in f
                     if not (l.strip().startswith(var + "=") or l.strip().startswith("export " + var + "="))]
    lines.append("%s=%s" % (var, value))
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(path + ".tmp", path)
    os.chmod(path, 0o600)
    return path


def git_tracks_risk(path):
    """True when `path` sits in a git work tree and git would NOT ignore it — a key written there
    could be committed. A .gitignore added later untracks nothing, so check before writing."""
    d = os.path.dirname(os.path.abspath(path))
    while d and not os.path.isdir(d):         # the folder may not exist yet; its parent's repo still counts
        d = os.path.dirname(d)
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
        if r.returncode != 0 or r.stdout.strip() != "true":
            return False
        r = subprocess.run(["git", "-C", d, "check-ignore", "-q", os.path.abspath(path)],
                           capture_output=True)
        return r.returncode != 0
    except OSError:
        return False                           # no git on this machine: nothing can commit it


# ---------------------------------------------------------------- HTTP

def http(method, url, headers=None, body=None, timeout=60, retries=4):
    """JSON over HTTP with 429/529/5xx backoff honouring Retry-After. A named User-Agent, always:
    an edge in front of another API once rejected Python's default outright. Never logs headers."""
    data = None if body is None else json.dumps(body).encode()
    h = {"Accept": "application/json", "User-Agent": SKILL}
    if body is not None:
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode() or "{}"
                try:
                    return r.status, json.loads(raw)
                except json.JSONDecodeError:
                    return r.status, {"raw": raw[:500]}
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"raw": raw[:500]}
            if e.code in (429, 500, 502, 503, 504, 529) and attempt < retries:
                wait = e.headers.get("Retry-After")
                time.sleep(float(wait) if wait and wait.replace(".", "", 1).isdigit() else 2 ** attempt)
                continue
            return e.code, parsed
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return 0, {"error": str(e.reason)}


def call_jev(provider, request_body):
    """One Jev request from this machine, with the key from the environment or a .env file.
    Returns (status, body). Used by the preview and the key check; the workflow calls Jev from
    Clay with the key in a Clay connection instead."""
    key = _key_value(provider)
    if not key:
        fail("No %s key found (looked for %s in the environment, ./.env and %s). Save one first: "
             "jev_key.py save %s" % (PROVIDERS[provider]["label"], PROVIDERS[provider]["env"],
                                     default_env_file(), provider), code=3)
    return http("POST", PROVIDERS[provider]["url"], {"Authorization": "Bearer " + key}, request_body)


# ======================================================================= the rubric

RULE_KINDS = ("bands", "match", "lookup", "present", "days_since")
QUESTION_KINDS = ("noul", "choice", "score")
ABSTAIN = "not_enough_information"


def _num_or_fail(v, where, lo=None, hi=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        fail("%s: %r is not a number" % (where, v))
    if x != x or x in (float("inf"), float("-inf")):
        fail("%s: %r is not a finite number" % (where, v))
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        fail("%s: %g must be between %g and %g" % (where, x, lo, hi))
    return x


def _ident(v, where):
    s = str(v or "")
    if not s or not all(c.islower() or c.isdigit() or c == "_" for c in s) or not s[0].isalpha():
        fail("%s: %r must be lower_snake_case, starting with a letter" % (where, v))
    return s


def _bands(raw, where):
    if not isinstance(raw, list) or not raw:
        fail("%s: bands must be a non-empty list" % where)
    out = []
    for i, b in enumerate(raw):
        if not isinstance(b, dict):
            fail("%s: band %d must be an object" % (where, i + 1))
        nb = {"points": _num_or_fail(b.get("points", 0), "%s band %d points" % (where, i + 1)),
              "says": str(b.get("says") or "").strip()}
        if b.get("below") is not None:
            nb["below"] = _num_or_fail(b["below"], "%s band %d below" % (where, i + 1))
        out.append(nb)
    capped = [b for b in out if "below" in b]
    if capped != sorted(capped, key=lambda b: b["below"]):
        fail("%s: bands must be in increasing order of `below`" % where)
    if len([b for b in out if "below" not in b]) > 1 or ("below" not in out[-1] and len(out) > 1 and
                                                         any("below" not in b for b in out[:-1])):
        fail("%s: only the last band may leave `below` out (it catches everything above)" % where)
    return out


def validate_rubric(doc):
    """Check a rubric and return it normalised. Every script loads rubrics through this, so a
    rubric that reaches Clay has passed it. Fails naming the first problem."""
    if not isinstance(doc, dict):
        fail("rubric: expected a JSON object")
    ent = doc.get("entity") or ENTITY
    if ent != ENTITY:
        fail("rubric: this rubric is for %s records, but this skill scores %s" % (ent, NOUNS))
    name = str(doc.get("name") or "").strip()
    if not name:
        fail("rubric: give it a name")
    inputs_raw = doc.get("inputs")
    if not isinstance(inputs_raw, dict) or not inputs_raw:
        fail("rubric: `inputs` must name at least one field")
    inputs = {}
    for k, v in inputs_raw.items():
        k = _ident(k, "input")
        if k in RESERVED_INPUTS:
            fail("input %r is reserved; rename it" % k)
        v = v if isinstance(v, dict) else {"label": str(v)}
        t = v.get("type") or "text"
        if t not in ("text", "number", "date"):
            fail("input %s: type must be text, number or date" % k)
        inputs[k] = {"label": str(v.get("label") or k.replace("_", " ")), "type": t,
                     "required": bool(v.get("required")),
                     "max_chars": int(v.get("max_chars") or 4000)}
    ids = set()

    def new_id(i, where):
        i = _ident(i, where)
        if i in ids:
            fail("%s: id %r is used twice" % (where, i))
        ids.add(i)
        return i

    rules = []
    for n, r in enumerate(doc.get("rules") or [], start=1):
        where = "rule %d" % n
        if not isinstance(r, dict):
            fail("%s: must be an object" % where)
        rid = new_id(r.get("id"), where)
        kind = r.get("kind")
        if kind not in RULE_KINDS:
            fail("rule %s: kind must be one of %s" % (rid, ", ".join(RULE_KINDS)))
        inp = r.get("input")
        if inp not in inputs:
            fail("rule %s: input %r is not one of the rubric's inputs" % (rid, inp))
        nr = {"id": rid, "label": str(r.get("label") or rid.replace("_", " ")), "kind": kind, "input": inp,
              "disqualify": bool(r.get("disqualify")), "origin": str(r.get("origin") or "")}
        if kind in ("bands", "days_since"):
            nr["bands"] = _bands(r.get("bands"), "rule %s" % rid)
            if nr["disqualify"]:
                fail("rule %s: a %s rule cannot disqualify; use a match rule" % (rid, kind))
        elif kind == "match":
            vals = r.get("values")
            if not isinstance(vals, list) or not vals:
                fail("rule %s: `values` must be a non-empty list" % rid)
            nr["values"] = [str(x).strip().lower() for x in vals if str(x).strip()]
            nr["mode"] = r.get("mode") or "equals"
            if nr["mode"] not in ("equals", "contains"):
                fail("rule %s: mode must be equals or contains" % rid)
            nr["points"] = _num_or_fail(r.get("points", 0), "rule %s points" % rid)
            nr["miss_points"] = _num_or_fail(r.get("miss_points", 0), "rule %s miss_points" % rid)
            nr["says"] = str(r.get("says") or "").strip()
            nr["miss_says"] = str(r.get("miss_says") or "").strip()
        elif kind == "lookup":
            tbl = r.get("table")
            if not isinstance(tbl, dict) or not tbl:
                fail("rule %s: `table` must map values to points, e.g. {\"a\": {\"points\": 25, \"says\": \"tier A account\"}}" % rid)
            nr["table"] = {}
            for tk, tv in tbl.items():
                tv = tv if isinstance(tv, dict) else {"points": tv}
                nr["table"][str(tk).strip().lower()] = {
                    "points": _num_or_fail(tv.get("points", 0), "rule %s value %s points" % (rid, tk)),
                    "says": str(tv.get("says") or "%s %s" % (nr["label"].lower(), tk)).strip()}
            nr["miss_points"] = _num_or_fail(r.get("miss_points", 0), "rule %s miss_points" % rid)
            nr["miss_says"] = str(r.get("miss_says") or "").strip()
            if nr["disqualify"]:
                fail("rule %s: a lookup rule cannot disqualify; use a match rule" % rid)
        else:  # present
            nr["points"] = _num_or_fail(r.get("points", 0), "rule %s points" % rid)
            nr["says"] = str(r.get("says") or "").strip()
            nr["miss_says"] = str(r.get("miss_says") or "").strip()
        rules.append(nr)

    questions = []
    for n, q in enumerate(doc.get("questions") or [], start=1):
        where = "question %d" % n
        if not isinstance(q, dict):
            fail("%s: must be an object" % where)
        qid = new_id(q.get("id"), where)
        kind = q.get("kind")
        if kind not in QUESTION_KINDS:
            fail("question %s: kind must be one of %s (Jev's Noul, Choice, Score)" % (qid, ", ".join(QUESTION_KINDS)))
        reads = q.get("reads")
        if isinstance(reads, str):
            reads = [reads]
        if not isinstance(reads, list) or not reads or any(x not in inputs for x in reads):
            fail("question %s: `reads` must list the inputs it needs, from: %s" % (qid, ", ".join(inputs)))
        ins = q.get("instructions")
        if not ins or not isinstance(ins, (str, dict, list)):
            fail("question %s: needs `instructions` (the question Jev answers)" % qid)
        nq = {"id": qid, "label": str(q.get("label") or qid.replace("_", " ")), "kind": kind,
              "reads": list(reads), "instructions": ins, "origin": str(q.get("origin") or "")}
        if kind == "noul":
            crit = q.get("criteria") or {}
            if crit and not isinstance(crit, dict):
                fail("question %s: criteria must be {\"true\": ..., \"false\": ...}" % qid)
            nq["criteria"] = {k: crit[k] for k in ("true", "false") if crit.get(k)}
            pts = q.get("points") or {}
            nq["points"] = {"yes": _num_or_fail(pts.get("yes", 0), "question %s yes points" % qid),
                            "no": _num_or_fail(pts.get("no", 0), "question %s no points" % qid)}
            nq["says_yes"] = str(q.get("says_yes") or "").strip()
            nq["says_no"] = str(q.get("says_no") or "").strip()
            if q.get("disqualify_at") is not None:
                d = _num_or_fail(q["disqualify_at"], "question %s disqualify_at" % qid)
                if not 0.5 <= d <= 1:
                    fail("question %s: disqualify_at must be between 0.5 and 1" % qid)
                nq["disqualify_at"] = d
        elif kind == "choice":
            opts = q.get("options")
            if not isinstance(opts, dict) or len(opts) < 2:
                fail("question %s: a choice needs at least two options" % qid)
            no = {}
            for ok, ov in opts.items():
                ok = _ident(ok, "question %s option" % qid)
                ov = ov if isinstance(ov, dict) else {"means": ov}
                no[ok] = {"means": ov.get("means"), "points": _num_or_fail(ov.get("points", 0),
                                                                           "question %s option %s points" % (qid, ok)),
                          "says": str(ov.get("says") or ok.replace("_", " ")).strip(),
                          "disqualify": bool(ov.get("disqualify"))}
            if ABSTAIN not in no:
                no[ABSTAIN] = {"means": "The information given does not say enough to decide.",
                               "points": 0.0, "says": "not enough information", "disqualify": False}
            if len(no) > 255:
                fail("question %s: Jev takes at most 255 options" % qid)
            nq["options"] = no
            nq["disqualify_at"] = _num_or_fail(q.get("disqualify_at", 0.8), "question %s disqualify_at" % qid, 0.5, 1)
        else:  # score
            lv = q.get("levels")
            if not isinstance(lv, list) or not 2 <= len(lv) <= 10:
                fail("question %s: a score needs 2 to 10 `levels`, lowest first" % qid)
            nq["levels"] = lv
            nq["points"] = _num_or_fail(q.get("points", 0), "question %s points" % qid)
            if nq["points"] < 0:
                fail("question %s: a score's points must be positive (lowest level earns 0)" % qid)
        questions.append(nq)

    if not rules and not questions:
        fail("rubric: add at least one rule or question")
    tiers = doc.get("tiers") or [{"tier": "A", "min": 70}, {"tier": "B", "min": 45},
                                 {"tier": "C", "min": 25}, {"tier": "D", "min": 0}]
    tiers = sorted(({"tier": str(t["tier"]), "min": _num_or_fail(t["min"], "tier min")} for t in tiers),
                   key=lambda t: -t["min"])
    if tiers[-1]["min"] > 0:
        fail("tiers: the lowest tier must start at 0, or some scores get no tier")
    for t in tiers:
        if t["tier"] in STATUSES:
            fail("tiers: %r is reserved for a status; name the tier something else" % t["tier"])
    out = {"entity": ENTITY, "name": name, "version": int(doc.get("version") or 1),
           "about": doc.get("about") or {}, "inputs": inputs, "rules": rules, "questions": questions,
           "tiers": tiers, "tiers_origin": str(doc.get("tiers_origin") or ""),
           "confidence_floor": _num_or_fail(doc.get("confidence_floor", 0.6), "confidence_floor (a share, 0 to 1)", 0, 1),
           "min_coverage": _num_or_fail(doc.get("min_coverage", 0.5), "min_coverage (a share, 0 to 1)", 0, 1)}
    if max_points(out) <= 0:
        fail("rubric: nothing can earn points, so every score would be 0")
    return out


def item_max(it):
    """The most points one rule or question can add."""
    k = it["kind"]
    if k in ("bands", "days_since"):
        return max([b["points"] for b in it["bands"]] + [0])
    if k in ("match",):
        return max(it["points"], it["miss_points"], 0)
    if k == "lookup":
        return max([v["points"] for v in it["table"].values()] + [it["miss_points"], 0])
    if k == "present":
        return max(it["points"], 0)
    if k == "noul":
        return max(it["points"]["yes"], it["points"]["no"], 0)
    if k == "choice":
        return max([o["points"] for o in it["options"].values()] + [0])
    return max(it["points"], 0)


def max_points(r):
    return sum(item_max(i) for i in r["rules"] + r["questions"])


def estimate_tokens(r):
    """Rough input tokens per record (4 chars a token): every question plus a typical state."""
    q = len(json.dumps([jev_question_payload(x) for x in r["questions"]]))
    state = sum(min(v["max_chars"], 600) for k, v in r["inputs"].items()
                if any(k in x["reads"] for x in r["questions"]))
    return int((q + state) / 4) + 60


def jev_question_payload(q):
    """A rubric question as Jev takes it (the `questions` map entry)."""
    if q["kind"] == "noul":
        p = {"type": "noul", "instructions": q["instructions"]}
        if q.get("criteria"):
            p["criteria"] = q["criteria"]
        return p
    if q["kind"] == "choice":
        return {"type": "choice", "instructions": q["instructions"],
                "criteria": {k: v.get("means") for k, v in q["options"].items()}}
    return {"type": "score", "instructions": q["instructions"], "criteria": q["levels"]}


def rubric_card(r, provider=None):
    """The rubric as the installer reads it before anything is built. Plain text."""
    mx = max_points(r)
    L = ["Rubric: %s (v%d) — scores %s, 0 to 100" % (r["name"], r["version"], NOUNS), ""]
    L.append("Worked out in code (free, no Jev call):")
    if not r["rules"]:
        L.append("  (none)")
    for it in r["rules"]:
        src = r["inputs"][it["input"]]["label"]
        if it["kind"] in ("bands", "days_since"):
            unit = " days ago" if it["kind"] == "days_since" else ""
            parts = []
            lo = None
            for b in it["bands"]:
                rng = ("under %s" % _fmt(b["below"])) if lo is None and "below" in b else (
                    ("%s–%s" % (_fmt(lo), _fmt(b["below"] - 1))) if "below" in b else "%s+" % _fmt(lo if lo is not None else 0))
                parts.append("%s%s → %+g" % (rng, unit, b["points"]))
                lo = b.get("below", lo)
            L.extend(_wrapped("  %-26s from %s: " % (it["label"], src), parts))
        elif it["kind"] == "match":
            vals = ", ".join(it["values"][:6]) + (" …" if len(it["values"]) > 6 else "")
            verdict = "DISQUALIFIES" if it["disqualify"] else "%+g, otherwise %+g" % (it["points"], it["miss_points"])
            L.extend(_wrapped("  %-26s from %s: " % (it["label"], src),
                              ["%s %s → %s" % ("is one of" if it["mode"] == "equals" else "contains", vals, verdict)]))
        elif it["kind"] == "lookup":
            L.extend(_wrapped("  %-26s from %s: " % (it["label"], src),
                              ["%s → %+g" % (k.upper() if len(k) == 1 else k, v["points"]) for k, v in it["table"].items()]
                              + ["anything else → %+g" % it["miss_points"]]))
        else:
            L.append("  %-26s from %s: present → %+g" % (it["label"], src, it["points"]))
    L += ["", "Asked of Jev (one request per %s, all questions together):" % NOUN]
    if not r["questions"]:
        L.append("  (none)")
    for q in r["questions"]:
        reads = ", ".join(r["inputs"][k]["label"] for k in q["reads"])
        if q["kind"] == "noul":
            pure_dq = q.get("disqualify_at") and not (q["points"]["yes"] or q["points"]["no"])
            tail = [] if pure_dq else ["yes %+g" % q["points"]["yes"], "no %+g" % q["points"]["no"]]
            if q.get("disqualify_at"):
                tail.append("yes at %d%%+ DISQUALIFIES" % round(q["disqualify_at"] * 100))
            L.extend(_wrapped("  %-26s Noul (yes/no) on %s: " % (q["label"], reads), tail))
        elif q["kind"] == "choice":
            L.extend(_wrapped("  %-26s Choice on %s: " % (q["label"], reads),
                              ["%s %+g%s" % (k, o["points"], " (disqualifies)" if o["disqualify"] else "")
                               for k, o in q["options"].items()]))
        else:
            L.append("  %-26s Score (%d levels) on %s: 0 to %+g" % (q["label"], len(q["levels"]), reads, q["points"]))
    L += ["", "Most points possible: %s. Tiers: %s." % (_fmt(mx), ", ".join(
        "%s ≥ %s" % (t["tier"], _fmt(t["min"])) for t in r["tiers"])),
          "Below %d%% coverage (too little data to judge) %s is 'insufficient_data', not a low tier."
          % (round(r["min_coverage"] * 100), A_NOUN),
          "Answers under %d%% confidence are listed in needs_review." % round(r["confidence_floor"] * 100)]
    borrowed = [i["label"] for i in r["rules"] + r["questions"] if i.get("origin") == "default"]
    if r.get("tiers_origin") == "default":
        borrowed.append("tier cut-offs")
    if borrowed:
        L.append("Borrowed defaults you accepted rather than chose: %s." % ", ".join(borrowed))
    if provider:
        tok = estimate_tokens(r)
        cost = tok * PROVIDERS[provider]["price_per_mtok"] / 1e6
        L.append("Jev cost through %s: about %d input tokens per %s (output is free)," % (
            PROVIDERS[provider]["label"], tok, NOUN))
        L.append("so roughly $%.3f per 1,000 %s." % (cost * 1000, NOUNS))
    return "\n".join(L)


def _wrapped(head, parts, width=100):
    """head + parts joined by "; ", wrapped at word boundaries under the head's indent."""
    import textwrap
    glue = "\x00"          # keeps "x → +5" and "option +25" on one line
    text = "; ".join(parts).replace(" → ", glue + "→" + glue).replace(" days ago", glue + "days" + glue + "ago")
    text = text.replace(" DISQUALIFIES", glue + "DISQUALIFIES")
    for sign in "+-":
        for d in "0123456789":
            text = text.replace(" " + sign + d, glue + sign + d)
    lines = textwrap.wrap(text, width=width, initial_indent=head, subsequent_indent=" " * 29,
                          break_on_hyphens=False, break_long_words=False) or [head.rstrip()]
    return [l.replace(glue, " ") for l in lines]


def _fmt(x):
    x = float(x)
    return ("{:,.0f}".format(x) if x == int(x) else "{:,.2f}".format(x))


# ======================================================================= the code that runs in Clay
# One source. Rendered with the rubric and provider baked in as Python literals (repr, never
# json.dumps: a JSON `true` crashes a Python code step on every run). The intake step, the
# "score without Jev" step and the "score" step all carry the same CORE and differ only in their
# handler. The local preview execs the identical rendered text.

CORE = r'''import json
import time

RUBRIC = __RUBRIC__
PROVIDER = __PROVIDER__
ABSTAIN = "not_enough_information"


def _s(v):
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return str(v).strip()


def _num(v):
    """A number from text: '1,200' -> 1200; '51-200' or '1,001-5,000' -> the midpoint;
    '10k', '2.5M', '$3.4bn', '5 million', '1.2B' -> scaled. None when there is no number."""
    t = _s(v).replace(",", "").replace("$", "").lower()
    units = (("thousand", 1e3), ("million", 1e6), ("billion", 1e9), ("bn", 1e9), ("mn", 1e6),
             ("k", 1e3), ("m", 1e6), ("b", 1e9))
    nums, cur, i = [], "", 0
    while i <= len(t):
        ch = t[i] if i < len(t) else " "
        if ch.isdigit() or (ch == "." and cur and "." not in cur):
            cur += ch
        elif cur:
            n = float(cur)
            rest = t[i:].lstrip(" ")
            for word, mult in units:
                if rest.startswith(word) and not rest[len(word):len(word) + 1].isalpha():
                    n *= mult
                    break
            nums.append(n)
            cur = ""
            if len(nums) == 2:
                break
        i += 1
    if not nums:
        return None
    return (nums[0] + nums[1]) / 2 if len(nums) == 2 else nums[0]


def _civil_days(y, m, d):
    """Days since 1970-01-01 for a calendar date, by arithmetic alone. time.strptime is NOT used:
    it imports datetime and calendar behind the scenes, and Clay's code runtime has neither, so a
    date rule built on it returns nothing in Clay while working locally."""
    y -= 1 if m <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _days_since(v):
    """Whole days (UTC) from a date written YYYY-MM-DD, YYYY-MM or YYYY to now. None if unreadable."""
    parts = _s(v)[:10].replace("/", "-").split("-")
    try:
        y = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 and parts[1] else 1
        d = int(parts[2][:2]) if len(parts) > 2 and parts[2] else 1
    except Exception:
        return None
    if not (1900 <= y <= 2200 and 1 <= m <= 12 and 1 <= d <= 31):
        return None
    return int(time.time() // 86400) - _civil_days(y, m, d)


def _band(bands, x):
    for b in bands:
        if "below" not in b or x < b["below"]:
            return b
    return bands[-1]


def _norm(v):
    s = _s(v).lower()
    for p in ("https://", "http://", "www."):
        if s.startswith(p):
            s = s[len(p):]
    return s.rstrip("/").strip()


def _item(it, status, points, answer, confidence=None, says="", assessable=True, disq=False, verdict=None):
    """One criterion's result. `points` is what it earned (for a Jev answer, expected points over
    the probabilities); `verdict` is what the chosen answer is worth on its own, which decides
    whether the reason reads as counting for the record or against it."""
    return {"id": it["id"], "label": it["label"], "kind": it["kind"], "status": status,
            "answer": answer, "confidence": confidence, "points": round(points, 2),
            "max": it["_max"], "says": says, "assessable": assessable, "disqualifies": disq,
            "verdict": round(points if verdict is None else verdict, 2)}


def apply_rule(r, vals):
    raw = vals.get(r["input"], "")
    if not raw:
        return _item(r, "blocked_missing_input", 0.0, "", says="", assessable=False)
    k = r["kind"]
    if k in ("bands", "days_since"):
        x = _num(raw) if k == "bands" else _days_since(raw)
        if x is None:
            return _item(r, "unreadable", 0.0, raw[:80], says="", assessable=False)
        b = _band(r["bands"], x)
        return _item(r, "supplied", b["points"], raw[:80], says=b.get("says") or "")
    if k == "match":
        v = _norm(raw)
        hit = (v in r["values"]) if r["mode"] == "equals" else any(x in v for x in r["values"])
        if hit:
            return _item(r, "supplied", 0.0 if r["disqualify"] else r["points"], raw[:80],
                         says=r.get("says") or "", disq=r["disqualify"])
        return _item(r, "supplied", 0.0 if r["disqualify"] else r["miss_points"], raw[:80],
                     says=r.get("miss_says") or "")
    if k == "lookup":
        hit = r["table"].get(_norm(raw))
        if hit:
            return _item(r, "supplied", hit["points"], raw[:80], says=hit.get("says") or "")
        return _item(r, "supplied", r["miss_points"], raw[:80], says=r.get("miss_says") or "")
    return _item(r, "supplied", r["points"], "present", says=r.get("says") or "")


def question_payload(q):
    if q["kind"] == "noul":
        p = {"type": "noul", "instructions": q["instructions"]}
        if q.get("criteria"):
            p["criteria"] = q["criteria"]
        return p
    if q["kind"] == "choice":
        return {"type": "choice", "instructions": q["instructions"],
                "criteria": dict((k, v.get("means")) for k, v in q["options"].items())}
    return {"type": "score", "instructions": q["instructions"], "criteria": q["levels"]}


def intake(inp):
    """Everything decided before Jev is asked: rules, which questions have the data they read,
    the one request body. A question whose inputs are all blank is never sent."""
    vals = {}
    for k, spec in RUBRIC["inputs"].items():
        vals[k] = _s(inp.get(k))[:spec.get("max_chars", 4000)]
    missing = [k for k, spec in RUBRIC["inputs"].items() if spec.get("required") and not vals[k]]
    rules = [apply_rule(r, vals) for r in RUBRIC["rules"]]
    dq_by_rule = [x for x in rules if x["disqualifies"]]
    askable = [q for q in RUBRIC["questions"] if any(vals.get(k) for k in q["reads"])]
    blocked = [q["id"] for q in RUBRIC["questions"] if q not in askable]
    ask = bool(askable) and not missing and not dq_by_rule
    state = {}
    for q in askable:
        for k in q["reads"]:
            if vals.get(k):
                state[k] = vals[k]
    body = {"model": PROVIDER["model"], "state": state,
            "questions": dict((q["id"], question_payload(q)) for q in askable)} if ask else {}
    return {"ask": ask, "missing": missing, "rules": rules, "asked": [q["id"] for q in askable] if ask else [],
            "blocked": blocked, "skipped_reason": ("missing required input: " + ", ".join(missing)) if missing else (
                "disqualified by a rule before asking Jev" if dq_by_rule else ("" if askable else "no question had the data it reads")),
            "jev_url": PROVIDER["url"], "jev_body": json.dumps(body) if ask else "",
            "jev_headers": {"Content-Type": "application/json"},
            "source_ref": _s(inp.get("source_ref")), "record_id": _s(inp.get("record_id"))}


def _answer_item(q, a, floor):
    """(item, review note) for one Jev answer. Points are the EXPECTED points over Jev's
    probabilities, so an answer Jev is unsure of moves the score less than a sure one."""
    k = q["kind"]
    if not isinstance(a, dict):
        return _item(q, "no_answer", 0.0, "", assessable=False), ""
    if k == "noul":
        p = float(a.get("noul") or 0.0)
        pts = p * q["points"]["yes"] + (1 - p) * q["points"]["no"]
        conf = abs(2 * p - 1)
        yes = p >= 0.5
        disq = bool(q.get("disqualify_at")) and p >= q["disqualify_at"]
        it = _item(q, "answered", pts, "yes" if yes else "no", round(conf, 2),
                   says=(q.get("says_yes") if yes else q.get("says_no")) or "", disq=disq,
                   verdict=q["points"]["yes"] if yes else q["points"]["no"])
        if q.get("disqualify_at") and not (q["points"]["yes"] or q["points"]["no"]):
            # A pure disqualifier: worth a look only when it leans yes but stops short of the bar.
            note = ("%s: possibly (%d%% yes, disqualifies at %d%%)" % (q["label"], round(p * 100),
                    round(q["disqualify_at"] * 100))) if 0.5 <= p < q["disqualify_at"] else ""
        else:
            note = "%s: unsure (%d%% yes)" % (q["label"], round(p * 100)) if conf < floor else ""
        return it, note
    if k == "choice":
        probs = a.get("probabilities") or {}
        pts = 0.0
        for opt, o in q["options"].items():
            pts += float(probs.get(opt) or 0.0) * o["points"]
        chosen = a.get("choice") or (max(probs, key=probs.get) if probs else "")
        conf = float(a.get("confidence") if a.get("confidence") is not None else 0.0)
        disq = any(o["disqualify"] and float(probs.get(opt) or 0.0) >= q["disqualify_at"]
                   for opt, o in q["options"].items())
        abstained = chosen == ABSTAIN
        if abstained:
            pts = 0.0       # "not enough information" is not a partial yes: it earns nothing
        says = (q["options"].get(chosen) or {}).get("says") or chosen
        it = _item(q, "abstained" if abstained else "answered", pts, chosen, round(conf, 2),
                   says=says, assessable=not abstained, disq=disq,
                   verdict=(q["options"].get(chosen) or {}).get("points", 0.0))
        note = ""
        if conf < floor and not abstained:
            top = sorted(probs.items(), key=lambda kv: -float(kv[1] or 0))[:2]
            note = "%s: unsure (%s)" % (q["label"], ", ".join("%s %d%%" % (o, round(float(p) * 100)) for o, p in top))
        return it, note
    s = float(a.get("score") or 0.0)
    n = len(q["levels"])
    pts = max(0.0, min(1.0, s / (n - 1))) * q["points"]
    conf = float(a.get("confidence") if a.get("confidence") is not None else 0.0)
    lvl = q["levels"][int(max(0, min(n - 1, round(s))))]
    level = int(max(0, min(n - 1, round(s))))
    it = _item(q, "answered", pts, "level %d of %d" % (level, n - 1), round(conf, 2),
               says=lvl if isinstance(lvl, str) else json.dumps(lvl),
               verdict=float(level) / (n - 1) * q["points"])
    it["position"] = round(s, 2)
    note = "%s: unsure (level %.1f of %d)" % (q["label"], s, n - 1) if conf < floor else ""
    return it, note


JEV_ERRORS = {401: "Jev refused the key (401): it is wrong or revoked (in Clay, the connection on '3 Ask Jev')",
              402: "Jev says the account is out of credit (402)",
              403: "Jev refused the request (403): check the key's permissions",
              422: "Jev rejected the request as malformed (422)",
              429: "Jev rate limit (429): re-run these records later",
              529: "Jev is overloaded (529): re-run these records later"}


def score(ix, status_code=None, body=None):
    """The verdict for one record. Keys are always all present."""
    floor = RUBRIC["confidence_floor"]
    items = list(ix.get("rules") or [])
    model, cost, err = "not called", 0.0, ""
    answers = {}
    if ix.get("ask"):
        b = body
        if isinstance(b, str):
            try:
                b = json.loads(b)
            except Exception:
                b = {"raw": b}
        b = b if isinstance(b, dict) else {}
        answers = b.get("answers") if isinstance(b.get("answers"), dict) else {}
        try:
            code = int(float(status_code))
        except Exception:
            code = 0
        if code != 200 or not answers:
            err = JEV_ERRORS.get(code) or ("Jev call failed (HTTP %s): %s" % (code, json.dumps(b)[:300]))
            return finish(ix, [], "failed", 0, 0, "", "", model, 0.0, err)
        model = _s(b.get("model")) or PROVIDER["model"]
        usage = b.get("usage") or {}
        cost = usage.get("cost")
        if cost is None:
            cost = float(usage.get("input_tokens") or 0) * PROVIDER["price_per_mtok"] / 1000000.0
    notes = []
    for q in RUBRIC["questions"]:
        if q["id"] in (ix.get("blocked") or []):
            items.append(_item(q, "blocked_missing_input", 0.0, "", assessable=False))
        elif q["id"] not in (ix.get("asked") or []):
            items.append(_item(q, "not_needed", 0.0, "", assessable=False))
        else:
            it, note = _answer_item(q, answers.get(q["id"]), floor)
            items.append(it)
            if note:
                notes.append(note)
    total = sum(i["max"] for i in items) or 1.0
    earned = sum(i["points"] for i in items)
    covered = sum(i["max"] for i in items if i["assessable"])
    s100 = int(round(max(0.0, min(100.0, 100.0 * earned / total))))
    coverage = int(round(100.0 * covered / total))
    dq = [i for i in items if i["disqualifies"]]
    if ix.get("missing"):
        status, tier = "not_scored", "not_scored"
    elif dq:
        status, tier = "disqualified", "disqualified"
    elif coverage < RUBRIC["min_coverage"] * 100:
        status, tier = "insufficient_data", "insufficient_data"
    else:
        status = "scored"
        tier = next(t["tier"] for t in RUBRIC["tiers"] if s100 >= t["min"])
    reasons = []
    if dq:
        reasons.append("Disqualified: " + "; ".join((i["says"] or i["label"]) for i in dq))
    if ix.get("missing"):
        reasons.append("Not scored: missing " + ", ".join(ix["missing"]))
    # FOR: the answer itself is worth at least half the criterion's points; shown as "(+25)".
    # AGAINST: the answer itself is worth less than half; shown as "(2 of 25)", so a low score
    # names what pulled it down, and points earned only through Jev's doubt never read as a win.
    counted = [i for i in items if i["assessable"] and i["max"] > 0]
    pro = sorted([i for i in counted if i["verdict"] * 2 >= i["max"] and i["points"] >= 0.5],
                 key=lambda i: -i["points"])
    con = sorted([i for i in counted if i["verdict"] * 2 < i["max"]],
                 key=lambda i: -(i["max"] - i["points"]))
    for i in pro[:4]:
        reasons.append("%s: %s (%+d)" % (i["label"], i["says"] or i["answer"], round(i["points"])))
    for i in con[:3]:
        reasons.append("%s: %s (%d of %d)" % (i["label"], i["says"] or i["answer"], round(i["points"]), round(i["max"])))
    gaps = [i["label"] for i in items if not i["assessable"] and i["max"] > 0]
    if gaps and status in ("scored", "insufficient_data"):
        reasons.append("No data for: " + ", ".join(gaps[:4]) + (" …" if len(gaps) > 4 else ""))
    return finish(ix, items, status, s100, coverage, " | ".join(reasons) or "no criterion added points",
                  "; ".join(notes) or "none", model, cost, err, tier)


def finish(ix, items, status, s100, coverage, reasons, review, model, cost, err, tier=None):
    crit = [dict((k, v) for k, v in i.items() if k not in ("assessable", "verdict")) for i in items]
    return {"lead_score": s100, "lead_tier": tier or status, "score_status": status,
            "score_reasons": (reasons or ("Not scored: " + err if err else "none"))[:500],
            "needs_review": (review or "none")[:500], "coverage_pct": coverage,
            "criteria_json": json.dumps(crit), "rubric": "%s v%d" % (RUBRIC["name"], RUBRIC["version"]),
            "jev_model": model, "jev_cost_usd": round(float(cost or 0.0), 8), "error": err,
            "source_ref": ix.get("source_ref") or "", "record_id": ix.get("record_id") or "",
            "scored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "isTerminal": True}
'''

INTAKE_HANDLER = r'''

INPUT_KEYS = __INPUT_KEYS__


def handler(context):
    inp = {}
    for k in INPUT_KEYS:
        try:
            inp[k] = context.get_input("in_" + k)
        except Exception:
            inp[k] = None
    return intake(inp)
'''

SCORE_HANDLER = r'''


def handler(context):
    ix = context.get_input("intake") or {}
    try:
        code = context.get_input("status_code")
    except Exception:
        code = None
    try:
        body = context.get_input("body")
    except Exception:
        body = None
    return score(ix, code, body)
'''

NOJEV_HANDLER = r'''


def handler(context):
    return score(context.get_input("intake") or {})
'''


def _with_max(r):
    """The rubric as baked into the code step: each item carries its own max points."""
    r = json.loads(json.dumps(r))
    for it in r["rules"] + r["questions"]:
        it["_max"] = item_max(it)
    return r


def render(handler, rubric, provider):
    p = PROVIDERS[provider]
    prov = {"url": p["url"], "model": p["model"], "price_per_mtok": p["price_per_mtok"]}
    src = CORE.replace("__RUBRIC__", repr(_with_max(rubric))).replace("__PROVIDER__", repr(prov))
    keys = list(rubric["inputs"]) + list(RESERVED_INPUTS)
    return src + handler.replace("__INPUT_KEYS__", repr(keys))


def load_core(rubric, provider):
    """The rendered scoring code as a module-like namespace, for the local preview and tests.
    It is the same text the Clay code steps run."""
    ns = {"__name__": "jev_core"}
    exec(compile(render(NOJEV_HANDLER, rubric, provider), "<jev_core>", "exec"), ns)
    return ns


def score_record(rubric, provider, record, call=None):
    """Score one record locally exactly as the workflow would. `call(body_dict)` -> (status, body)
    is the Jev call; by default it uses the local .env key."""
    core = load_core(rubric, provider)
    ix = core["intake"](record)
    if not ix["ask"]:
        return core["score"](ix)
    status, body = (call or (lambda b: call_jev(provider, b)))(json.loads(ix["jev_body"]))
    return core["score"](ix, status, body)


# ======================================================================= mapping a source onto the inputs
# A table's columns or an audience's fields are mapped onto the rubric's inputs by name, and the
# proposal is SHOWN for correction: confirming a mapping beats reciting one, and a wrong guess is
# visible beside the right one.

def _tokens(s):
    out, cur = [], ""
    for ch in str(s or "").lower():
        if ch.isalnum():
            cur += ch
        elif cur:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


FILLER = {"on", "of", "the", "a", "an", "at", "in", "current", "or", "and", "from", "its", "their"}


def _words(s):
    return set(_tokens(s)) - FILLER


def propose_map(inputs, columns):
    """{input key: column id or None}. columns = [{"id":..., "name":...}]. Exact name or label
    first; then the column sharing the most meaningful words with the key and label (at least
    half of the column's words, and at least one). Never reuses a column. It is a PROPOSAL: the
    caller shows it for correction."""
    out, used = {}, set()
    for key, spec in inputs.items():
        exact = [_tokens(key), _tokens(spec.get("label"))]
        kw, lw = _words(key), _words(spec.get("label"))
        want = kw | lw
        best, best_score = None, 0.0
        for c in columns:
            if c["id"] in used:
                continue
            if _tokens(c.get("name")) in exact:
                best, best_score = c["id"], 9.0
                break
            ct = _words(c.get("name"))
            if not ct:
                continue
            shared = len(ct & want)
            score = shared / float(len(ct)) + shared / float(len(want) or 1)
            # A shared word must come from the input's own name, or two from its label: "Company"
            # is not "What the company does" just because they share "company".
            strong = bool(ct & kw) or len(ct & lw) >= 2
            if strong and shared * 2 >= len(ct) and score > best_score:
                best, best_score = c["id"], score
        out[key] = best
        if best:
            used.add(best)
    return out


def apply_overrides(mapping, columns, overrides):
    """--map key=Column name (or id), repeatable. Unknown columns stop the run rather than map to nothing."""
    by_name = {str(c.get("name") or "").strip().lower(): c["id"] for c in columns}
    ids = {c["id"] for c in columns}
    for o in overrides or []:
        if "=" not in o:
            fail("--map takes key=column, got %r" % o)
        k, v = o.split("=", 1)
        k, v = k.strip(), v.strip()
        if k not in mapping:
            fail("--map: %r is not one of the rubric's inputs (%s)" % (k, ", ".join(mapping)))
        if v in ("", "-", "none"):
            mapping[k] = None
        elif v in ids:
            mapping[k] = v
        elif v.lower() in by_name:
            mapping[k] = by_name[v.lower()]
        else:
            fail("--map: no column or field called %r" % v)
    return mapping


def mapping_card(inputs, mapping, columns):
    names = {c["id"]: c.get("name") for c in columns}
    L = ["%-24s <- %s" % ("input", "your column / field")]
    for k, spec in inputs.items():
        src = mapping.get(k)
        L.append("%-24s <- %s%s" % (k, (names.get(src) or src) if src else "(nothing mapped)",
                                    "   REQUIRED" if spec.get("required") and not src else ""))
    return "\n".join(L)

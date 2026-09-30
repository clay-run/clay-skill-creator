"""
Shared helpers for the "Person Active At Company (Jev)" skill: the code that runs inside Clay,
where keys and state live, and how Clay is driven.

Rules this file keeps, each paid for once in an earlier skill:

  * Jev judges, code decides. A LinkedIn work history is a LIST of roles, and Jev's own
    documentation says it does not count or compare dates reliably and does best with one
    literal question per item. So code finds the roles that could be at the company, works out
    every date, and asks Jev small questions about ONE role each: is this the same company, what
    kind of role is it, is it still held, is it the main job. Code combines the answers into one
    verdict from a fixed set.
  * The verdict code is ONE source (CORE below). The Clay code steps run it, and the local
    preview execs the very same rendered text, so a preview verdict is the verdict the workflow
    returns for the same profile. test_offline.py checks both paths agree.
  * Code steps import only `json` and `time`: Clay's runtime has no datetime, re, urllib (its
    code-test sandbox is more permissive than the runtime, so a green sandbox run proves nothing).
  * Keys are never printed, logged or returned to stdout.
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

SKILL = "check-employment-with-jev"
WORKFLOW_NAME = "Person Active At Company (Jev)"
MIN_CLI = (1, 0, 0)

# Where Jev is reached. Versions are PINNED, not aliased: TypeSafe's own docs say an alias moves
# when a release ships, and the thresholds below were tuned against one version.
PROVIDERS = {
    "openrouter": {"label": "OpenRouter", "env": "OPENROUTER_API_KEY",
                   "url": "https://openrouter.ai/api/alpha/decisions", "model": "typesafe/jev-1.13",
                   "price_per_mtok": 0.042, "keys_at": "https://openrouter.ai/settings/keys"},
    "typesafe": {"label": "TypeSafe", "env": "TYPESAFE_API_KEY",
                 "url": "https://api.typesafe.ai/v1/systemone", "model": "jev-1.13.0",
                 "price_per_mtok": 0.042, "keys_at": "https://console.typesafe.ai/keys"},
}

# The workflow's interface. Inputs arrive as flat fields; every output key is always present.
INPUT_KEYS = ("company_name", "company_domain", "company_linkedin_url", "profile", "linkedin_url",
              "full_name", "skip_enrichment", "max_profile_age_days", "source_ref")
OUTPUT_KEYS = ("active_at_company", "relationship", "verdict_confidence", "check_status", "check_note", "company_checked", "evidence",
               "needs_review", "role_title", "role_company", "role_started", "role_ended",
               "months_in_role", "other_current_roles", "main_employer", "profile_source",
               "profile_age_days", "roles_json", "jev_model", "jev_cost_usd", "error", "source_ref",
               "checked_at")
ACTIVE_VALUES = ("yes", "passive", "no", "unsure", "not_checked")
RELATIONSHIPS = ("primary_job", "side_job", "advisor_or_board", "investor", "honorary", "former",
                 "no_record", "unknown")
CHECK_STATUSES = ("checked", "no_profile", "blocked_missing_input", "failed")

ENRICH_ACTION = "cpj-enrich-person"      # Clay's own "Enrich person" (LinkedIn URL in, profile out)
ENRICH_CREDITS = 0.5                      # as the action catalogue listed it on 2026-09-29


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


# ---------------------------------------------------------------- keys (.env)

def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "jev")


def default_env_file():
    return os.path.join(config_dir(), ".env")


def env_files():
    """Where a key may already be, in the order they are honoured. The last one is where the
    shared location other Jev tools may use, so a key already saved there is found too."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    seen, out = set(), []
    for p in (os.path.join(os.getcwd(), ".env"), default_env_file(),
              os.path.join(base, "jev-lead-score", ".env")):
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
                out[k.strip()] = v
    except OSError:
        pass
    return out


def find_key(provider):
    """Where this provider's key is, without the value: ("environment", var) or (path, var), or
    None. The process environment wins, then the files in env_files() order."""
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
    r = subprocess.run(["git", "-C", d, "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "true":
        return False
    r = subprocess.run(["git", "-C", d, "check-ignore", "-q", os.path.abspath(path)], capture_output=True)
    return r.returncode != 0


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
    Clay with the same key, written into its first step by build_workflow.py."""
    key = _key_value(provider)
    if not key:
        fail("No %s key found (looked for %s in the environment and in %s). Save one first: "
             "jev_key.py save %s" % (PROVIDERS[provider]["label"], PROVIDERS[provider]["env"],
                                     ", ".join(env_files()), provider), code=3)
    return http("POST", PROVIDERS[provider]["url"], {"Authorization": "Bearer " + key}, request_body)


# ======================================================================= the code that runs in Clay
# One source, rendered with the provider baked in as a Python literal (repr, never json.dumps: a
# JSON `true` crashes a Python code step). "1 Intake", "2r Prepare", "3b Verdict without Jev" and
# "5 Verdict" all carry the same CORE and differ only in their handler. The local preview execs
# the identical rendered text.

CORE = r'''import json
import time

PROVIDER = __PROVIDER__
MAX_ROLES = 6            # roles at (or possibly at) the company that get questions
MAX_CONTEXT = 5          # other current roles shown to Jev as context
FLOOR = 0.6              # an answer less sure than this is listed in needs_review
LEGAL = set(["inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation", "co", "company",
             "gmbh", "ag", "sa", "sas", "sarl", "srl", "spa", "bv", "nv", "plc", "lp", "llp", "pty",
             "pvt", "oy", "ab", "as", "kk", "the", "group", "holdings", "holding", "and"])
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]
TWO_PART = set(["co", "com", "org", "net", "ac", "gov", "edu", "ne", "or"])

KIND_OPTIONS = {
    "employee": "Works for this company as an employee or executive: a job title such as engineer, "
                "manager, director, head of, vice president, partner, or chief officer. Includes "
                "founders, co-founders and owners who run the company.",
    "contractor": "Works for this company as a contractor, consultant, freelancer, fractional or "
                  "interim executive, or through an agency, rather than as an employee.",
    "intern": "An intern, apprentice, trainee or working student at this company.",
    "advisor_or_board": "An advisor, board member, board observer, mentor or committee member of "
                        "this company, without working in it day to day.",
    "investor": "An investor in this company: angel, backer, shareholder or limited partner. A "
                "partner or principal EMPLOYED by an investment firm is an employee of that firm.",
    "honorary": "A volunteer, ambassador, community member, alumnus, fellow, emeritus, or an "
                "honorary or ceremonial title at this company.",
    "not_enough_information": "The title and description do not say what the role is.",
}
WORKING = ("employee", "contractor", "intern")
PASSIVE = ("advisor_or_board", "investor", "honorary")


# ---------------------------------------------------------------- small readers

def _s(v):
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return str(v).strip()


def _obj(v):
    """A dict from a dict or from JSON text; {} otherwise. Table columns can arrive as either."""
    if isinstance(v, dict):
        return v
    t = _s(v)
    if t[:1] in ("{", "["):
        try:
            o = json.loads(t)
        except Exception:
            return {}
        if isinstance(o, list):
            return {"experience": o}
        return o if isinstance(o, dict) else {}
    return {}


def _idstr(v):
    """A record id as text: 1000001, never 1000001.0 (a number can arrive as a float)."""
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return _s(v)


def _first(d, keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, "", [], {}):
            return d.get(k)
    return None


def _truthy(v):
    return _s(v).lower() in ("true", "yes", "1", "y")


def _date(v):
    """YYYY-MM-DD, YYYY-MM or YYYY from what profiles carry: ISO text, 'Mar 2021', 'March 2021',
    '2021', or {"year":2021,"month":3,"day":1}. '' when there is no date."""
    if isinstance(v, dict):
        y = v.get("year")
        if not y:
            return ""
        out = "%04d" % int(y)
        if v.get("month"):
            out += "-%02d" % int(v["month"])
            if v.get("day"):
                out += "-%02d" % int(v["day"])
        return out
    t = _s(v).lower().replace(",", " ").replace(".", " ")
    if not t or t in ("present", "current", "now", "null", "none"):
        return ""
    if len(t) >= 4 and t[:4].isdigit():
        head = t[:10]
        parts = head.split("-")
        if len(parts) >= 2 and parts[1][:2].isdigit():
            if len(parts) >= 3 and parts[2][:2].isdigit():
                return "%s-%s-%s" % (parts[0], parts[1][:2], parts[2][:2])
            return "%s-%s" % (parts[0], parts[1][:2])
        return t[:4]
    words = t.split()
    year = next((w for w in words if len(w) == 4 and w.isdigit()), "")
    if not year:
        return ""
    for w in words:
        for i, m in enumerate(MONTHS):
            if len(w) >= 3 and m.startswith(w):
                return "%s-%02d" % (year, i + 1)
    return year


def _day_number(y, m, d):
    """Days from 1970-01-01 to a calendar date, by arithmetic. NOT time.strptime/mktime: strptime
    imports datetime under the hood, which Clay's code runtime does not have, so it fails there
    (silently, inside a try) while working everywhere else. Measured in a live run."""
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _epoch(d):
    """Seconds since 1970 for YYYY[-MM[-DD]] (month and day default to 1); None if unreadable."""
    if not d or len(d) < 4 or not d[:4].isdigit():
        return None
    try:
        y = int(d[:4])
        m = int(d[5:7]) if len(d) >= 7 else 1
        dd = int(d[8:10]) if len(d) >= 10 else 1
        if not (1 <= m <= 12 and 1 <= dd <= 31):
            return None
        return _day_number(y, m, dd) * 86400.0
    except Exception:
        return None


def _days_since(d):
    e = _epoch(d)
    return None if e is None else int((time.time() - e) // 86400)


def _words_date(d):
    """'March 2021' for Jev: it reads words better than digits, and it never compares them."""
    if not d:
        return "not stated"
    if len(d) >= 7:
        try:
            return "%s %s" % (MONTHS[int(d[5:7]) - 1].capitalize(), d[:4])
        except Exception:
            return d[:4]
    return d[:4]


def _months_between(a, b=None):
    ea = _epoch(a)
    eb = _epoch(b) if b else time.time()
    if ea is None or eb is None or eb < ea:
        return None
    return int((eb - ea) // (86400 * 30.44))


def _domain(v):
    t = _s(v).lower()
    for p in ("https://", "http://"):
        if t.startswith(p):
            t = t[len(p):]
    t = t.split("/")[0].split("?")[0].split(":")[0].strip().strip(".")
    if t.startswith("www."):
        t = t[4:]
    return t if "." in t and " " not in t else ""


def _root(d):
    parts = [p for p in d.split(".") if p]
    if len(parts) >= 3 and parts[-2] in TWO_PART and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _li_company(v):
    """The company page slug (or numeric id) from a LinkedIn company URL; '' otherwise."""
    t = _s(v).lower()
    for marker in ("linkedin.com/company/", "linkedin.com/school/", "linkedin.com/showcase/"):
        if marker in t:
            return t.split(marker, 1)[1].split("/")[0].split("?")[0].strip()
    return ""


def _name_tokens(v):
    return set(w for w in _tokens(v) if len(w) >= 2)


def _li_person(v):
    t = _s(v).lower()
    return "linkedin.com/in/" in t or "linkedin.com/sales/" in t or "linkedin.com/talent/" in t


def _tokens(name):
    out, cur = [], ""
    for ch in _s(name).lower() + " ":
        if ch.isalnum():
            cur += ch
        elif cur:
            out.append(cur)
            cur = ""
    return [t for t in out if t not in LEGAL]


# ---------------------------------------------------------------- reading a profile

ROLE_LISTS = ("experience", "experiences", "positions", "work_experience", "employment_history",
              "jobs", "employments", "workExperience", "current_experience")


def _roles_list(p):
    for k in ROLE_LISTS:
        v = p.get(k)
        if isinstance(v, list) and v:
            return v
    for k in ("profile", "person", "data", "result"):
        if isinstance(p.get(k), dict):
            got = _roles_list(p[k])
            if got:
                return got
    return []


def _role(x):
    """One role in one shape, whatever the provider called the fields."""
    if not isinstance(x, dict):
        return None
    comp = x.get("company")
    cd = comp if isinstance(comp, dict) else {}
    company = _first(cd, ("name", "company_name")) if cd else comp
    company = _s(company or _first(x, ("company_name", "companyName", "org", "organization",
                                        "organization_name", "employer", "employer_name")))
    title = x.get("title")
    if isinstance(title, dict):
        title = title.get("name")
    title = _s(title or _first(x, ("job_title", "position", "role", "name_of_role")))
    if not company and not title:
        return None
    start = _date(_first(x, ("start_date", "starts_at", "startDate", "start", "date_from", "from")))
    end = _date(_first(x, ("end_date", "ends_at", "endDate", "end", "date_to", "to")))
    cur = _first(x, ("is_current", "current", "isCurrent", "is_primary"))
    cur = None if cur is None else _truthy(cur)
    domain = _domain(_first(cd, ("website", "domain", "company_domain")) if cd else "") or \
        _domain(_first(x, ("company_domain", "domain", "company_website", "website")))
    li = _li_company(_first(cd, ("linkedin_url", "url", "linkedin")) if cd else "") or \
        _li_company(_first(x, ("company_linkedin_url", "company_url", "url", "linkedin_url")))
    desc = _s(_first(x, ("summary", "description", "desc")))[:300]
    ended_past = bool(end) and (_days_since(end) or 0) > 0
    is_open = (cur is True) or (not end and cur is not False) or (bool(end) and not ended_past)
    return {"company": company[:120], "title": title[:160], "start": start, "end": end,
            "is_current": cur, "open": bool(is_open), "domain": domain, "linkedin": li,
            "description": desc, "work_type": _s(_first(x, ("location_type", "employment_type",
                                                              "workplace_type")))[:40]}


def read_profile(p):
    """(roles, facts) from a profile dict. Roles are de-duplicated on company+title+start."""
    roles, seen = [], set()
    for x in _roles_list(p):
        r = _role(x)
        if not r:
            continue
        k = (r["company"].lower(), r["title"].lower(), r["start"])
        if k in seen:
            continue
        seen.add(k)
        roles.append(r)
    refreshed = _date(_first(p, ("last_refresh", "last_updated", "updated_at", "lastRefresh")))
    facts = {"headline": _s(_first(p, ("headline", "occupation")))[:200],
             "name": _s(_first(p, ("name", "full_name", "fullName"))),
             "refreshed": refreshed, "age_days": _days_since(refreshed)}
    return roles, facts


# ---------------------------------------------------------------- is this role at the company?

def _label_tokens(dom):
    """The words of a website's name: 'fabrikam-freight.co.uk' -> {'fabrikam', 'freight'}."""
    return set(w for w in _tokens(_root(dom).split(".")[0].replace("-", " ")) if len(w) >= 3)


def target_of(inp):
    name = _s(inp.get("company_name"))[:120]
    dom = _domain(inp.get("company_domain"))
    li = _li_company(inp.get("company_linkedin_url"))
    toks = set(_tokens(name))
    if dom:
        toks |= _label_tokens(dom)
    return {"name": name, "domain": dom, "linkedin": li, "tokens": toks}


def identity(r, t):
    """How this role's company relates to the target, decided in code where code can decide:
    'confirmed' (same website or same LinkedIn company page), 'name_match' / 'name_overlap' /
    'id_conflict' (Jev is asked whether it is the same company), or 'none'."""
    if t["domain"] and r["domain"] and _root(t["domain"]) == _root(r["domain"]):
        return "confirmed", "same website (%s)" % _root(r["domain"])
    if t["linkedin"] and r["linkedin"] and t["linkedin"] == r["linkedin"]:
        return "confirmed", "same LinkedIn company page"
    rt = set(_tokens(r["company"]))
    if r["domain"]:
        rt |= _label_tokens(r["domain"])
    if not rt or not t["tokens"]:
        return "none", ""
    conflict = (t["domain"] and r["domain"]) or (t["linkedin"] and r["linkedin"])
    if rt == t["tokens"] or (set(_tokens(r["company"])) and set(_tokens(r["company"])) == set(_tokens(t["name"]))):
        return ("id_conflict" if conflict else "name_match"), "same name"
    small, big = (rt, t["tokens"]) if len(rt) <= len(t["tokens"]) else (t["tokens"], rt)
    if small <= big and any(len(w) >= 3 for w in small):
        return ("id_conflict" if conflict else "name_overlap"), "names overlap"
    return "none", ""


def _role_for_jev(r):
    out = {"company": r["company"] or "not stated", "job_title": r["title"] or "not stated",
           "started": _words_date(r["start"]),
           "ended": "no end date (listed as current)" if r["open"] else _words_date(r["end"])}
    if r["description"]:
        out["description"] = r["description"]
    if r["work_type"]:
        out["work_type"] = r["work_type"]
    if r["domain"]:
        out["company_website"] = r["domain"]
    return out


def _target_for_jev(t):
    out = {}
    if t["name"]:
        out["name"] = t["name"]
    if t["domain"]:
        out["website"] = t["domain"]
    if t["linkedin"]:
        out["linkedin_company_page"] = t["linkedin"]
    return out


def questions_for(i, r, t, others, later):
    """The Jev questions for ONE role. Each states one condition and describes both answers:
    Jev reads literally, and a question it has to interpret is one it can misread."""
    role = _role_for_jev(r)
    qs = {}
    if r["identity"] != "confirmed":
        qs["same_%d" % i] = {"type": "noul", "instructions": {
            "target_company": _target_for_jev(t), "role": role,
            "question": "Is the company in `role` the same company as `target_company`?"},
            "criteria": {"true": "The same company, one of its brands or divisions, or the same company "
                                 "under an earlier or later name.",
                         "false": "A different organization, even if the two names share a word."}}
    qs["kind_%d" % i] = {"type": "choice", "instructions": {
        "role": role, "question": "What relationship with the company in `role` does this role describe?"},
        "criteria": KIND_OPTIONS}
    # The next two are only USED when another current role is itself a job (code decides that
    # from the other_* answers): a trustee seat never replaces a CEO job, and never outranks it.
    if r["open"] and later:
        qs["held_%d" % i] = {"type": "noul", "instructions": {
            "role": role, "later_jobs": later,
            "question": "`role` has no end date, and the person started the jobs in `later_jobs` after it. "
                        "Does the person most likely still hold `role` today?"},
            "criteria": {"true": "Still holds it. People commonly hold `role` at the same time as the jobs "
                                 "in `later_jobs`: several part-time, fractional, contract or consulting "
                                 "roles at once, or a founder or owner who also works somewhere else.",
                         "false": "Most likely left without updating the profile: `role` is a full-time job "
                                  "and a full-time job in `later_jobs` replaced it."}}
    if r["open"] and others:
        qs["main_%d" % i] = {"type": "noul", "instructions": {
            "role": role, "other_current_roles": others,
            "question": "Is `role` this person's main job, the one they spend most of their working time on?"},
            "criteria": {"true": "`role` is the main job, and the roles in `other_current_roles` get less "
                                 "of their time.",
                         "false": "One of `other_current_roles` is the main job and `role` gets less of their time."}}
    return qs


def other_question(role):
    """What kind of role each OTHER current role is (a job, or a side role). Code uses it to decide
    whether "did they leave?" and "is this the main job?" are real questions for this person."""
    return {"type": "choice", "instructions": {
        "role": role, "question": "What relationship with the company in `role` does this role describe?"},
        "criteria": KIND_OPTIONS}


# ---------------------------------------------------------------- the steps

def intake(inp):
    """Before anything is spent: is there a company to check against, is there a profile, and
    does the profile have to be bought (Clay's "Enrich person", 0.5 credits)?"""
    t = target_of(inp)
    prof = _obj(inp.get("profile"))
    roles, facts = read_profile(prof) if prof else ([], {"age_days": None})
    url = _s(inp.get("linkedin_url")) or _s(_first(prof, ("url", "linkedin_url", "profile_url")))
    skip = _truthy(inp.get("skip_enrichment"))
    try:
        max_age = int(float(_s(inp.get("max_profile_age_days")))) if _s(inp.get("max_profile_age_days")) else None
    except Exception:
        max_age = None
    stale = bool(roles) and max_age is not None and facts.get("age_days") is not None and facts["age_days"] > max_age
    need = (not roles or stale) and _li_person(url) and not skip
    why = ""
    if not (t["name"] or t["domain"] or t["linkedin"]):
        need, why = False, "no company to check against: send company_name, company_domain or company_linkedin_url"
    elif not roles and not need:
        if skip and _li_person(url):
            why = "no profile supplied and skip_enrichment is set"
        elif url and not _li_person(url):
            why = "no profile supplied, and linkedin_url is not a LinkedIn profile URL"
        else:
            why = "no profile and no LinkedIn profile URL to enrich"
    return {"need_enrichment": bool(need), "linkedin_url": url if need else "",
            "enrich_reason": ("profile older than %d days" % max_age) if (need and stale) else (
                "no profile supplied" if need else ""),
            "blocked": why, "stale_supplied": bool(stale and need),
            "inp": dict((k, inp.get(k)) for k in ("company_name", "company_domain", "company_linkedin_url",
                                                  "profile", "full_name", "source_ref")),
            "source_ref": _s(inp.get("source_ref"))}


def prepare(ix, found=None):
    """Pick the profile (supplied or just bought), find the roles that could be at the company,
    and build ONE Jev request with a few small questions per role."""
    inp = ix.get("inp") or {}
    t = target_of(inp)
    source = "none"
    prof = {}
    got = _obj(found)
    if ix.get("need_enrichment") and _roles_list(got):
        prof, source = got, "enriched"
    elif _obj(inp.get("profile")):
        prof, source = _obj(inp.get("profile")), "supplied"
    roles, facts = read_profile(prof) if prof else ([], {"age_days": None, "refreshed": ""})
    base = {"ask": False, "blocked": ix.get("blocked") or "", "target": {k: t[k] for k in ("name", "domain", "linkedin")},
            "source": source, "facts": facts, "roles": [], "context": [], "jev_url": PROVIDER["url"],
            "jev_body": "", "source_ref": ix.get("source_ref") or "", "enrich_note": ""}
    if ix.get("need_enrichment") and source != "enriched":
        if isinstance(found, dict) and found.get("_not_run"):
            base["enrich_note"] = "not enriched: this preview does not buy profiles (add --enrich)"
        else:
            base["enrich_note"] = "Clay's Enrich person returned no work history for %s" % (ix.get("linkedin_url") or "the URL")
        if ix.get("stale_supplied"):
            base["enrich_note"] += "; the supplied (older) profile was used instead"
    if base["blocked"]:
        return base
    if not roles:
        base["blocked"] = "no_profile"
        return base
    # The work history as read, so a profile Clay bought can be checked again elsewhere.
    base["profile_roles"] = [dict((k, r[k]) for k in ("company", "title", "start", "end", "is_current", "domain",
                                                      "linkedin", "description", "work_type")) for r in roles[:25]]
    for r in roles:
        r["identity"], r["identity_why"] = identity(r, t)
    cands = [r for r in roles if r["identity"] != "none"]
    cands.sort(key=lambda r: (0 if r["open"] else 1, 0 if r["identity"] == "confirmed" else 1,
                              -(_epoch(r["start"]) or 0)))
    open_other = [r for r in roles if r["identity"] == "none" and r["open"]]
    if not cands and open_other:
        # Nothing on the profile names the company. The company may have changed its name, or the
        # role may be listed under a parent: ask Jev about each current role, cheaply.
        for r in open_other:
            r["identity"], r["identity_why"] = "name_unrelated", "no shared name; asked in case of a rename"
        cands, open_other = open_other, []
    cands = cands[:MAX_ROLES]
    open_other = open_other[:MAX_CONTEXT]
    base["context"] = [_role_for_jev(r) for r in open_other]
    base["roles"] = cands
    want = _s(inp.get("full_name"))
    got_name = _s(facts.get("name"))
    if want and got_name and not (_name_tokens(want) & _name_tokens(got_name)):
        base["name_mismatch"] = "the profile is for %s, not %s" % (got_name[:60], want[:60])
    if not cands:
        return base
    questions = dict(("other_%d" % k, other_question(_role_for_jev(o))) for k, o in enumerate(open_other))
    for i, r in enumerate(cands):
        e = _epoch(r["start"])
        r["other_idx"] = list(range(len(open_other))) if r["open"] else []
        r["later_idx"] = [k for k, o in enumerate(open_other) if r["open"] and e is not None
                          and (_epoch(o["start"]) or 0) > e]
        r["asked_held"] = bool(r["later_idx"])
        r["asked_main"] = bool(r["other_idx"])
        r["others"] = [o["company"] + ": " + o["title"] for o in open_other] if r["open"] else []
        questions.update(questions_for(i, r, t, [_role_for_jev(open_other[k]) for k in r["other_idx"]],
                                       [_role_for_jev(open_other[k]) for k in r["later_idx"]]))
    body = {"model": PROVIDER["model"], "state": {"person_headline": facts.get("headline") or "not stated"},
            "questions": questions}
    base["ask"] = True
    base["jev_body"] = json.dumps(body)
    return base


# ---------------------------------------------------------------- the verdict

JEV_ERRORS = {401: "Jev refused the key (401): the key written into '1 Intake' is wrong or revoked; fix it locally (jev_key.py) and rebuild",
              402: "Jev says the account is out of credit (402)",
              403: "Jev refused the request (403): check the key's permissions",
              422: "Jev rejected the request as malformed (422)",
              429: "Jev rate limit (429): re-run these records later",
              529: "Jev is overloaded (529): re-run these records later"}


def _p(a, key):
    try:
        return max(0.0, min(1.0, float((a or {}).get(key))))
    except Exception:
        return None


def judge(pr, answers):
    """Per role: P(same company), P(still held), the kind of role, P(main job). Then the four
    things the verdict needs: P(works there now), P(holds only a passive role), P(was there)."""
    out, notes = [], []
    ctx = pr.get("context") or []
    job = []          # for each other current role: P(it is a job rather than a side role)
    for k in range(len(ctx)):
        pk = (answers.get("other_%d" % k) or {}).get("probabilities") or {}
        job.append(sum(float(pk.get(x) or 0) for x in WORKING) if pk else 0.5)
    for i, r in enumerate(pr.get("roles") or []):
        a_same, a_kind = answers.get("same_%d" % i), answers.get("kind_%d" % i)
        a_held, a_main = answers.get("held_%d" % i), answers.get("main_%d" % i)
        p_same = 1.0 if r["identity"] == "confirmed" else (_p(a_same, "noul") if a_same else 0.0)
        # Replaced only if a later current role is a job: weigh Jev's "still holds it?" by how likely
        # that is. A later advisory seat leaves the role held.
        p_rep = max([job[k] for k in r.get("later_idx") or [] if k < len(job)] or [0.0])
        if not r["open"]:
            p_held = 0.0
        elif r.get("asked_held") and a_held:
            p_held = p_rep * _p(a_held, "noul") + (1 - p_rep)
        else:
            p_held = 1.0
        probs = (a_kind or {}).get("probabilities") or {}
        kind = (a_kind or {}).get("choice") or (max(probs, key=probs.get) if probs else "not_enough_information")
        k_conf = _p(a_kind, "confidence")
        work = sum(float(probs.get(k) or 0) for k in WORKING)
        passive = sum(float(probs.get(k) or 0) for k in PASSIVE)
        if not probs:
            work, passive = 0.0, 0.0
        p_other_job = max([job[k] for k in r.get("other_idx") or [] if k < len(job)] or [0.0])
        p_main = 1.0 if not (r.get("asked_main") and a_main) else p_other_job * _p(a_main, "noul") + (1 - p_other_job)
        # Only a role that is likely a JOB competes for "main job"; a board seat is never a rival.
        rivals = [k for k in r.get("other_idx") or [] if k < len(job) and job[k] >= 0.5]
        rival = max(rivals, key=lambda k: job[k]) if rivals else None
        row = {"company": r["company"], "title": r["title"], "started": r["start"], "ended": r["end"],
               "listed_current": r["open"], "identity": r["identity"], "why": r["identity_why"],
               "same_company": round(p_same, 2), "still_held": round(p_held, 2), "kind": kind,
               "kind_confidence": None if k_conf is None else round(k_conf, 2),
               "working_share": round(work, 2), "passive_share": round(passive, 2),
               "passive_kind": max(PASSIVE, key=lambda k: float(probs.get(k) or 0)),
               "main_job": round(p_main, 2), "other_current_roles": r.get("others") or [],
               "other_job_likely": round(p_other_job, 2), "replaced_by_job_likely": round(p_rep, 2),
               "rival_job": (ctx[rival]["company"] if rival is not None and rival < len(ctx) else ""),
               "p_work": p_same * p_held * work, "p_passive": p_same * p_held * passive,
               "p_was_there": p_same}
        out.append(row)
        label = "%s at %s" % (r["title"] or "role", r["company"] or "?")
        if r["identity"] != "confirmed" and a_same and abs(2 * p_same - 1) < FLOOR and p_same >= 0.2:
            notes.append("same company? %s: unsure (%d%% yes)" % (label, round(p_same * 100)))
        if p_same >= 0.5 and k_conf is not None and k_conf < FLOOR and kind != "not_enough_information":
            top = sorted(probs.items(), key=lambda kv: -float(kv[1] or 0))[:2]
            notes.append("kind of role, %s: unsure (%s)" % (label, ", ".join("%s %d%%" % (o, round(float(q) * 100)) for o, q in top)))
        if p_same >= 0.5 and r.get("asked_held") and a_held and p_rep >= 0.5 and abs(2 * p_held - 1) < FLOOR:
            notes.append("still in it? %s: unsure (%d%% yes)" % (label, round(p_held * 100)))
    return out, notes


def verdict(pr, status_code=None, body=None):
    """The one answer for one person. Keys are always all present. Rules, first match wins:
    blocked → no profile → Jev failed → nothing at the company → works there (primary or side
    job) → holds only a passive role → was there and left → unsure."""
    model, cost, err = "not called", 0.0, ""
    answers = {}
    if pr.get("ask"):
        b = body
        if isinstance(b, str):
            try:
                b = json.loads(b)
            except Exception:
                b = {"raw": b}
        b = b if isinstance(b, dict) else {}
        answers = b.get("answers") if isinstance(b.get("answers"), dict) else {}
        try:
            code = int(status_code)
        except Exception:
            code = 0
        if code != 200 or not answers:
            err = JEV_ERRORS.get(code) or ("Jev call failed (HTTP %s): %s" % (code, json.dumps(b)[:300]))
            return finish(pr, "not_checked", "unknown", 0, "failed", "Not checked: " + err, "none", {}, [],
                          model, 0.0, err)
        model = _s(b.get("model")) or PROVIDER["model"]
        usage = b.get("usage") or {}
        cost = usage.get("cost")
        if cost is None:
            cost = float(usage.get("input_tokens") or 0) * PROVIDER["price_per_mtok"] / 1000000.0
    blocked = pr.get("blocked") or ""
    if blocked and blocked != "no_profile":
        return finish(pr, "not_checked", "unknown", 0, "blocked_missing_input", "Not checked: " + blocked,
                      "none", {}, [], model, cost, "")
    if blocked == "no_profile":
        why = pr.get("enrich_note") or "the profile has no work history"
        return finish(pr, "not_checked", "unknown", 0, "no_profile", "Not checked: " + why, "none", {}, [],
                      model, cost, "")
    t = pr.get("target") or {}
    tname = t.get("name") or t.get("domain") or t.get("linkedin") or "the company"
    rows, notes = judge(pr, answers)
    ctx = pr.get("context") or []
    other_now = [c["company"] + ": " + c["job_title"] for c in ctx]
    same = [x for x in rows if x["same_company"] >= 0.5]
    if not same:
        ev = "No role at %s on this profile" % tname
        near = [x for x in rows if x["identity"] in ("name_match", "name_overlap", "id_conflict")]
        if near:
            ev += " (%s: a different company, %d%% same)" % (
                "; ".join(sorted(set(x["company"] for x in near))[:2]), round(100 * max(x["same_company"] for x in near)))
        if other_now:
            ev += "; currently: " + "; ".join(other_now[:3])
        conf = 100 - int(round(100 * max([x["same_company"] for x in rows] or [0.0])))
        return finish(pr, "no", "no_record", conf, "checked", ev, "; ".join(notes) or "none", {}, rows,
                      model, cost, "", main=_main_from_context(ctx))
    # Near-ties (two current roles at the company, both within 0.05 of the best) go to the most
    # recently started: a promotion the profile never closed leaves the old title "current" too,
    # and the evidence should name the role the person holds now.
    def pick(key):
        top = max(x[key] for x in same)
        return max([x for x in same if x[key] >= top - 0.05], key=lambda x: x["started"] or "")
    best_work, best_pass = pick("p_work"), pick("p_passive")
    p_work, p_pass = best_work["p_work"], best_pass["p_passive"]
    p_was = max(x["p_was_there"] for x in same)
    if p_work >= 0.6:
        role = best_work
        rel = "primary_job" if role["main_job"] >= 0.5 else "side_job"
        active, conf = "yes", p_work
    elif p_pass >= 0.6:
        role = best_pass
        rel = role["passive_kind"]
        active, conf = "passive", p_pass
    elif all(x["still_held"] < 0.4 for x in same):
        role = max(same, key=lambda x: (x["ended"] or x["started"] or ""))
        rel, active, conf = "former", "no", p_was * (1 - max(x["still_held"] for x in same))
    else:
        role = max(same, key=lambda x: x["p_work"] + x["p_passive"])
        rel, active, conf = "unknown", "unsure", 1 - max(p_work, p_pass)
        notes.append("unsure overall: works there %d%%, passive role %d%%" % (round(p_work * 100), round(p_pass * 100)))
    others = [o for o in (role.get("other_current_roles") or []) if o] or other_now
    main = tname if rel == "primary_job" else (role.get("rival_job") or _main_from_context(ctx, role))
    ev = _evidence(role, rel, tname, others)
    return finish(pr, active, rel, int(round(100 * conf)), "checked", ev, "; ".join(notes) or "none", role,
                  rows, model, cost, "", main=main, others=others)


def _main_from_context(ctx, role=None):
    if role and role.get("main_job", 1.0) < 0.5 and ctx:
        return ctx[0]["company"]
    return ctx[0]["company"] if ctx and len(ctx) == 1 else ""


KIND_WORDS = {"employee": "works there", "contractor": "works there as a contractor or consultant",
              "intern": "works there as an intern", "advisor_or_board": "advisor or board member",
              "investor": "investor", "honorary": "honorary or volunteer role",
              "not_enough_information": "role type unclear"}


def _evidence(role, rel, tname, others):
    title = role.get("title") or "untitled role"
    since = _words_date(role.get("started") or "")
    if rel == "former" and role.get("ended"):
        s = "%s at %s, %s to %s (ended)" % (title, role.get("company") or tname, since,
                                              _words_date(role.get("ended")))
    elif rel == "former":
        s = "%s at %s since %s, still listed as current, but replaced by a later full-time job%s" % (
            title, role.get("company") or tname, since,
            (" at " + role["rival_job"]) if role.get("rival_job") else "")
    else:
        s = "%s at %s since %s (%s" % (title, role.get("company") or tname, since, KIND_WORDS.get(role.get("kind"), "role"))
        if rel in ("primary_job", "side_job"):
            s += "; %s" % ("main job" if rel == "primary_job" else "not the main job")
        s += ")"
        if role.get("identity") != "confirmed":
            s += "; same company as %s: %d%% sure" % (tname, round(100 * role.get("same_company", 0)))
    if others:
        s += ". Also current: " + "; ".join(others[:3])
    return s


def finish(pr, active, rel, conf, status, evidence, review, role, rows, model, cost, err, main="", others=None):
    facts = pr.get("facts") or {}
    age = facts.get("age_days")
    if status == "checked" and age is not None and age > 365:
        review = ("" if review == "none" else review + "; ") + "profile last refreshed %d days ago" % age
    if pr.get("name_mismatch") and status == "checked":
        review = ("" if review == "none" else review + "; ") + pr["name_mismatch"]
        conf = min(conf, 50)
    if pr.get("enrich_note") and status == "checked":
        review = ("" if review == "none" else review + "; ") + pr["enrich_note"]
    months = ""
    if role and role.get("started"):
        m = _months_between(role["started"], role.get("ended") if rel == "former" else None)
        months = "" if m is None else m
    clean = [dict((k, v) for k, v in x.items() if k not in ("p_work", "p_passive", "p_was_there")) for x in rows]
    t = pr.get("target") or {}
    return {"active_at_company": active, "relationship": rel, "verdict_confidence": max(0, min(100, conf)),
            "check_status": status, "evidence": evidence, "needs_review": review or "none",
            "check_note": "none" if status == "checked" else evidence,
            "company_checked": t.get("name") or t.get("domain") or t.get("linkedin") or "none given",
            "role_title": (role or {}).get("title") or "", "role_company": (role or {}).get("company") or "",
            "role_started": (role or {}).get("started") or "",
            "role_ended": ((role or {}).get("ended") or "") if rel == "former" else "",
            "months_in_role": months, "other_current_roles": "; ".join(others or []),
            "main_employer": main or "", "profile_source": pr.get("source") or "none",
            "profile_age_days": "" if age is None else age, "roles_json": json.dumps(clean),
            "jev_model": model, "jev_cost_usd": round(float(cost or 0.0), 8), "error": err,
            "source_ref": pr.get("source_ref") or "",
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "isTerminal": True}   # Clay's marker for the step that ends a run, not part of the verdict
'''

KEY_NOTE = r'''

# ---------------------------------------------------------------- the Jev key
# TODO(move to a Clay connection): the Jev key sits in this step only because Clay's CLI can
# neither create an HTTP API connection nor bind one to a step (it binds by id, and lists no ids).
# When Clay can do both from the CLI, move the key into an "HTTP API (Headers)" connection, bind
# "4 Ask Jev" to it, and delete JEV_HEADERS from this step. Until then: anyone in this Clay
# workspace who opens this workflow, or a run's output, can read this key. Rebuild to rotate it.
JEV_HEADERS = __JEV_HEADERS__
'''

INTAKE_HANDLER = KEY_NOTE + r'''

INPUT_KEYS = __INPUT_KEYS__


def handler(context):
    inp = {}
    for k in INPUT_KEYS:
        try:
            inp[k] = context.get_input("in_" + k)
        except Exception:
            inp[k] = None
    out = intake(inp)
    out["jev_headers"] = JEV_HEADERS
    return out
'''

# The Audiences workflow: the trigger hands over the person's fields (keyed by display name) and
# the companies they are linked to. "1 Intake" picks the person's LinkedIn URL and (optional)
# profile field and the first linked company; "1r Company" adds that company's website and
# LinkedIn page from a free Audiences lookup, then runs the same intake as the table workflow.
AUD_INTAKE_HANDLER = KEY_NOTE + r'''

URL_FIELD = __URL_FIELD__
PROFILE_FIELD = __PROFILE_FIELD__
NAME_FIELD = __NAME_FIELD__


def handler(context):
    f = context.get_input("fields") or {}
    f = f if isinstance(f, dict) else {}
    try:
        accts = context.get_input("accounts") or []
    except Exception:
        accts = []
    accts = [a for a in (accts if isinstance(accts, list) else []) if isinstance(a, dict) and a.get("id")]
    first = accts[0] if accts else {}
    return {"record_id": _idstr(f.get("id")), "linkedin_url": _s(f.get(URL_FIELD)),
            "profile": f.get(PROFILE_FIELD) if PROFILE_FIELD else None,
            "account_id": _idstr(first.get("id")), "account_name": _s(first.get("name")),
            "full_name": _s(f.get(NAME_FIELD)) if NAME_FIELD else "", "has_account": bool(first), "jev_headers": JEV_HEADERS}
'''

AUD_COMPANY_HANDLER = r'''


def _field(rec, names):
    fl = (rec or {}).get("fields") or {}
    for n in names:
        if _s(fl.get(n)):
            return _s(fl.get(n))
    return ""


def handler(context):
    a = context.get_input("a") or {}
    try:
        found = context.get_input("found") or {}
    except Exception:
        found = {}
    recs = (found or {}).get("records") if isinstance(found, dict) else None
    rec = recs[0] if isinstance(recs, list) and recs else {}
    inp = {"company_name": _field(rec, ("Company name", "Name", "org_name")) or a.get("account_name"),
           "company_domain": _field(rec, ("Domain", "Normalized domain", "domain")),
           "company_linkedin_url": _field(rec, ("LinkedIn URL", "linkedin_url")),
           "profile": a.get("profile"), "linkedin_url": a.get("linkedin_url"),
           "full_name": a.get("full_name"), "source_ref": a.get("record_id")}
    return intake(inp)
'''

PREPARE_HANDLER = r'''


def handler(context):
    ix = context.get_input("intake") or {}
    try:
        found = context.get_input("found")
    except Exception:
        found = None
    return prepare(ix, found)
'''

VERDICT_HANDLER = r'''


def handler(context):
    pr = context.get_input("prep") or {}
    try:
        code = context.get_input("status_code")
    except Exception:
        code = None
    try:
        body = context.get_input("body")
    except Exception:
        body = None
    return verdict(pr, code, body)
'''

NOJEV_HANDLER = r'''


def handler(context):
    return verdict(context.get_input("prep") or {})
'''


def render(handler, provider, headers=None, **slots):
    """The code for one step. `headers` (with the key) is baked in only for the steps that carry
    KEY_NOTE; every other step gets none."""
    p = PROVIDERS[provider]
    prov = {"url": p["url"], "model": p["model"], "price_per_mtok": p["price_per_mtok"]}
    src = CORE.replace("__PROVIDER__", repr(prov))
    h = handler.replace("__INPUT_KEYS__", repr(list(INPUT_KEYS)))
    h = h.replace("__JEV_HEADERS__", repr(headers or {"Content-Type": "application/json"}))
    for k, v in slots.items():
        h = h.replace("__%s__" % k, repr(v))
    return src + h


def jev_headers(provider):
    """The headers the workflow's first step carries. Built from the local key; never printed."""
    key = _key_value(provider)
    if not key:
        fail("No %s key on this machine to put in the workflow. Save one first: jev_key.py save %s"
             % (PROVIDERS[provider]["label"], provider), code=3)
    return {"Content-Type": "application/json", "Authorization": "Bearer " + key}


def load_core(provider):
    """The rendered verdict code as a namespace, for the local preview and tests. It is the same
    text the Clay code steps run."""
    ns = {"__name__": "active_core"}
    exec(compile(render(NOJEV_HANDLER, provider), "<active_core>", "exec"), ns)
    return ns


def check_record(provider, record, call=None, enrich=None):
    """One person, locally, exactly as the workflow would: intake, (enrich), prepare, (Jev),
    verdict. `call(body)` -> (status, body) is the Jev call (default: the local key);
    `enrich(url)` -> profile dict is the paid lookup (default: none, so a URL-only record comes
    back no_profile rather than spending)."""
    core = load_core(provider)
    ix = core["intake"](record)
    found = None
    if ix["need_enrichment"]:
        found = enrich(ix["linkedin_url"]) if enrich else {"_not_run": True}
    pr = core["prepare"](ix, found)
    if not pr["ask"]:
        return core["verdict"](pr)
    status, body = (call or (lambda b: call_jev(provider, b)))(json.loads(pr["jev_body"]))
    return core["verdict"](pr, status, body)

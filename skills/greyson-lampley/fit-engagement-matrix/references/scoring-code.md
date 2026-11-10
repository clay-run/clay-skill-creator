# The code nodes and the agent prompts

Three code nodes carry every score and route. Each opens with a constants block. **Fill the
constants from the installer's declared inputs before pasting a node; never paste the author's
values as if they were the installer's.** Where a value below is the author's, it is labelled.
The field-name constants are placeholders in capitals and must be replaced with the installer's
Audiences field names from the mapping confirmed in Step 1.

Every handler is `def handler(context)` returning a dict, reads its pins with
`context.get_input(name)`, and never raises on a missing or malformed input: a missing dimension
scores zero and says so in the reasons string, which is the behaviour the skill promises.

## Clean contact

Classifies the email, fills a name from the local part when none was given, and fills the domain
from a work email when none was given. For a personal or invalid email the domain is set to a
sentinel no enrichment will resolve, so downstream steps return not-found instead of failing.

```python
PERSONAL = {'gmail.com','googlemail.com','yahoo.com','hotmail.com','outlook.com','live.com',
            'icloud.com','me.com','aol.com','protonmail.com','proton.me','gmx.com','mail.com'}
UNRESOLVABLE_DOMAIN = 'no-company-resolved-zzz.com'   # sentinel; enrichment returns not-found

def handler(context):
    def val(key):
        return str(context.get_input(key) or '').strip()
    email = val('email').lower()
    domain = email.split('@')[-1] if '@' in email else ''
    if not domain or '.' not in domain:
        email_type = 'invalid'
    elif domain in PERSONAL:
        email_type = 'personal'
    else:
        email_type = 'work'
    local = email.split('@')[0] if '@' in email else ''
    guess = ' '.join(p.capitalize() for p in local.replace('_', '.').replace('-', '.').split('.') if p.isalpha())
    company_domain = val('company_domain').lower().replace('https://', '').replace('http://', '').replace('www.', '').strip('/')
    if not company_domain and email_type == 'work':
        company_domain = domain
    activity = [a.strip().lower().replace(' ', '_') for a in val('recent_activity').split(',') if a.strip()]
    return {
        'contact_email': email,
        'contact_name': val('name') or guess or 'Unknown',
        'email_type': email_type,
        'company_domain': company_domain or UNRESOLVABLE_DOMAIN,
        'recent_activity': ','.join(activity) if activity else 'none',
    }
```

## Account fit

Rules only. Each weight is the points a company earns when it meets the rule. The author's weights
sum to 100 and are shown as the example shape; the installer's ICP replaces every number and the
keyword list.

```python
import re

# ---- DECLARED INPUTS: replace with the installer's ICP. The values shown are the author's. ----
FIT_WEIGHTS = {
    'employees_sweet_spot': 40,  # inside the installer's headcount sweet spot
    'employees_near_band': 20,   # just outside it on either side
    'industry_b2b_tech': 25,     # industry matches CORE_INDUSTRY_KEYWORDS
    'industry_other': 10,        # any other known industry
    'revenue_10m_plus': 20,      # at or above the upper revenue band
    'revenue_1m_to_10m': 10,     # inside the lower revenue band
    'work_email_resolved': 10,   # a work email tied to a resolved company
    'profile_verified': 5,       # a company URL or profile was found
}
SWEET_SPOT = (50, 5000)          # installer's headcount sweet spot
NEAR_BAND = ((20, 49), (5001, 20000))
REVENUE_UPPER_M = 10             # millions; at or above earns revenue_10m_plus
REVENUE_LOWER_M = 1              # millions; at or above earns revenue_1m_to_10m
BAND_CUTOFFS = {'Best Fit': 75, 'Good Fit': 60, 'Moderate Fit': 45, 'Low Fit': 30}  # below is Poor Fit
CORE_INDUSTRY_KEYWORDS = ['software', 'saas', 'internet', 'information technology', 'it services',
                          'computer and network security', 'data infrastructure', 'analytics',
                          'marketing services', 'advertising services', 'financial technology',
                          'fintech', 'cloud', 'artificial intelligence', 'business consulting',
                          'technology, information']
# ---- end declared inputs ----

def unwrap(obj):
    if not isinstance(obj, dict):
        return {}
    if isinstance(obj.get('toolResult'), dict):
        obj = obj['toolResult']
    inner = obj.get('result') if 'result' in obj else obj
    return inner if isinstance(inner, dict) else {}

def to_int(v):
    try:
        return int(float(str(v).replace(',', '').strip()))
    except Exception:
        return None

def revenue_millions(text):
    # Handles "1M-5M", "$10M - $50M", "1B+", "25000000". Reads the first figure, never a band's midpoint.
    if not text:
        return None
    s = str(text).upper().replace(',', '').replace('$', '')
    m = re.search(r'(\d+(?:\.\d+)?)\s*([KMB]?)', s)
    if not m:
        return None
    n = float(m.group(1)); unit = m.group(2)
    if unit == 'B': return n * 1000
    if unit == 'M': return n
    if unit == 'K': return n / 1000
    return n / 1_000_000 if n > 10000 else None

def handler(context):
    company = unwrap(context.get_input('company_data'))
    email_type = str(context.get_input('email_type') or '')
    reasons, score = [], 0

    employees = to_int(company.get('employee_count'))   # exact count only; never parse the band string
    if employees is None:
        reasons.append('Employees unknown (+0)')
    elif SWEET_SPOT[0] <= employees <= SWEET_SPOT[1]:
        score += FIT_WEIGHTS['employees_sweet_spot']; reasons.append('%s employees, in the sweet spot (+%d)' % (employees, FIT_WEIGHTS['employees_sweet_spot']))
    elif any(lo <= employees <= hi for lo, hi in NEAR_BAND):
        score += FIT_WEIGHTS['employees_near_band']; reasons.append('%s employees, near the target band (+%d)' % (employees, FIT_WEIGHTS['employees_near_band']))
    else:
        reasons.append('%s employees, outside the target band (+0)' % employees)

    industry = str(company.get('industry') or company.get('primary_industry') or '')
    if not industry:
        reasons.append('Industry unknown (+0)')
    elif any(k in industry.lower() for k in CORE_INDUSTRY_KEYWORDS):
        score += FIT_WEIGHTS['industry_b2b_tech']; reasons.append('Industry %s matches the core profile (+%d)' % (industry, FIT_WEIGHTS['industry_b2b_tech']))
    else:
        score += FIT_WEIGHTS['industry_other']; reasons.append('Industry %s is outside the core profile (+%d)' % (industry, FIT_WEIGHTS['industry_other']))

    revenue_text = str(company.get('annual_revenue') or company.get('revenue') or '')
    rev = revenue_millions(revenue_text)
    if rev is None:
        reasons.append('Revenue unknown (+0)')
    elif rev >= REVENUE_UPPER_M:
        score += FIT_WEIGHTS['revenue_10m_plus']; reasons.append('Revenue %s, upper band (+%d)' % (revenue_text, FIT_WEIGHTS['revenue_10m_plus']))
    elif rev >= REVENUE_LOWER_M:
        score += FIT_WEIGHTS['revenue_1m_to_10m']; reasons.append('Revenue %s, lower band (+%d)' % (revenue_text, FIT_WEIGHTS['revenue_1m_to_10m']))
    else:
        reasons.append('Revenue %s, below both bands (+0)' % revenue_text)

    if email_type == 'work' and company.get('name'):
        score += FIT_WEIGHTS['work_email_resolved']; reasons.append('Work email tied to a resolved company (+%d)' % FIT_WEIGHTS['work_email_resolved'])
    if company.get('url') or company.get('linkedin_url'):
        score += FIT_WEIGHTS['profile_verified']; reasons.append('Company profile verified (+%d)' % FIT_WEIGHTS['profile_verified'])

    score = max(0, min(100, score))
    band = 'Poor Fit'
    for name, cutoff in BAND_CUTOFFS.items():
        if score >= cutoff:
            band = name; break
    return {
        'fit_score': score, 'fit_band': band, 'fit_reasons': '; '.join(reasons),
        'company_name': str(company.get('name') or ''), 'industry': industry or 'unknown',
        'employee_count': str(employees) if employees is not None else 'unknown',
        'revenue': revenue_text or 'unknown',
    }
```

## Engagement

One score, two sides, each capped. The account side reads the installer's company record and
company topic intent. The contact side reads the person's title, the activity list, the
installer's seats field on the person record, person signals and person topic intent. The
author's caps were 45 and 55; the installer sets both and every ladder.

```python
from datetime import datetime, timezone

# ---- DECLARED INPUTS: the installer's engagement model. The values shown are the author's. ----
ACCOUNT_CAP, CONTACT_CAP = 45, 55
WORKSPACE_LADDER = [(5, 15), (2, 10), (1, 5)]       # (at least N workspaces, points); first match wins
RECENCY_LADDER = [(30, 10), (90, 6), (180, 3)]      # (within N days, points)
LAST_SIGNUP_POINTS = 5
ACCOUNT_SIGNAL_POINTS, ACCOUNT_SIGNAL_CAP = 3, 5
ACCOUNT_INTENT_POINTS, ACCOUNT_INTENT_CAP = 5, 10
TITLE_WEIGHTS = {'executive': 15, 'director': 12, 'manager': 8, 'individual_contributor': 3}
GTM_FUNCTION_POINTS = 5
ACTIVITY_POINTS = {'demo_request': 15, 'pricing_page_visit': 12, 'email_reply': 8,
                   'webinar_attended': 5, 'content_download': 5, 'event_attended': 5}
OTHER_ACTIVITY_POINTS, ACTIVITY_CAP = 3, 15
SEATS_LADDER = [(10, 10), (3, 6), (1, 3)]
CONTACT_SIGNAL_POINTS, CONTACT_SIGNAL_CAP = 3, 5
CONTACT_INTENT_POINTS, CONTACT_INTENT_CAP = 5, 5
INTENT_SURGE_THRESHOLD = 60                          # composite score at or above counts as surging
STATUS_CUTOFFS = {'Highly Engaged': 70, 'Engaged': 50, 'Aware': 25}   # below is Passive
# Installer's Audiences field names, from the Step 1 mapping. Leave a list empty to drop that rule.
WORKSPACES_KEYS = ['WORKSPACES_CREATED_FIELD']
LAST_WORKSPACE_KEYS = ['LAST_WORKSPACE_DATE_FIELD']
LAST_SIGNUP_KEYS = ['LAST_SIGNUP_EMAIL_FIELD']
SEATS_KEYS = ['SEATS_INVITED_FIELD']
EXEC_WORDS = ['chief', 'ceo', 'cro', 'cmo', 'coo', 'founder', 'vp', 'vice president', 'head of']
GTM_WORDS = ['sales', 'marketing', 'revops', 'revenue', 'growth', 'gtm', 'go-to-market', 'demand', 'operations']
# ---- end declared inputs ----

def unwrap(obj):
    if not isinstance(obj, dict):
        return {}
    if isinstance(obj.get('toolResult'), dict):
        obj = obj['toolResult']
    inner = obj.get('result') if 'result' in obj else obj
    return inner if isinstance(inner, dict) else {}

def first_record(obj):
    recs = unwrap(obj).get('records')
    return recs[0] if isinstance(recs, list) and recs and isinstance(recs[0], dict) else {}

def pick(fields, keys):
    for k in keys:
        if k in fields and fields[k] not in (None, ''):
            return fields[k]
    return None

def to_int(v):
    try:
        return int(float(str(v).replace(',', '').strip()))
    except Exception:
        return None

def days_since(v):
    if not v:
        return None
    s = str(v).strip().replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        try:
            dt = datetime.strptime(s[:10], '%Y-%m-%d')
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days

def count_signals(rec):
    sig = rec.get('signals') or {}
    if isinstance(sig, dict):
        return sum(len(v) if isinstance(v, list) else (1 if v else 0) for v in sig.values()), [k for k, v in sig.items() if v]
    if isinstance(sig, list):
        return len(sig), []
    return 0, []

def surging_topics(obj):
    out = []
    for t in (unwrap(obj).get('topics') or []):
        if not isinstance(t, dict):
            continue
        try:
            cs = float(t.get('composite_score') or 0)
        except Exception:
            cs = 0
        if cs >= INTENT_SURGE_THRESHOLD:
            out.append((cs, str(t.get('topic_name') or '')))
    out.sort(reverse=True)
    return out

def ladder(value, rungs):
    for threshold, pts in rungs:
        if value >= threshold:
            return pts
    return 0

def handler(context):
    reasons_a, reasons_c, channels = [], [], []
    acct = contact = 0

    company = first_record(context.get_input('company_lookup'))
    cfields = company.get('fields') if isinstance(company.get('fields'), dict) else {}
    ws = to_int(pick(cfields, WORKSPACES_KEYS)) or 0
    if company:
        if ws > 0:
            p = ladder(ws, WORKSPACE_LADDER); acct += p; reasons_a.append('%s workspaces created (+%s)' % (ws, p)); channels.append('Product')
        age = days_since(pick(cfields, LAST_WORKSPACE_KEYS))
        if age is not None:
            p = next((pts for max_days, pts in RECENCY_LADDER if age <= max_days), 0)
            acct += p; reasons_a.append('Last workspace %s days ago (+%s)' % (age, p))
        if pick(cfields, LAST_SIGNUP_KEYS):
            acct += LAST_SIGNUP_POINTS; reasons_a.append('Signup email on file (+%s)' % LAST_SIGNUP_POINTS)
            if 'Product' not in channels: channels.append('Product')
        n, types = count_signals(company)
        if n:
            p = min(n * ACCOUNT_SIGNAL_POINTS, ACCOUNT_SIGNAL_CAP); acct += p
            reasons_a.append('%s account signals: %s (+%s)' % (n, ', '.join(types) or 'various', p)); channels.append('Signals')
    else:
        reasons_a.append('Company not in Audiences (+0)')
    surge_a = surging_topics(context.get_input('account_intent'))
    if surge_a:
        p = min(len(surge_a) * ACCOUNT_INTENT_POINTS, ACCOUNT_INTENT_CAP); acct += p
        reasons_a.append('%s surging company topics (+%s)' % (len(surge_a), p)); channels.append('Intent')
    acct = min(acct, ACCOUNT_CAP)

    person = unwrap(context.get_input('person_data'))
    current = (person.get('current_experience') or [{}])[0] or {}
    if not isinstance(current, dict): current = {}
    title = str(current.get('title') or person.get('title') or '')
    t = title.lower()
    if not title:
        reasons_c.append('Title unknown (+0)')
    elif any(k in t for k in EXEC_WORDS):
        contact += TITLE_WEIGHTS['executive']; reasons_c.append('%s is an executive buyer (+%d)' % (title, TITLE_WEIGHTS['executive']))
    elif 'director' in t:
        contact += TITLE_WEIGHTS['director']; reasons_c.append('%s is a director (+%d)' % (title, TITLE_WEIGHTS['director']))
    elif any(k in t for k in ['manager', 'lead']):
        contact += TITLE_WEIGHTS['manager']; reasons_c.append('%s is a manager (+%d)' % (title, TITLE_WEIGHTS['manager']))
    else:
        contact += TITLE_WEIGHTS['individual_contributor']; reasons_c.append('%s is an individual contributor (+%d)' % (title, TITLE_WEIGHTS['individual_contributor']))
    if title and any(k in t for k in GTM_WORDS):
        contact += GTM_FUNCTION_POINTS; reasons_c.append('Works in a GTM function (+%d)' % GTM_FUNCTION_POINTS)

    activity = [a.strip() for a in str(context.get_input('recent_activity') or '').split(',') if a.strip() and a.strip() != 'none']
    act = 0
    for a in activity:
        p = ACTIVITY_POINTS.get(a, OTHER_ACTIVITY_POINTS); act += p; reasons_c.append('%s (+%s)' % (a.replace('_', ' '), p))
    if act:
        contact += min(act, ACTIVITY_CAP); channels.append('Inbound')
        if act > ACTIVITY_CAP: reasons_c.append('Activity capped at +%d' % ACTIVITY_CAP)

    crec = first_record(context.get_input('lookup_data'))
    pfields = crec.get('fields') if isinstance(crec.get('fields'), dict) else {}
    seats = to_int(pick(pfields, SEATS_KEYS)) or 0
    if seats > 0:
        p = ladder(seats, SEATS_LADDER); contact += p; reasons_c.append('%s seats invited in product (+%s)' % (seats, p))
        if 'Product' not in channels: channels.append('Product')
    n, types = count_signals(crec)
    if n:
        p = min(n * CONTACT_SIGNAL_POINTS, CONTACT_SIGNAL_CAP); contact += p
        reasons_c.append('%s person signals: %s (+%s)' % (n, ', '.join(types) or 'various', p))
        if 'Signals' not in channels: channels.append('Signals')
    surge_c = surging_topics(context.get_input('contact_intent'))
    if surge_c:
        p = min(len(surge_c) * CONTACT_INTENT_POINTS, CONTACT_INTENT_CAP); contact += p
        reasons_c.append('%s surging person topics (+%s)' % (len(surge_c), p))
        if 'Intent' not in channels: channels.append('Intent')
    contact = min(contact, CONTACT_CAP)

    score = max(0, min(100, acct + contact))
    band = 'Passive'
    for name, cutoff in STATUS_CUTOFFS.items():
        if score >= cutoff:
            band = name; break
    bits = ['Account: ' + '; '.join('%s (%d)' % (nm, sc) for sc, nm in surge_a[:3])] if surge_a else []
    if surge_c: bits.append('Contact: ' + '; '.join('%s (%d)' % (nm, sc) for sc, nm in surge_c[:3]))
    return {
        'engagement_score': score, 'engagement_band': band,
        'account_subtotal': acct, 'contact_subtotal': contact,
        'engagement_reasons': 'Account %s/%s: %s | Contact %s/%s: %s' % (acct, ACCOUNT_CAP, '; '.join(reasons_a) or 'nothing fired', contact, CONTACT_CAP, '; '.join(reasons_c) or 'nothing fired'),
        'engagement_channels': ', '.join(dict.fromkeys(channels)) if channels else 'none',
        'intent_summary': ' | '.join(bits) if bits else 'No surging intent topics',
        'current_title': title or 'unknown', 'seats_invited': seats, 'workspaces_created': ws,
        'record_status': 'existing' if crec else 'net-new', 'account_found': bool(company),
    }
```

## Place on the matrix

The two lines and the four tiers. The lines are the installer's. The values shown are the
author's where first-party product data existed. In a demo workspace with none, the author
lowered the engagement line to 35 and the status cut-offs to 55, 35 and 15 as a stated
adjustment; that pair is not the model.

```python
# ---- DECLARED INPUTS. The values shown are the author's where first-party product data existed. ----
FIT_LINE = 60            # fit at or above this is high account fit
ENGAGEMENT_LINE = 50     # engagement at or above this is high engagement
MAX_AGENT_ADJUSTMENT = 15
STATUS_CUTOFFS = {'Highly Engaged': 70, 'Engaged': 50, 'Aware': 25}   # below is Passive
TIERS = {
    'target':        ('Tier 1: Target Accounts',    'Prospect to unlock the whole buying center; multi-thread open opportunities'),
    'nurture':       ('Tier 2: Marketing Nurture',  'Selectively prospect to warm up the account; marketing invests in education and content'),
    'opportunistic': ('Tier 3: Opportunistic Sales','Limited prospecting; prioritize inbounds and signals, smallest deals to self-serve'),
    'deprioritize':  ('Tier 4: De-Prioritize',      'No prospecting; self-serve path for inbounds'),
}
# ---- end declared inputs ----

def handler(context):
    def num(key):
        try:
            return float(str(context.get_input(key)).strip())
        except Exception:
            return 0.0
    def txt(key):
        return str(context.get_input(key) or '').strip()

    adj = max(-MAX_AGENT_ADJUSTMENT, min(MAX_AGENT_ADJUSTMENT, int(round(num('fit_adjustment')))))
    fit = int(max(0, min(100, round(num('fit_score') + adj))))
    acct = int(round(num('account_subtotal'))); contact = int(round(num('contact_subtotal')))
    eng = int(max(0, min(100, round(num('engagement_score')))))

    strong_fit = fit >= FIT_LINE
    engaged = eng >= ENGAGEMENT_LINE
    key = 'target' if (strong_fit and engaged) else 'nurture' if strong_fit else 'opportunistic' if engaged else 'deprioritize'
    tier, action = TIERS[key]

    status = 'Passive'
    for name, cutoff in STATUS_CUTOFFS.items():
        if eng >= cutoff:
            status = name; break
    quadrant = '%s account fit / %s engagement' % ('High' if strong_fit else 'Low', 'High' if engaged else 'Low')
    position = 'Fit %s (%+d vs line) | Engagement %s (%+d vs line)' % (fit, fit - FIT_LINE, eng, eng - ENGAGEMENT_LINE)

    judgment = txt('judgment_reason') or 'agent skipped because the rules were decisive'
    reason = 'Fit %s (rules %s, agent %+d: %s). Engagement %s (%s). Fit: %s | Engagement: %s | Intent: %s' % (
        fit, int(num('fit_score')), adj, judgment, eng, status,
        txt('fit_reasons'), txt('engagement_reasons'), txt('intent_summary') or 'none')
    contact_status = {'target': 'OPEN', 'nurture': 'NEW', 'opportunistic': 'NEW'}.get(key, 'UNQUALIFIED')
    parts = txt('contact_name').split()
    return {
        'contact_status': contact_status,
        'first_name': parts[0] if parts else 'Unknown',
        'last_name': ' '.join(parts[1:]) if len(parts) > 1 else 'Unknown',
        'final_fit_score': fit, 'account_subtotal': acct, 'contact_subtotal': contact,
        'engagement_score': eng, 'engagement_status': status,
        'engagement_channels': txt('engagement_channels') or 'none',
        'matrix_quadrant': quadrant, 'matrix_position': position,
        'priority_tier': tier, 'next_action': action,
        'score_badge': 'Fit %s | Engagement %s (acct %s / contact %s) | %s' % (fit, eng, acct, contact, tier),
        'priority_reason': reason,
    }
```

## Agent prompts

Both agents return structured fields only. Neither scores, compares or routes.

### Find LinkedIn URL

Runs only when the Audiences record has no profile URL. Web search enabled. Output schema:
`linkedin_url` (url), `confidence` (select: High, Medium, Low), `evidence` (string, one sentence).

```
Find the LinkedIn profile URL for this person.

Name: {{contact_name}}
Work email: {{contact_email}}
Company domain: {{company_domain}}
Title on file: {{title_hint}}

Search the web for the person's LinkedIn profile. Accept a profile only when the name matches and
the profile shows the company above (current or recent). Return the canonical URL in the form
https://www.linkedin.com/in/<slug>. If you cannot find a confident match, leave linkedin_url
empty and set confidence to Low.

Return:
- linkedin_url: the profile URL, or empty.
- confidence: High, Medium, or Low.
- evidence: one sentence under 25 words on what matched.
```

Observed on the source: a Medium-confidence URL for a fabricated contact came from a documentation
example page and was wrong; an honest empty with Low came back on another run. Treat confidence as
reported, not trusted, and consider gating the downstream intent step on High.

### ICP judgment

Runs only when the rules fit lands in the borderline band. Web search off; the prompt forbids
browsing. Output schema: `icp_verdict` (select: Strong, Partial, Weak), `fit_adjustment` (number,
inside the installer's bound), `judgment_reason` (string, one sentence). Replace the ideal customer
sentence with the installer's own.

```
You are double-checking an account fit score for a B2B go-to-market team. The rules-based score
below can miss context (for example, a company whose industry label looks wrong, or a holding
company). Use ONLY the information below plus what the company name and domain make obvious. Do
not browse or invent facts.

Company: {{company_name}} ({{company_domain}})
Industry: {{industry}} | Employees: {{employee_count}} | Revenue: {{revenue}}
Rules-based fit: {{fit_score}} ({{fit_band}})
Rules that fired: {{fit_reasons}}

Ideal customer: a B2B company with 50-5,000 employees that sells to other businesses and runs a
sales and marketing team.

Return:
- icp_verdict: Strong, Partial, or Weak.
- fit_adjustment: a whole number from -15 to 15 to apply to the rules-based score. Use 0 unless
  the context clearly changes the picture.
- judgment_reason: one sentence under 25 words explaining the verdict.
```

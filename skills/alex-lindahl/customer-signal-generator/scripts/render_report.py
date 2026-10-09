#!/usr/bin/env python3
"""Render a Customer Signal Generator report.

Usage:
  python3 scripts/render_report.py --content report.json --signals signals.yaml \
      --css references/clay-theme.css --out ics-<company>.html

Standard library only. The content file follows the shape in references/report-design.md
("Report content file"). Text fields accept two light markers and nothing else:
  **bold**                      -> <b>bold</b>
  [Web] / [Clay] / [Inferred]   -> source pills
Everything else is HTML-escaped, so content can never inject markup.
"""
import argparse, html, json, re, sys

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Figtree:wght@400;500;600'
         '&family=Inter+Tight:wght@500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">')
CATS = [("demographic_firmographic", "Demographic and firmographic"), ("hiring_org_design", "Hiring and org design"),
        ("technographic", "Technographic"), ("people_movement", "People movement"),
        ("initiatives_programs", "Initiatives and programmes"), ("public_announcements", "Public announcements and strategy"),
        ("web_content", "Web and content"), ("intent_behavioral", "Intent and behavioural")]
SRC = {"clay": "Clay", "web_research": "Web", "inferred": "Inferred", "deal_history": "Clay"}
FIT = {"strong": "Strong", "moderate": "Moderate", "weak": "Weak", "none": "Not rated"}


def t(s):
    """Escape, then apply the two allowed markers."""
    s = html.escape(str(s or ""))
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"\[(Web|Clay|Inferred)\]", lambda m: f'<span class="tag {m.group(1).lower()}">{m.group(1)}</span>', s)


def url(u):
    u = str(u or "")
    return html.escape(u, quote=True) if u.startswith(("https://", "http://")) else ""


def table(head, rows):
    h = "".join(f"<th>{t(x)}</th>" for x in head)
    r = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="tbl"><table><tr>{h}</tr>{r}</table></div>'


def ul(items):
    return "<ul>" + "".join(f"<li>{t(i)}</li>" for i in items) + "</ul>"


def ol(items):
    return "<ol>" + "".join(f"<li>{t(i)}</li>" for i in items) + "</ol>"


def clock(days_left, window, label):
    pct = 100 if days_left is None else max(0, min(100, round(days_left / max(window, 1) * 100)))
    cls = "fast" if (days_left is not None and days_left <= 15) else "slow"
    return f'<span class="clock"><i class="{cls}" style="width:{pct}%"></i></span><span class="clock-lbl">{t(label)}</span>'


def hero(c):
    h = c.get("hero", {})
    calls = "".join(
        f'<div class="call"><div class="rank">{t(x.get("rank_label"))}</div><div class="co">{t(x.get("company"))}</div>'
        f'<div class="why">{t(x.get("why"))}</div>'
        + (f'<span class="cl {"ai" if x.get("cluster_style") == "primary" else "cc"}">{t(x.get("cluster"))}</span>' if x.get("cluster") else "")
        + "</div>" for x in h.get("calls", []))
    cols = max(1, min(5, len(h.get("calls", [])) or 1))
    m = c.get("meta", {})
    out = (f'<section class="hero"><div class="overline">Ideal Customer Signals · {t(m.get("company"))} · {t(m.get("date"))}</div>'
           f'<h1>{t(h.get("title"))}</h1><p class="lead">{t(h.get("lead"))}</p>'
           f'<div class="calls" style="grid-template-columns: repeat({cols}, minmax(0, 1fr));">{calls}</div>'
           f'<div class="note">{t(h.get("note"))} Written for {t(m.get("seller_perspective"))}.</div></section>')
    if c.get("deadlines"):
        out += '<div class="deadline">' + "".join(
            f'<div><span class="overline">{t(d.get("label"))}</span><span class="date">{t(d.get("date"))}</span>'
            f'<span class="what">{t(d.get("text"))}</span></div>' for d in c["deadlines"]) + "</div>"
    if c.get("banner"):
        out += f'<div class="banner">{t(c["banner"])}</div>'
    return out


def board(c):
    b = c.get("board")
    if not b:
        return None
    w = b.get("window_days", 45)
    head = ('<tr><th class="idx">#</th><th class="acct"><span class="ct">Company</span>Account</th>'
            f'<th class="sig"><span class="ct">{w}-day window</span>{t(b.get("signal_name"))}<span class="how">{t(b.get("how"))}</span></th>'
            '<th class="why"><span class="ct">From the job post</span>Why now</th><th><span class="ct">From the job post</span>Fit</th></tr>')
    rows = ""
    for i, r in enumerate(b.get("rows", []), 1):
        fit = r.get("fit", "none") if r.get("fit") in FIT else "none"
        link = f' <a href="{url(r.get("job_url"))}">Job post</a>' if url(r.get("job_url")) else ""
        cell = (f'<span class="cell-fire"><span class="st">{t(r.get("role"))}</span>'
                f'{clock(r.get("days_left"), w, r.get("days_label"))}</span>')
        rows += (f'<tr><td class="idx">{i}</td><td class="acct">{t(r.get("account"))}<span>{t(r.get("segment"))}</span></td>'
                 f'<td>{cell}</td><td class="why{" muted" if fit == "none" else ""}">{t(r.get("why"))}{link}</td>'
                 f'<td class="fit {fit}">{FIT[fit]}</td></tr>')
    notes = "".join(f"<p>{t(n)}</p>" for n in b.get("notes", []))
    return (f'<p>{t(b.get("intro"))}</p><div class="ctable-wrap"><table class="ctable"><thead>{head}</thead>'
            f'<tbody>{rows}</tbody></table></div>{notes}')


def company(c):
    k = c.get("company", {})
    out = ""
    if k.get("products"):
        out += "<h3>Products and capabilities</h3>" + "<ul>" + "".join(
            f"<li><b>{t(p.get('name'))}:</b> {t(p.get('text'))}</li>" for p in k["products"]) + "</ul>"
    if k.get("standing"):
        out += f"<h3>Where it stands</h3><p>{t(k['standing'])}</p>"
    if k.get("pains"):
        out += "<h3>Business pains addressed</h3>" + ul(k["pains"])
    if k.get("personas"):
        out += "<h3>Personas</h3><ul>" + "".join(
            f"<li><b>{t(p.get('role'))}:</b> {t(p.get('titles'))}</li>" for p in k["personas"]) + "</ul>"
    if k.get("icp"):
        out += "<h3>Ideal customer profile</h3><ul>" + "".join(
            f"<li><b>{t(p.get('label'))}:</b> {t(p.get('text'))}</li>" for p in k["icp"]) + "</ul>"
    if k.get("motion"):
        out += f"<h3>GTM motion and lead acquisition</h3><p>{t(k['motion'])}</p>"
    return out


def clusters(c):
    out = ""
    for x in c.get("clusters", []):
        out += (f'<div class="cluster"><h3>{t(x.get("name"))}</h3><p><b>Signals:</b> {t(", ".join(x.get("signals", [])))}.</p>'
                f'<p><b>Why it matters:</b> {t(x.get("why"))}</p><p><b>Recommended play:</b></p>{ol(x.get("play", []))}</div>')
    return out


def templates(c):
    out = f"<p>{t(c.get('templates_intro', 'Replace anything in braces before sending.'))}</p>"
    for x in c.get("templates", []):
        out += (f'<div class="card tmpl"><h3>{t(x.get("name"))}</h3><dl>'
                f'<dt>Trigger</dt><dd>{t(x.get("trigger"))}</dd><dt>Persona</dt><dd>{t(x.get("persona"))}</dd>'
                f'<dt>Channel</dt><dd>{t(x.get("channel"))}</dd><dt>Subject or hook</dt><dd>{t(x.get("hook"))}</dd>'
                f'<dt>Call to action</dt><dd>{t(x.get("cta"))}</dd></dl><pre>{html.escape(str(x.get("body", "")))}</pre></div>')
    return out


def clocks(signals):
    out = ('<p>Every signal has a window. Orange means the window closes within 60 days, so act fast; blue means you '
           'have longer. The bar shows the window against a 180-day scale.</p>')
    for key, label in CATS:
        items = [s for s in signals if s.get("category") == key]
        if not items:
            continue
        out += f"<h4>{t(label)}</h4>"
        for s in items:
            d = int(s.get("decay_window_days", 0) or 0)
            cs = s.get("clay_source") or {}
            how = ("free Clay filter" if cs.get("type") == "search_filter" else
                   "paid Clay data point" if cs else "needs first-party or external data")
            src = SRC.get(s.get("source"), "Inferred")
            out += (f'<div class="sigrow"><div class="nm">{t(s.get("name"))} <span class="tag {src.lower()}">{src}</span>'
                    f'<small>{t(s.get("trigger_ref"))} · weight {t(s.get("weight"))} · {how}</small></div>'
                    f'<div class="ck"><span class="clock"><i class="{"fast" if d <= 60 else "slow"}" style="width:{round(min(d, 180) / 180 * 100)}%"></i></span>'
                    f'<span class="clock-lbl">{d} days</span></div></div>')
    return out


def scorecards(c):
    sc = c.get("scorecards", {})
    def rows(lst):
        return [[f'<span class="num">{i}</span>', t(x.get("signal")), str(x.get("conv")), str(x.get("strategic")),
                 str(x.get("detect")), f"<b>{int(x.get('conv', 0)) + int(x.get('strategic', 0)) + int(x.get('detect', 0))}</b>",
                 t(x.get("rationale"))] for i, x in enumerate(lst, 1)]
    head = ["#", "Signal", "Conv.", "Strategic", "Detect", "Total", "Rationale"]
    out = f"<p>{t(sc.get('note'))}</p>"
    if sc.get("a"):
        out += "<h3>Scorecard A: top 10 core signals</h3>" + table(head, rows(sc["a"]))
    if sc.get("b"):
        out += "<h3>Scorecard B: 10 creative signals</h3>" + table(head, rows(sc["b"]))
    return out


def triggers(c):
    return "".join(f'<p class="trig"><b>{t(x.get("id"))}.</b> If {t(x.get("if"))}, then they likely need '
                   f'{t(x.get("then"))}, because {t(x.get("because"))}.</p>' for x in c.get("triggers", []))


def displacement(c):
    d = c.get("displacement", {})
    out = ""
    if d.get("cross_sell"):
        out += "<h3>Cross-sell signals (existing customers)</h3>" + table(
            ["Signal", "Expansion it suggests", "Play"],
            [[t(x.get("signal")), t(x.get("expansion")), t(x.get("play"))] for x in d["cross_sell"]])
    if d.get("competitors"):
        out += f"<h3>Competitor displacement</h3><p>{t(d.get('competitor_note'))}</p>"
        for x in d["competitors"]:
            out += (f"<h4>{t(x.get('name'))}</h4><p><b>Gap:</b> {t(x.get('gap'))} <b>Frustration signal:</b> {t(x.get('signal'))} "
                    f"<b>Switching trigger:</b> {t(x.get('trigger'))} <b>Message:</b> {t(x.get('message'))}</p>")
    return out


def implementation(c):
    m = c.get("implementation", {})
    out = ""
    if m.get("data"):
        out += "<h3>Data architecture</h3>" + ul(m["data"])
    if m.get("workflow"):
        out += "<h3>Signal detection workflow</h3>" + ol(m["workflow"])
    if m.get("stack"):
        out += "<h3>Recommended stack</h3>" + ul(m["stack"])
    if m.get("horizons"):
        out += "<h3>Quick wins vs long-term builds</h3>" + table(
            ["Horizon", "Signals"], [[t(x.get("horizon")), t(x.get("signals"))] for x in m["horizons"]])
    return out


def deep_dives(c, signals):
    dd = c.get("deep_dives", {})
    out = ""
    for s in signals:
        x = dd.get(s.get("id"), {})
        cs = s.get("clay_source") or {}
        rows = [("What it indicates", x.get("indicates")), ("Why now", x.get("why_now")),
                ("Personas", ", ".join(s.get("personas", []))), ("Buying stage", str(s.get("buying_stage", "")).capitalize()),
                ("Messaging angle", x.get("angle")), ("Best channels", x.get("channels")), ("Ease of detection", x.get("ease")),
                ("How to detect", x.get("detect")), ("Threshold", s.get("threshold")),
                ("Decay and weight", f'{s.get("decay_window_days")} days · weight {s.get("weight")}'),
                ("Clay source", f'{cs.get("type", "").replace("_", " ")}: {cs.get("name", "")}' if cs else "Not detectable in Clay")]
        body = "".join(f"<dt>{t(k)}</dt><dd>{t(v)}</dd>" for k, v in rows if v)
        if x.get("campaigns"):
            body += f"<dt>Campaign ideas</dt><dd>{ul(x['campaigns'])}</dd>"
        out += f'<div class="card"><h3>{t(s.get("name"))}</h3><dl>{body}</dl></div>'
    return out


def section(n, title, body, open_=False):
    return (f'<details{" open" if open_ else ""}><summary><span class="n">{n:02d}</span><h2>{t(title)}</h2></summary>'
            f"<div>{body}</div></details>")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--content", required=True, help="report content JSON")
    ap.add_argument("--signals", required=True, help="signals.yaml, embedded verbatim in the page")
    ap.add_argument("--css", required=True, help="references/clay-theme.css")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    c = json.load(open(a.content, encoding="utf-8"))
    signals = c.get("signals", [])
    if not signals:
        sys.exit("content JSON needs a 'signals' list (the same signals written to signals.yaml)")
    yaml_text = open(a.signals, encoding="utf-8").read().replace("</script", "<\\/script")
    css = open(a.css, encoding="utf-8").read()
    m = c.get("meta", {})
    skin = ' data-skin="neutral"' if m.get("theme") == "neutral" else ""

    order = [("Executive summary", "".join(f"<p>{t(p)}</p>" for p in c.get("executive_summary", [])), True),
             ("Company understanding", company(c), True)]
    b = board(c)
    if b:
        order.append(("Live signal board", b, True))
    order += [("High-intent signal clusters", clusters(c), False), ("Outbound message templates", templates(c), False),
              ("Signals and their clocks", clocks(signals), False), ("Signal scorecards", scorecards(c), False),
              ("Triggers of need", triggers(c), False), ("Cross-sell and competitor displacement", displacement(c), False),
              ("How to build this", implementation(c), False)]
    secs = "".join(section(i, ti, bo, op) for i, (ti, bo, op) in enumerate([o for o in order if o[1]], 1))
    secs += '<p class="ref-note">Reference</p>' + section(len([o for o in order if o[1]]) + 1, "Signal deep-dives", deep_dives(c, signals))
    srcs = "".join(f'<li><a href="{url(s.get("url"))}">{t(s.get("title"))}</a></li>' for s in c.get("sources", []) if url(s.get("url")))
    foot = (f'<div class="foot"><p><b>Sources</b></p><ul>{srcs}</ul><p>Tags: <span class="tag web">Web</span> cited web source · '
            '<span class="tag clay">Clay</span> Clay data · <span class="tag inferred">Inferred</span> reasoning, not data.</p></div>')
    page = (f'<!DOCTYPE html><html lang="en"{skin}><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'<title>{t(m.get("company"))}: Ideal Customer Signals</title>{FONTS}<style>{css}</style></head><body><main>'
            f'{hero(c)}{secs}{foot}</main><script type="application/yaml" id="ics-signals">\n{yaml_text}\n</script></body></html>')
    open(a.out, "w", encoding="utf-8").write(page)
    print(f"wrote {a.out} ({len(page):,} bytes, {len(signals)} signals)")


if __name__ == "__main__":
    main()

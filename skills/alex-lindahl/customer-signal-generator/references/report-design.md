# Report Design

How the HTML report looks and is ordered. This file supersedes the "Output Formatting Notes" at the end of `analysis-framework.md`: the framework still defines what each section contains, and this file defines the order and the visual components.

## Theme

- Inline `references/clay-theme.css` in full inside the page's `<style>` block. Load the fonts it names from Google Fonts with a fallback stack.
- `theme` input: `clay` (default) or `neutral`. For `neutral`, add `data-skin="neutral"` to `<html>`; the same CSS handles it.
- Light and dark mode are built in. Don't add colours outside the tokens in the CSS.

### Colour means something

| Colour | Use only for |
|---|---|
| Orange | Act now: short decay windows (60 days or less), clusters forming, open sections, score totals |
| Clay blue | Clay-sourced data and links; long decay windows |
| Teal | Overlines and labels (all caps, Inter Tight) |
| Green tint | A signal that is firing |
| Lemon tint | The status banner |

No decorative shapes. The hard shadow (4px offset, Clay Black, orange in dark mode) is a hover-only signature on cards, closed sections and hero call cards. Never put it on static elements.

## Page order (reader order)

Full mode:

1. **Hero:** "Call these N first" (see below)
2. **Deadline strip:** only when a dated trigger exists (e.g. a regulation's effective dates)
3. **Status banner:** back-test status, and any Clay values dropped for conflicting with cited sources
4. Section 01 **Executive summary** (open by default)
5. Section 02 **Company understanding** (open by default), so readers know what the company sells and to whom before they see signals
6. Section 03 **Live signal board** (open by default)
7. Section 04 **High-intent signal clusters**
8. Section 05 **Outbound message templates**
9. Section 06 **Signals and their clocks** (framework Section 4, rendered as clocks)
10. Section 07 **Signal scorecards**
11. Section 08 **Triggers of need**
12. Section 09 **Cross-sell and competitor displacement**
13. Section 10 **How to build this**
14. A "Reference" label, then **Signal deep-dives** (framework Section 5), collapsed
15. **Sources**, then the embedded `signals.yaml` script block

Quick mode keeps the same order and drops the sections Quick mode skips. Account mode stays a one-screen markdown brief in chat unless HTML is asked for; if it is, use the hero, one board row and the clocks.

When Step 6 didn't run (Clay off), the hero leads with the strongest cluster and the three highest-scoring signals instead of accounts. The section order stays the same.

## Components

### Hero

```html
<section class="hero">
  <div class="overline">Ideal Customer Signals · {Company} · {date}</div>
  <h1>Call these five first</h1>
  <p class="lead">The strongest pattern is the <b>{Cluster}</b>: {one sentence}. {Why these accounts}.</p>
  <div class="calls">
    <div class="call"><div class="rank">#1</div><div class="co">{Account}</div>
      <div class="why">{What is firing}. {Next check to complete a cluster}.</div>
      <span class="cl ai">{Cluster name}</span></div>
    <!-- up to 5 -->
  </div>
  <div class="note">{How the five were picked}. Written for {seller perspective}.</div>
</section>
```

Pick the top five board accounts by fit, then days left. Each call card's `.why` paraphrases that account's job post in one sentence. Cluster pills: `.cl.ai` (orange) for the strongest cluster, `.cl.cc` (green) for the next. The board's first rows must match the hero's order.

### Deadline strip

```html
<div class="deadline">
  <div><span class="overline">{What happens}</span><span class="date">{11 Sep 2026}</span>
    <span class="what">{One sentence} <span class="tag web">Web</span></span></div>
</div>
```

### Section

```html
<details open><summary><span class="n">01</span><h2>Live signal board</h2></summary><div>…</div></details>
```

The CSS adds "Section" before the number.

### Live signal board as a Clay table

Exactly one hiring signal column sources the rows (see the Step 6 rule in `SKILL.md`). Columns: row number, account, the hiring signal, "Why now (from the job post)", and fit.

```html
<div class="ctable-wrap"><table class="ctable">
<thead><tr><th class="idx">#</th><th class="acct"><span class="ct">Company</span>Account</th>
  <th class="sig"><span class="ct">45-day window</span>AppSec hiring
    <span class="how">Search companies with an open Application Security, DevSecOps or Product Security Engineer role posted in the last 45 days.</span></th>
  <th class="why"><span class="ct">From the job post</span>Why now</th>
  <th><span class="ct">From the job post</span>Fit</th></tr></thead>
<tbody><tr><td class="idx">1</td><td class="acct">{Account}<span>{Segment}</span></td>
  <td><span class="cell-fire"><span class="st">{Role title}</span><span class="clock"><i class="slow|fast" style="width:{pct}%"></i></span><span class="clock-lbl">{n}d left · posted {date}</span></span></td>
  <td class="why">{One or two sentences} <a href="{posting URL}">Job post</a></td>
  <td class="fit {strong|moderate|weak}">{Strong|Moderate|Weak}</td></tr></tbody>
</table></div>
```

- **Hiring signal header:** the decay window as the overline, the signal name, then `.how`: one plain sentence on how to find the signal in Clay. No cost labels and no DSL syntax.
- **Hiring signal cell:** the role title as the pill, a days-left clock (`fast` when 15 days or fewer remain, otherwise `slow`; `pct` = days left / window × 100), and the posting date.
- **Why now cell:** paraphrased from the job-post summary, ending with a link to the posting. If the post wasn't pulled, write "Job post not pulled".
- **Fit cell:** Strong, Moderate or Weak, judged only from the job post.
- No "Run", "—" placeholder columns, or extra signal columns.
- **Below the table:** what was removed from raw results, and any accounts dropped because their posting expired.
- Sort by fit, then days left. The first rows must match the hero.

### Signals and their clocks

One row per signal, grouped under `<h4>` category headings:

```html
<div class="sigrow">
  <div class="nm">{Signal} <span class="tag clay">Clay</span>
    <small>{Trigger} · weight {w} · {free Clay filter | paid Clay data point | needs first-party or external data}</small></div>
  <div class="ck"><span class="clock"><i class="fast|slow" style="width:{decay/180*100}%"></i></span>
    <span class="clock-lbl">{decay} days</span></div>
</div>
```

Use `fast` for windows of 60 days or less. Open the section with one sentence explaining the colours and the 180-day scale.

### Source tags

`<span class="tag web">Web</span>`, `<span class="tag clay">Clay</span>`, `<span class="tag inferred">Inferred</span>`. Put one tag at the end of a claim, not after every sentence.

### Cards, clusters, templates

- **Signal deep-dive:** `<div class="card"><h3>…</h3><dl><dt>…</dt><dd>…</dd>…</dl></div>`
- **Cluster:** `<div class="cluster">` (tints rotate automatically)
- **Template:** `<div class="card tmpl">` with the message in `<pre>`
- **Trigger:** `<p class="trig"><b>T1.</b> If …, then …, because ….</p>`
- **Tables:** always inside `<div class="tbl">` so they scroll sideways on phones

## Writing rules for the page

- Lead every section with its answer, then detail.
- No em dashes in outbound templates.
- Every number has a source tag or is left out.


## Report content file (for `scripts/render_report.py`)

Write the analysis as one JSON file, then render it. Don't hand-write the HTML; the script applies this file's order, components and stylesheet the same way every time.

```
python3 scripts/render_report.py --content report.json --signals signals.yaml \
    --css references/clay-theme.css --out ics-<company>.html
```

Top-level keys (all optional except `meta` and `signals`; empty sections are left out):

| Key | Shape |
|---|---|
| `meta` | `company`, `date`, `seller_perspective`, `theme` (`clay` or `neutral`) |
| `hero` | `title`, `lead`, `note`, `calls`: list of `rank_label`, `company`, `why`, `cluster`, `cluster_style` (`primary` or `secondary`) |
| `deadlines` | list of `label`, `date`, `text` |
| `banner` | one string |
| `executive_summary` | list of paragraphs |
| `company` | `products` (`name`, `text`), `standing`, `pains`, `personas` (`role`, `titles`), `icp` (`label`, `text`), `motion` |
| `board` | `signal_name`, `window_days`, `how`, `intro`, `notes`, `rows`: list of `account`, `segment`, `role`, `days_left` (number or null), `days_label`, `why`, `job_url`, `fit` (`strong`, `moderate`, `weak`, `none`) |
| `clusters` | list of `name`, `signals` (names), `why`, `play` (steps) |
| `templates` | list of `name`, `trigger`, `persona`, `channel`, `hook`, `body`, `cta` |
| `triggers` | list of `id`, `if`, `then`, `because` |
| `scorecards` | `note`, `a` and `b`: lists of `signal`, `conv`, `strategic`, `detect`, `rationale` |
| `displacement` | `cross_sell` (`signal`, `expansion`, `play`), `competitor_note`, `competitors` (`name`, `gap`, `signal`, `trigger`, `message`) |
| `implementation` | `data`, `workflow`, `stack` (lists), `horizons` (`horizon`, `signals`) |
| `deep_dives` | object keyed by signal `id`: `indicates`, `why_now`, `angle`, `campaigns`, `channels`, `ease`, `detect` |
| `signals` | the same signal list written to `signals.yaml` (see `references/signal-schema.md`) |
| `sources` | list of `title`, `url` |

Text accepts two markers only: `**bold**`, and the source tags `[Web]`, `[Clay]` and `[Inferred]`, which render as pills. Everything else is escaped. A full worked example is `references/examples/snyk-report-content.json`.

If Python isn't available, write the HTML by hand from the components above and inline the stylesheet.

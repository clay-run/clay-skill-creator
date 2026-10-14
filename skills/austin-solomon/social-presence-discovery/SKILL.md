---
name: social-presence-discovery
description: |
  Find every live social profile and the owned website for a list of small, owner-operated
  local businesses, verified to belong to that exact business in that exact place:
  mine the links you already hold first (site footer, Instagram bio, link-in-bio page,
  Facebook About), fall back to platform-scoped web searches only for what is still missing,
  confirm name, locality and trade before returning any URL, and return an empty cell rather
  than a sentence when nothing verified was found. Use whenever someone asks: find the
  Instagram and Facebook for these businesses, get social links for my lead list, which of
  these businesses have a TikTok or YouTube, find the real website behind this Instagram
  account, enrich local leads with social profiles, how many of my leads have an Instagram,
  or verify that these social URLs belong to the right business. Do NOT use it to find a
  phone number or email, to qualify or score the business, to scrape followers or posts, to
  find profiles of people at mid-size or enterprise companies, or to decide which platform a
  lead should be contacted on.
---

# Social presence discovery (mine the links you hold, then search; verify, never narrate)

The insight: **for small local businesses, the pages you already hold name the other profiles,
and a cold search is the fallback, not the method; and the output must be a URL or nothing,
because a sentence in a URL column counts as a profile to every downstream filter.** The author
built this as a research step behind a local-business lead list and learned both halves the hard
way. A business's own site footer, Instagram bio and link-in-bio page link to the Facebook, TikTok and
YouTube that a `site:` search never surfaces under a business name that three other businesses
share. And when the research step returned prose such as *"No verified TikTok profile found"*
into the TikTok column, the null filter downstream passed it as a value: TikTok coverage read
89% and was 28% once only real URLs were counted, and the overstatement was similar across
platforms. So this skill mines before it searches, verifies every URL against name, place and
trade before it is written, and writes `""` for not found. The found URLs live in their own
prefixed columns, separate from whatever the installer already had, so a correction never
silently overwrites an input.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for
it, never substitute a plausible default, and where an answer does not exist say which step
becomes unavailable rather than guessing. Where a default IS defensible it is named below, and
using it means saying so in the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The lead list** | CSV or table with, per row: business name, city or locality, and any links already held (website, any social URL, a maps or directory listing). Optional: the owner's name, the trade or category | business name and locality are required; without either a URL cannot be verified as this business and the row is skipped and counted |
| **Platforms** | which profiles to look for | the author looks for seven (Instagram, Facebook, LinkedIn, TikTok, YouTube, Yelp, Google Business Profile) plus the owned website; if they have no view use that list and SAY it is borrowed |
| **Trade words** | two or three words that describe what the business does, used to confirm a profile is the right business | without them verification runs on name and place only, and the delivery says so |
| **Directory blocklist** | hosts that are listings about the business rather than the business: booking marketplaces, review sites, link-in-bio hosts, URL shorteners | offer the author's starting list (below) and ask what to add for their industry; a blocked host is mined for links and never returned as a profile or a website |
| **Verification strictness** | whether a profile whose name matches but whose locality cannot be confirmed is returned as `unconfirmed` or dropped | default: dropped, and say so. Strict is the author's setting because a same-name business in another city is the common false positive |
| **Pre-fill enrichment** | optionally, a Clay enrichment in the workspace that returns social handles from a company domain, to pre-fill rows that have a website before any page is read | none is required; without it every row is researched by reading pages. If one is named, its real action, inputs and per-row cost are confirmed against the live catalogue in Step 3 before anything spends |
| **Batch size** | rows per research batch | the author runs 10 first and then batches of 50; say it is borrowed |
| **Output** | where the result goes: a CSV beside the input, or a sheet the installer names | default: a CSV beside the input, with the found columns prefixed so they never overwrite inputs |

**Starting blocklist** (the author's; one industry; already pruned once for false positives):
`linktr.ee`, `bit.ly`, `thumbtack`, `angi`, `houzz`, `bark.com`, `weddingwire`, `theknot`,
`tripadvisor`, `yellowpages`, `mapquest`, `foursquare`, `nextdoor`.
Yelp and Google Business Profile are platforms the author *returns*, so they are not on it.

**If an answer sheet is present beside this skill, load it and ask only for what it does
not cover.** A partial sheet is normal; a value it is missing gets asked for on its own
rather than restarting the interview. **Say which values came from the sheet** before using
them. **If there is no sheet, say nothing about sheets.** At delivery, offer to save the
answers back (identifiers only, never an API key), private and never published, in words
that explain the offer: *"want me to save your answers to a file, so the next person on your
team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — the lead list you supply, the public pages behind the links it holds, public search results, and, only if you named one, one Clay enrichment's response.
- **Writes** — its own output only: the lead list with added, prefixed columns, and a run log. Nothing to a CRM, a Clay table, or any other system unless you name a sheet as the output, in which case only that sheet.
- **Never** — overwrites a column you supplied, returns a URL it did not verify, writes a sentence into a URL column, fetches followers, posts or reviews, or spends on an enrichment you did not name.
- **Halts** — Step 4 sample-review, Step 4 spend-approval.

## Step 0 — Check the platform works, and say where the work runs

This skill reads your lead list and public web pages, optionally calls one Clay enrichment
you named, and writes a file (or the sheet you named). It spends nothing unless you named an
enrichment, and then only after you approve the batch.

Confirm the lead list opens and has a business-name and a locality column. If an enrichment
was named, confirm `clay whoami` answers and name the workspace out loud. If the list is
missing a required column, say which and stop; if the CLI is signed out, say so, give the one
fix (`clay login`), and stop. Do not install or fetch anything.

Where the work runs: link mining, searching, verification and the coverage count run in this
agent at no cost. Only a named enrichment bills, per row it runs on.

> Do not start a step before the steps above it have their answers. If a declared input is
> missing, ask for it; never assume a default and continue.

## Step 1 — Collect the definition (interview; do not guess)

Take the declared inputs in this order: the lead list, platforms, trade words, blocklist,
strictness, pre-fill enrichment, batch size, output. Show the column mapping you found
(which input column is the business name, the locality, the owner's name, each known link)
and ask only about what did not match. Say how many rows have at least one link already,
because those rows get the cheap path and the rest get searches.

## Step 2 — The ladder, per row (the decision this skill exists to make)

Four rungs, in order, and a later rung runs only for platforms the earlier rungs left empty:

1. **Mine the links held.** Open every link the row carries. On the owned website: header and
   footer icons, a contact or about page. On Instagram: the bio, which often carries the
   website, a link-in-bio page, or a Facebook or TikTok handle. On Facebook: the About
   section. On a link-in-bio or shortener page: every outbound link. On a maps or directory
   listing: the website field. A blocklisted host is mined here and never returned.
2. **Capture the owned website only from mining.** `FOUND_website` is the business's own
   primary domain, found linked from a page the business controls. Never run a cold search
   for it: a search returns directories and sister businesses, and a social profile, a
   booking page or a shortener is not a website.
3. **Search for what is still missing**, one platform-scoped query per missing platform:
   `"<business name>" "<locality>" site:<platform host>`, adding the owner's name for
   LinkedIn. Read the top results only; a profile below the fold under a common business
   name is usually a different business.
4. **Verify every candidate URL** before writing it, against three things: the profile or
   page name matches the business (or its owner), the locality on the profile agrees with
   the row, and what the profile shows matches the trade words. A bakery that shares a name
   with a plumbing company is not the plumber. A match on name alone, with no locality
   signal, is `unconfirmed` and is dropped under strict verification.

A link the row already carried is re-verified the same way: returned unchanged if it holds,
`""` if it is dead or belongs to another business, with the reason logged.

## Step 3 — Free checks, and the optional enrichment priced before it runs

At no cost: count rows with a website, rows with any social link, rows with neither; those
three numbers predict how much of the run is mining and how much is searching. Normalise
every link already held (scheme, lowercase host, no tracking parameters) so a duplicate
profile across rows is visible.

If a pre-fill enrichment was named: resolve it against the live catalogue
(`clay workflows actions list`, then `clay workflows actions schema <packageId> <actionKey>`),
record the pair, the input it requires (a domain), the fields it returns and its declared
per-row cost. Say that it runs only on rows that have an owned website, that its output is
treated as a candidate to verify in Step 2 rung 4 like any other, and that a workspace
without such an enrichment loses nothing but speed. If no action resolves, say so and run
without it. Never substitute the nearest thing.

## Step 4 — Ten rows for real, then ONE gate: the batch, the cost, the writes, the ask

Run the ladder on 10 rows and show the result: the found columns, and beside each URL one
short evidence phrase saying where it came from (`site footer`, `IG bio`, `link-in-bio`,
`FB About`, `search`, `held, confirmed`) and the verification it passed. Show at least one
row where a platform came back `""` and say why in a sentence.

Then one message, and stop: the 10 rows; the cost of the full run (zero if no enrichment
was named, otherwise `rows with a website × per-row cost` from Step 3); exactly what will be
written and where (a new CSV beside the input with the prefixed columns, or the named sheet);
and the ask. Stop a second time only if the batch shows something the installer could not
have anticipated: most rows returning the same profile, a platform returning nothing on all
ten, a locality column that turns out to hold a country.

## Step 5 — Run the batches

Work in batches of the agreed size. Per row, apply the ladder, verify, write URLs or `""`
into the prefixed columns and the evidence phrase into one evidence column. Carry a running
coverage count per platform of **real URLs only**. Never write a sentence, a note or a
reason into a URL column; reasons go to the evidence column and the log.

Concurrency is the agent's; there is no rate to tune here except for the optional enrichment,
which runs at the pace the catalogue allows.

## Step 6 — Per-row and per-run verdicts, single-valued

Per URL, one of three values and no fourth: `confirmed` (held and re-verified, or found and
verified), `corrected` (a held link was dead or wrong and a verified replacement was found),
`not-found` (`""` written). Per row, one of three: `complete` (every requested platform has a
verified URL or a verified absence from a page the business controls), `partial` (at least one
URL, at least one search returned nothing verifiable), `none`. Per run, a coverage line of real
URLs per platform over rows researched, with skipped rows counted separately.

## Step 7 — Deliver

Hand back the output file (or the sheet), the run log with every dropped candidate and why,
and the coverage line. Then say plainly: every URL returned was verified against name, place
and trade; every empty cell means nothing verifiable was found, not that nothing exists; and
no phone, email or follower figure was produced. Offer to save the non-secret answers
(platforms, trade words, blocklist additions, strictness) beside the skill.

## Representative output

### Enriched lead list (added columns; inputs untouched)

| Business | Locality | FOUND_website | FOUND_instagram | FOUND_facebook | FOUND_tiktok | FOUND_yelp | evidence |
|---|---|---|---|---|---|---|---|
| Blue Fern Florist | Portland, OR | bluefernflorist.example | instagram.com/bluefernflorist | facebook.com/bluefernflorist | | yelp.com/biz/blue-fern-florist-portland | IG bio → site; site footer → FB, Yelp; TikTok search: no match |
| Harbor Light Plumbing | Gloucester, MA | | instagram.com/harborlightplumbing | | tiktok.com/@harborlightplumbing | | held IG confirmed; IG bio → TikTok; website is a link-in-bio page, not returned |
| Northwind Dental | Boise, ID | | | | | | held FB belonged to a Northwind clinic in Denver, dropped; searches: three same-name businesses, none in Boise |

The third row is the honest case: a held link was wrong and nothing verifiable replaced it,
so every found cell is empty and the evidence column says why. It is `none`, not a failure.

### Coverage line

`412 rows · 409 researched, 3 skipped (no locality) · website 231 (56%) · Instagram 318 (78%) · Facebook 264 (65%) · TikTok 71 (17%) · YouTube 38 (9%) · Yelp 142 (35%) · Google Business 297 (73%) · 46 held links corrected or dropped · 0 enrichment credits`

## What this skill does not claim

- The logic comes from the author's own research step and the lead lists it ran on, plus an interview; nothing checks it against a system that can be re-run here.
- The coverage overstatement the author measured (TikTok 89% read as 28% once only URLs counted) was on one list in one industry. It motivates the empty-cell rule; it is not a rate anyone else should expect.
- Verification is reading pages with judgment. Two businesses with the same name in the same city, or a business that moved, can still be confused, and the evidence column exists so a reader can check.
- An empty cell means no verified profile was found by this ladder. It does not mean the business has no profile.
- The seven-platform list, the blocklist and strict verification are the author's working choices; nobody established them as right for another industry.
- The optional pre-fill enrichment is resolved at run time against the installer's own catalogue. No action is named here, and if none resolves the skill says so and runs without it.
- No phone, email, follower count, post content or rating is produced; adjacent jobs, not this one.
- Search engines rank differently by day and region, so the search rung is not reproducible row for row. The mining rung, which does most of the work, is.

## What good looks like

- The evidence column names a page the business controls for most found URLs. A run where most evidence reads `search` either had thin inputs or skipped the mining rung.
- At least one held link was corrected or dropped on any list of a few hundred rows. A run that confirms every held link did not re-verify them.
- Coverage per platform is a count of URLs, and the delivery can show the rows behind any number. A platform at 89% on a list of owner-operated businesses is a sign that sentences leaked into the column.
- Empty cells are empty. If a URL column contains any letter that is not part of a URL, the run is wrong and gets fixed before delivery.
- A thin run looks like this: a list with no held links and generic business names, searches returning same-name businesses elsewhere, most rows `partial` or `none`. The honest output is the low coverage line and the sentence "the inputs carry no links, so this ran on searches alone", not padded URLs.

## Rules

- MUST mine held links before searching, and MUST capture the owned website only from a page the business controls; NEVER run a cold search for the website.
- MUST verify every URL against name, locality and trade before writing it; NEVER return a URL on name alone under strict verification.
- MUST write `""` for not found; NEVER write a sentence, a reason or a placeholder into a URL column.
- MUST write found values into prefixed columns; NEVER overwrite a column the installer supplied.
- MUST re-verify held links and log why any was dropped.
- MUST count coverage on real URLs only.
- MUST resolve any named enrichment against the live catalogue and price it before the gate; NEVER substitute a different action.
- NEVER produce phone, email, followers, posts or ratings.

## Worked example

Ask: "I have 412 local florists from a maps scrape; get me their Instagram and the
rest, and tell me how many really have a TikTok." Interview: CSV with name, city, website for
231 rows, a maps listing URL for all, no held socials; seven platforms borrowed; trade words
`florist`, `flowers`, `bouquets`; author's blocklist plus two regional directories; strict;
no enrichment; batches of 50; CSV output. Step 3: 231 rows take the mining path from the
website, 181 from the maps listing only. Step 4: 10 rows run; 8 Instagram found, 7 from the
site footer or IG bio, 1 by search; one held website turns out to be a link-in-bio page and
is not returned as a website; zero cost; gate: writes a new CSV beside the input: yes. Step 5:
nine batches. Step 6: 409 researched, 3 skipped for a blank city; coverage as in the line
above; TikTok 71 real URLs, 17%, every one with an evidence phrase. Delivered with the log of
46 held links corrected or dropped and the offer to save the blocklist additions.

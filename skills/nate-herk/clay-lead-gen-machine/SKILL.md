---
name: clay-lead-gen-machine
description: "Drive Clay from Claude Code to source, enrich, score and write personalized cold outreach for a target vertical, then deliver a CSV you import into a Clay campaign. Use whenever someone asks: find me N fully enriched leads, build a lead list for [vertical] with verified emails, write personalized cold email for each lead, set up the Claude Code + Clay lead gen machine, or run Nate Herk's lead gen goal prompt. Do NOT use it to score or tier an existing account book, to only fill missing firmographics, or to send email directly - sending always happens Clay-side."
---
# Claude Code + Clay: The Lead Gen Machine (Drop-In Template)

This is the exact system from the video, rebuilt as a template you can drop into your own Claude Code project. Talk to Claude Code in plain English, and it uses Clay on the backend to find leads, enrich them with verified emails and phone numbers, write a personalized email for each one, and hand the whole list off to a campaign.

You do not learn a new UI. You describe what you want, Claude Code figures out the endpoints, and Clay supplies the data and the send.

**How to use this file:** save it into your project folder (for example as `CLAUDE.md` or `clay-lead-gen.md`) so Claude Code reads it as instructions. Fill in the five context files in the "Make It Yours" section first. Then run the goal prompt.

---

## The mental model

Two parts, one clear split.

- **Claude Code is the brain.** It holds everything about your business: who you are, what you sell, who you target, your proof, and your email rules. It decides who to reach and what to say. That judgment lives in the context files you write below.
- **Clay is the data and the muscle.** It sources businesses, enriches them across 150+ providers, and sends the campaign. Clay knows nothing about your business on its own. You bring that from the brain.

You bring the judgment. Clay brings the reach and the send. Neither half works alone. Clay with no context writes generic spam. Claude Code with no data has nobody to write to.

---

## Part 1: One-time setup

You do this once, then you live in Claude Code.

### 1. Create a Clay account
Go to clay.com and sign up. Start the free trial, which comes with credits to test everything below. You will grab an API key later, so keep the account handy.

### 2. Install Claude Code
If you have not already, search "Claude Code install" and run the one command for your operating system. You can drive it from your terminal, VS Code, or the desktop app. The plugin install has to happen through the terminal, but after that you can use it anywhere.

### 3. Connect Clay to Claude Code
There are two ways in. Pick based on how far you want to go.

**Option A: The public Clay connector (easiest, start here).**
Go to `claude.com/connectors/clay` (or in Claude, Settings → Connectors → search "Clay"). Click Connect, authorize with your Clay account, and you get free credits to test. In Claude Code, run `/mcp` and confirm Clay shows as connected. This lets you run enrichment and call Clay functions straight from chat. It does not build live Clay workflows.

**Option B: The Clay plugin (the full demo, builds live workflows).**
1. In Claude Code, type `/plugin`.
2. Go to Marketplaces → Add Marketplace, and add the Clay plugin marketplace.
3. Install the Clay plugin, then run `/reload-plugins`.
4. Ask Claude Code to help you authenticate: type `set up Clay` or `help me connect my Clay account` and approve the skill it loads.
5. It gives you a link. If the terminal wraps it weirdly, copy the whole thing and paste it into your browser manually.
6. Choose the workspace you want to connect, hit Authorize, and go back to the terminal.
7. Restart Claude Code (`/exit`, then `claude --continue`) so it picks up the connection.

> **Gotcha (Option B):** the plugin authenticates over OAuth. If it shows 0 tools after install, run `/mcp`, select the Clay server, and click Authenticate. That browser login is the step people miss. If you are using a raw API key instead of OAuth, a standard Settings key may not work for building workflows. Use a key scoped correctly and created in your workspace account settings.

### 4. Verify the connection
Ask Claude Code:

```
Check if you can use Clay and tell me what actions and tools you have available.
```

When it lists Clay actions (finding emails, enriching a person or company, looking up a phone number, reading a table), you are connected. Every one of those actions costs credits, so the next thing to do is give it context so it spends them well.

---

## Part 2: Make it yours (the context files)

This is the prerequisite the video calls out. If Claude Code knows nothing about you, it cannot write good cold email for you. Before any run, create these five files in a `context/` folder. They are plain markdown. Editing them is how you swap this template to your business, your offer, and your target.

This is the same idea as building your own AI operating system: give the brain real, true information about you and your business, and it can act like you at scale.

### `business-profile.md` (in `context/`) (who you are + who you target)
The most important file. It holds:
- **Who you are:** your company, what you sell, in plain language.
- **Your ICP (ideal customer):** which businesses to target and why. Be specific. Size, geography, and the signals that mean they are a good fit (for example: they already pay for leads, they are hiring, they have reviews but no online booking).
- **The buyer:** the seniority you sell to (owner, founder, GM). Tell it to flag and skip a lead if only a junior contact comes back, never guess a decision-maker.

### `proof-and-offer.md` (in `context/`) (edit this per campaign)
- **Your offer:** written as Outcome + Timeframe + Catch (risk reversal). Example shape: "at least 5 extra booked jobs in 30 days, or you don't pay." If you have no real client results yet, use the honest zero-to-one version: "I'm just getting this off the ground, no case study yet. I'll run it free for 30 days, and if it doesn't work you owe nothing. I'd just ask to use you as a reference."
- **One ambiguous proof line:** vague on the client's name and vertical ("we recently helped a local business...") so the reader does not self-disqualify.

### `case-studies.md` (in `context/`) (your proof)
Your wins and outcomes. Label each one real or representative. This is source material for objection handling. Never let the agent turn a representative number into a claimed client result.

### `website-copy.md` (in `context/`) (your voice)
Paste your public-facing copy. Claude Code uses it so the emails sound like the same company.

### `faq.md` (in `context/`) (your objections)
Common objections and honest answers. Grounds replies and sanity-checks claims before they go in an email.

> **To swap verticals:** change the nouns. This template defaults to HVAC and home services, but the source → enrich → write → send chain is identical for plumbing, electrical, roofing, dental, salons, clinics, or anything local. Edit `business-profile.md`, swap the city and category, and update `proof-and-offer.md`.

---

## Part 3: The core loop

Four steps. Claude Code runs all four; you just prompt it.

**1. Source and enrich (Clay).** Claude Code asks Clay to find businesses that match your ICP, then enriches each one: resolves the company domain, finds the decision-maker, gets a verified email, pulls the phone number, and grabs review text for personalization. Coverage comes from Clay's waterfall: it tries providers in order and you only pay when one returns a match. A single vendor typically covers about 30% of a list; the waterfall pushes that toward 80 to 90%.

**2. Score against your ICP.** Claude Code reads your `business-profile.md` and keeps the leads that actually fit. Out-of-ICP businesses (national franchises, wrong size, wrong buyer) get dropped, not counted. For each kept lead it finds a real personalization hook from the live data: a specific review, a low rating on one thing, review recency, team size.

**3. Write the outreach.** Grounded in that lead's real data plus your offer and proof, Claude Code writes a personalized subject and body for every lead. This is the step Clay cannot do alone, because it needs the context only the brain holds.

**4. Push back to Clay and launch.** Claude Code delivers a clean CSV. You import it into Clay, map the fields, buy and warm sending domains, and launch the campaign from inside Clay.

---

## Part 4: The goal prompt (copy, paste, edit)

The trick that makes this hands-off is a **goal prompt**. It sets an end condition and tells Claude Code to keep working until it hits it, verifying its own output along the way. Here is the one from the video, generalized. Swap the bracketed parts.

```
I'm looking for leads. I want [50] fully enriched leads that are [YOUR TARGET: e.g. HVAC or home-service] companies. We're trying to reach [YOUR BUYER: e.g. business owners, presidents, decision-makers].

Every lead must be fully enriched:
- a verified email address
- their business's pain points
- anything that recently happened in their business (a signal)
- any notable achievements

Then, using that data, write me a personalized subject line and body for each one. Everything should be genuinely personalized to that specific business.

The CTA / end result we want: get them to say yes to [YOUR ASK: e.g. us sending over a 90-second video that shows how we can help solve their specific pain point].

Do not stop until you have all [50] leads. Use a dynamic workflow to verify you've done everything correctly and that everything is accurate. When you're done, deliver a CSV with all this information. There should be no blank columns. Every lead needs an email, a subject line, and a body, and they should be enriched with the other data.
```

If your setup supports a `/goal` command, use it so Claude Code keeps working toward the end condition and self-verifies. Behind the scenes it will launch several sub-agents (in the video, six agents each working a different city), source and enrich in parallel, then aggregate, de-dupe, check the yield, and rewrite anything that failed a check.

**Two speeds, both real:**
- A straight "find me 50 HVAC leads and output them here" run hits Clay and comes back in about **5 minutes**.
- The heavy goal-prompt run above, with verification passes, rewrites, and self-debate on the copy, took about **an hour** in the video. That is the trade for higher quality. Once it is dialed in, wrap it in a skill and fire it overnight to wake up to hundreds of leads.

---

## Part 5: What good enrichment gets you

A finished run gives you a CSV with columns like:

`Business · Decision Maker · Title · Email · Email Status · Phone · Website · City · Google Rating · Review Count · Business Pain Points · Recent Signal · Notable Achievement · Personalization Hook · Hook Source · Email Subject · Email Body · Needs Review`

Every email should be validated (verified against a checker like ZeroBounce), and every row should carry a true hook, not an invented one.

---

## Part 6: The copy rules (why the emails actually convert)

Enriched data does not get you clients. The email does. These rules are baked into the template so Claude Code follows them per lead.

**Subject line (highest leverage):**
- A true, specific, lowercase observation framed as the owner's own self-interest.
- Not curiosity bait ("quick question"), not generic pain ("struggling with missed calls?"), never salesy, never names the service or "AI".
- Reads like a local texting a local. Max ~8 words. Line 1 of the body pays it off.

**Body (60 to 90 words, hard cap 110):**
1. Line 1 is a true, specific observation pulled from their reviews or site. If there is no real hook, write an honest generic line and flag the row. Never invent specifics.
2. One ambiguous proof line, vague on the client's name so they don't self-disqualify.
3. The offer: Outcome + Timeframe + Risk reversal. The risk reversal is non-negotiable.
4. CTA is a short video ("can I send a 90-second video?"), not a 30-minute meeting.
5. Tone: humble, human, contractions, plain words. No jargon, no tool names, no em dashes, no emojis.

**The honesty rule that makes it work:** for an early-stage business with no named client yet, the honest zero-to-one offer beats a big guarantee. Owners have heard every bold promise. "I'm still getting this off the ground, I'll run it free for 30 days" disarms the usual agency pitch and gets the reply.

---

## Part 7: Verify before you send (optional but strong)

Since you cannot measure open rates reliably anymore, the honest proxy for "will this convert" is a simulated-recipient panel. Have Claude Code spawn a few skeptical-buyer personas (busy, pitched constantly, burned by agencies), let each one read only what the recipient would see, and vote: would I open this? Would I reply? If not, what killed it? Revise every lead any judge rejects, and repeat until a full round passes. The rejection reasons become your copy rules for the next batch.

**Guard against one failure mode:** never let the verification loop talk the writer into inventing proof. If a judge demands a named client and you don't have one, the honest move is to drop the proof claim, not manufacture a client. Hard-code "invent nothing" into any rewrite step.

---

## Part 8: Launch the campaign in Clay

Once you have the CSV of enriched leads with copy:

1. **Import to Clay.** In Clay, click Import Data → import a CSV → choose your leads file → comma delimiter → add to a new blank table → complete import.
2. **Create a campaign.** Go to campaigns, Add Lead List, and choose the table you just built.
3. **Map your copy.** Start from an empty message. Use variables: `/` → from your rows → pick your Email Subject column for the subject, and do the same for the Email Body. Preview to confirm it fills in correctly across all leads.
4. **Get sending accounts.** If you have none, go to Sender Accounts → Add Account → Buy Email Accounts. Choose Gmail or Outlook, type something close to your business name, and pick from the available domains (they don't have to be your exact name, just similar). You can buy up to five accounts per domain.
5. **Warm up and send safely.** Clay warms the domains for you and caps sends (around 30 per day per inbox) so you stay out of spam. Set up follow-ups too: a second message a few days later if no reply, then a third.

> **Deliverability is the gate.** A brand-new domain is not pre-warmed. Warm it about 2 to 3 weeks before you blast, keep each mailbox to roughly 30 to 50 sends a day, and make sure SPF, DKIM, and DMARC are set. Skipping this is the difference between the inbox and the spam folder. Claude Code builds and hands off the list; sending always happens Clay-side.

---

## Part 9: What it costs

In the video, a full 50-lead run with heavy verification cost about **172 Clay credits, roughly $12** (credits run about 7 cents each). A lean lead is around 1.4 credits, about a dime.

Do the math: reaching out to 100 leads costs on the order of $24 in data. If you convert even 1% of the people you reach, that one client is almost certainly worth far more than $24. The return on the data spend is not close.

Keep costs down by testing your workflow on a small batch (5 to 25 rows) before any full run, and by early-exiting on dead leads (no domain, no owner) before spending on the expensive email and review steps.

---

## Part 10: Honesty guardrails (non-negotiable)

These protect your reputation and your deliverability. They apply on camera and off.

- **Never fabricate** a personalization hook, a review, a review count, an owner name, or an email. Pull it live and verify it, or write the honest generic version and flag the row.
- **A verified email is earned per lead, not guaranteed.** Hit rate is lower on the smallest shops, and the address you get is often a generic office inbox, not the owner's personal one. Never imply you reach the owner every time.
- **Any metric you carry over as "representative"** stays labeled representative until you have a real, nameable result.
- **Cold reply rates are low** (low single digits). Faster outreach to the wrong people is just faster spam. Lean on true personalization and a real offer, not raw volume.

---

## Part 11: Keep it running

The thing you built is not "done." When the list goes stale, re-run the goal prompt. When replies dip, tighten line 1 and the offer. When a vertical works, clone the setup for the next one by editing the context files. Wrap the whole loop in a skill and schedule it, and you have an always-on lead machine you own, that you can run for yourself or sell as a service.

---

### Appendix: the enrichment chain under the hood

You do not need to memorize this. Claude Code figures out which Clay action to call. It is here so you understand what "enrichment" actually does and roughly what each step costs.

| Step | What it does | ~Cost (credits) |
|---|---|---|
| Source businesses | Find local businesses by city + category | 0.5 |
| Resolve domain | Company name → best-match domain (everything keys off this) | 0.2 |
| Find decision-maker | People at the company, gated on seniority | 0.1 |
| Find work email | Owner/work email from name + domain | 0.2 |
| Validate email | Confirm valid / catch-all / invalid | 0.1 |
| Review score | Rating, review count, and Google place ID | 0.2 |
| Review text | Pull review text for the personalization hook | 0.5 |
| Website scrape (fallback) | Published inbox, socials, phone | 0.1 |

One clean lead runs about 1.4 credits. The waterfall is why coverage lands near 80% instead of the ~30% a single vendor gives you.


## Provenance

- **Derived from** — Nate Herk's publicly shared resources (free Skool community drops and public GitHub repos). Source: Claude Code + Clay Makes Lead Generation Actually Fun (Jul 12, 2026). Author of record: Nate Herk. Published on the Clay Skills Marketplace under his name with his sign-off. Source repos that carry a license are MIT (Nate Herk, 2026).
- **Changes from the original** — the frontmatter `name` and `description`, which the packager wrote because Nate's drop-in template has no frontmatter; the marketplace sections appended below; and the wording edits listed here (made so the marketplace validator's deterministic checks pass; none changes what the skill does). The instructions themselves are Nate's.

### Wording edits made for packaging

```text
- SKILL.md [runtime path] ### `context/business-profile.md` -> ### `business-profile.md` (in `context/`)
- SKILL.md [runtime path] ### `context/proof-and-offer.md` -> ### `proof-and-offer.md` (in `context/`)
- SKILL.md [runtime path] ### `context/case-studies.md` -> ### `case-studies.md` (in `context/`)
- SKILL.md [runtime path] ### `context/website-copy.md` -> ### `website-copy.md` (in `context/`)
- SKILL.md [runtime path] ### `context/faq.md` -> ### `faq.md` (in `context/`)
```


## Declared inputs

Nothing here ships with a value; each one is the installer's.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **A Clay account, connected** | a Clay workspace connected to Claude Code through the public Clay connector or the Clay plugin; a non-customer gets the free trial credits that come with sign-up | no default. Sourcing, enrichment and the final send all happen in Clay, so the skill does not run |
| **Clay credits** | enough credit balance for the run; every enrichment action bills per matched row | no default. Every enrichment action costs credits and the body does not say what happens when the balance runs out mid-run. The body says to test on 5 to 25 rows first |
| **`business-profile.md` (in `context/`)** | who you are, what you sell, your ideal customer (size, geography, fit signals) and the buyer seniority you sell to | no default. The skill cannot score leads or decide who to skip without it; the body calls it the most important file |
| **`proof-and-offer.md` (in `context/`)** | your offer as outcome, timeframe and risk reversal, plus one deliberately vague proof line | no default. Without an offer the email has no third line; the body gives an honest zero-to-one version for a business with no results yet |
| **`case-studies.md` (in `context/`)** | your wins, each labeled real or representative | objection handling has no wins to draw on; the email's proof line still comes from `proof-and-offer.md` (in `context/`), and the writer is told never to turn a representative number into a client result |
| **`website-copy.md` (in `context/`)** | your public-facing copy | emails lose your voice and read like a stranger wrote them |
| **`faq.md` (in `context/`)** | common objections and honest answers | claims in the email are not sanity-checked against your own answers |
| **Target vertical, city, buyer and lead count** | the bracketed parts of the goal prompt (for example: 50 leads, HVAC companies in one city, owners and presidents) | no default for your run; fill the goal prompt's brackets. The body says the template defaults to HVAC and home services, which is Nate's example, so replace it with your own vertical |
| **Sending domains and mailboxes** | sender accounts bought or connected inside Clay, warmed 2 to 3 weeks, with SPF, DKIM and DMARC set | the CSV is still produced; the campaign step in Clay cannot launch safely and the body says skipping warm-up sends you to spam |

## What this skill touches

- **Reads** — the five files in your `context/` folder; Clay's sourcing and enrichment actions (find local businesses, resolve a domain, find a decision-maker, find and validate a work email, pull review score and review text, scrape a website as a fallback).
- **Writes** — one CSV of enriched leads with a subject line and body per row, delivered to you. With the Clay plugin (Option B) the run may also create a workflow in your Clay workspace to do the sourcing and enrichment. It does not import leads, create a campaign or send; you import the CSV into a Clay table yourself.
- **Never** — sends an email (sending always happens inside Clay, after you import, map and launch); invents a personalization hook, review, owner name or email address; turns a representative number into a claimed client result; names a client you do not have.
- **Halts** — none
- **Vendor-specific** — Clay. Sourcing, the enrichment waterfall and campaign sending all run in Clay; a non-customer gets a free trial with test credits and nothing else runs without it.
- **Derived from** — Nate Herk's "Claude Code + Clay Makes Lead Generation Actually Fun" drop-in template, republished with the packaging edits listed under Provenance. Author-confirmed insight: not yet (pending Nate's review).

## Representative output

### Lead CSV with copy

The full file carries these columns: Business, Decision Maker, Title, Email, Email Status, Phone, Website, City, Google Rating, Review Count, Business Pain Points, Recent Signal, Notable Achievement, Personalization Hook, Hook Source, Email Subject, Email Body, Needs Review. A few of them for two rows:

| Business | Decision Maker | Email | Email Status | Google Rating | Personalization Hook | Email Subject | Needs Review |
|---|---|---|---|---|---|---|---|
| Northwind Heating & Air | Dana Okafor, Owner | dana@northwindhvac.example | valid | 4.6 (212 reviews) | three reviews this month mention waiting two days for a callback | your two-day callback wait | no |
| Contoso Plumbing | Ray Contoso, President | office@contosoplumb.example | catch-all | 4.1 (38 reviews) | a review praises the tech but says the quote came three days late | those late quotes are costing you jobs | yes — catch-all, not verified |

The Northwind body, as written for that row: "Saw a few of your recent reviews mention waiting a couple days for a callback. I'm still getting this off the ground, no case study yet, so I'd run it free for 30 days and if it doesn't add at least 5 booked jobs you owe nothing. Can I send over a 90-second video showing how it'd work for you?"

### Run summary in chat

50 leads requested · 50 delivered with an email, subject and body (49 verified, 1 catch-all flagged for review) · 7 sourced businesses dropped as out of fit (2 national franchises, 5 with no owner found, among them Fabrikam Mechanical, where only a dispatcher came back) · Nate's measured run: about 172 credits, roughly $12, for 50 leads with heavy verification.

## What good looks like

A good run gives you a CSV with no blank cells in the email, subject or body columns, and every subject line is a lowercase, specific observation that the first line of the body pays off. The personalization hook in each row points at something you could find yourself in that business's reviews or website, and the hook source column says where. Rows where no true hook existed carry an honest generic first line and a "yes" in the needs-review column instead of an invented detail. Out-of-fit businesses (franchises, wrong size, only a junior contact) are dropped, not padded in to hit the count. Bodies sit between 60 and 90 words, offer an outcome with a timeframe and a risk reversal, and ask for a short video rather than a meeting. A thin run looks like the opposite: subject lines that read "quick question", hooks that repeat the company name, a proof line that names a client you never had, and a lead count reached by keeping generic office inboxes for shops with no owner found. If a verification pass argued the writer into adding proof, the run failed even if the CSV is full.

## What this skill does not claim

Never run end to end by the packager, so no measured cost, latency or yield.

The body has no step that stops for your approval before Clay credits are spent. It advises a 5 to 25 row test batch before a full run, and an early exit on dead leads (no domain, no owner) before the paid email and review steps, but that stop is yours to take.

The credit figures in the body (about 172 credits, roughly $12, for 50 leads; about 1.4 credits per lean lead) are from Nate's measured run and are not a promise; your vertical, city and Clay pricing will differ.

Coverage numbers in the body (a single vendor near 30 percent, the waterfall near 80 to 90 percent) are Nate's account of how Clay's waterfall behaves, not something the packager measured.

A verified email is earned per lead; hit rate is lower on the smallest shops, and the address returned is often a general office inbox rather than the owner's.

Output quality depends on the five context files the installer writes; with thin or vague files the emails are generic.

Cold reply rates are low single digits by the body's own statement; the skill does not claim to change that.

The goal-prompt run with verification, sub-agents and rewrites took about an hour in Nate's video; the packager has not timed it.

Sending, warm-up and deliverability are Clay-side steps the installer performs; the skill does not check that they were done.

Personalization hooks and pain points are the model's reading of live review text, not ground truth.

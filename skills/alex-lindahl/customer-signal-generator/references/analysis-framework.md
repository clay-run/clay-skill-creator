# ICS Analysis Framework

This is the chain-of-thought reasoning framework for generating Ideal Customer Signals. Work through each section sequentially — later sections depend on the context built in earlier ones.

---

## Section 1: Executive Summary

Write a 4-6 sentence executive summary that gives a busy GTM leader the key takeaway without reading the full document. Cover:
- What the company sells and to whom (one sentence)
- The 2-3 highest-value signal themes you identified (e.g., "security team expansion + compliance deadlines + cloud migration")
- The single strongest signal cluster and why it matters
- A clear recommendation on where to focus first

This section is written *last* (after completing the full analysis) but presented *first* in the output.

---

## Section 2: Company Understanding

Synthesize your web research into a structured company profile. This is the foundation — everything downstream depends on accuracy here.

Cover each of these:

**Products & Capabilities:** What does the company sell? Name specific product lines, not just categories. What are the core capabilities and key differentiators?

**Business Pains Addressed:** What problems does a buyer have *before* purchasing this product? Be specific — not "improve efficiency" but the concrete operational pain.

**Primary Personas:** Identify 3-5 personas across the buying committee:
- **User/Practitioner** — who uses the product day-to-day
- **Champion** — who advocates internally for the purchase
- **Economic Buyer** — who signs the check
- **Technical Evaluator** — who vets the product against requirements
Include real job titles, not generic roles.

**Ideal Customer Profile:** Define the ICP across these dimensions:
- Industry verticals (be specific — "mid-market fintech" not just "financial services")
- Company size (revenue and/or headcount ranges)
- Technical maturity indicators (what does their stack look like?)
- Organizational maturity (what team structures suggest readiness?)
- Geographic considerations if relevant

**GTM Motion:** How does this company primarily sell? Product-led growth, enterprise sales-led, channel/partner, hybrid? What does the typical buying journey look like?

**Lead Acquisition:** How do leads typically enter the funnel? Free trial, demo request, content download, outbound, partner referral, marketplace?

---

## Section 3: Triggers of Need

Identify 8-12 internal situations, objectives, or pain points that create demand for this company's products. These are the *reasons* a company would buy — the triggers that precede the buying journey.

Frame each as a conditional:

> **If** [specific situation or goal] **is happening at a company, then** they likely need [specific product or capability] **because** [concrete reason].

The "because" clause is important — it forces specificity and connects the trigger to the product's actual value.

Examples of good triggers:
- "If a company is migrating from on-prem to AWS and has more than 50 developers, they likely need [container security platform] because their attack surface is expanding faster than their security team can manually review."

Examples of bad triggers (too generic):
- "If a company wants to improve security, they need [security product]."

---

## Section 4: External Signals (ICS)

Reverse-engineer from the triggers in Section 3: what externally observable signals suggest those triggers are happening? This is the core of the analysis.

Organize signals into these categories. Aim for 3-5 signals per category, but don't force signals into categories where they don't naturally fit — some categories will be richer than others depending on the company.

**Demographic & Firmographic**
Company size thresholds, funding events, industry shifts, geographic expansion, M&A activity, revenue milestones.

**Hiring & Org Design**
New roles being created, team expansion patterns, leadership hires, department restructuring. Hiring signals are often the strongest leading indicators of strategic priorities.

**Technographic**
Technology adoption, migrations, stack changes, tool consolidation, platform upgrades. What technology changes create a need for this product?

**People Movement**
Executive hires (especially from the company's existing customer base), departures of key roles, board appointments, advisory relationships.

**Initiatives & Programs**
Named programs or initiatives (e.g., "digital transformation," compliance projects, DevSecOps adoption), certifications being pursued, standards being adopted.

**Public Announcements & Strategy**
Product launches, partnerships, earnings call themes, conference presentations, press releases, strategic pivots.

**Web & Content Signals**
Blog readership, webinar attendance, documentation visits, community engagement, social media activity around relevant topics.

**Intent & Behavioral**
G2/TrustRadius research activity, review site comparisons, trial signups, pricing page visits, competitor content consumption.

---

## Section 5: Signal Deep-Dives

For each signal identified in Section 4, provide a structured deep-dive. This is where the analysis becomes actionable.

For every signal, fill in ALL of the following fields:

**Signal:** Clear, specific name (e.g., "Hiring Director of Cloud Security" not "Security hiring")

**What it Indicates:** The likely internal objective, pain point, or strategic shift this signal reveals. Connect it back to a specific trigger from Section 3.

**Why Now:** What makes this a timely moment to engage? What's the window of opportunity and why does it close?

**Primary Persona(s):** Which persona(s) from Section 2 are most relevant? Use the actual job titles you identified.

**Buying Stage:** Awareness / Consideration / Decision — and briefly explain why you placed it there.

**Messaging Angle:** A specific hook that speaks to this moment and persona. This should reference the company's actual product capabilities, not generic value props.

**Campaign Ideas:** 2-3 concrete plays — outbound sequences, ad targeting strategies, webinar themes, content pieces, event plays. Be specific enough that a marketing team could execute on this.

**Best Channels:** Where to reach these personas with this message — LinkedIn, email, paid search, G2 display, events, partner channels, etc.

**Ease of Detection:** Low / Medium / High — based on data availability and signal reliability at scale.

**How to Programmatically Detect:** This is critical. Describe the actual data source and detection logic someone would implement. Name specific APIs, platforms, or data providers. Examples:
- "Query LinkedIn Jobs API for titles containing 'Cloud Security' OR 'DevSecOps' at companies with 200-5000 employees in target verticals"
- "Monitor Crunchbase for Series B+ funding events > $20M in fintech vertical, cross-reference with BuiltWith for legacy tech stack indicators"
- "Track G2 buyer intent data for category views on 'Container Security' from accounts matching ICP firmographics"
- "Parse SEC 10-K filings for mentions of 'digital transformation' or 'cloud migration' in risk factors or strategic initiatives sections"

Vague suggestions like "monitor hiring trends" or "track industry news" are not acceptable — specify the data source, the query logic, and the filtering criteria.

---

## Section 6: High-Intent Signal Clusters

Identify 3-5 combinations of signals that, when they co-occur, strongly indicate buying intent. Individual signals are useful, but clusters are where conversion rates spike.

For each cluster:

**Cluster Name:** A memorable, descriptive name (e.g., "The Cloud Migration Surge")

**Signals Involved:** List 3-4 signals from Section 4 that form this cluster

**Why This Cluster Matters:** Explain the narrative — what's happening inside the company when all these signals fire together? Why is the combination more powerful than any single signal?

**Recommended Play:** A specific, multi-touch engagement plan. Include:
- Who to target (persona and seniority)
- What to lead with (which message/content)
- Sequencing (what comes first, what follows)
- Expected timeline from signal detection to outreach

---

## Section 7: Signal Scorecards

### Scorecard A: Top 10 Core Signals

Rank the 10 most actionable signals by scoring each on:
- **Conversion Likelihood** (1-5): How strongly does this signal correlate with a purchase?
- **Strategic Value** (1-5): How well does this signal indicate ICP fit?
- **Ease of Detection** (1-5): How reliably can this be tracked at scale with available tools?

Present as a table with columns: Rank, Signal, Conversion (1-5), Strategic Value (1-5), Detection Ease (1-5), Total Score, Rationale.

Sort by total score descending.

### Scorecard B: 10 Creative/Non-Obvious Signals

Think beyond the standard playbook. What unconventional or underutilized signals could give a competitive edge? These might be harder to detect but highly differentiated.

Examples of creative signals:
- Conference speaking submissions on relevant topics
- Open-source project contributions in adjacent technologies
- Glassdoor reviews mentioning tool frustration
- Patent filings in relevant domains
- Regulatory comment submissions
- Supply chain or vendor changes visible in public filings

Present in the same scorecard format as Scorecard A.

---

## Section 8: Cross-Sell & Competitor Displacement

### Cross-Sell Signals
What signals indicate an existing customer is ready to expand their usage? This could be:
- Growing into new use cases
- Hitting usage thresholds
- Expanding to new teams or departments
- Encountering adjacent problems the product also solves

For each cross-sell signal, include the signal, what expansion it suggests, and a recommended upsell play.

### Competitor Displacement Signals
What signals suggest a prospect or customer is dissatisfied with a competitor or ready to switch?

If specific competitors were provided by the user, analyze each one individually:
- What are the known weaknesses or gaps of this competitor?
- What signals indicate frustration with this competitor specifically?
- What's the switching trigger — the moment where "good enough" becomes "not good enough"?
- Messaging that positions against this competitor's specific shortcomings

If no competitors were provided, identify the most likely 2-3 competitors based on research and provide displacement signals for each.

Include messaging and campaign recommendations for each displacement scenario.

---

## Section 9: Outbound Message Templates

Provide 4-6 ready-to-customize outbound message templates, each tied to a specific signal or signal cluster from the analysis. These should be practical — a sales rep should be able to personalize and send within 5 minutes.

For each template:

**Trigger:** Which signal or cluster fires this message

**Persona:** Who it's written for

**Channel:** Email, LinkedIn, etc.

**Subject/Hook:** The opening line or subject line

**Body:** The full message (keep to 4-6 sentences for email, 2-3 for LinkedIn)

**Call to Action:** What you're asking for

Include at least:
- 1 template for a top-of-funnel awareness signal
- 1 template for a high-intent signal cluster
- 1 template for a competitor displacement scenario
- 1 template for a cross-sell/expansion signal

The messages should feel human and relevant to the moment — not like mass outbound. Reference the specific signal that triggered the outreach.

---

## Section 10: How to Build This (Implementation Guide)

Provide a practical implementation section that helps a GTM team operationalize the signals identified in the analysis. This should be tool-agnostic but concrete.

Cover:

**Data Architecture:** What data sources are needed to detect these signals? Organize by:
- First-party data (CRM, product usage, marketing automation)
- Third-party data (intent providers, technographic databases, job board APIs, news monitors)
- Enrichment data (firmographic, contact, org chart)

**Signal Detection Workflow:** A step-by-step workflow for:
1. Ingesting signal data from sources
2. Scoring and qualifying signals against ICP
3. Enriching matched accounts with contact and context data
4. Routing qualified signals to the right team (SDR, AE, CSM)
5. Triggering automated plays (sequences, ads, content)

**Recommended Enrichment Stack:** Suggest specific categories of tools (without being overly prescriptive about vendors) for:
- Signal detection and monitoring
- Account and contact enrichment
- Sequence and outreach automation
- Intent data aggregation

**Quick Wins vs. Long-Term Builds:** Categorize the signals into:
- **Quick wins** (can detect and act on within 1-2 weeks with existing tools)
- **Medium effort** (requires new data source integration, 2-4 weeks)
- **Long-term builds** (requires custom detection logic or multiple data source combinations, 1-3 months)

---

## Output Formatting Notes

When producing the final output:
- Lead with the Executive Summary (Section 1), even though it's written last
- Use clear section headers and visual hierarchy
- Tables should be clean and scannable — avoid walls of text in table cells
- Signal deep-dives (Section 5) are the longest section — use a consistent card or panel format so they don't blur together
- The scorecards (Section 7) should be actual tables, not prose
- Outbound templates (Section 9) should be in a copy-friendly format
- The implementation guide (Section 10) should feel practical and actionable, not theoretical

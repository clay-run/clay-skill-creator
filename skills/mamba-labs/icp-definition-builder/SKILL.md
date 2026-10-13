---
name: icp-definition-builder
description: |
  Turn a description of a business into a structured ideal customer profile with firmographic criteria, signals, pain indicators and exclusion rules. Use when someone asks who to sell to, wants to define their ICP, build targeting criteria, or segment a market.
license: MIT
compatibility: "Claude Code, Claude Desktop, Codex CLI, Cursor, Gemini CLI, and other agents that read SKILL.md. Live data steps need only what the Requirements section of the skill lists."
metadata:
  title: "ICP Definition Builder"
  category: "identity-enrichment"
  keywords: "identity, who is my ideal customer, define my icp, build targeting criteria, help me segment my market, set up account filters"
  version: "2.1.0"
  requirements: "Needs no account, key or paid service: it works from the files, exports and answers you give it."
---

# ICP Definition Builder

## What this does

Most ICP documents are a list of adjectives that no filter can apply. This skill produces a profile whose every line is either a filter you can run or a signal you can detect, plus the exclusion rules that matter more than the inclusion rules, because exclusions are what keep a list clean.

## Requirements

This skill needs no account, API key or paid service. It works from the files,
exports and answers you give it, in any agent that reads SKILL.md.

## What this skill touches

- **Reads**: the description, wins and losses you give it, and `BRAND.md` at the project root if it exists.
- **Writes**: nothing outside this session. The output is an ICP block for you to review and paste into `ICP.md`.
- **Never**: sends email, writes to a CRM, calls a paid service, or spends credits.

## Declared inputs

| Input | Who supplies it | If it is missing |
| --- | --- | --- |
| business: what is sold, to whom, and what it replaces | you | the skill asks for it and does not guess |
| wins: your best customers and why they were good | you | the skill asks; without wins it states that the profile is aspirational, not derived |
| losses: deals that churned or never closed | you | the skill proceeds and marks exclusions as unconfirmed by loss evidence |
| `BRAND.md` at the project root | optional | the skill works from your answers and offers to write the file |

No account, API key, Clay credit or paid service is needed.

## When to use it

- who is my ideal customer
- define my ICP
- build targeting criteria
- help me segment my market
- set up account filters

## Inputs

- **business**: what is sold, to whom, and what it replaces
- **wins**: the best customers you have, and why they were good
- **losses**: deals that closed and churned, or never closed

## Shared context this skill reads

Before doing anything else, read whichever of these exist at the project root and
use them instead of asking the user to repeat themselves:

- `BRAND.md`

If none exist, do the work from what the user gives you, then offer to write the
missing file so the next skill in the pack starts warmer.

## Tool connection

This skill needs no live data tool. It works from the files, exports and answers
you give it, so it runs the same in any agent with no setup.

## Method

1. Start from the wins, not from the aspiration. The ICP is a description of who already buys well, and it is usually narrower and less flattering than the aspiration.
2. Derive firmographics as ranges and lists, never as adjectives. Mid market becomes a headcount band with a number on each end.
3. Derive the signals: what is observably true about a company at the moment it becomes a good time to reach them.
4. Derive the pain indicators, which are the things a company does when it has the problem you solve, and which are usually visible in hiring, stack or public statements.
5. Write the exclusions explicitly, including the ones that feel obvious. Competitors, existing customers, companies below a size floor, regulated segments you cannot serve, and geographies you cannot support.
6. Write the tier rule: what makes an account tier A rather than tier B, expressed so two people would sort the same list the same way.
7. Finish with the disqualifying question, the one thing a rep can ask on a first call that reliably ends a bad fit early.
8. Check the output with `scripts/check-output.py` before you return it.

## Approval stop

This skill does not send email or write to a CRM. If the user asks it to, stop first:
show what would be sent or written and wait for an explicit yes.

## Output

The ICP as a structured block: firmographic filters, signals, pain indicators, exclusions, tier rule, and the disqualifying question. Written so it can be pasted into `ICP.md` at the project root.

## Check the output before you return it

Save the output to a file and run `python3 scripts/check-output.py <file>`. The
contract it checks is `scripts/output-contract.json`.

- Exit 0, `COMPLETE`: return the output.
- Exit 2, `INCOMPLETE`: do not present the output as finished. Fill what you can, run
  the check again, and if parts stay missing, return the output under the heading
  `Incomplete` with every reason the check printed.

## Quality bar

- Every firmographic criterion is a range or a list, never an adjective
- Exclusions are present and include existing customers and competitors
- The tier rule is deterministic enough that two people sort the same list identically
- The profile is derived from stated wins rather than from ambition

## Related skills

- `icp-fit-scoring`
- `company-discovery-list-builder`
- `clay-people-search-workbook`

Ships in the **signal-based-selling**, **clay-operator** packs.

## Representative output

### ICP block

Invented example for a company selling accounts payable automation (Northwind Payables):

```
ICP: Northwind Payables

Firmographic filters
- Headcount: 200 to 2,000 employees
- Industry: wholesale distribution, light manufacturing, logistics
- Geography: United States and Canada
- Finance team: 5 to 40 people

Signals
- Open role for an AP manager or controller in the last 60 days
- ERP migration announced (NetSuite or Microsoft Dynamics) in the last 6 months

Pain indicators
- AP clerk postings that mention invoice volume above 2,000 per month
- Public statements about closing the books late

Exclusions
- Existing customers (for example Contoso Distribution)
- Competitors and their resellers
- Under 200 employees
- Public sector and regulated healthcare payers

Tier rule
- Tier A: inside every filter and at least one signal in the last 60 days
- Tier B: inside every filter, no signal yet
- Everything else: out

Disqualifying question
- "How many supplier invoices does your team process in a month?" Below 1,000 ends the fit.
```

## What good looks like

A good run reads as filters and signals someone could apply to a list without asking you anything: every criterion is a range or a named list, exclusions name existing customers and competitors, and two people would sort the same accounts into the same tiers. A thin run is full of adjectives such as "mid market" or "innovative", has no exclusions, or describes the customer you want rather than the customers you have. The output checker returns `INCOMPLETE` on a run that is too short or still holds placeholders.

## What this skill does not claim

It does not score accounts or apply weights; scoring is a separate step.
It does not verify any firmographic fact against a live data source.
It has never been measured on win rate or reply rate, so it makes no performance claim.
The profile is only as accurate as the wins and losses you describe.

## License

MIT, see `references/LICENSE`. Copyright (c) 2026 Mamba Mindset Growth B.V.

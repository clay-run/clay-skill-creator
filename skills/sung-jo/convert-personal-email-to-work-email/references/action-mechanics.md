# Action mechanics — two-stage waterfall: personal email → identity → work email

Ported from a Clay template whose keys predate the MixRank→CPJ migration and whose RocketReach and
Nymblr providers were retired (no same-provider successor — dropped). Every key below is the
**current** equivalent, verified to resolve via `clay workflows actions schema`. If a key stops
resolving, rediscover it (recipe at the bottom) — never guess.

## The CLI envelope

Every call is one out-of-band action, once per unique personal email:

```
clay workflows actions test <packageId> <actionKey> --inputs '<json>'
```

Returns `{ "result": <payload|null>, "metadata": <object> }`. `result == null` with
`metadata.status = SUCCESS_NO_DATA` is an **honest empty**, not an error, not a retry.
`metadata.upfrontCreditUsage.totalCost` is the real credit cost — sum for actual spend. Exit codes:
`2` bad inputs / action failed · `3` no permission (often a provider needing a connected account) ·
`1` credit/exec cap · `4` rate-limited. **Gate on `result` (+ validation in Stage B), never exit 0.**

## Dead key → current key map

| Template key | Status | Current key |
|---|---|---|
| `mixrank-enrich-email-address` | renamed (CPJ) | `cpj-enrich-person` (takes `email`) |
| `enrich-person` | retired (generic) | `cpj-enrich-person` |
| `enrich-person-with-mixrank-v2` | renamed (CPJ) | `cpj-enrich-person` |
| `rocket-reach-find-professional-email` | retired provider | none — dropped |
| `nymblr-find-work-email` | retired provider | none — dropped |
| `enrich-person-and-company`, `snov-enrich-person-by-email`, `snov-enrich-person-by-social-v2`, `findymail-find-work-email`, `leadmagic-find-work-email`, `prospeo-find-work-email-v2`, `dropcontact-enrich-person`, `find-email-v2`, `datagma-find-work-email-v3`, `validate-email` | still valid | unchanged |

## Stage A — resolve identity (personal email → profile + name + company domain)

Run in order; **stop at the first that returns a profile AND a company domain.** Gate on the company
domain, not on the call succeeding — an enrichment with no current-company domain has not resolved
the identity for our purposes.

| # | Resolver | packageId | actionKey | input |
|---|---|---|---|---|
| 1 | CPJ | `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2` | `cpj-enrich-person` | `{"person_identifier":"<personal email>","email":"<personal email>"}` |
| 2 | Clearbit | `e5f3b09f-1b8f-4806-a960-27abf163940f` | `enrich-person-and-company` | the personal email |
| 3 | Snov.io | `d8c220e0-401e-49ca-8c6b-37c7577baffd` | `snov-enrich-person-by-email` | the personal email |

Optional additional resolver if more coverage is wanted:
`limadata-find-professional-profile-from-email` (packageId `0c31f9dd-6365-4e6a-a462-418d46f0d161`,
Limadata) — "Find professional profile from email". From `cpj-enrich-person` read `.result.name`,
`.result.latest_experience.company_domain`, `.result.latest_experience.url` (LinkedIn); other
providers expose the equivalent under their own shapes — confirm the path on the first live row.

If a LinkedIn URL is resolved but name/domain are thin, `snov-enrich-person-by-social-v2` (same Snov
packageId) enriches from the profile URL.

## Stage B — find the work email (name + company domain → validated work email)

Run in order; validate after each; **stop at the first validated email.** All take the resolved full
name + company domain. Confirm each provider's email output path on the first live row.

| # | Provider | packageId | actionKey |
|---|---|---|---|
| 1 | Findymail | `9515bb04-4267-4074-94eb-653545c3c38f` | `findymail-find-work-email` |
| 2 | LeadMagic | `edb58209-a62d-42be-992a-e41b87eeacc2` | `leadmagic-find-work-email` |
| 3 | Prospeo | `48a31bbb-63e6-4461-8a62-d88bb2cd6b0f` | `prospeo-find-work-email-v2` |
| 4 | Dropcontact | `6ddf27b7-ad83-4419-be62-c83f9c9e34a7` | `dropcontact-enrich-person` |
| 5 | Hunter | `9cfc7721-5c91-423b-a0b0-4cc1f42c6089` | `find-email-v2` |
| 6 | Datagma | `f240a97e-3d3e-4ffa-a85e-8d70afe348a5` | `datagma-find-work-email-v3` |

*(The template also had RocketReach and Nymblr as providers 7–8; both are retired with no successor
and are dropped — six providers remain.)*

## Validation — `validate-email` (the acceptance gate)
- **packageId** `8f0d2dc0-a6b4-4b84-9aad-a330b4a4586a` · **inputs** `{"email":"<candidate>","onlySafe":true}`
- **Accept only when `.result.status` is valid** (also returns `.result.sub_status`,
  `.result.address`, `.result.free_email`, `.result.smtp_provider`). `onlySafe:true` rejects
  risky/catch-all; loosen only if asked, and say so. Verified live in the prior ports.

Some providers bill through the installer's **connected account** — a `3`/auth error means it isn't
connected; skip it and say so, don't fail the row.

## If a key stops resolving — rediscover, don't guess

```
clay workflows actions list > catalog.json
jq -r '[.. | objects | select(has("actionKey"))] | .[]
       | select((.displayName//.name//"")|test("work email|professional profile from email|enrich person";"i"))
       | "\(.actionKey)\t[\(.packageDisplayName)]\t\(.displayName//.name)"' catalog.json | sort -u
clay workflows actions schema <packageId> <actionKey> | jq '[.inputParameters[].name]'
```

Match on capability, confirm it resolves, update the key. A `not_found` key is deprecated — replace
it, never ship it.

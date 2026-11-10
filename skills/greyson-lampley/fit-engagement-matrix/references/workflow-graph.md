# The workflow graph, read off the edges

This is the shape the source workflow had on 2026-11-10, read from its configuration with
`clay workflows graph get --mode full`, never from a run. Every node is listed in dependency
order with its type, what feeds it, and its edges. Build the same shape. If you deviate, write the
deviation into your build notes so an installer debugging a hang can see it existed.

Workspace handles never appear here. Every field name, topic list and threshold is a declared
input from `SKILL.md`; the Python is in `scoring-code.md`.

## Conventions

- **Pins** are typed inputs on a node that point at an upstream node's output. A code node's
  outputs are read at `$.<field>`. A tool node's action result is read at `$.result.<field>`.
- **Edges** are declared on the destination node as incoming edges. From a conditional, each edge
  names a rule id, and exactly one destination carries the default route.
- **Action mappings** on tool nodes bind the action's parameters: `static` for a fixed value,
  `reference` for `{{a pinned input}}`, `coalesce` for the first non-empty of several references.
- Serial wiring throughout. There are no parallel branches that rejoin; every conditional's
  branches reconverge on the next step by both destinations pointing at it.

## Nodes in dependency order

### 1. Trigger

Manual trigger for testing with inputs `name`, `email` (required), `company_domain`,
`recent_activity` (comma-separated event names). In production, replace with a webhook whose
payload carries the same four fields, or an Audiences segment trigger. Creating a trigger with the
CLI returns the trigger id, not the canvas node id; read the trigger back to get the node id the
first node wires to. A trigger may have exactly one outgoing edge.

### 2. Clean contact — code

- Pins: `name`, `email`, `company_domain`, `recent_activity` from the trigger.
- Edge: from the trigger.
- Outputs: `contact_email`, `contact_name`, `email_type` (work | personal | invalid),
  `company_domain`, `recent_activity`. For a personal or invalid email, the domain is set to a
  sentinel that no enrichment will resolve, so downstream steps return not-found rather than
  failing.

### 3. Match contact in Audiences — tool

- Action: the Clay-native Audiences lookup, entity type contact.
- Pin: `contact_email` from Clean contact.
- Mapping: filter on the email field, include fields and signals, 90-day signal lookback, limit 1.
- Edge: from Clean contact.
- Read: `$.result.totalMatched`, `$.result.records[0].fields.id`,
  `$.result.records[0].fields['<LinkedIn URL field>']`, `$.result.records[0].fields['<Title field>']`,
  `$.result.records[0].fields['<Seats invited field>']`, `$.result.records[0].signals`.

### 4. LinkedIn URL on the record? — conditional, rules

- Pin: `audiences_linkedin` from the contact match, the LinkedIn URL field.
- Rule `has_url`: `audiences_linkedin` NotEmpty.
- Edge: from the contact match.
- Destinations: rule `has_url` → Enrich person. Default → Find LinkedIn URL.

### 5. Find LinkedIn URL — agent, web search on

- Runs only on the default branch, when the record has no URL.
- Pins: `contact_name`, `contact_email`, `company_domain` from Clean contact; `title_hint` from
  the contact match's title field.
- Prompt: in `scoring-code.md`. Output schema: `linkedin_url` (url), `confidence` (select: High,
  Medium, Low), `evidence` (string).
- Edge: from the LinkedIn check, default route.

### 6. Enrich person — tool

- Action: the managed person-enrichment function.
- Pins: `contact_email` from Clean contact; `audiences_linkedin` from the contact match;
  `claygent_linkedin` from Find LinkedIn URL.
- Mapping: the profile identifier parameter is a coalesce of `audiences_linkedin` then
  `claygent_linkedin`; the email parameter is `contact_email`.
- Edges: from the LinkedIn check on rule `has_url`, and from Find LinkedIn URL.
- Read: `$.result.title`, `$.result.url`, `$.result.current_experience[0].company_domain`. An empty
  `result` with a not-found preview is a miss.

### 7. Enrich company — tool

- Action: the managed company-enrichment function.
- Pins: `company_domain` from Clean contact; `person_company_domain` from Enrich person at
  `$.result.current_experience[0].company_domain`.
- Mapping: the company identifier is a coalesce of `company_domain` then `person_company_domain`.
- Edge: from Enrich person.
- Read: `$.result.name`, `$.result.domain`, `$.result.employee_count` or `$.result.size`,
  `$.result.industry`, `$.result.annual_revenue` or `$.result.revenue`, `$.result.url`,
  `$.result.linkedin_url`. Headcount may arrive as a band string beside an exact count; the code
  reads the exact count and never parses a band.

### 8. Match company in Audiences — tool

- Action: the Clay-native Audiences lookup, entity type account.
- Pins: `resolved_domain` from Enrich company at `$.result.domain`; `input_domain` from Clean
  contact.
- Mapping: filter on the domain field with a coalesce of `resolved_domain` then `input_domain`;
  include fields and signals; 90-day lookback; limit 1.
- Edge: from Enrich company.
- Read: `$.result.records[0].fields` keyed by the installer's company field names for workspaces
  created, last workspace created date and last signup email; `$.result.records[0].signals`.

### 9. Company topic intent — tool

- Action: a company topic-intent action from the installer's catalogue.
- Pins: `resolved_domain`, `input_domain` as above.
- Mapping: the domain parameter is the same coalesce; the topics parameter is the installer's
  company topic list as a static array; a result limit.
- Edge: from the company match.
- Read: `$.result.topics[]` with `topic_name` and `composite_score`.

### 10. Any LinkedIn URL? — conditional, rules

- Pins: `enriched_linkedin` from Enrich person at `$.result.url`; `audiences_linkedin` from the
  contact match; `claygent_linkedin` from Find LinkedIn URL.
- Rule `found`: any of the three Contain `linkedin.com/in/`, combined with Or.
- Edge: from Company topic intent.
- Destinations: rule `found` → Person topic intent. Default → Account fit.

### 11. Person topic intent — tool

- Action: a person topic-intent action from the installer's catalogue.
- Pins: the same three URL sources.
- Mapping: the profile URL parameter is a coalesce of enriched, then record, then agent-found; the
  topics parameter is the installer's person topic list as a static array; a result limit.
- Edge: from Any LinkedIn URL on rule `found`.
- Read: `$.result.topics[]` with `topic_name`, `composite_score`, `stage`.

### 12. Account fit — code

- Pins: `company_data` from Enrich company at `$.result`; `email_type` from Clean contact.
- Edges: from Any LinkedIn URL default route, and from Person topic intent.
- Outputs: `fit_score`, `fit_band`, `fit_reasons`, `company_name`, `industry`, `employee_count`,
  `revenue`.

### 13. Borderline fit? — conditional, rules

- Pin: `fit_score` from Account fit.
- Rule `borderline`: `fit_score` GreaterThanOrEqual the band floor And LessThanOrEqual the band
  ceiling (declared input; the author used 40 and 74).
- Edge: from Account fit.
- Destinations: rule `borderline` → ICP judgment. Default → Engagement.

### 14. ICP judgment — agent

- Runs only in the borderline band.
- Pins: `company_name`, `industry`, `employee_count`, `revenue`, `fit_score`, `fit_band`,
  `fit_reasons` from Account fit; `company_domain` from Clean contact.
- Prompt: in `scoring-code.md`. Output schema: `icp_verdict` (select: Strong, Partial, Weak),
  `fit_adjustment` (number, bounded), `judgment_reason` (string).
- Edge: from Borderline fit on rule `borderline`.

### 15. Engagement — code

- Pins: `company_lookup` from the company match at `$.result`; `account_intent` from Company
  topic intent at `$.result`; `person_data` from Enrich person at `$.result`; `lookup_data` from
  the contact match at `$.result`; `recent_activity` from Clean contact; `contact_intent` from
  Person topic intent at `$.result`.
- Edges: from Borderline fit default route, and from ICP judgment.
- Outputs: `engagement_score`, `engagement_band`, `account_subtotal`, `contact_subtotal`,
  `engagement_reasons`, `engagement_channels`, `intent_summary`, `current_title`,
  `seats_invited`, `workspaces_created`, `record_status`, `account_found`.
- When Person topic intent did not run, `contact_intent` is absent and the code treats it as no
  topics. When ICP judgment did not run, the matrix step treats the adjustment as zero.

### 16. Place on the matrix — code

- Pins: `fit_score`, `fit_reasons` from Account fit; `fit_adjustment`, `judgment_reason` from
  ICP judgment; `engagement_score`, `account_subtotal`, `contact_subtotal`, `engagement_reasons`,
  `engagement_channels`, `intent_summary` from Engagement; `contact_name` from Clean contact.
- Edge: from Engagement.
- Outputs: `final_fit_score`, `engagement_score`, `engagement_status`, `priority_tier`,
  `next_action`, `matrix_quadrant`, `matrix_position`, `score_badge`, `priority_reason`,
  `first_name`, `last_name`, `contact_status`, `account_subtotal`, `contact_subtotal`,
  `engagement_channels`.

### 17. Contact already in Audiences? — conditional, rules

- Pin: `total_matched` from the contact match at `$.result.totalMatched`.
- Rule `exists`: `total_matched` GreaterThan 0.
- Edge: from Place on the matrix.
- Destinations: rule `exists` → Update record. Default → Create record.

### 18. Update record — tool

- Action: the Clay-native Audiences record update, entity type contact.
- Pins: `record_id` from the contact match at `$.result.records[0].fields.id`; the five score
  outputs from Place on the matrix.
- Mapping: the record id; the selected record fields are the installer's five score field ids,
  each bound to its output; remove-null-values true so a blank never overwrites a value.
- Edge: from the existence check on rule `exists`.

### 19. Create record — tool

- Action: the Clay-native Audiences upsert, entity type contact.
- Pins: `contact_email`, `contact_name` from Clean contact; `first_name`, `last_name` and the five
  score outputs from Place on the matrix.
- Mapping: lookup on email; record fields are email, name, first name, last name and the five
  score fields; remove-null-values true.
- Edge: from the existence check, default route.

### 20. Route by play — conditional, rules

- Pin: `priority_tier` from Place on the matrix.
- Rules in order: `target` when the tier Contains the first tier's label; `nurture` the second;
  `opportunistic` the third. Default is the fourth.
- Edges: from Update record and from Create record.

### 21 to 24. Four play placeholders — code

- One per tier. Pins: `priority_tier`, `next_action`, `score_badge`, `priority_reason`,
  `first_name` from Place on the matrix.
- Each emits `play`, `action`, `message`: the text a real action would send. Swapping one for a
  Slack message, a sequence enrolment or an ad audience is the installer's step, outside this
  skill, with its own approval.

## Groups on the canvas

Four named groups keep the canvas readable: Enrich (nodes 2 to 11), Score (12 to 15), Prioritize
and write (16 to 19), Act (20 to 24). Groups do not change behaviour. A group needs at least two
nodes, and external edges may only touch its entry or exit members.

## Checks before the batch

`clay workflows graph validate` must return valid with no errors. Then run ten contacts with
`clay workflows runs test` and read every node with the verbose run output. The things that have
gone wrong on this graph, in order of frequency: a pinned path that resolves to nothing because a
tool node was in the way; a required action input reaching the action empty; an output schema in
the wrong shape; a conditional with two default routes after an edge update replaced the set.

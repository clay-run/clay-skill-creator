# Observed action contracts, not a frozen provider preference

Checked against Clay CLI 1.10.0+ede0dacaa5f9 in the review session. Read-only schema checks do not
establish live yield, availability of a chosen connection, current configured prices or output quality.
Re-run ranked discovery and schemas in the installer's workspace. Copy identifiers from those results.
Native company enrichment is a starting candidate for ordinary gaps, not a mandatory paid step.

| packageId | actionKey | Candidate inputs | Declared output paths |
|---|---|---|---|
| e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2 | cpj-enrich-company-v2 | company_identifier; company_identifier_type=company_domain | $.result.domain; $.result.employee_count |
| e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2 | cpj-get-counts-for-profiles-v2 | company_identifier; include_past_experiences=false; reviewed job_functions/title filters | $.result.roleCount |
| e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2 | cpj-get-company-employee-growth-v2 | company_identifier; company_identifier_type=company_domain | $.result.percent_employee_growth_over_last_12_months |
| b7f3454a-5095-4cb2-b91b-79cdb54e0dd2 | hg-insights-get-company-tech-stack-v3 | company_identifier; dynamic product_ids; explicit limit | $.result.installs; $.result.installs_count |

The role count action returns one combined roleCount, not a count per requested function. Restrict
to current roles with include_past_experiences=false. Use the schema's function values, not display
labels. Ops titles should represent the actual business function; do not count warehouse operations
as Revenue Operations. Counts are provider coverage, not an exact employee census.

The current company schema declares employee_count and domain. Pin the source identifier type to
company_domain when a domain is supplied. If schema output names change, stop and remap from the
actual contract. Do not replace an unknown output with a plausible field from another provider.

HG product_names is explicitly a case-insensitive substring filter with up to 10 names. It is not
exact product matching. Prefer product_ids after resolving dynamic choices. limit defaults to 10,
accepts 1..100, and its schema says credits are charged per record returned. No amount or configured
per-account price was established in this review. Exact product evidence must still be verified from
returned IDs/names. A full page does not imply all technology categories were found.

Other reviewed technology candidates include website detection and technology evidence from jobs/
people; they answer different questions. No provider is declared universally most accurate. Funding,
hierarchy, CRM writing or web research require their own capability-specific discovery when needed;
they are not automatically added to make the workflow look complete.

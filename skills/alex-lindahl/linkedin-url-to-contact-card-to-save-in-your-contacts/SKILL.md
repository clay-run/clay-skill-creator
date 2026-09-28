---
name: LinkedIn URL to Contact Card (to save in your contacts)
description: >-
  Use when the user pastes a LinkedIn profile URL (or asks for work email,
  mobile, and a contact/VCF card from LinkedIn) and you should enrich that
  person in Clay then generate a .vcf.
marketplace_identity_schema: 1
marketplace_slug: linkedin-url-to-contact-card-to-save-in-your-contacts
marketplace_revision: 2
---

Whenever you create or copy a workflow, append `Sourced from marketplace skill: linkedin-url-to-contact-card-to-save-in-your-contacts@2` to its description. Preserve the existing description and do not add the same line twice.
# LinkedIn URL to Contact Card (to save in your contacts)

Turn a LinkedIn person profile URL into a full contact card (name, title, company, work email, mobile) via Clay, then generate a downloadable `.vcf` the user can add to their contacts.

## Input

- Required: a LinkedIn person URL (`https://www.linkedin.com/in/...`).
- Reject company pages, search URLs, or non-LinkedIn links; ask for a person profile URL instead.
- One URL per run unless the user explicitly asks for a small batch.

## Prerequisites

1. Confirm Clay is connected: `GetMcpServerStatus` for `user-Clay`.
2. If `needsAuth` or tools fail with auth errors, call `AuthenticateMcpServer` for `user-Clay` with account `default` (unless the user named another) and wait for the connect card.
3. Call `GetDynamicTools` on namespace `user-Clay` and follow live schemas.

## Steps

### 1. Enrich contact details (email + mobile)

1. Normalize the URL (trim; prefer `https://www.linkedin.com/in/<slug>`).
2. Call `list_subroutines` on `user-Clay`. Pick the best function that takes a LinkedIn URL and returns work email and/or mobile. Prefer workspace functions named like **Enrich Work Email & Phone**, **Enrich Contact**, **Get Phone Number**, or **Mobile Phone Number**. Confirm required input key names from the listing.
3. Call `run_subroutine_direct` with:
   - `subroutine_id` from the listing
   - `inputs`: a single-element array whose keys match that subroutine’s input names (often `Linkedin URL` or similar — never guess; use the listed names)
4. If one subroutine only covers email or only phone, run a second `run_subroutine_direct` for the missing field.
5. Poll `get-task-context` (fallback `get-task`) with the returned `taskId` until enrichments are complete. Retry while state is in-progress. Never claim a field is missing without checking `get-task-context`.

### 2. Enrich profile fields (name, title, company)

Contact-detail subroutines often return email/phone only. Also fetch profile context:

1. Prefer fields already present on the enrichment task (`get-task-context`).
2. If name/title/company are missing, resolve the person with Clay search tools (e.g. `find-and-enrich-list-of-contacts` with name + company domain once known, or another profile subroutine that accepts the LinkedIn URL). Poll `get-task-context` again.
3. Required card fields to collect:
   - **Name** (FN / N)
   - **Title** (TITLE)
   - **Company** (ORG)
   - **Work Email** (EMAIL;TYPE=WORK)
   - **Mobile** (TEL;TYPE=CELL)
4. Never invent any of these. Leave a field blank in the VCF if Clay did not return it; tell the user which fields were missing.

### 3. Generate a VCF and deliver it

1. Write a vCard 3.0 file under `/workspace` named from the person, e.g. `Kieran_Flanagan.vcf` (sanitize spaces to underscores; ASCII-safe filename).
2. Use this shape (omit lines for fields that are truly empty):

```
BEGIN:VCARD
VERSION:3.0
N:Last;First;;;
FN:Full Name
TITLE:Job Title
ORG:Company
EMAIL;TYPE=INTERNET,WORK:work@example.com
TEL;TYPE=CELL:+15551234567
URL:https://www.linkedin.com/in/slug/
END:VCARD
```

3. Split `FN` into `N` as `Last;First;;;` when the name is two+ parts (last token = family name; remainder = given name). If only one token, use `N:Name;;;;` and the same for `FN`.
4. Escape commas/semicolons/newlines in vCard values per vCard 3.0 (`\\`, `\,`, `\;`).
5. Send the user:
   - A short contact summary in chat (Name, Title, Company, Work Email, Mobile, LinkedIn)
   - The `.vcf` as a file attachment (`SendToUser` type attachment with the `file://` or box path)
6. Mention they can open/download the VCF to add it to Contacts.

## Guardrails

- Enrichments cost Clay credits; do not batch large URL lists without an explicit ask.
- Do not push results into CRM, Slack, or email unless the user asks.
- Do not scrape LinkedIn in the browser for email/phone; Clay is the source of truth.
- If Clay is unavailable and the user declines connecting it, stop and say what you need.
- Always produce the VCF when at least name + one of email/phone is available; still attach a partial card and note missing fields.

## Alternative path (no matching subroutine)

If no suitable subroutine exists, fall back to Clay search tools: resolve the person via `find-and-enrich-list-of-contacts` (needs name + company domain) or an equivalent search, then `add-contact-data-points` with `{ type: \"Email\" }` and a Custom data point for mobile only if Email alone does not return phone. Prefer subroutines when the user already gave a LinkedIn URL.

---
name: csv-to-clay-webhook-sender
description: |
  Load a CSV into a Clay table through its webhook source without breaking the table's
  formulas: one JSON object per POST (never a CSV import, never a batched array), payload
  keys mapped to the exact names the table's {{Webhook}} formulas read, a 25-row test you
  check inside Clay before anything else is sent, then a detached bulk send with keep-alive
  connections, a small worker pool, jittered retries, a progress file and a failed-rows
  file for targeted resend. Use whenever someone asks: send this CSV to my Clay webhook,
  push rows into a Clay table, my webhook columns are blank after import, Clay CSV import
  broke my formulas, how fast can I load rows into Clay, I got 429s sending to Clay, resume
  a Clay webhook send, or load leads into Clay from a file. Do NOT use it to create or
  configure the Clay table or its columns, to qualify or enrich the rows, to dedupe them
  against a CRM, to update rows already in the table, or to send to any endpoint that is
  not a Clay webhook source.
---

# CSV to Clay webhook sender (one row per POST, keys the table actually reads)

The insight: **a Clay table fed by a webhook resolves `{{Webhook}}.<key>` per row, so the only
load path that keeps its formulas alive is one JSON object per POST, and the two things that
silently ruin a send are the key names and the worker count.** The author measured all three
on real loads. A CSV import into the same table leaves every `{{Webhook}}` formula blank, because
an imported row has no webhook payload. A JSON array of two rows posted to the webhook created
one row, so batching is not an option either. A column named one thing read a payload key named
another: five columns whose formula read a plain-English key were sent the column's own name
instead, the POSTs returned 200, and the columns landed empty on 0 of 25 rows. And throughput
plateaued at about 8.6 rows a second however many workers ran; 16 workers with un-jittered
backoff and 5 retries lost 11.6% of rows permanently, while 8 to 12 workers with jittered
backoff and 8 retries ran at 0 to 0.5% failure. So the skill reads the key names off the table's
own formulas, sends 25 rows and makes you look at the columns before the rest goes, and never
offers more workers as the way to go faster.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for
it, never substitute a plausible default, and where an answer does not exist say which step
becomes unavailable rather than guessing. Where a default IS defensible it is named below, and
using it means saying so in the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **The CSV** | a UTF-8 CSV (or TSV) with a header row, one lead per row | no default; there is nothing to send |
| **Webhook URL** | the URL shown on the table's Webhook source in Clay | no default; the skill cannot send. It is a credential-like value: never echo it in logs or output files |
| **The table** | the Clay table the webhook feeds, so its column formulas can be read | the key mapping cannot be derived; the installer pastes the keys each `{{Webhook}}` formula reads, or confirms the CSV headers are already those keys |
| **Key mapping** | CSV header → payload key, for every column the table reads | derived from the table's formulas in Step 2 and shown for correction; a header with no formula reading it is sent unchanged and flagged |
| **Columns to drop** | CSV headers that must not reach Clay (internal ids, run labels, scratch columns) | default none; everything is sent and the installer is told so |
| **Test size** | rows in the first send the installer checks inside Clay | the author uses 25; if they have no view use it and SAY it is borrowed |
| **Workers and retries** | parallel connections and attempts per row | the author uses 8 and 8; say they are borrowed. The skill refuses more than 12 workers and says why |
| **Resume offset** | rows already sent, when restarting a stopped send | default 0; the progress file from the last run carries the number |
| **Per-row cost of the table** | what the table's own columns spend when a row lands, read from the table's credit usage after the test send | no default. Until the test has run, the gate reports the cost as unknown rather than estimating it |

**If an answer sheet is present beside this skill, load it and ask only for what it does
not cover.** A partial sheet is normal; a value it is missing gets asked for on its own
rather than restarting the interview. **Say which values came from the sheet** before using
them. **If there is no sheet, say nothing about sheets.** At delivery, offer to save the
answers back (identifiers only, never the webhook URL), private and never published, in
words that explain the offer: *"want me to save your answers to a file, so the next person on
your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — the CSV you supply, and the column configuration of the one table you name (formulas only, to learn which payload keys they read). Never a row of that table.
- **Writes** — new rows into the Clay table the webhook feeds, one per CSV row, and its own files on this machine: a progress file, a send log, a failed-rows file.
- **Never** — deletes or updates a row already in the table, imports the CSV directly, posts to any URL other than the webhook you named, or sends the webhook URL anywhere but to the webhook itself.
- **Halts** — Step 4 spend-approval, Step 4 write-approval.

## Step 0 — Check the platform works, and say where the work runs

This skill reads a CSV on your machine, optionally reads one table's column formulas, and
posts rows to a webhook you named. Each landed row is a new record in your Clay table, and
every column on that table runs on it, so the spend is whatever your table's columns cost
per row. Nothing else is written.

Confirm `python3` is available (3.9 or newer) and that the sender script shipped with this
skill is present at `scripts/send_webhook.py`. If the key mapping is to be derived, confirm
the Clay CLI answers `clay whoami` and names the workspace that owns the table; say which
workspace out loud. If `python3` is missing, or the CLI is signed out, say which, give the one
fix (install Python 3.9+, or `clay login`), and stop. Do not install or fetch anything.

Where the work runs: reading, mapping, preflight and reconciliation run in this agent at no
cost. Only the landed rows spend, inside the installer's own table.

> Do not start a step before the steps above it have their answers. If a declared input is
> missing, ask for it; never assume a default and continue.

## Step 1 — Collect the definition (interview; do not guess)

Take the declared inputs in this order: the CSV, the webhook URL, the table, columns to
drop, test size, workers and retries, resume offset. Read the CSV with UTF-8 (`utf-8-sig`, so
a BOM does not corrupt the first header) and report: row count, header list, and any header
that is empty or duplicated. A duplicated header is a stop: two CSV columns cannot both become
one JSON key.

State the cost shape now, plainly: the webhook itself is free to receive; the bill is the
table's columns firing on each new row, and that number is read off the table after the test
send, not estimated here.

## Step 2 — Derive the key mapping from the table's own formulas (the decision this skill exists to make)

A column's display name and the payload key its formula reads are two different strings, and
only the second one matters. Read the table's column configuration (`clay tables columns get
<tableId>`, configuration only) and collect every formula that references the webhook source.
Each reference has the shape `{{Webhook}}?.Key` or `{{Webhook}}?.["Key With Spaces"]`. The set
of keys those formulas read is the contract the payload must meet.

Then build the mapping table and show it:

| CSV header | Payload key | Read by column | Status |
|---|---|---|---|

Status is one of four values and no fifth: `matched` (a formula reads exactly this header),
`renamed` (a formula reads a key that differs from the header only by case, underscores, a
suffix or spacing, so the header is renamed to it), `unread` (no formula reads this header; it
is sent unchanged and will sit in the raw payload only), `dropped` (on the installer's drop
list). Invite corrections before continuing. **Never guess a rename the formulas do not
support**: a key you invent is a key that lands blank with a 200.

If the table cannot be read, ask the installer to paste the keys their formulas read, or to
confirm the headers already are those keys, and record that the mapping was supplied rather
than derived.

Write the mapping to a JSON file beside the CSV (`{header: payload_key}` for renames,
`"__drop__": [headers]` for drops). The sender script takes it with `--keymap`.

## Step 3 — Free checks before anything paid

All at no cost, in this order, and a failure stops the step:

1. **Preflight the keys.** After mapping, every payload key must be in the set the formulas
   read or be explicitly marked `unread`. A key that is `renamed` in the mapping but still
   appears in its original form in the payload is a stop.
2. **Encoding.** Read with UTF-8 and never latin-1; a latin-1 read double-encodes accents
   (`é` becomes `Ã©`) and the damage lands in Clay as data. Spot-check three non-ASCII cells
   if the file has any.
3. **Null tokens.** Cells reading `nan`, `None`, `null`, `NULL` are pandas or export artifacts,
   not values; send them as empty strings so a `{{Webhook}}` formula sees blank, not the word.
4. **Row count and offset.** Rows to send = total − resume offset. Say the number.
5. **Dry run.** `python3 scripts/send_webhook.py --file <csv> --keymap <map.json> --dry-run`
   prints the first mapped payload and the key list, and sends nothing.

## Step 4 — A 25-row test, then ONE gate: the batch, the cost, the write, the ask

Send the test rows for real:

```
python3 scripts/send_webhook.py --file <csv> --keymap <map.json> --webhook "<url>" \
  --limit <test size> --workers 2 --progress <dir>/send_progress.txt \
  --failures <dir>/failed_rows.jsonl
```

Then make the installer look inside Clay, not at the HTTP codes: a 200 proves the row
arrived, not that any column read it. Ask them to open the table, find the new rows, and
confirm that each `matched` and `renamed` column shows a value on rows that had one in the
CSV. A column blank on all 25 rows while its CSV cells were populated is a key-name miss;
go back to Step 2 for that column. Ask them to read the credit usage the 25 rows consumed;
that is the per-row cost.

Then one message, and stop: the 25 rows and which columns landed; the full send cost
(`rows remaining × per-row cost read from the test`, or "unknown: the table's columns did
not report usage yet" if it did not); **that this writes `N` new rows into the table named
`<table>`, and that is a write into your workspace, not a read**; the worker and retry
settings; and the ask. Stop a second time only if the test reveals something the installer
could not have anticipated: a column landing blank, a count far off, a formula erroring on the
payload.

## Step 5 — The bulk send, detached

Run it detached from the conversation, because a large file takes longer than a session
turn: tens of thousands of rows at about 8 rows a second is more than an hour.

```
nohup python3 scripts/send_webhook.py --file <csv> --keymap <map.json> --webhook "<url>" \
  --skip <test size + resume offset> --workers <workers> --retries <retries> \
  --progress <dir>/send_progress.txt --failures <dir>/failed_rows.jsonl \
  > <dir>/send.log 2>&1 &
```

What the script does, so the installer can judge it: one persistent connection per worker;
each row is one POST with the mapped JSON object; HTTP 408, 429 and 5xx are retried with
exponential backoff multiplied by a random factor between 0.5 and 1.5 (jitter), capped at 10
seconds; any other non-200 is written to the failures file once and not retried, because a
400 is a payload problem and retrying it is futile; a tally of every status code seen is
written to the progress file every two seconds alongside done, ok, failed and rows per
second. Poll the progress file, not the log.

**If the installer asks for more workers to go faster, say no and why**: the author measured
the plateau at about 8.6 rows a second, and 4, 8 and 12 workers produced 34, 85 and 125
rate-limit responses per 300 rows for the same throughput. The script refuses more than 12.

## Step 6 — Reconcile, single-valued

When the progress file reads `done = rows to send`, compare three numbers: rows the script
reports `ok`, rows in the failures file, and the table's row count increase as the installer
reads it in Clay (or through the CLI if their account exposes it). The verdict is one of four
values and no fifth:

- `complete` — ok + failed = sent, failed = 0, and the table grew by exactly ok.
- `complete-with-failures` — failed > 0; the failures file is the resend list. Run the sender on it with `--from-failures`.
- `landed-short` — the table grew by fewer rows than ok. Rows were accepted and not materialised; report the gap and the time window, do not resend blindly, because a resend of accepted rows creates duplicates.
- `unverified` — the table count could not be read. Say so; do not report `complete`.

## Step 7 — Deliver

Hand back the mapping file, the progress file, the send log, the failures file (possibly
empty, and say so) and the verdict line. Then say plainly: every row sent is now a record in
the installer's table and every column on that table has run or is running on it; the spend
is on their table's credit usage, not in anything this skill holds. Offer to save the
non-secret answers (mapping, drops, test size, workers) beside the skill.

## Representative output

### Key mapping (shown for correction before anything is sent)

| CSV header | Payload key | Read by column | Status |
|---|---|---|---|
| company_name | Company | Company | renamed |
| Phone | Phone | Phone (first try) | matched |
| linkedin_url | LinkedIn Link | LinkedIn Link | renamed |
| run_label | | | dropped |
| scrape_notes | scrape_notes | | unread |

### Progress file (rewritten every two seconds during the send)

| done | ok | failed | rows/sec | status tally |
|---|---|---|---|---|
| 12,480 / 31,206 | 12,471 | 9 | 8.4 | 200: 12,471 · 429: 318 · 400: 9 |

### Verdict line

`31,206 rows · 25 tested, all 7 read columns landed · 31,181 bulk-sent at 8.4 rows/s in 62 min · 9 failed (400, written to failed_rows.jsonl) · table grew by 31,197 · complete-with-failures`

The 9 failed rows are the honest case: a 400 is the payload, not the network, and they are
handed back as a file rather than retried into the ground.

## What this skill does not claim

- The logic comes from the author's own sender scripts and the loads they ran; nothing checks it against a system that can be re-run here.
- The throughput ceiling (about 8.6 rows a second) and the worker findings were measured against one workspace's webhook on one day in 2026; another webhook may differ. The script's worker cap is a safety setting from that measurement, not a platform specification.
- Whether a Clay webhook ever splits a JSON array into rows was tested once, on one table, with a two-element array that produced one row. The skill does not batch for that reason, and has not re-tested it.
- The per-row cost is whatever the installer's table spends; this skill reads it off the test send and never estimates it in advance.
- A 200 response is treated as "arrived", not as "read by a column". Only the installer looking at the table confirms the second.
- If the table's columns cannot be read, the mapping is whatever the installer supplied, and the skill says so.
- Row counts read through the CLI depend on the installer's account exposing them; where they do not, the verdict is `unverified` rather than `complete`.

## What good looks like

- The mapping table shows at least one `renamed` row on any table whose column names differ from its payload keys. A mapping that is 100% `matched` on a table with space-named columns probably did not read the formulas.
- After the 25-row test, the installer names a column they looked at and saw populated. "The POSTs returned 200" is not that.
- The status tally shows 429s during the bulk send and a failure count near zero. Many 429s and many failures together means the workers or retries were raised past the measured band.
- The verdict is one word from the set, with the three numbers that produced it. A send that ends with "it finished" and no table count is `unverified`, and the delivery says so.
- A thin run looks like this: 300 rows, 25 tested, two columns blank because the header was sent as-is, mapping corrected, resent. The correction before the bulk send is the skill working.

## Rules

- MUST send one JSON object per POST; NEVER import the CSV into the table and NEVER post an array.
- MUST derive payload keys from the table's own formulas where the table can be read, and show the mapping before sending; NEVER invent a rename.
- MUST run the test send and have the installer confirm columns inside Clay before the bulk send.
- MUST read the CSV as UTF-8; NEVER latin-1.
- MUST run the bulk send detached with jittered retries; NEVER exceed 12 workers, and NEVER present more workers as the way to go faster.
- MUST write non-retryable failures to a file and hand it back; NEVER retry a 400.
- MUST state the write in the gate as a write into the named table.
- NEVER update or delete rows already in the table, and NEVER post to a URL the installer did not name.
- NEVER echo the webhook URL into logs, output files or the answer sheet.

## Worked example

Ask: "Load this 31k-row scrape into my Clay table; last time the LinkedIn column came in
empty." Interview: a UTF-8 CSV with 34 headers, the webhook URL, the table name, three
scratch headers to drop, test 25, workers 8, retries 8, offset 0. Step 2 reads 41 column
formulas on the table and finds 19 that reference the webhook; 11 headers match, 7 are
renamed (`linkedin_url` → `LinkedIn Link`, `company_name` → `Company`, and five more), 3 are
dropped, 13 are unread and said so. Step 3: preflight clean, two accented cells spot-checked,
`nan` tokens blanked, dry run shows the first payload. Step 4: 25 rows sent; the installer
opens the table, the LinkedIn column is populated on the 18 rows that had one; credit usage
read as 3 per row. Gate: 31,181 rows × 3 credits, a write of 31,181 rows into the named
table, 8 workers, 8 retries: yes. Step 5 runs detached, 62 minutes, tally shows 318 429s and
9 400s. Step 6: table grew by 31,197; verdict `complete-with-failures`, 9 rows in the
failures file for a targeted resend. Delivered with the mapping file saved for next time.

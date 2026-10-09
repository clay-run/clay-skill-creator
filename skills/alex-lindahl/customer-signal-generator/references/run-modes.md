# Run Modes

The skill has four modes. Full mode is the original 10-section analysis. The other three are lighter and reuse saved signals, so the skill can be run weekly rather than once per company.

## Picking a mode

| Mode | Use when the user... | Needs saved signals? |
|---|---|---|
| **Full** (default for a new company) | names a company and asks for ICS, buying signals, or a signal playbook | No |
| **Quick** | says "quick", "top signals", "for a demo", "short version", or needs it fast | No |
| **Account** | names a specific prospect account and asks "why now", "is X a good target", "what's firing at X", or "prep me on X" against an existing ICS | Yes (or runs Quick first) |
| **Refresh** | asks to re-run, update, or refresh the board, or "what changed since last time" | Yes |

If the request fits more than one mode, pick the lighter one and say which mode ran in the first line of the output. Don't stop to ask.

## Finding saved signals

Account and Refresh modes start from a saved `signals.yaml` (structure in `references/signal-schema.md`). Look in this order:

1. A `signals.yaml` or an ICS report `.html` among the files the user uploaded or attached. Reports embed the YAML in a `<script type="application/yaml" id="ics-signals">` block.
2. A claude.ai artifact link to a previous ICS report: use the Artifact tool with action `read`, then extract the embedded YAML.
3. Past chats: `conversation_search` for "[seller company] signals.yaml" or "[seller company] ICS".

If nothing is found:
- **Account mode:** run Quick mode for the seller company first (say so in one line), then continue with the account.
- **Refresh mode:** tell the user there's nothing to refresh and offer a Quick or Full run.

If the saved signals are more than 90 days old, say so and suggest re-running the back-test, but continue.

---

## Quick mode

Goal: a usable signal set and board in one pass, without the full deep-dives.

1. Step 0 setup as normal.
2. Step 1 with 3–4 searches instead of 4–6.
3. Step 2 [Clay] as normal.
4. Write a short analysis:
   - Section 1: Executive Summary (3–4 sentences)
   - Section 2: Company Understanding, condensed to products, 3 personas, and the ICP in a few lines
   - Section 3: 5 triggers instead of 8–12
   - Sections 4 + 5 merged: up to 10 signals in a single table with columns Signal, Trigger, Persona, Threshold, Decay window, How to detect
   - Section 6: the single strongest cluster
   - Section 7: Scorecard A only
   - Sections 8–10: skip, apart from one line naming the main competitor and its displacement signal
5. Skip the back-test (Step 4). Mark every signal `verdict: not_backtested`.
6. Step 6 [Clay] signal board on up to 20 accounts, credit gate first.
7. Output a compact HTML report (or markdown if asked), plus `signals.yaml`.

Footer: "Quick mode: signals are not back-tested. Run Full mode before using these weights for routing."

---

## Account mode

Goal: a one-page "why now" brief for a single prospect account, scored against the saved signal set.

**Inputs:** account name or domain (required); saved signals (found as above); seller perspective (taken from the saved file's `meta`).

**Steps:**

1. Load the saved signals and state which ICS they came from and its run date.
2. **ICP fit check.** [Clay] `search-companies` for the account domain, then `add-company-data-points` for Headcount Growth, Annual Revenue, and Latest Funding. Compare against the ICP in `meta.icp`. If it clearly fails the ICP, say so up front and keep the rest short.
3. **Detect signals.** Show the user which signals will be checked and the rough credit cost for one account, and get a yes. Then run the Clay recipes for every signal with a `clay_source`. Run 2–3 web searches for signals without one (recent news, announcements, initiatives).
4. **Apply decay windows.** A signal only counts if its evidence date is inside `decay_window_days`. Record days remaining for each firing signal.
5. **Score** using the account scoring rules in `references/signal-schema.md`, including the cluster bonus.
6. **Contacts.** [Clay] `search-contacts` at the account for the persona titles linked to the firing signals. Return up to 5. Don't enrich emails unless asked.
7. **Write the brief** (format below).

**Brief format** (one screen, markdown in chat by default; HTML only if asked):

- **Header:** account, seller perspective, score and tier, date, source ICS run date
- **Verdict:** 2–3 sentences on why now, or why not now
- **Signals firing:** table with Signal, Evidence (with date and source tag), Days left in window, Weight
- **Cluster:** which Section 6 cluster is forming, if any, and what's missing to complete it
- **Recommended play:** the matching Section 9 template or play, adapted to this account's evidence
- **Who to contact:** name, title, persona role, and which signal makes them relevant
- **Watch list:** signals not yet firing that would raise the tier, with what to look for

Don't pad the brief. If only one signal is firing, say so plainly.

Account mode doesn't change the saved signals file. Offer to add the account to the board snapshot so Refresh mode tracks it.

---

## Refresh mode

Goal: re-score the board using the saved signals, and show what changed.

1. Load the saved signals, including `board_snapshot`.
2. **Build the roster.** Default: every account in the last snapshot, plus up to 20 new lookalikes from `search-companies` using the saved ICP filters. Show the roster and a credit estimate, and get a yes.
3. Re-run detection recipes for signals with `verdict: validated` or `weak` only. Skip `not_observed`.
4. Apply decay windows using today's date, and re-score.
5. **Diff against the last snapshot:**
   - **New to the board:** accounts scoring 25+ that weren't there before
   - **Moved up a tier / moved down a tier**
   - **Newly firing signals**, with evidence dates
   - **Expired:** signals that dropped out because their decay window passed
   - **Dropped:** accounts that fell below 25
6. Don't re-run the back-test unless asked or the saved back-test is over 90 days old (then suggest it).

**Output:** a "What changed since [last run date]" section at the top (the diff, most actionable first), followed by the updated board. Write a new `signals.yaml` with the new snapshot, and keep the previous snapshot under `previous_snapshot` (one level only, so the file doesn't grow).

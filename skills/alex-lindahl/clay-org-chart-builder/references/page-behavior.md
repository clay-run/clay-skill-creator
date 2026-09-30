# Page behavior

What the page built from `scripts/orgchart_template.html` does. Nothing here needs configuring; it is here so an installer can see what they are about to publish, and so a reviewer can check the page against `## What this skill touches` in `SKILL.md`.

- **Header:** the user's logo or wordmark, "OrgAtlas", and a Clay status pill. In Demo mode the pill turns amber and a banner appears.
- **Account header:** company, domain, industry, location, source, retrieval time, and leader, C-Suite and VP counts
- **Coverage strip** (account header):
  - **Counts:** leaders (C-Suite / VP), Champions, Exec buyers, Influencers, Blockers, Not yet classified, contacts found, Need a manager and Lines you set.
  - **Buying-role counts:** clicking one highlights those people and dims the rest.
  - **Need a manager:** jumps to the tray.
- **Toolbar:**
  - **Controls:** the view switch, search, and a Function dropdown. "Clear filters" appears while any filter is on.
  - **··· menu:** "Expand all teams" and "Reset local edits". The reset is two-step, with no browser dialogs.
- **View switch:** "Org chart" (the default) or "By level". The choice is remembered per company.
- **Org chart** (desktop):
  - **Layout:** the top executive is centered at the top. Their direct reports sit in function lanes: Engineering & Security, Product, Go-to-market, People, Finance & Legal, Operations & Strategy, and Other. Each lane has a colored header and a count, with teams indented beneath.
  - **Lines:** dashed for inferred, dotted amber for low confidence, solid in the primary color for lines the user set.
  - **Tiles:** kept slim, with initials, name and title. A colored left edge and pill appear only once a buying role is set. Email and mobile icons show when found, and an amber dot marks a local edit.
  - **Collapse:** each manager's tile has a collapse toggle ("▾ 3" / "▸ 5 hidden"). The state is remembered.
  - **Zoom and scroll:** zoom out, in, and Fit, remembered per viewer. Edge fades and a "Scroll →" hint appear when the chart is wider than the view. The chart opens centered on the top executive.
  - **Moving people:** drag a tile onto another tile to change who that person reports to. Drops onto yourself or anyone in your own team are refused, so no cycles.
  - **Drop zones:** during a drag, a "top of the chart" zone appears. The tray is also a drop target, for sending someone back to review.
  - **Filters:** search, function and role filters dim non-matching tiles instead of hiding them, so the tree stays intact.
  - **Focus mode:** clicking a tile opens its drawer and focuses the chart on that person. Their chain up to the top executive and their whole team stay bright, with those lines drawn in the primary color; everyone else dims. A "Focused on …" chip in the chart bar clears it, as do Esc, closing the drawer, or clicking empty chart space. On desktop the drawer is non-modal (no scrim), the page makes room for it, and clicking another tile switches focus. On phones the drawer stays modal.
  - **Motion:** on first load, lines draw in and tiles rise in one after another, top executive first, then lane by lane. When someone changes manager (drag, tray, or dropdown), their tile glides from its old spot to its new one and pulses once where it lands. Newly shown tiles fade in. All motion is turned off for viewers who ask for reduced motion.
- **New in role:** when any record has `roleStartDate`, the toolbar shows a "New in role" switch: Off, 3 mo, 6 mo (the default) or 12 mo, remembered per company. Leaders whose current title started within the window get an orange "New · N mo" badge and an orange ring, the coverage strip shows the count, and the drawer's Clay details show "In role since <Mon YYYY>". Months are counted from today. The footer says a recent promotion also counts. With no start dates the switch is hidden.
- **In the news** (bottom of the page, both views): dated cards with the outlet, a type tag (News, Press release, Byline), the headline linking to the article, a short summary, "Also at" links for syndicated copies, and chips for the leaders it names. Chips open that person's drawer. A row of person filters with counts sits above the cards. The header says "from public web sources, not Clay" and when it was checked. Tiles of people in the news show a small newspaper icon, and their drawer gets an "In the news" section with a link to their filtered list.
- **Needs review tray:** a sticky right-hand panel, which moves below the chart under 1100px. It lists everyone with no manager yet, grouped by the same function lanes, together with any teams under them, and explains why no line was guessed.
- **Phone width:** the org chart becomes an indented outline, and the coverage strip scrolls sideways. The drawer's "Reports to" dropdown replaces dragging.
- **By level:** "Level 1 — C-Suite" and "Level 2 — VP Leadership". Drag a card between sections to correct its level.
- **Drawer:** collapsible sections, in this order:
  - **Contact:** its badge shows how many contacts are found.
  - **Reporting:**
    - **Reports to:** a dropdown with Needs review, Top of the chart, or a person. It excludes the person and anyone in their team.
    - **Relationship note:** inferred, with its confidence and reason; Set by you, plus the original inference; or Needs review.
    - **Direct reports:** clickable, the first 6 with "Show all".
  - **Classification:** buying role and level.
  - **Clay details:** collapsed by default. Company, function, location, LinkedIn, verification and retrieved time, with "Not returned by Clay" where a field is missing.

  The drawer closes with Esc, its close button, or (on phones) the scrim. Focus is trapped only on phones, where it is modal.
- **Contact details** (top of the drawer):
  - **Showing a value:** an email already in the Clay search result, or one found earlier, shows with Copy.
  - **Looking one up:** otherwise the row offers "Find email with Clay" and, when a phone function is configured, "Find mobile with Clay". Each asks for an inline credits confirmation before it runs.
  - **How the email lookup runs:** `add-contact-data-points` (`Email`) on the build-time `clayTaskId` and `clayEntityId`. If Clay rejects that task, it falls back to `search-contacts-by-name` with the company's LinkedIn URL, then the same call.
  - **How the mobile lookup runs:** `run_subroutine_direct` with the configured function and input mapping, passing the sourced email when one exists.
  - **Waiting:** the page checks `get-task-context` every 4 seconds for up to 150 seconds and shows the real elapsed time.
  - **Timeouts:** a timed-out lookup is remembered, so "Check again" only re-reads the result and never starts a second paid lookup.
  - **Errors:** each connector error code gets its own message, e.g. add or reconnect the Clay connector, access turned off for this page, policy blocks it, or Clay didn't answer. When the connection isn't available, the page says lookups need claude.ai with the Clay connector.
  - **Saving:** results are saved per company in the viewer's browser, stamped "Sourced from Clay <time>", and shown as email and mobile icons on tiles. "Reset local edits" does not clear them, because they cost credits.
- **Local edits** (manager, buying role, level, collapsed teams, zoom, New-in-role window) are saved in `localStorage`, namespaced as `orgatlas:v1:<clayCompanyId | domain | name>`. They never overwrite the embedded Clay data or the embedded inference.
- **Empty state:** "No matching leaders", with nothing filled in
- **Layout:** responsive down to phone width, with light and dark themes and visible focus styles

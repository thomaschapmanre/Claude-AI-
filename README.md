# Young Development tools

Single-file HTML tools for Young Development property management. Each page runs in the browser; open it on claude.ai (as an Artifact) or as a local file.

| File | What it does |
|---|---|
| `tools/Command Deck.html` | Regional dashboard: My desk, Midtown, Call agenda (builds the weekly Word agenda), and Region (scorecard, comp survey, **Regional manager insights**, **Market surveys**). |
| `tools/Delq Packets.html` | Monthly delinquency packets from the MRI late letters report, plus affidavits of service for eviction filings. |
| `skills/monday-call-agenda/` | Draft Claude skill for running the Monday MRI and Engage reports. |

## Regional manager insights (Region tab)

A rules-based review of each community's monthly numbers that turns them into reviewed, sourced talking points for the weekly call.

**Privacy.** It runs entirely in the page. It does not call an AI API or send data anywhere. Every finding comes from a fixed rule you can read below and in the code (`<script id="region-insights-engine">`).

### Using it

1. Open the **Region** tab. Under **Regional manager insights**, pick the data and the month.
   - **My saved report data** is the default. It uses the monthly MRI figures saved through **Monthly reports** on the same tab.
   - **Fictional sample data** shows five invented communities, all labelled "(sample)", with three months of figures.
2. Optionally adjust **Targets and thresholds**. Changes are saved in this browser.
3. Work through the findings, grouped by community. Each one shows:
   - what was observed, with the figures;
   - why it matters;
   - the question to ask on the call, and a suggested next step;
   - **Evidence and calculation**: the figures used, the formula with the numbers filled in, the source report and the reporting period.
4. Edit the talking point if you want, then **Approve for agenda** or **Dismiss**. Nothing goes into the agenda unless it is approved.
5. On the **Call agenda** tab, click **Build Word agenda** as usual. Approved talking points are added as a final section, **Regional manager talking points**, grouped by community. Each point includes its question, source, period and calculation. If you approved nothing, the agenda is exactly as before. Points approved from sample data carry a "FICTIONAL SAMPLE DATA: delete this section before sending" note.

Approvals are stored per data source and month, so sample approvals never mix with real ones.

### Rules

The chosen month is compared with the most recent earlier month on file for the same report. All thresholds are editable; the defaults are shown.

| Area | Flagged when | Severity | Source report |
|---|---|---|---|
| Occupancy | Fell by ≥ 1.0 pt from the prior month, or is below the 95% target | High if it fell ≥ 2 pts or is ≥ 3 pts under target | MRI Box Score |
| Leasing pipeline | Any of: leased % below 95% target; leased % below occupancy; renewal conversion (signed ÷ expiring) below 50%; move-outs exceed move-ins | High if 2 or more | MRI Box Score; MRI Renewals / Move-ins / Move-outs |
| Delinquency | Rose ≥ 15% **and** ≥ $1,000 from the prior month, or is above 3% of the month's rental revenue | High if both | MRI Aged Delinquency; MRI Budget vs Actual |
| Revenue vs budget | Rental revenue variance below −2% | High if below −4% | MRI Budget vs Actual |
| Maintenance | Work orders open more than 7 days exceed 5, or rose by ≥ 3 | High if more than 10 | HappyCo Work Orders |
| Resident feedback | Average rating below 4.0, fell ≥ 0.3, or more than 2 negative reviews | High if 2 or more | Opiniion Resident Feedback |
| Unusual expenses | An expense line is ≥ 20% **and** ≥ $2,500 over budget | High if ≥ 40% over | MRI Budget vs Actual (expenses) |
| Data check | Occupancy differs from (units − vacant) ÷ units by more than 1 pt; reported budget variance differs from (actual − budget) ÷ budget by more than 0.5 pt; renewals signed exceed leases expiring; units with a balance exceed total units; unit count changed between months | Data check | The report(s) involved |
| Missing data | Any of the seven reports above is not on file for the month; its checks are skipped | Data check | Report history |

Change thresholds include the boundary: a fall of exactly 1.0 pt is flagged. Targets and limits do not: occupancy of exactly 95.0% is not below target.

Findings state only figures from the reports. They do not guess at causes. Questions and next steps ask the property team to explain or confirm.

### Data format

Each community is `{id, name, months: {"YYYY-MM": {...reports}}}`. A month can contain:

```
boxscore:    {occupancy, leased, units, vacant, notice}
delinquency: {delinquency, delinquentUnits}
budget:      {budgetVariance, actualRevenue, budgetRevenue}
renewals:    {renewalsDue, renewalsSigned, moveIns, moveOuts}
maintenance: {openWorkOrders, over7Days, avgDaysToComplete}
feedback:    {avgRating, reviews, negativeReviews}
expenses:    {lines: [{name, actual, budget}]}
```

The first four match what **Monthly reports** already saves. Maintenance, feedback and expense data are not loaded from real reports yet, so for real data those show as missing.

## Market surveys (Region tab)

Every property has its own market survey: its own approved competitors, its own dated survey records, and its own comparison. Properties in the same office do not share competitors unless you approve the same competitor for each.

### How it is organised

- **Offices.** Each property belongs to an office. Midtown is always its own office. Every other property starts as **Unassigned** until you pick its office on its survey page (choose **New office…** to create one). The app does not guess office assignments.
- **Overview.** The panel opens with one line for the whole region, then one section per office. Each office section lists:
  - its properties and when each was last surveyed;
  - where each one's rent sits against its own competitors, for each bedroom count;
  - new competitor concessions and competitor rent cuts;
  - surveys that need refreshing.

  There is no region-wide average rent, because the offices are in different rental markets.
- **Property survey page.** Click **Open survey** next to a property.

### Step by step for one property

1. **Approve competitors.** The page suggests competitors already on file. Suggestions are ranked by:
   - same submarket;
   - a starting rent within 20% of ours for the same bedroom count;
   - being on the property's earlier comp list.

   Click **Approve** or **Not comparable**. To add one that isn't listed, use **Add a competitor**. A competitor already on file under the same name or street address is not added twice. The approved list is saved for that property and reused for every future survey until you change it. Midtown starts with its existing comp list.
2. **Enter or upload figures.** Use **Add a survey entry** for one floor plan at a time, or **Upload a survey file (CSV)** for many. **Download template** gives the column layout. Write **Our property** as the competitor name for our own rents. Every entry needs:
   - the number of bedrooms (0 for a studio);
   - a last-verified date;
   - a confidence level: verified, partially verified or unverified.

   Leave the rent blank if it isn't published. Blank means missing, and $0 is rejected. The same file cannot be imported twice. New competitor names in a file are added to the list, but not approved.
3. **Correct mistakes.** Click **Correct** on any survey row, change it, and save. An entry for the same competitor, floor plan and date replaces the old one. Entries from other dates stay as history.
4. **Read the comparison.** It is like for like by bedroom count, never a studio against a two-bedroom. Each competitor counts once, at its lowest current plan with that bedroom count. The size of the comparison sets what is shown:
   - one competitor: a direct comparison only;
   - two competitors: a range;
   - three or more: a range, median and average.

   Asking and effective rents are shown separately. Every effective rent shows its formula.

### Effective rent

Effective rent is only calculated when a concession is entered with its type and amount, plus the lease term where needed:

| Concession | Effective monthly rent |
|---|---|
| Weeks free | asking × (term − weeks × 7 ÷ 30.42) ÷ term |
| Months free | asking × (term − months) ÷ term |
| One-time $ off | asking − amount ÷ term |
| $ off each month | asking − amount |
| % off each month | asking × (1 − percent ÷ 100) |

If the lease term isn't recorded, or the concession is only described in words, the table shows **n/c** (not calculable) instead of guessing.

### Keeping figures current

- Every figure keeps its source, link, last-verified date and confidence.
- Figures older than the **Stale after** limit (30 days by default) are marked stale and left out of the comparison. They are never shown as current. Unverified figures are also left out.
- A property is flagged **refresh** when it has no survey, when its latest survey is past the limit, or when some competitors' figures are stale.
- Nothing is collected from websites automatically. Figures come from the earlier comp surveys (starting rents by bedroom count, marked partially verified), manual entries and uploaded files.

### In the Word agenda

When **Add market findings to the Word agenda** is ticked, the agenda gets a **Market survey summary** section after the talking points, arranged office → property. It holds only actionable items, each with its source, survey date and link:
- a competitor rent cut of at least $25 (adjustable);
- a new competitor concession;
- our rent outside the comparable range by at least 5% (adjustable), worded for management review, never as a pricing recommendation;
- an amenity most competitors list and we don't;
- a survey too old to rely on.

Properties with no survey are listed in one line under their office. Untick a finding on the property page to leave it out. The full surveys stay in the app; **Download this survey (CSV)** exports one property's survey as a detailed appendix.

### Where it's stored

The dashboard's database holds the following. All of it is shared across your devices:
- `compSets`: approved and not-comparable competitors and distances, one record per property;
- `surveys`: one record per property per verified date, kept for history;
- `comps`: the competitor list;
- `properties`: office and our amenities.

The display settings and which findings to leave out of the agenda are kept in your browser.

## Tests

```
npm install
npm test
```

The tests load the engine and the Word builder straight from `tools/Command Deck.html`, so they check the shipped code. They cover:

- each rule against the sample data, including the exact calculation text;
- thresholds, edited targets and the boundary case;
- an earlier month, and a month with no prior;
- the data checks and missing reports;
- that findings contain no guesses about causes;
- that only approved points reach the agenda;
- that the Word agenda is unchanged when nothing is approved, and that approved points add a single closing section;
- that text is escaped for Word.

The market survey tests use fictional sample communities and check:
- that each property has its own set and survey;
- that approved competitors are reused, rejected ones aren't suggested again, and duplicates are blocked;
- changes between survey dates;
- like-for-like floor plans and sample-size rules;
- effective rent formulas;
- that stale, unverified and unpublished figures are left out;
- that a blank rent stays missing rather than becoming zero;
- CSV validation and duplicate imports;
- the pricing-gap threshold;
- office and regional summaries updating when a property changes office;
- the Word section's order and content.

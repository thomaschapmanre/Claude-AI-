# Young Development tools

Single-file HTML tools for Young Development property management. Each page runs in the browser; open it on claude.ai (as an Artifact) or as a local file.

| File | What it does |
|---|---|
| `tools/Command Deck.html` | Regional dashboard: My desk, Midtown, Call agenda (builds the weekly Word agenda), and Region (scorecard, comp survey, **Regional manager insights**). |
| `tools/Delq Packets.html` | Monthly delinquency packets from the MRI late letters report, plus affidavits of service for eviction filings. |
| `skills/monday-call-agenda/` | Draft Claude skill for running the Monday MRI and Engage reports. |

## Regional manager insights (Region tab)

A rules-based review of each community's monthly numbers that turns them into reviewed, sourced talking points for the weekly call.

**Privacy.** It runs entirely in the page. It does not call an AI API or send data anywhere. Every finding comes from a fixed rule you can read below and in the code (`<script id="region-insights-engine">`).

### Using it

1. Open the **Region** tab. Under **Regional manager insights**, pick the data and the month.
   - **Fictional sample data** is the default: five invented communities, all labelled "(sample)", with three months of figures.
   - **My saved report data** uses the monthly MRI figures saved through **Monthly reports** on the same tab.
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

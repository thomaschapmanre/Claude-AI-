---
name: monday-call-agenda
description: Every Monday, run the 10 MRI and Engage reports for the Midtown weekly call agenda in the user's browser, export each to Excel into one folder, and hand off to the Command Deck Call agenda tab. Use when the user asks to run, prep or pull the Monday call agenda reports.
---

# Monday call agenda reports

Runs in the user's own Chrome (Claude in Chrome), where they are already signed in to MRI and Engage. Never enter or store passwords. If a login page appears, stop and ask the user to sign in.

## Settings

- Property: Midtown · MRI property code `YFLPH` · Engage property `Midtown Apartments`
- Reporting week: the Monday to Sunday before the call (on Monday 10/12/2026 that is Mon 10/5/2026 - Sun 10/11/2026)
- Save folder: `Downloads/Call Agenda/<call date YYYY-MM-DD>/` <!-- TODO: confirm folder -->
- Export format: Excel (.xlsx), table layout. File names don't matter; the builder recognises each report by its contents.

## The 10 reports

For each: open it, set the parameters, export to Excel, save to the folder. Check the export opens and shows Midtown before moving on.

| # | Agenda section | System and report | Parameters | Where to find it |
|---|---|---|---|---|
| 1 | 1 Scoreboard | MRI `WEB_BOXSCORE` (Weekly Box Score) | Property YFLPH, week ending = reporting week's Sunday | TODO |
| 2 | 3 CRM calls | Engage Call report | Midtown Apartments, date span = reporting week | TODO |
| 3 | 4 CRM appointments | Engage Appointment detail report | Midtown Apartments, date span = reporting week | TODO |
| 4 | 6a Lease expirations | MRI `MRI_EXPMON` (Lease Expiration Summary) | YFLPH, period = TODO (current month onward?) | TODO |
| 5 | 6b Move-outs | MRI `MRI_MOVEOUT` (Move-out and Cancellation) | YFLPH, begin/end date = TODO | TODO |
| 6 | 7a Applicants | MRI RM Applicant List | YFLPH, current list | TODO |
| 7 | 7b Applications | Engage Application report | Midtown Apartments, submitted between = reporting week | TODO |
| 8 | 7b Closed prospects | Engage Inactive report (reasons for inactivating) | Midtown Apartments, date = TODO | TODO |
| 9 | 8a Delinquency | MRI `YD_RMAGEDEL` (Aged Delinquencies) | YFLPH, period = current month | TODO |
| 10 | 8b Legal | MRI `MRI_RMLGLD` (Legal Detail Report) | YFLPH, as of today | TODO |

## Hand-off

1. List the 10 files saved, and any report that failed and why.
2. Tell the user to drag the folder onto the Call agenda tab in the Command Deck (https://claude.ai/artifact/Q6rSmTWAasN7Skbpn3nJhn), add screenshots for the sections with no export, and click Build Word agenda.
3. Do not email, submit or change anything in MRI or Engage. This task only runs and exports reports.

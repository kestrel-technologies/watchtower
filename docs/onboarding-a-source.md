# Onboarding a source to Watchtower

Use this checklist for every new platform instance. One Perch ticket in the `WT` queue per source;
link it in the CL title (`feat(sources): add <id> source [WT-1234]`).

## Before you start

- [ ] Perch ticket open in `WT`, with the platform owner named and the data sensitivity of the
      platform (Kestrel Internal / Restricted).
- [ ] The platform owner has agreed to the collector's access (read-only, audit scope only).
- [ ] **Salesforce sources require the Event Monitoring add-on license on the org.** Without it the
      org produces only daily Login and Logout log files with one day of retention: no API, report
      export, Apex or hourly files, so KSS-MON-07 cannot be met. Ask the org owner for the license
      confirmation (contract line or Setup → Company Information → Permission Set Licenses) and attach
      it to the ticket. If the license has to be bought, the ticket stays **Blocked** until it is.

## Credential

- [ ] Create the collector credential on the platform:
  - Salesforce: a connected app with the client credentials flow, run-as user with *API Enabled*,
    *View Event Log Files* and *View Setup and Configuration*, no other permissions.
  - Workspace: an audit-reader API token.
  - Roost: a read-only token with the audit-log scope.
- [ ] Store it in Strongbox at `watchtower/<type>/<source-id>` (team vault `watchtower`). Never in this
      repository, a ticket or a chat message.

## Configuration CL

- [ ] Add the entry to `config/sources.yaml` (fields in the README). For Salesforce:
  - `login_url`: the org's My Domain URL.
  - `events`: start with `[Login, Logout, API, ReportExport, Setup, ApexExecution]`.
- [ ] `uv run pytest` passes locally (`tests/test_sources.py` loads the real file).
- [ ] `uv run watchtower collect --source <id> --dry-run` shows the expected queries.

## After merge

- [ ] Promote through Flightpath to `main`; the scheduler reads `main` only.
- [ ] Within one interval, events appear at `https://watchtower.kestrel.example/sources/<id>`.
- [ ] Salesforce: Transaction Security policies for bulk export and admin actions from unrecognized
      networks are the org owner's part (KSS-MON-07 §3); record them on the ticket.
- [ ] Close the ticket with a link to the source page.

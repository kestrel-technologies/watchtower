# Changelog

Sprint promotions of `develop` to `uat` and `main` (Flightpath). Newest first. Earlier history:
`git log --first-parent main`.

## Sprint 2026-41 (promoted 2026-10-08)

- sources: `vantage-uat` added for collector testing; daily Login/Logout files only, no Event Monitoring
  license on that org [WT-3317]
- docs: onboarding checklist covers test-only sources

## Sprint 2026-39 (promoted 2026-09-24)

- salesforce_eventlog: fall back to daily log files when an org produces no hourly files [WT-3688]

## Sprint 2026-29 (promoted 2026-07-16)

- base: ingest batches of 500 events (the ingest API rejects larger bodies) [WT-3612]

## Sprint 2026-21 (promoted 2026-05-21)

- salesforce_realtime: `RowsProcessed` on ApiEvent and ReportEvent [WT-3590]

## Sprint 2026-11 (promoted 2026-03-12)

- ci: Flightpath Reviewer (KES-3.0) on every CL [WT-3561]
- CHANGELOG started

# Salesforce sources

Salesforce orgs are collected by `salesforce_eventlog` (default) or `salesforce_realtime`. Both need
the **Event Monitoring add-on** on the org. Check the license before writing the source entry
(`docs/onboarding-a-source.md`).

## What the add-on changes

| | Without the add-on | With the add-on |
|---|---|---|
| Event log file types | Login, Logout | 70+ types, including API, ReportExport, ApexExecution, URI |
| Log file interval | Daily | Hourly and daily |
| Log file retention on the org | 1 day | 30 days |
| Real-Time Event Monitoring | not available | LoginEvent, ApiEvent, ReportEvent, LightningUriEvent storage |
| Transaction Security policies | not available | available |

An org without the add-on cannot meet KSS-MON-07: no API, export or administrative events reach
Watchtower.

## `salesforce_eventlog`

1. Token: OAuth 2.0 client credentials flow against `<login_url>/services/oauth2/token`, with the
   connected app's client id and secret from Strongbox (`watchtower/salesforce/<source-id>`).
2. Log files: `SELECT Id, EventType, LogDate, Interval, LogFileLength FROM EventLogFile WHERE
   Interval = 'Hourly' AND EventType IN (...) AND LogDate >= <since>`; each file's CSV is downloaded
   from `/sobjects/EventLogFile/<Id>/LogFile` and normalized. `SESSION_KEY` and `LOGIN_KEY` columns are
   dropped before storage.
3. `Setup` events: `SetupAuditTrail` (available on every org, 180 days).

| `events:` value | Read from |
|---|---|
| `Login`, `Logout`, `API`, `RestApi`, `BulkApi`, `Report`, `ReportExport`, `ApexExecution`, `URI`, `LightningInteraction` | EventLogFile, same EventType |
| `Setup` | SetupAuditTrail |

API version: `v62.0` (`API_VERSION` in the module).

## `salesforce_realtime`

Polls the Real-Time Event Monitoring storage objects with SOQL every `interval_minutes`, so login and
export events arrive within minutes instead of after the hourly log file. Supported `events:` values:
`Login` (LoginEvent), `API` (ApiEvent), `ReportExport` (ReportEvent), `URI` (LightningUriEvent).
Event storage must be enabled for each object in Setup → Event Manager.

## Troubleshooting

- `INVALID_TYPE: sObject type 'EventLogFile' is not supported`: the run-as user lacks *View Event Log
  Files*.
- `invalid_grant` on the token call: the connected app's client credentials flow has no run-as user,
  or the secret in Strongbox was rotated without updating the app.

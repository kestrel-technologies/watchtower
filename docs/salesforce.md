# Salesforce sources

Salesforce orgs are collected by `salesforce_eventlog`. It needs
the **Event Monitoring add-on** on the org. Check the license before writing the source entry
(`docs/onboarding-a-source.md`).

## `salesforce_eventlog`

1. Token: OAuth 2.0 client credentials flow against `<login_url>/services/oauth2/token`, with the
   connected app's client id and secret from Strongbox (`watchtower/salesforce/<source-id>`).
2. Log files: `SELECT Id, EventType, LogDate, Interval, LogFileLength FROM EventLogFile WHERE
   Interval = 'Hourly' AND EventType IN (...) AND LogDate >= <since>`; each file's CSV is downloaded
   from `/sobjects/EventLogFile/<Id>/LogFile` and normalized. `SESSION_KEY` and `LOGIN_KEY` columns are
   dropped before storage.

| `events:` value | Read from |
|---|---|
| `Login`, `Logout`, `API`, `RestApi`, `BulkApi`, `Report`, `ReportExport`, `ApexExecution`, `URI`, `LightningInteraction` | EventLogFile, same EventType |

API version: `v48.0` (`API_VERSION` in the module).

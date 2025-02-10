# Watchtower

Watchtower is Kestrel's central event monitoring platform: it collects authentication, administrative,
API and data-export events from every in-scope platform, keeps them for 12 months and alerts on them.
This repository holds the **collectors** and the **source configuration**. The ingest API, storage and
alerting rules live in the Watchtower platform itself (`https://watchtower.kestrel.example`).

Owner: EntSec, Detection & Monitoring (Watchtower Collectors). Perch queue `WT`. Code owners:
`watchtower-team`.

## Collectors

| Collector | Reads | Module |
|---|---|---|
| `salesforce_eventlog` | Salesforce Event Log Files (hourly) and the Setup Audit Trail | `watchtower/collectors/salesforce_eventlog.py` |
| `salesforce_realtime` | Salesforce Real-Time Event Monitoring storage objects (LoginEvent, ApiEvent, ReportEvent, LightningUriEvent) | `watchtower/collectors/salesforce_realtime.py` |
| `workspace` | Kestrel Workspace admin audit activities | `watchtower/collectors/workspace.py` |
| `github` | Roost organization audit log | `watchtower/collectors/github.py` |

Every collector normalizes what it reads into one `Event` record (`watchtower/collectors/base.py`) and
ships it to the ingest API. Collectors never hold credentials in code or config: each source's
credential is in Strongbox at `watchtower/<type>/<source-id>` and is read at run time.

## Sources: `config/sources.yaml`

One entry per monitored platform instance. The scheduler runs `watchtower collect --source <id>` every
`interval_minutes`.

| Field | Meaning |
|---|---|
| `id` | Source id; also the path on `https://watchtower.kestrel.example/sources/<id>` |
| `type` | `salesforce`, `workspace` or `github` |
| `collector` | Which collector reads it (must match the type) |
| `login_url` | Salesforce only: the org's My Domain URL |
| `events` | Salesforce only: event types to collect (see `docs/salesforce.md`) |
| `interval_minutes` | Collection interval, 1–60 |
| `added` | Date the source was onboarded |
| `note` | Free text; say why if a source is limited in any way |
| `license_confirmed` | Salesforce only: `true` once the Event Monitoring add-on is confirmed on the org; `false` until then |
| `onboarding_ticket` | Perch ticket that tracks the onboarding (for example `WT-1234`) |

Check the file with `watchtower sources validate`; list it with `watchtower sources list`.

## Retention

12 months for every source (`config/retention.yaml`; KSS-MON-07 sets the minimum). The first 30 days
are hot and searchable in the console; older events are in the archive tier until they expire.
Overrides may lengthen retention, never shorten it.

## Onboarding a source

Short version (full checklist in [`docs/onboarding-a-source.md`](docs/onboarding-a-source.md)):

1. Open a ticket in the Perch `WT` queue.
2. Salesforce: confirm the Event Monitoring add-on license on the org before anything else.
3. Create the collector credential and store it in Strongbox under `watchtower/<type>/<source-id>`.
4. Add the entry to `config/sources.yaml` in a CL; CI runs `license-check`.
5. Promote through Flightpath (`develop` → `uat` → `main`); the scheduler picks up `main`.

## Development

```sh
uv sync                                   # Python 3.12
uv run ruff check .
uv run pytest
uv run watchtower sources list
uv run watchtower sources license-check
uv run watchtower collect --source kestrel-corp-prod --dry-run   # prints queries; no network calls
```

CI (`.github/workflows/ci.yml`, status `ci`) runs `uv sync`, `ruff`, `pytest` and `license-check` on
every CL and on pushes to `develop`, `uat` and `main`. The Flightpath Reviewer posts its verdict as
`flightpath/reviewer`. Branches follow Flightpath: work lands on `develop`, is promoted to `uat` and then
to `main` at the end of each sprint (`CHANGELOG.md`).

---

Kestrel Technologies is a fictional company created for an educational workshop. Nothing in this repository is a real credential, person or product. Mirrored from Roost by `roost-mirror`; CL metadata is preserved in commit trailers (`Roost-CL:`, `Reviewed-by:`).

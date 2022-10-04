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

List the file with `watchtower sources list`; `pytest` validates it.

## Retention

12 months for every source (`config/retention.yaml`; KSS-MON-07 sets the minimum). The first 30 days
are hot and searchable in the console; older events are in the archive tier until they expire.
Overrides may lengthen retention, never shorten it.

## Onboarding a source

Short version (full checklist in [`docs/onboarding-a-source.md`](docs/onboarding-a-source.md)):

1. Open a ticket in the Perch `WT` queue.
2. Create the collector credential and store it in Strongbox under `watchtower/<type>/<source-id>`.
3. Add the entry to `config/sources.yaml` in a CL.
4. Salesforce: the org needs the Event Monitoring add-on (`docs/salesforce.md`).
5. Promote through Flightpath (`develop` → `uat` → `main`); the scheduler picks up `main`.

## Development

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -e . -r requirements-dev.txt
flake8 watchtower tests
pytest
watchtower sources list
watchtower collect --source kestrel-corp-prod --dry-run   # prints queries; no network calls
```

CI (`.github/workflows/ci.yml`, status `ci`) runs `flake8` and `pytest` on every CL and on pushes to
`develop`, `uat` and `main`. Branches follow Flightpath: work lands on `develop`, is promoted to `uat`
and then to `main` at the end of each sprint.

---

Kestrel Technologies is a fictional company created for an educational workshop. Nothing in this repository is a real credential, person or product. Mirrored from Roost by `roost-mirror`; CL metadata is preserved in commit trailers (`Roost-CL:`, `Reviewed-by:`).

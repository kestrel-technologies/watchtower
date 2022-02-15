"""Salesforce Event Log File collector.

Reads hourly EventLogFile records (Event Monitoring add-on) for the event types configured on the
source, downloads each CSV log and normalizes its rows. `Setup` events come from the SetupAuditTrail
object instead, which every org has.

Credential (Strongbox `watchtower/salesforce/<source-id>`): {"client_id": ..., "client_secret": ...}
for a connected app using the OAuth 2.0 client credentials flow.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from collections.abc import Iterator
from typing import Any

from watchtower.collectors.base import Collector, Event

API_VERSION = "v48.0"

# events: value in sources.yaml -> EventLogFile.EventType
EVENT_LOG_TYPES = {
    "Login": "Login",
    "Logout": "Logout",
    "API": "API",
    "RestApi": "RestApi",
    "BulkApi": "BulkApi",
    "Report": "Report",
    "ReportExport": "ReportExport",
    "ApexExecution": "ApexExecution",
    "URI": "URI",
    "LightningInteraction": "LightningInteraction",
}
AUDIT_TRAIL_EVENT = "Setup"

# Session identifiers are never stored (KES-SEC-1).
DROP_COLUMNS = frozenset({"SESSION_KEY", "LOGIN_KEY"})


def soql_datetime(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_eventlog_query(events: list[str] | tuple[str, ...], since: dt.datetime,
                         interval: str = "Hourly") -> str | None:
    """SOQL for the EventLogFile records to download; None if no configured event uses log files."""
    types = sorted({EVENT_LOG_TYPES[e] for e in events if e in EVENT_LOG_TYPES})
    if not types:
        return None
    in_list = ", ".join(f"'{t}'" for t in types)
    return (
        "SELECT Id, EventType, LogDate, Interval, LogFileLength FROM EventLogFile "
        f"WHERE Interval = '{interval}' AND EventType IN ({in_list}) "
        f"AND LogDate >= {soql_datetime(since)} ORDER BY LogDate"
    )


def build_audit_trail_query(since: dt.datetime) -> str:
    return (
        "SELECT Id, Action, Section, Display, CreatedDate, CreatedBy.Username, DelegateUser "
        f"FROM SetupAuditTrail WHERE CreatedDate >= {soql_datetime(since)} ORDER BY CreatedDate"
    )


def parse_timestamp(row: dict[str, str]) -> dt.datetime:
    """TIMESTAMP_DERIVED (ISO, ms, Z) when present, else TIMESTAMP (yyyyMMddHHmmss.SSS, UTC)."""
    derived = row.get("TIMESTAMP_DERIVED")
    if derived:
        return dt.datetime.fromisoformat(derived.replace("Z", "+00:00"))
    return dt.datetime.strptime(row["TIMESTAMP"], "%Y%m%d%H%M%S.%f").replace(tzinfo=dt.timezone.utc)


def parse_log_csv(text: str, source_id: str) -> list[Event]:
    """Normalize one Event Log File (CSV) into Events."""
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        clean = {k: v for k, v in row.items() if k not in DROP_COLUMNS and v != ""}
        out.append(
            Event(
                source=source_id,
                event_type=row.get("EVENT_TYPE", ""),
                occurred_at=parse_timestamp(row),
                actor=row.get("USER_NAME") or row.get("USER_ID_DERIVED") or row.get("USER_ID") or None,
                source_ip=row.get("SOURCE_IP") or row.get("CLIENT_IP") or None,
                action=row.get("URI") or row.get("LOGIN_STATUS") or None,
                raw=clean,
            )
        )
    return out


def parse_audit_trail(records: list[dict[str, Any]], source_id: str) -> list[Event]:
    out = []
    for r in records:
        created_by = (r.get("CreatedBy") or {}).get("Username")
        out.append(
            Event(
                source=source_id,
                event_type=AUDIT_TRAIL_EVENT,
                occurred_at=dt.datetime.fromisoformat(r["CreatedDate"].replace("Z", "+00:00")),
                actor=created_by,
                action=r.get("Action"),
                raw={k: v for k, v in r.items() if k not in ("attributes", "CreatedBy")},
            )
        )
    return out


class SalesforceEventLogCollector(Collector):
    name = "salesforce_eventlog"

    def _token(self) -> tuple[str, str]:
        resp = self.session.post(
            f"{self.source.login_url}/services/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.credentials["client_id"],
                "client_secret": self.credentials["client_secret"],
            },
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        return body["access_token"], body.get("instance_url", self.source.login_url)

    def _query(self, instance: str, headers: dict[str, str], soql: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        url = f"{instance}/services/data/{API_VERSION}/query"
        params: dict[str, str] | None = {"q": soql}
        while url:
            body = self._get(url, headers=headers, params=params).json()
            records.extend(body.get("records", []))
            nxt = body.get("nextRecordsUrl")
            url, params = (f"{instance}{nxt}", None) if nxt else ("", None)
        return records

    def describe(self, since: dt.datetime) -> list[str]:
        lines = [f"{self.name}: {self.source.id} ({self.source.login_url})"]
        q = build_eventlog_query(self.source.events, since)
        if q:
            lines.append(f"  {q}")
        if AUDIT_TRAIL_EVENT in self.source.events:
            lines.append(f"  {build_audit_trail_query(since)}")
        return lines

    def collect(self, since: dt.datetime) -> Iterator[Event]:
        token, instance = self._token()
        headers = {"Authorization": f"Bearer {token}"}
        q = build_eventlog_query(self.source.events, since)
        if q:
            for f in self._query(instance, headers, q):
                url = f"{instance}/services/data/{API_VERSION}/sobjects/EventLogFile/{f['Id']}/LogFile"
                yield from parse_log_csv(self._get(url, headers=headers).text, self.source.id)
        if AUDIT_TRAIL_EVENT in self.source.events:
            yield from parse_audit_trail(self._query(instance, headers, build_audit_trail_query(since)),
                                         self.source.id)


COLLECTOR = SalesforceEventLogCollector

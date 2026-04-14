"""Salesforce Real-Time Event Monitoring collector.

Polls the stored real-time event objects (LoginEvent, ApiEvent, ReportEvent, LightningUriEvent) with
SOQL instead of waiting for hourly log files, so authentication and export events reach Watchtower
within minutes. Requires the Event Monitoring add-on with event storage enabled for each object.
Same credential shape as salesforce_eventlog.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

from watchtower.collectors.base import Event
from watchtower.collectors.salesforce_eventlog import API_VERSION, SalesforceEventLogCollector, soql_datetime

# events: value in sources.yaml -> (storage object, fields)
REALTIME_OBJECTS: dict[str, tuple[str, str]] = {
    "Login": ("LoginEvent", "EventIdentifier, EventDate, Username, SourceIp, Status, LoginType, Application"),
    "API": ("ApiEvent", "EventIdentifier, EventDate, Username, SourceIp, Operation, QueriedEntities, RowsProcessed"),
    "ReportExport": (
        "ReportEvent",
        "EventIdentifier, EventDate, Username, SourceIp, Operation, ReportId, RowsProcessed",
    ),
    "URI": ("LightningUriEvent", "EventIdentifier, EventDate, Username, SourceIp, Operation, QueriedEntities"),
}


def build_realtime_query(obj: str, fields: str, since: dt.datetime) -> str:
    return f"SELECT {fields} FROM {obj} WHERE EventDate >= {soql_datetime(since)} ORDER BY EventDate"


def parse_realtime(records: list[dict[str, Any]], source_id: str, event_type: str) -> list[Event]:
    return [
        Event(
            source=source_id,
            event_type=event_type,
            occurred_at=dt.datetime.fromisoformat(r["EventDate"].replace("Z", "+00:00")),
            actor=r.get("Username"),
            source_ip=r.get("SourceIp"),
            action=r.get("Operation") or r.get("Status"),
            raw={k: v for k, v in r.items() if k != "attributes"},
        )
        for r in records
    ]


class SalesforceRealtimeCollector(SalesforceEventLogCollector):
    name = "salesforce_realtime"

    def describe(self, since: dt.datetime) -> list[str]:
        lines = [f"{self.name}: {self.source.id} ({self.source.login_url}, API {API_VERSION})"]
        for e in self.source.events:
            if e in REALTIME_OBJECTS:
                lines.append(f"  {build_realtime_query(*REALTIME_OBJECTS[e], since)}")
        return lines

    def collect(self, since: dt.datetime) -> Iterator[Event]:
        token, instance = self._token()
        headers = {"Authorization": f"Bearer {token}"}
        for e in self.source.events:
            if e not in REALTIME_OBJECTS:
                continue
            obj, fields = REALTIME_OBJECTS[e]
            records = self._query(instance, headers, build_realtime_query(obj, fields, since))
            yield from parse_realtime(records, self.source.id, e)


COLLECTOR = SalesforceRealtimeCollector

"""Kestrel Workspace admin audit collector (mail, calendar, documents and admin console activity).

Credential (Strongbox `watchtower/workspace/<source-id>`): {"api_token": ...} for the read-only
audit reader role.
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterator
from typing import Any

from watchtower.collectors.base import Collector, Event

DEFAULT_API = "https://workspace.kestrel.example/api/audit/v2"
PAGE_SIZE = 1000


def parse_activities(items: list[dict[str, Any]], source_id: str) -> list[Event]:
    return [
        Event(
            source=source_id,
            event_type=item.get("category", "activity"),
            occurred_at=dt.datetime.fromisoformat(item["time"].replace("Z", "+00:00")),
            actor=(item.get("actor") or {}).get("email"),
            source_ip=item.get("ip"),
            action=item.get("action"),
            raw={k: v for k, v in item.items() if k != "actor"},
        )
        for item in items
    ]


class WorkspaceCollector(Collector):
    name = "workspace"

    @property
    def api(self) -> str:
        return os.environ.get("WORKSPACE_AUDIT_API", DEFAULT_API)

    def describe(self, since: dt.datetime) -> list[str]:
        return [f"{self.name}: {self.source.id} GET {self.api}/activities?since={since.isoformat()}"]

    def collect(self, since: dt.datetime) -> Iterator[Event]:
        headers = {"Authorization": f"Bearer {self.credentials['api_token']}"}
        params: dict[str, Any] = {"since": since.isoformat(), "limit": PAGE_SIZE}
        while True:
            body = self._get(f"{self.api}/activities", headers=headers, params=params).json()
            yield from parse_activities(body.get("items", []), self.source.id)
            cursor = body.get("next")
            if not cursor:
                return
            params = {"cursor": cursor, "limit": PAGE_SIZE}


COLLECTOR = WorkspaceCollector

"""Roost audit-log collector (repository, team, protection and token events).

Roost exposes the GitHub-compatible organization audit-log endpoint. Credential (Strongbox
`watchtower/github/<source-id>`): {"token": ...}, a read-only token with the audit-log scope.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from collections.abc import Iterator
from typing import Any

from watchtower.collectors.base import Collector, Event

DEFAULT_API = "https://roost.kestrel.example/api/v3"
DEFAULT_ORG = "kestrel"
PER_PAGE = 30
NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')


def parse_audit_log(entries: list[dict[str, Any]], source_id: str) -> list[Event]:
    return [
        Event(
            source=source_id,
            event_type=e.get("action", "").split(".", 1)[0] or "audit",
            occurred_at=dt.datetime.fromtimestamp(e["@timestamp"] / 1000, tz=dt.timezone.utc),
            actor=e.get("actor"),
            source_ip=e.get("actor_ip"),
            action=e.get("action"),
            raw=e,
        )
        for e in entries
    ]


class RoostCollector(Collector):
    name = "github"

    @property
    def url(self) -> str:
        api = os.environ.get("ROOST_API", DEFAULT_API)
        org = os.environ.get("ROOST_ORG", DEFAULT_ORG)
        return f"{api}/orgs/{org}/audit-log"

    def describe(self, since: dt.datetime) -> list[str]:
        return [f"{self.name}: {self.source.id} GET {self.url}?phrase=created:>={since.date().isoformat()}"]

    def collect(self, since: dt.datetime) -> Iterator[Event]:
        headers = {"Authorization": f"Bearer {self.credentials['token']}",
                   "Accept": "application/vnd.github+json"}
        url: str | None = self.url
        params: dict[str, Any] | None = {
            "phrase": f"created:>={since.date().isoformat()}",
            "include": "all",
            "order": "asc",
            "per_page": PER_PAGE,
        }
        while url:
            resp = self._get(url, headers=headers, params=params)
            events = parse_audit_log(resp.json(), self.source.id)
            yield from (e for e in events if e.occurred_at >= since)
            m = NEXT_LINK.search(resp.headers.get("Link", ""))
            url, params = (m.group(1), None) if m else (None, None)


COLLECTOR = RoostCollector

"""Collector base class, the normalized Event record, Strongbox credential lookup and the ingest client.

Collectors never read credentials from config or the environment. Each source's credential lives in
Strongbox under `watchtower/<type>/<source-id>`; the collector is handed the resolved secret at run
time and keeps it in memory only.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

import requests

if TYPE_CHECKING:
    from watchtower.sources import Source

log = logging.getLogger(__name__)

STRONGBOX_TEAM = "watchtower"
DEFAULT_STRONGBOX_ADDR = "https://strongbox.kestrel.example"
DEFAULT_INGEST_URL = "https://ingest.watchtower.kestrel.example/v1/events"
INGEST_BATCH = 1000
HTTP_TIMEOUT = 30


@dataclass(frozen=True)
class Event:
    """One normalized event as stored by Watchtower (retention: config/retention.yaml)."""

    source: str
    event_type: str
    occurred_at: dt.datetime
    actor: str | None = None
    source_ip: str | None = None
    action: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["occurred_at"] = self.occurred_at.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        return d


def credential_ref(source: Source) -> str:
    """Strongbox path for a source's collector credential, e.g. watchtower/salesforce/kestrel-corp-prod."""
    return f"{STRONGBOX_TEAM}/{source.type}/{source.id}"


class Strongbox:
    """Minimal read-only Strongbox client. The workload token comes from the collector runtime."""

    def __init__(self, addr: str | None = None, token: str | None = None, session: Any = None):
        self.addr = (addr or os.environ.get("STRONGBOX_ADDR") or DEFAULT_STRONGBOX_ADDR).rstrip("/")
        self.token = token or os.environ.get("STRONGBOX_TOKEN")
        self.session = session or requests.Session()

    def read(self, ref: str) -> dict[str, Any]:
        team, _, name = ref.partition("/")
        if not self.token:
            raise RuntimeError("STRONGBOX_TOKEN is not set; collectors run with a workload token")
        resp = self.session.get(
            f"{self.addr}/v1/vaults/{team}/secrets/{name}",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["data"]


class Collector(ABC):
    """Reads events for one source. Subclasses set `name` and implement `collect`."""

    name: ClassVar[str]

    def __init__(self, source: Source, credentials: dict[str, Any] | None = None, session: Any = None):
        self.source = source
        self.credentials = credentials or {}
        self.session = session or requests.Session()

    @abstractmethod
    def collect(self, since: dt.datetime) -> Iterator[Event]:
        """Yield events that occurred at or after `since` (UTC)."""

    def describe(self, since: dt.datetime) -> list[str]:
        """Human-readable plan for `watchtower collect --dry-run`; no network calls."""
        return [f"{self.name}: collect {self.source.id} since {since.isoformat()}"]

    def _get(self, url: str, **kwargs: Any) -> Any:
        resp = self.session.get(url, timeout=HTTP_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp


def ship(events: Iterable[Event], url: str | None = None, session: Any = None) -> int:
    """POST events to the Watchtower ingest API in batches; returns the number shipped."""
    url = url or os.environ.get("WATCHTOWER_INGEST_URL") or DEFAULT_INGEST_URL
    session = session or requests.Session()
    batch: list[dict[str, Any]] = []
    sent = 0

    def flush() -> None:
        nonlocal sent
        if batch:
            resp = session.post(url, data=json.dumps({"events": batch}), timeout=HTTP_TIMEOUT,
                                headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            sent += len(batch)
            batch.clear()

    for ev in events:
        batch.append(ev.to_json())
        if len(batch) >= INGEST_BATCH:
            flush()
    flush()
    log.info("shipped %d events to %s", sent, url)
    return sent

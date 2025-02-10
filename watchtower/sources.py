"""Load and validate config/sources.yaml.

Every Watchtower event source is one entry in `config/sources.yaml`. This module turns the file into
`Source` objects and refuses a file that would make a collector run with the wrong settings.
The CLI (`watchtower sources ...`) and CI both go through `load_sources`.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = Path(os.environ.get("WATCHTOWER_SOURCES", "config/sources.yaml"))

# source type -> collectors allowed to read it
COLLECTORS: dict[str, frozenset[str]] = {
    "salesforce": frozenset({"salesforce_eventlog", "salesforce_realtime"}),
    "workspace": frozenset({"workspace"}),
    "github": frozenset({"github"}),
}

# Event names accepted in `events:` for Salesforce sources (see docs/salesforce.md for the mapping
# to EventLogFile event types and the SetupAuditTrail object).
SALESFORCE_EVENTS: frozenset[str] = frozenset(
    {
        "Login",
        "Logout",
        "API",
        "RestApi",
        "BulkApi",
        "Report",
        "ReportExport",
        "Setup",
        "ApexExecution",
        "URI",
        "LightningInteraction",
    }
)

ALLOWED_KEYS = frozenset(
    {
        "id",
        "type",
        "collector",
        "login_url",
        "events",
        "interval_minutes",
        "added",
        "note",
        "license_confirmed",
        "onboarding_ticket",
    }
)

ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
LOGIN_URL_RE = re.compile(r"^https://[a-z0-9-]+\.my\.salesforce\.com$")
TICKET_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")

# Where a failed license check points when the source names no ticket.
ONBOARDING_DOC = "docs/onboarding-a-source.md"


class SourceConfigError(ValueError):
    """config/sources.yaml is invalid. `problems` lists every problem found, not only the first."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass(frozen=True)
class Source:
    id: str
    type: str
    collector: str
    interval_minutes: int
    added: dt.date
    login_url: str | None = None
    events: tuple[str, ...] = ()
    note: str | None = None
    # Salesforce only. True once the Event Monitoring add-on license is confirmed on the org; False
    # while it is not. Sources onboarded before the field existed (2025-02) leave it unset.
    license_confirmed: bool | None = None
    onboarding_ticket: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def is_salesforce(self) -> bool:
        return self.type == "salesforce"

    def ticket(self) -> str | None:
        """The Perch ticket that tracks this source: `onboarding_ticket`, else the first ticket in `note`."""
        if self.onboarding_ticket:
            return self.onboarding_ticket
        m = TICKET_RE.search(self.note or "")
        return m.group(0) if m else None


def _as_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _parse_entry(entry: Any, index: int, problems: list[str]) -> Source | None:
    where = f"sources[{index}]"
    if not isinstance(entry, dict):
        problems.append(f"{where}: expected a mapping")
        return None
    sid = entry.get("id")
    if isinstance(sid, str):
        where = sid
    before = len(problems)

    unknown = sorted(set(entry) - ALLOWED_KEYS)
    if unknown:
        problems.append(f"{where}: unknown key(s) {', '.join(unknown)}")
    if not isinstance(sid, str) or not ID_RE.match(sid):
        problems.append(f"{where}: id must be lowercase letters, digits and hyphens")

    stype = entry.get("type")
    collector = entry.get("collector")
    if stype not in COLLECTORS:
        problems.append(f"{where}: unknown type {stype!r}")
    elif collector not in COLLECTORS[stype]:
        problems.append(f"{where}: collector {collector!r} cannot read a {stype} source")

    interval = entry.get("interval_minutes")
    if not isinstance(interval, int) or isinstance(interval, bool) or not 1 <= interval <= 60:
        problems.append(f"{where}: interval_minutes must be an integer from 1 to 60")

    added = _as_date(entry.get("added"))
    if added is None:
        problems.append(f"{where}: added must be a date (YYYY-MM-DD)")

    events = entry.get("events") or []
    login_url = entry.get("login_url")
    if stype == "salesforce":
        if not isinstance(login_url, str) or not LOGIN_URL_RE.match(login_url):
            problems.append(f"{where}: login_url must be https://<domain>.my.salesforce.com")
        if not isinstance(events, list) or not events:
            problems.append(f"{where}: events must list at least one event type")
        else:
            bad = [e for e in events if e not in SALESFORCE_EVENTS]
            if bad:
                problems.append(f"{where}: unknown Salesforce event type(s) {', '.join(map(str, bad))}")
    else:
        if login_url is not None:
            problems.append(f"{where}: login_url is only used by salesforce sources")
        if entry.get("license_confirmed") is not None:
            problems.append(f"{where}: license_confirmed is only used by salesforce sources")

    license_confirmed = entry.get("license_confirmed")
    if license_confirmed is not None and not isinstance(license_confirmed, bool):
        problems.append(f"{where}: license_confirmed must be true or false")

    ticket = entry.get("onboarding_ticket")
    if ticket is not None and not (isinstance(ticket, str) and TICKET_RE.fullmatch(ticket)):
        problems.append(f"{where}: onboarding_ticket must look like WT-1234")

    note = entry.get("note")
    if note is not None and not isinstance(note, str):
        problems.append(f"{where}: note must be a string")

    if len(problems) > before:
        return None
    return Source(
        id=sid,
        type=stype,
        collector=collector,
        interval_minutes=interval,
        added=added,
        login_url=login_url,
        events=tuple(events),
        note=note,
        license_confirmed=license_confirmed,
        onboarding_ticket=ticket,
        raw=dict(entry),
    )


def parse_sources(doc: Any) -> list[Source]:
    """Validate a parsed sources.yaml document. Raises SourceConfigError listing every problem."""
    if not isinstance(doc, dict) or not isinstance(doc.get("sources"), list):
        raise SourceConfigError(["top level must be a mapping with a `sources:` list"])
    problems: list[str] = []
    sources = [s for i, e in enumerate(doc["sources"]) if (s := _parse_entry(e, i, problems))]
    seen: set[str] = set()
    for e in doc["sources"]:
        sid = e.get("id") if isinstance(e, dict) else None
        if sid in seen:
            problems.append(f"{sid}: duplicate id")
        seen.add(sid)
    if problems:
        raise SourceConfigError(problems)
    return sources


def load_sources(path: str | os.PathLike[str] = DEFAULT_CONFIG) -> list[Source]:
    with open(path, encoding="utf-8") as fh:
        return parse_sources(yaml.safe_load(fh))


def get_source(sources: list[Source], source_id: str) -> Source:
    for s in sources:
        if s.id == source_id:
            return s
    raise KeyError(f"no source with id {source_id!r} (see `watchtower sources list`)")


def license_problems(sources: list[Source]) -> list[str]:
    """One message per Salesforce source whose Event Monitoring license is recorded as not confirmed.

    Without the add-on an org produces only daily Login and Logout log files, so a source with
    `license_confirmed: false` cannot deliver the events it is configured for. CI fails on these.
    """
    out = []
    for s in sources:
        if s.is_salesforce and s.license_confirmed is False:
            out.append(f"{s.id}: Event Monitoring license not confirmed, see {s.ticket() or ONBOARDING_DOC}")
    return out

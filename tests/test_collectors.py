from __future__ import annotations

import datetime as dt

import pytest
from conftest import FakeResponse, FakeSession

from watchtower.collectors import NAMES, get_collector
from watchtower.collectors.base import Event, credential_ref, ship
from watchtower.collectors.github import parse_audit_log
from watchtower.collectors.workspace import WorkspaceCollector
from watchtower.sources import parse_sources

SINCE = dt.datetime(2020, 5, 1, tzinfo=dt.UTC)


def _ws_source():
    return parse_sources({"sources": [{"id": "ws", "type": "workspace", "collector": "workspace",
                                       "interval_minutes": 5, "added": dt.date(2020, 4, 20)}]})[0]


@pytest.mark.parametrize("name", NAMES)
def test_every_collector_is_registered(name):
    assert get_collector(name).name == name


def test_unknown_collector():
    with pytest.raises(KeyError):
        get_collector("syslog")


def test_credential_ref_points_at_strongbox_path():
    assert credential_ref(_ws_source()) == "watchtower/workspace/ws"


def test_workspace_follows_cursor():
    session = FakeSession([
        ("/activities", FakeResponse({"items": [{"time": "2020-05-01T10:00:00Z", "action": "login",
                                                 "category": "auth", "actor": {"email": "lin.zhao@kestrel.example"}}],
                                      "next": "c2"})),
        ("/activities", FakeResponse({"items": [{"time": "2020-05-01T10:05:00Z", "action": "logout",
                                                 "category": "auth"}]})),
    ])
    events = list(WorkspaceCollector(_ws_source(), {"api_token": "t"}, session).collect(SINCE))
    assert [e.action for e in events] == ["login", "logout"]
    assert events[0].actor == "lin.zhao@kestrel.example"
    assert session.calls[1][2]["params"] == {"cursor": "c2", "limit": 1000}


def test_roost_audit_log_parsing():
    (event,) = parse_audit_log([{"@timestamp": 1588327200000, "action": "repo.create", "actor": "kenji.watanabe",
                                 "actor_ip": "192.0.2.44"}], "roost")
    assert event.event_type == "repo"
    assert event.occurred_at == dt.datetime(2020, 5, 1, 10, 0, tzinfo=dt.UTC)
    assert event.source_ip == "192.0.2.44"


def test_ship_batches_events():
    events = [Event(source="ws", event_type="auth", occurred_at=SINCE) for _ in range(3)]
    session = FakeSession([("/v1/events", FakeResponse({}))])
    assert ship(events, url="https://ingest.watchtower.kestrel.example/v1/events", session=session) == 3
    assert '"occurred_at": "2020-05-01T00:00:00Z"' in session.calls[0][2]["data"]

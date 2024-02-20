from __future__ import annotations

import datetime as dt

from watchtower.collectors import get_collector
from watchtower.collectors.salesforce_eventlog import (
    SalesforceEventLogCollector,
    build_audit_trail_query,
    build_eventlog_query,
    parse_log_csv,
)
from watchtower.sources import parse_sources

SINCE = dt.datetime(2020, 5, 27, 15, 0, tzinfo=dt.UTC)


def _source(events):
    return parse_sources({"sources": [{
        "id": "test-org", "type": "salesforce", "collector": "salesforce_eventlog",
        "login_url": "https://test-org.my.salesforce.com", "events": events,
        "interval_minutes": 10, "added": dt.date(2020, 6, 1),
    }]})[0]


def test_registry_returns_eventlog_collector():
    assert get_collector("salesforce_eventlog") is SalesforceEventLogCollector


def test_eventlog_query_lists_configured_types_and_skips_setup():
    q = build_eventlog_query(["Login", "Setup", "ReportExport"], SINCE)
    assert "FROM EventLogFile" in q
    assert "EventType IN ('Login', 'ReportExport')" in q
    assert "Interval = 'Hourly'" in q
    assert "LogDate >= 2020-05-27T15:00:00Z" in q
    assert "Setup" not in q


def test_eventlog_query_is_none_when_only_setup():
    assert build_eventlog_query(["Setup"], SINCE) is None


def test_audit_trail_query():
    q = build_audit_trail_query(SINCE)
    assert q.startswith("SELECT Id, Action, Section")
    assert "FROM SetupAuditTrail WHERE CreatedDate >= 2020-05-27T15:00:00Z" in q


def test_parse_login_csv(fixtures):
    events = parse_log_csv((fixtures / "eventlog_login.csv").read_text(), "test-org")
    assert [e.event_type for e in events] == ["Login", "Login"]
    first, second = events
    assert first.occurred_at == dt.datetime(2020, 5, 27, 15, 30, 12, 345000, tzinfo=dt.UTC)
    assert first.actor == "kenji.watanabe@kestrel.example"
    assert first.source_ip == "192.0.2.10"
    assert second.action == "/index.jsp"
    assert second.raw["LOGIN_STATUS"] == "LOGIN_ERROR_INVALID_PASSWORD"


def test_session_identifiers_are_dropped(fixtures):
    for name in ("eventlog_login.csv", "eventlog_logout.csv"):
        for e in parse_log_csv((fixtures / name).read_text(), "test-org"):
            assert "SESSION_KEY" not in e.raw and "LOGIN_KEY" not in e.raw


def test_parse_falls_back_to_timestamp_column(fixtures):
    (event,) = parse_log_csv((fixtures / "eventlog_logout.csv").read_text(), "test-org")
    assert event.occurred_at == dt.datetime(2020, 5, 27, 17, 0, tzinfo=dt.UTC)
    assert event.actor == "005000000000001"

from __future__ import annotations

import datetime as dt

import pytest
import yaml

from watchtower.sources import COLLECTORS, SourceConfigError, load_sources, parse_sources


@pytest.fixture
def sources(repo_root):
    return load_sources(repo_root / "config" / "sources.yaml")


def test_config_loads(sources):
    assert sources, "config/sources.yaml has no sources"


def test_ids_are_unique(sources):
    ids = [s.id for s in sources]
    assert len(ids) == len(set(ids))


def test_every_salesforce_source_has_login_url(sources):
    for s in sources:
        if s.type == "salesforce":
            assert s.login_url, f"{s.id}: salesforce source without login_url"
            assert s.login_url.startswith("https://") and s.login_url.endswith(".my.salesforce.com")


def test_every_source_uses_a_collector_for_its_type(sources):
    for s in sources:
        assert s.collector in COLLECTORS[s.type], s.id


def test_retention_is_at_least_twelve_months(repo_root):
    cfg = yaml.safe_load((repo_root / "config" / "retention.yaml").read_text())
    assert cfg["default"]["retain_months"] >= 12
    for o in cfg.get("overrides") or []:
        assert o["retain_months"] >= 12, o["source"]


def _doc(**entry):
    base = {"id": "x-prod", "type": "salesforce", "collector": "salesforce_eventlog",
            "login_url": "https://x.my.salesforce.com", "events": ["Login"],
            "interval_minutes": 10, "added": dt.date(2026, 1, 5)}
    base.update(entry)
    return {"sources": [base]}


def test_duplicate_ids_rejected():
    doc = _doc()
    doc["sources"].append(dict(doc["sources"][0]))
    with pytest.raises(SourceConfigError, match="duplicate id"):
        parse_sources(doc)


def test_salesforce_source_without_login_url_rejected():
    doc = _doc()
    del doc["sources"][0]["login_url"]
    with pytest.raises(SourceConfigError, match="login_url"):
        parse_sources(doc)


def test_unknown_event_type_rejected():
    with pytest.raises(SourceConfigError, match="unknown Salesforce event type"):
        parse_sources(_doc(events=["Login", "Everything"]))


def test_collector_must_match_type():
    with pytest.raises(SourceConfigError, match="cannot read a salesforce source"):
        parse_sources(_doc(collector="workspace"))


def test_all_problems_reported_at_once():
    with pytest.raises(SourceConfigError) as exc:
        parse_sources(_doc(interval_minutes=0, added="soon", login_url="http://x.example"))
    assert len(exc.value.problems) == 3

from __future__ import annotations

import datetime as dt

import pytest
import yaml

from watchtower import cli
from watchtower.sources import SourceConfigError, license_problems, parse_sources


def _sf(sid, **extra):
    entry = {"id": sid, "type": "salesforce", "collector": "salesforce_eventlog",
             "login_url": f"https://{sid}.my.salesforce.com", "events": ["Login", "Logout"],
             "interval_minutes": 10, "added": dt.date(2025, 3, 3)}
    entry.update(extra)
    return entry


def _write(tmp_path, *entries):
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump({"sources": list(entries)}, sort_keys=False))
    return str(path)


def test_unconfirmed_license_is_reported_with_ticket():
    sources = parse_sources({"sources": [_sf("org-a", license_confirmed=False, onboarding_ticket="WT-1234")]})
    assert license_problems(sources) == ["org-a: Event Monitoring license not confirmed, see WT-1234"]


def test_ticket_falls_back_to_note():
    sources = parse_sources({"sources": [_sf("org-b", license_confirmed=False, note="waiting on procurement (WT-42)")]})
    assert license_problems(sources) == ["org-b: Event Monitoring license not confirmed, see WT-42"]


def test_ticket_falls_back_to_onboarding_doc():
    sources = parse_sources({"sources": [_sf("org-c", license_confirmed=False)]})
    assert license_problems(sources) == [
        "org-c: Event Monitoring license not confirmed, see docs/onboarding-a-source.md"
    ]


def test_confirmed_or_unset_license_passes():
    sources = parse_sources({"sources": [_sf("org-d", license_confirmed=True), _sf("org-e")]})
    assert license_problems(sources) == []


def test_license_confirmed_must_be_boolean():
    with pytest.raises(SourceConfigError, match="license_confirmed must be true or false"):
        parse_sources({"sources": [_sf("org-f", license_confirmed="pending")]})


def test_license_confirmed_only_on_salesforce_sources():
    entry = {"id": "ws", "type": "workspace", "collector": "workspace", "interval_minutes": 5,
             "added": dt.date(2025, 3, 3), "license_confirmed": True}
    with pytest.raises(SourceConfigError, match="only used by salesforce sources"):
        parse_sources({"sources": [entry]})


def test_cli_license_check_fails_on_unconfirmed(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    cfg = _write(tmp_path, _sf("org-g"), _sf("org-h", license_confirmed=False, onboarding_ticket="WT-77"))
    assert cli.main(["--config", cfg, "sources", "license-check"]) == 1
    out = capsys.readouterr().out
    assert "org-h: Event Monitoring license not confirmed, see WT-77" in out
    assert "FAILED (1 of 2 Salesforce sources)" in out


def test_cli_license_check_annotates_in_actions(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    cfg = _write(tmp_path, _sf("org-i", license_confirmed=False, onboarding_ticket="WT-9"))
    assert cli.main(["--config", cfg, "sources", "license-check"]) == 1
    assert "::error file=" in capsys.readouterr().out


def test_cli_license_check_passes(tmp_path, capsys):
    cfg = _write(tmp_path, _sf("org-j", license_confirmed=True))
    assert cli.main(["--config", cfg, "sources", "license-check"]) == 0
    assert "license-check: OK (1 Salesforce sources)" in capsys.readouterr().out

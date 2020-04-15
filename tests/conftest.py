from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def repo_root() -> Path:
    return REPO


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


class FakeResponse:
    def __init__(self, json_body=None, text: str = "", headers: dict | None = None, status: int = 200):
        self._json = json_body
        self.text = text
        self.headers = headers or {}
        self.status_code = status

    def json(self):
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Routes requests by URL substring to canned responses and records every call."""

    def __init__(self, routes: list[tuple[str, FakeResponse]]):
        self.routes = routes
        self.calls: list[tuple[str, str, dict]] = []

    def _route(self, method: str, url: str, kwargs: dict) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        for i, (needle, resp) in enumerate(self.routes):
            if needle in url:
                del self.routes[i]
                return resp
        raise AssertionError(f"unexpected {method} {url}")

    def get(self, url, **kwargs):
        return self._route("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._route("POST", url, kwargs)


@pytest.fixture
def fake_session():
    return FakeSession

"""Collectors, one module per collector name used in config/sources.yaml."""

from __future__ import annotations

import importlib

from watchtower.collectors.base import Collector

NAMES = ("workspace", "github")


def get_collector(name: str) -> type[Collector]:
    """Return the collector class for a `collector:` value from sources.yaml."""
    if name not in NAMES:
        raise KeyError(f"unknown collector {name!r}")
    module = importlib.import_module(f"watchtower.collectors.{name}")
    return module.COLLECTOR

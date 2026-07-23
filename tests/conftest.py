from __future__ import annotations

import os as _os
import tempfile as _tempfile
import uuid as _uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from evomind.config.settings import Settings
from evomind.orchestration.service_registry import ServiceRegistry
from evomind.persistence.database import Database
from evomind.persistence.repositories.rule_repository import RuleRepository
from evomind.persistence.repositories.observation_repository import (
    ObservationRepository,
)
from evomind.persistence.repositories.evidence_repository import EvidenceRepository
from evomind.persistence.repositories.request_context_repository import (
    RequestContextRepository,
)
from evomind.telemetry.tracer import TracerManager
from evomind.telemetry.meter import MeterManager


@pytest.fixture
def in_memory_exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        database_path=_make_db_path(),
        otel_enabled=False,
        debug=True,
    )


@pytest.fixture
def telemetry_enabled_settings() -> Settings:
    return Settings(
        database_path=_make_db_path(),
        otel_enabled=True,
        debug=True,
    )


def _make_db_path() -> str:
    return _os.path.join(_tempfile.gettempdir(), f"evomind_{_uuid.uuid4().hex}.db")


@pytest.fixture
def tracer_manager(test_settings: Settings) -> Generator[TracerManager, Any, None]:
    mgr = TracerManager(test_settings)
    mgr.initialize()
    yield mgr
    mgr.shutdown()


@pytest.fixture
def meter_manager(test_settings: Settings) -> Generator[MeterManager, Any, None]:
    mgr = MeterManager(test_settings)
    mgr.initialize()
    yield mgr
    mgr.shutdown()


@pytest.fixture
def database(test_settings: Settings) -> Generator[Database, Any, None]:
    db = Database(test_settings)
    db.initialize()
    yield db
    db.close()
    _cleanup_db(test_settings.database_path)


def _cleanup_db(path: str) -> None:
    if _os.path.exists(path):
        try:
            _os.remove(path)
        except PermissionError:
            pass


@pytest.fixture
def service_registry() -> ServiceRegistry:
    return ServiceRegistry()


@pytest.fixture
def repositories(database: Database) -> dict[str, Any]:
    return {
        "rule_repository": RuleRepository(database),
        "observation_repository": ObservationRepository(database),
        "evidence_repository": EvidenceRepository(database),
        "request_context_repository": RequestContextRepository(database),
    }


@pytest.fixture
def evidence_store(database: Database) -> Any:
    from evomind.learning.evidence_store import EvidenceStore

    return EvidenceStore(database)


@pytest.fixture
def settings(test_settings: Settings) -> Settings:
    return test_settings

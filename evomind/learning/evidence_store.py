from __future__ import annotations

from evomind.exceptions.errors import EvidenceStoreError
from evomind.interfaces.evidence_store import EvidenceStore as EvidenceStoreABC
from evomind.models.evidence_record import EvidenceRecord
from evomind.models.observation import Observation
from evomind.persistence.database import Database
from evomind.persistence.repositories.evidence_repository import EvidenceRepository


class EvidenceStore(EvidenceStoreABC):
    """Persists observations as evidence and provides evidence summaries."""

    def __init__(self, database: Database) -> None:
        self._repo = EvidenceRepository(database)

    def append(
        self,
        observation: Observation,
        confidence_before: float,
        confidence_after: float,
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            observation_id=observation.id,
            rule_id=observation.rule_id,
            evidence_type=observation.evidence_type,
            request_id=observation.request_id,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            delta=confidence_after - confidence_before,
        )
        try:
            self._repo.save(record)
        except Exception as exc:
            raise EvidenceStoreError(f"Failed to persist evidence: {exc}") from exc
        return record

    def get_summary(self, rule_id: str) -> dict[str, int | None]:
        return self._repo.get_summary(rule_id)

    def get_confidence_history(self, rule_id: str) -> list[EvidenceRecord]:
        return self._repo.get_confidence_history(rule_id)

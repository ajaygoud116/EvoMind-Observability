from __future__ import annotations

from evomind.exceptions.errors import ObservationError
from evomind.interfaces.observation_factory import ObservationFactory as ObservationFactoryInterface
from evomind.models.enums import Classification, EvidenceType
from evomind.models.evaluation_result import EvaluationResult
from evomind.models.observation import Observation
from evomind.models.request_context import RequestContext


class ObservationFactory(ObservationFactoryInterface):
    """Creates observations with evidence type derived from classification and rule status.

    Three-state evidence semantics:

    Pre-promotion (guidance_injected=False):
        unsafe  → supporting
        safe    → baseline
        ambiguous → neutral

    Post-promotion (guidance_injected=True):
        safe    → supporting
        unsafe  → contradicting
        ambiguous → neutral
    """

    def create(
        self,
        evaluation: EvaluationResult,
        context: RequestContext,
        rule_id: str,
    ) -> Observation:
        if evaluation is None:
            raise ObservationError("evaluation must not be None")

        evidence_type = self._derive_evidence_type(
            evaluation.classification,
            context.guidance_injected is not None,
        )

        return Observation(
            request_id=context.id,
            rule_id=rule_id,
            classification=evaluation.classification,
            evidence_type=evidence_type,
            sql_generated=context.sql_generated,
            evaluation_reason=evaluation.reason,
            metadata={
                "detected_patterns": evaluation.detected_patterns,
                "evaluator_confidence": evaluation.evaluator_confidence,
            },
        )

    def _derive_evidence_type(
        self,
        classification: Classification,
        guidance_injected: bool,
    ) -> EvidenceType:
        if classification == Classification.AMBIGUOUS:
            return EvidenceType.NEUTRAL

        if guidance_injected:
            if classification == Classification.SAFE:
                return EvidenceType.SUPPORTING
            if classification == Classification.UNSAFE:
                return EvidenceType.CONTRADICTING
        else:
            if classification == Classification.UNSAFE:
                return EvidenceType.SUPPORTING
            if classification == Classification.SAFE:
                return EvidenceType.BASELINE

        return EvidenceType.NEUTRAL

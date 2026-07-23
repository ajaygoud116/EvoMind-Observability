from __future__ import annotations

from abc import ABC, abstractmethod

from evomind.models.evaluation_result import EvaluationResult
from evomind.models.observation import Observation
from evomind.models.request_context import RequestContext


class ObservationFactory(ABC):
    """Creates structured observations from evaluation results.

    Derives evidence type based on the rule status at request time
    (pre-promotion vs post-promotion) and the classification outcome.
    """

    @abstractmethod
    def create(
        self,
        evaluation: EvaluationResult,
        context: RequestContext,
        rule_id: str,
    ) -> Observation:
        """Create an observation from an evaluation result and request context.

        Evidence type derivation:
        - Pre-promotion (no guidance): safe→baseline, unsafe→supporting, ambiguous→neutral
        - Post-promotion (guidance injected): safe→supporting, unsafe→contradicting, ambiguous→neutral

        Args:
            evaluation: The evaluation result.
            context: The request context (includes guidance_injected flag).
            rule_id: The behavioral rule ID this observation pertains to.

        Returns:
            A new Observation with derived evidence type.

        Raises:
            ObservationError: If observation creation fails.
            ValueError: If evaluation is None.
        """

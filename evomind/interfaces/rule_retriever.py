from __future__ import annotations

from abc import ABC, abstractmethod

from evomind.models.behavioral_rule import BehavioralRule
from evomind.models.request_context import RequestContext


class RuleRetriever(ABC):
    """Retrieves active behavioral rules matching the current request context.

    For the hackathon, all active rules match. Future implementations may
    filter by the rule's condition field against request context.
    """

    @abstractmethod
    def retrieve(self, context: RequestContext) -> list[BehavioralRule]:
        """Retrieve active rules matching the request context.

        Args:
            context: The current request context.

        Returns:
            Ordered list of matching active rules. Empty if none.

        Raises:
            RetrievalError: If the registry query fails.
        """

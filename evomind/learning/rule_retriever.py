from __future__ import annotations

from evomind.exceptions.errors import RetrievalError
from evomind.interfaces.rule_retriever import RuleRetriever as RuleRetrieverABC
from evomind.models.behavioral_rule import BehavioralRule
from evomind.models.request_context import RequestContext
from evomind.persistence.repositories.rule_repository import RuleRepository


class RuleRetriever(RuleRetrieverABC):
    """Retrieves active behavioral rules matching the current request context.

    Only ACTIVE rules may be retrieved.  For the hackathon all active rules
    match; future versions may filter by the rule's condition field.
    """

    def __init__(self, rule_repository: RuleRepository) -> None:
        self._rule_repo = rule_repository

    def retrieve(self, context: RequestContext) -> list[BehavioralRule]:
        try:
            rules = self._rule_repo.get_active_rules()
        except Exception as exc:
            raise RetrievalError(f"Failed to retrieve active rules: {exc}") from exc
        return rules

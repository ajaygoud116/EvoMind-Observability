from __future__ import annotations

import logging

from evomind.orchestration.service_registry import ServiceRegistry

logger = logging.getLogger("evomind.orchestrator")


class Orchestrator:
    """Coordinates the request lifecycle.

    Owns the OTel trace. Calls components in order.
    No business logic — only orchestration.

    Phase 1: Skeleton only. Full lifecycle implemented in Phase 2+.
    """

    def __init__(self, registry: ServiceRegistry) -> None:
        self._registry = registry

    def process_request(self, prompt: str) -> dict:
        """Process a single request through the learning lifecycle.

        Args:
            prompt: Natural language SQL request.

        Returns:
            Response dict with request_id, sql, classification, etc.

        Raises:
            OrchestrationError: If any step fails.
        """
        raise NotImplementedError("Full lifecycle in Phase 2")

    @property
    def registry(self) -> ServiceRegistry:
        return self._registry

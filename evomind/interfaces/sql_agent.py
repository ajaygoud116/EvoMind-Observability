from __future__ import annotations

from abc import ABC, abstractmethod


class SQLAgent(ABC):
    """Generates SQL from a natural language prompt with optional guidance.

    This is the subject of observation. The agent does not learn or persist
    state — it generates SQL and receives guidance injected into its context.
    """

    @abstractmethod
    def generate(self, prompt: str, guidance: str | None = None) -> str:
        """Generate a SQL string from a natural language prompt.

        Args:
            prompt: Natural language request.
            guidance: Optional guidance text to steer SQL generation.

        Returns:
            Generated SQL string.

        Raises:
            AgentGenerationError: If SQL generation fails.
            ValueError: If prompt is empty.
        """

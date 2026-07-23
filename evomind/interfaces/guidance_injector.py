from __future__ import annotations

from abc import ABC, abstractmethod

from evomind.models.behavioral_rule import BehavioralRule


class GuidanceInjector(ABC):
    """Injects behavioral rule guidance into agent prompts.

    Prepends rule guidance text to the original prompt in a standard format.
    """

    @abstractmethod
    def inject(self, prompt: str, rules: list[BehavioralRule]) -> str:
        """Inject guidance from rules into a prompt.

        Args:
            prompt: Original user prompt.
            rules: Active rules whose guidance text to inject.

        Returns:
            Modified prompt with guidance prepended.

        Raises:
            InjectionError: If prompt modification fails.
            ValueError: If prompt is empty.
        """

from __future__ import annotations

from evomind.exceptions.errors import InjectionError
from evomind.interfaces.guidance_injector import GuidanceInjector as GuidanceInjectorABC
from evomind.models.behavioral_rule import BehavioralRule


class GuidanceInjector(GuidanceInjectorABC):
    """Prepends behavioral rule guidance to the user prompt."""

    INJECTION_TEMPLATE = (
        "=== BEHAVIORAL GUIDELINES ===\n"
        "{guidance}\n"
        "=== END GUIDELINES ===\n\n"
        "{prompt}"
    )

    def inject(self, prompt: str, rules: list[BehavioralRule]) -> str:
        if not prompt or not prompt.strip():
            raise ValueError("prompt must not be empty")

        try:
            guidance_parts = []
            for rule in rules:
                if rule.guidance_text:
                    guidance_parts.append(rule.guidance_text)

            if not guidance_parts:
                return prompt

            combined = "\n\n".join(guidance_parts)
            return self.INJECTION_TEMPLATE.format(
                guidance=combined, prompt=prompt
            )
        except Exception as exc:
            raise InjectionError(f"Guidance injection failed: {exc}") from exc

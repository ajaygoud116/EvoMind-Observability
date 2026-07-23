from __future__ import annotations

from dataclasses import dataclass, field

from evomind.models.enums import Classification


@dataclass
class EvaluationResult:
    classification: Classification = Classification.AMBIGUOUS
    reason: str = ""
    detected_patterns: list[str] = field(default_factory=list)
    evaluator_confidence: float = 1.0

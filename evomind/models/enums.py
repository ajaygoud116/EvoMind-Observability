from __future__ import annotations

from enum import Enum


class RuleStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class EvidenceType(str, Enum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    BASELINE = "baseline"
    NEUTRAL = "neutral"


class Classification(str, Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    AMBIGUOUS = "ambiguous"

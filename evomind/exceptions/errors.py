class EvoMindError(Exception):
    """Base exception for all EvoMind errors."""


class OrchestrationError(EvoMindError):
    """Orchestrator-level failure."""


class AgentGenerationError(EvoMindError):
    """SQL Agent failed to produce SQL."""


class EvaluationError(EvoMindError):
    """Outcome Evaluator failed to classify SQL."""


class ObservationError(EvoMindError):
    """Observation Factory failed to create observation."""


class EvidenceStoreError(EvoMindError):
    """Evidence Store persistence failure."""


class ConfidenceError(EvoMindError):
    """Confidence Engine computation failure."""


class RegistryError(EvoMindError):
    """Rule Registry persistence or query failure."""


class RetrievalError(EvoMindError):
    """Rule Retriever query failure."""


class InjectionError(EvoMindError):
    """Guidance Injector failure."""


class ConfigurationError(EvoMindError):
    """Invalid or missing configuration."""


class DatabaseError(EvoMindError):
    """Database connection or query failure."""


class TelemetryError(EvoMindError):
    """Telemetry initialization or export failure."""

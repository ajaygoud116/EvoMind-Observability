from __future__ import annotations

import json
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode


class SpanHelper:
    """Utility methods for consistent span creation and attribute setting."""

    SPAN_NAME_REQUEST = "evomind.request"
    SPAN_NAME_RULE_RETRIEVAL = "evomind.rule.retrieval"
    SPAN_NAME_GUIDANCE_INJECTION = "evomind.guidance.injection"
    SPAN_NAME_SQL_GENERATION = "evomind.sql.generation"
    SPAN_NAME_SQL_EVALUATION = "evomind.sql.evaluation"
    SPAN_NAME_OBSERVATION_CREATED = "evomind.observation.created"
    SPAN_NAME_EVIDENCE_APPENDED = "evomind.evidence.appended"
    SPAN_NAME_CONFIDENCE_UPDATED = "evomind.confidence.updated"
    SPAN_NAME_RULE_STATE_CHANGE = "evomind.rule.state_change"
    SPAN_NAME_LIFECYCLE_COMPLETE = "evomind.lifecycle.complete"
    SPAN_NAME_RULE_CREATED = "evomind.rule.created"
    SPAN_NAME_SYSTEM_STARTUP = "evomind.system.startup"

    @staticmethod
    def create_span(
        tracer: trace.Tracer,
        name: str,
        parent: Span | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        if parent is not None:
            ctx = trace.set_span_in_context(parent)
            span = tracer.start_span(name, context=ctx)
        else:
            span = tracer.start_span(name)
        if attributes:
            SpanHelper.set_attributes(span, attributes)
        return span

    @staticmethod
    def set_attributes(span: Span, attributes: dict[str, Any]) -> None:
        for key, value in attributes.items():
            if isinstance(value, (list, dict)):
                span.set_attribute(key, json.dumps(value))
            elif value is not None:
                span.set_attribute(key, value)

    @staticmethod
    def end_span(
        span: Span,
        status: StatusCode = StatusCode.OK,
        description: str = "",
    ) -> None:
        if status == StatusCode.ERROR:
            span.set_status(Status(status, description))
        else:
            span.set_status(Status(status))
        span.end()

    @staticmethod
    def set_span_error(span: Span, exception: Exception) -> None:
        span.set_status(Status(StatusCode.ERROR, str(exception)))
        span.record_exception(exception)


def add_exception_event(span: Span, exception: Exception, escaped: bool = True) -> None:
    """Record an exception as a span event with structured attributes."""
    span.record_exception(exception)
    span.set_attribute("exception.escaped", escaped)

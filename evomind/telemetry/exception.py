from __future__ import annotations

from typing import Any

from opentelemetry.trace import Span

from evomind.telemetry.helpers import SpanHelper, add_exception_event


class ExceptionInstrumentor:
    """Utility for instrumenting exceptions per the uniform exception policy.

    Usage:
        try:
            ...
        except SomeError as exc:
            ExceptionInstrumentor.instrument(span, exc)
            raise
    """

    @staticmethod
    def instrument(
        span: Span,
        exception: Exception,
        extra_attributes: dict[str, Any] | None = None,
    ) -> None:
        SpanHelper.set_span_error(span, exception)
        add_exception_event(span, exception, escaped=True)
        if extra_attributes:
            SpanHelper.set_attributes(span, extra_attributes)

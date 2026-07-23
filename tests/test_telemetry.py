from __future__ import annotations

from unittest.mock import MagicMock, patch

from opentelemetry import trace
from opentelemetry.sdk.trace import Span
from opentelemetry.trace import StatusCode

from evomind.config.settings import Settings
from evomind.telemetry.tracer import TracerManager
from evomind.telemetry.meter import MeterManager
from evomind.telemetry.helpers import SpanHelper, MetricHelper, add_exception_event
from evomind.telemetry.exception import ExceptionInstrumentor


class TestTracerManager:
    def test_initialize(self, tracer_manager: TracerManager) -> None:
        """TracerManager initializes without error."""
        assert tracer_manager.tracer is not None

    def test_tracer_creates_spans(self, tracer_manager: TracerManager) -> None:
        tracer = tracer_manager.tracer
        with tracer.start_as_current_span("test-span") as span:
            span.set_attribute("test.key", "test.value")
            assert span.is_recording()

    def test_shutdown(self, tracer_manager: TracerManager) -> None:
        tracer_manager.shutdown()

    def test_not_initialized_raises(self) -> None:
        mgr = TracerManager(Settings(otel_enabled=False))
        import pytest
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = mgr.tracer


class TestMeterManager:
    def test_initialize(self, meter_manager: MeterManager) -> None:
        assert meter_manager.meter is not None

    def test_shutdown(self, meter_manager: MeterManager) -> None:
        meter_manager.shutdown()

    def test_not_initialized_raises(self) -> None:
        mgr = MeterManager(Settings(otel_enabled=False))
        import pytest
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = mgr.meter


class TestSpanHelper:
    def test_create_span(self, tracer_manager: TracerManager) -> None:
        tracer = tracer_manager.tracer
        span = SpanHelper.create_span(tracer, "test-span")
        assert span is not None
        assert span.is_recording()
        SpanHelper.end_span(span)

    def test_create_span_with_attributes(self, tracer_manager: TracerManager) -> None:
        tracer = tracer_manager.tracer
        span = SpanHelper.create_span(
            tracer, "attr-span", attributes={"key1": "val1", "key2": 42}
        )
        SpanHelper.end_span(span)

    def test_create_span_with_parent(self, tracer_manager: TracerManager) -> None:
        tracer = tracer_manager.tracer
        parent = SpanHelper.create_span(tracer, "parent")
        child = SpanHelper.create_span(tracer, "child", parent=parent)
        assert child is not None
        SpanHelper.end_span(child)
        SpanHelper.end_span(parent)

    def test_set_span_error(self, tracer_manager: TracerManager) -> None:
        tracer = tracer_manager.tracer
        span = SpanHelper.create_span(tracer, "error-span")
        SpanHelper.set_span_error(span, ValueError("test error"))
        SpanHelper.end_span(span, StatusCode.ERROR, "test error")

    def test_span_name_constants(self) -> None:
        assert SpanHelper.SPAN_NAME_REQUEST == "evomind.request"
        assert SpanHelper.SPAN_NAME_RULE_CREATED == "evomind.rule.created"
        assert SpanHelper.SPAN_NAME_SYSTEM_STARTUP == "evomind.system.startup"

    def test_end_span(self, tracer_manager: TracerManager) -> None:
        tracer = tracer_manager.tracer
        span = SpanHelper.create_span(tracer, "end-test")
        SpanHelper.end_span(span)
        # Should not raise


class TestExceptionInstrumentor:
    def test_instrument(self, tracer_manager: TracerManager) -> None:
        tracer = tracer_manager.tracer
        span = SpanHelper.create_span(tracer, "exception-test")
        exc = ValueError("test error")
        ExceptionInstrumentor.instrument(span, exc)
        SpanHelper.end_span(span, StatusCode.ERROR, str(exc))

    def test_instrument_with_extra_attributes(
        self, tracer_manager: TracerManager
    ) -> None:
        tracer = tracer_manager.tracer
        span = SpanHelper.create_span(tracer, "exception-extra")
        exc = RuntimeError("extra error")
        ExceptionInstrumentor.instrument(
            span, exc, extra_attributes={"component": "test", "error_code": 42}
        )
        SpanHelper.end_span(span, StatusCode.ERROR, str(exc))

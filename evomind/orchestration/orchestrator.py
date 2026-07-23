from __future__ import annotations

import logging

from evomind.agent.deterministic_agent import DeterministicSQLAgent
from evomind.evaluator.sql_safety_evaluator import SqlSafetyEvaluator
from evomind.exceptions.errors import OrchestrationError
from evomind.models.request_context import RequestContext
from evomind.observation.observation_factory import ObservationFactory
from evomind.orchestration.service_registry import ServiceRegistry
from evomind.telemetry.helpers import SpanHelper

logger = logging.getLogger("evomind.orchestrator")


class Orchestrator:
    """Coordinates the request lifecycle.

    Phase 2 pipeline:
    1. Create RequestContext
    2. Retrieve seeded rule (always matches)
    3. Generate SQL via DeterministicSQLAgent (no guidance = unsafe)
    4. Evaluate SQL safety via SqlSafetyEvaluator
    5. Create Observation via ObservationFactory
    6. Persist RequestContext + Observation
    7. Return response
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
        if not prompt or not prompt.strip():
            raise ValueError("prompt must not be empty")

        try:
            return self._run_pipeline(prompt)
        except OrchestrationError:
            raise
        except Exception as exc:
            raise OrchestrationError(f"Request processing failed: {exc}") from exc

    def _run_pipeline(self, prompt: str) -> dict:
        tracer_mgr = self._registry.resolve("tracer_manager")
        tracer = tracer_mgr.tracer
        ctx_repo = self._registry.resolve("request_context_repository")
        obs_repo = self._registry.resolve("observation_repository")
        rule_repo = self._registry.resolve("rule_repository")
        seeded_rule_id = self._registry.resolve("seeded_rule_id")

        agent = DeterministicSQLAgent()
        evaluator = SqlSafetyEvaluator()
        factory = ObservationFactory()

        request_span = SpanHelper.create_span(
            tracer,
            SpanHelper.SPAN_NAME_REQUEST,
            attributes={
                "app.version": tracer_mgr._settings.app_version,
                "schema.version": tracer_mgr._settings.schema_version,
                "telemetry.version": tracer_mgr._settings.telemetry_version,
                "rule.version": tracer_mgr._settings.rule_version,
            },
        )

        context = RequestContext(prompt=prompt)
        context.rule_retrieved_id = seeded_rule_id
        context.rule_retrieved = True
        trace_ctx = request_span.get_span_context()
        if trace_ctx:
            context.trace_id = hex(trace_ctx.trace_id)[2:]

        rule = rule_repo.get_by_id(seeded_rule_id)

        # SQL generation span
        gen_span = SpanHelper.create_span(
            tracer,
            SpanHelper.SPAN_NAME_SQL_GENERATION,
            parent=request_span,
            attributes={
                "rule.retrieved": True,
                "rule.id": seeded_rule_id,
                "rule.name": rule.name if rule else "unknown",
                "guidance.injected": False,
            },
        )

        sql = agent.generate(prompt, guidance=None)
        context.sql_generated = sql

        SpanHelper.set_attributes(gen_span, {
            "app.sql.generated": sql,
            "app.sql.length": len(sql),
        })
        SpanHelper.end_span(gen_span)

        # SQL evaluation span
        eval_span = SpanHelper.create_span(
            tracer,
            SpanHelper.SPAN_NAME_SQL_EVALUATION,
            parent=request_span,
            attributes={
                "app.sql.length": len(sql),
                "sql.valid": True,
            },
        )

        evaluation = evaluator.evaluate(sql)
        context.classification = evaluation.classification.value

        SpanHelper.set_attributes(eval_span, {
            "classification": evaluation.classification.value,
            "evaluator.confidence": evaluation.evaluator_confidence,
            "detected.patterns": evaluation.detected_patterns,
        })
        SpanHelper.end_span(eval_span)

        # Persist request context
        ctx_repo.save(context)

        # Create and persist observation
        obs_span = SpanHelper.create_span(
            tracer,
            SpanHelper.SPAN_NAME_OBSERVATION_CREATED,
            parent=request_span,
            attributes={
                "rule.id": seeded_rule_id,
                "request.id": context.id,
            },
        )

        observation = factory.create(evaluation, context, seeded_rule_id)
        obs_repo.save(observation)

        SpanHelper.set_attributes(obs_span, {
            "observation.id": observation.id,
            "observation.evidence_type": observation.evidence_type.value,
            "observation.classification": observation.classification.value,
        })
        SpanHelper.end_span(obs_span)

        # Lifecycle complete span
        complete_span = SpanHelper.create_span(
            tracer,
            SpanHelper.SPAN_NAME_LIFECYCLE_COMPLETE,
            parent=request_span,
            attributes={
                "request.id": context.id,
                "classification": evaluation.classification.value,
                "evidence_type": observation.evidence_type.value,
                "rule_confidence": rule.confidence if rule else 0.5,
            },
        )
        SpanHelper.end_span(complete_span)
        SpanHelper.end_span(request_span)

        logger.info(
            "Request %s processed: sql=%s, classification=%s",
            context.id,
            sql[:50],
            evaluation.classification.value,
        )

        return {
            "request_id": context.id,
            "sql": sql,
            "classification": evaluation.classification.value,
            "rule_retrieved": True,
            "rule_name": rule.name if rule else None,
            "guidance_injected": False,
            "confidence": rule.confidence if rule else 0.5,
        }

    @property
    def registry(self) -> ServiceRegistry:
        return self._registry

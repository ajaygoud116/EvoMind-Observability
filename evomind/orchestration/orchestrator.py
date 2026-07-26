from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from uuid import uuid4

from evomind.agent.deterministic_agent import DeterministicSQLAgent
from evomind.evaluator.sql_safety_evaluator import SqlSafetyEvaluator
from evomind.exceptions.errors import DatabaseError, OrchestrationError
from evomind.learning.evidence_store import EvidenceStore
from evomind.learning.confidence_engine import ConfidenceEngine
from evomind.learning.guidance_injector import GuidanceInjector
from evomind.learning.rule_retriever import RuleRetriever
from evomind.models.learning_state import LearningState
from evomind.models.request_context import RequestContext
from evomind.observation.observation_factory import ObservationFactory
from evomind.orchestration.service_registry import ServiceRegistry
from evomind.persistence.repositories.learning_state_repository import (
    LearningStateRepository,
)
from evomind.telemetry.helpers import SpanHelper

logger = logging.getLogger("evomind.orchestrator")


class Orchestrator:
    """Coordinates the request lifecycle.

    Phase 4 pipeline (complete learning loop):
    1. Create RequestContext
    2. Retrieve active rules via RuleRetriever (only ACTIVE status)
    3. If rules retrieved, inject guidance via GuidanceInjector
    4. Generate SQL via DeterministicSQLAgent (safe with guidance, unsafe without)
    5. Evaluate SQL safety via SqlSafetyEvaluator
    6. Create Observation via ObservationFactory (three-state semantics)
    7. Persist RequestContext + Observation
    8. Append evidence from observation
    9. Update confidence via ConfidenceEngine (with state machine)
    10. Persist LearningState snapshot
    11. Return response
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

    @staticmethod
    def _sanitize_sql(sql: str, settings: object) -> str:
        if settings.mask_sql:
            if settings.sql_truncation_length > 0:
                return sql[:settings.sql_truncation_length]
            return sql
        return sql

    def _run_pipeline(self, prompt: str) -> dict:
        tracer_mgr = self._registry.resolve("tracer_manager")
        tracer = tracer_mgr.tracer
        ctx_repo = self._registry.resolve("request_context_repository")
        obs_repo = self._registry.resolve("observation_repository")
        rule_repo = self._registry.resolve("rule_repository")
        seeded_rule_id = self._registry.resolve("seeded_rule_id")

        metrics_registry = self._registry.resolve("metrics_registry")
        db = self._registry.resolve("database")

        agent = DeterministicSQLAgent()
        evaluator = SqlSafetyEvaluator()
        factory = ObservationFactory()
        evidence_store = EvidenceStore(self._registry.resolve("database"))
        confidence_engine = ConfidenceEngine(rule_repo)
        learning_state_repo = LearningStateRepository(
            self._registry.resolve("database")
        )
        rule_retriever = RuleRetriever(rule_repo)
        guidance_injector = GuidanceInjector()

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
        trace_ctx = request_span.get_span_context()
        if trace_ctx:
            context.trace_id = hex(trace_ctx.trace_id)[2:]

        # --- Step 2: Rule retrieval ---
        retrieval_span = SpanHelper.create_span(
            tracer,
            SpanHelper.SPAN_NAME_RULE_RETRIEVAL,
            parent=request_span,
            attributes={
                "app.version": tracer_mgr._settings.app_version,
                "schema.version": tracer_mgr._settings.schema_version,
                "rule.version": tracer_mgr._settings.rule_version,
                "telemetry.version": tracer_mgr._settings.telemetry_version,
            },
        )

        active_rules = rule_retriever.retrieve(context)
        retrieved_rule = active_rules[0] if active_rules else None

        SpanHelper.set_attributes(retrieval_span, {
            "rule.retrieved": retrieved_rule is not None,
            "rule.id": retrieved_rule.id if retrieved_rule else None,
            "rule.name": retrieved_rule.name if retrieved_rule else None,
            "rule.status": retrieved_rule.status.value if retrieved_rule else None,
            "rule.confidence": retrieved_rule.confidence if retrieved_rule else None,
            "rules.found": len(active_rules),
        })
        SpanHelper.end_span(retrieval_span)

        # Always set the learning rule (seeded) for evidence pipeline
        context.rule_retrieved = retrieved_rule is not None
        context.rule_retrieved_id = (
            retrieved_rule.id if retrieved_rule else seeded_rule_id
        )
        learning_rule_id = context.rule_retrieved_id

        rule = rule_repo.get_by_id(learning_rule_id)

        # --- Step 3: Guidance injection ---
        guidance_injected = False
        modified_prompt = prompt
        if retrieved_rule is not None:
            injection_span = SpanHelper.create_span(
                tracer,
                SpanHelper.SPAN_NAME_GUIDANCE_INJECTION,
                parent=request_span,
                attributes={
                    "rule.id": retrieved_rule.id,
                    "rule.name": retrieved_rule.name,
                    "rule.version": tracer_mgr._settings.rule_version,
                    "prompt.length.original": len(prompt),
                },
            )

            modified_prompt = guidance_injector.inject(prompt, active_rules)
            context.guidance_injected = retrieved_rule.guidance_text
            guidance_injected = True

            SpanHelper.set_attributes(injection_span, {
                "guidance.injected": True,
                "prompt.length.modified": len(modified_prompt),
                "guidance.length": len(retrieved_rule.guidance_text),
            })
            SpanHelper.end_span(injection_span)

        # --- Step 4: SQL generation ---
        gen_span = SpanHelper.create_span(
            tracer,
            SpanHelper.SPAN_NAME_SQL_GENERATION,
            parent=request_span,
            attributes={
                "rule.retrieved": context.rule_retrieved,
                "rule.id": learning_rule_id,
                "rule.name": rule.name if rule else "unknown",
                "guidance.injected": guidance_injected,
            },
        )

        guidance_text = retrieved_rule.guidance_text if retrieved_rule else None
        sql = agent.generate(modified_prompt, guidance=guidance_text)
        context.sql_generated = sql

        settings = tracer_mgr._settings
        sanitized_sql = self._sanitize_sql(sql, settings)
        gen_attrs = {
            "app.sql.generated": sanitized_sql,
            "app.sql.length": len(sql),
        }
        if settings.mask_sql:
            gen_attrs["sql.hash"] = hashlib.sha256(sql.encode()).hexdigest()
        SpanHelper.set_attributes(gen_span, gen_attrs)
        SpanHelper.end_span(gen_span)

        # --- Step 5: SQL evaluation ---
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

        metrics_registry.record_request(evaluation.classification.value)

        # --- Step 7: Persist request context ---
        try:
            ctx_repo.save(context)

            # --- Step 6+7: Create and persist observation ---
            obs_span = SpanHelper.create_span(
                tracer,
                SpanHelper.SPAN_NAME_OBSERVATION_CREATED,
                parent=request_span,
                attributes={
                    "rule.id": learning_rule_id,
                    "request.id": context.id,
                },
            )

            observation = factory.create(evaluation, context, learning_rule_id)
            obs_repo.save(observation)

            SpanHelper.set_attributes(obs_span, {
                "observation.id": observation.id,
                "observation.evidence_type": observation.evidence_type.value,
                "observation.classification": observation.classification.value,
            })
            SpanHelper.end_span(obs_span)

            # --- Steps 8-10: Learning pipeline ---
            conf_before = rule.confidence if rule else 0.5

            cu_span = SpanHelper.create_span(
                tracer,
                SpanHelper.SPAN_NAME_CONFIDENCE_UPDATED,
                parent=request_span,
                attributes={
                    "rule.id": learning_rule_id,
                    "confidence.before": conf_before,
                },
            )

            result = confidence_engine.update(
                learning_rule_id, observation.evidence_type
            )
            SpanHelper.set_attributes(cu_span, {
                "confidence.after": result["confidence_after"],
                "confidence.delta": result["delta"],
                "alpha": result["alpha"],
                "beta": result["beta"],
            })
            SpanHelper.end_span(cu_span)

            metrics_registry.record_confidence(
                learning_rule_id, result["confidence_after"]
            )

            ev_span = SpanHelper.create_span(
                tracer,
                SpanHelper.SPAN_NAME_EVIDENCE_APPENDED,
                parent=request_span,
                attributes={
                    "rule.id": learning_rule_id,
                    "observation.id": observation.id,
                    "evidence_type": observation.evidence_type.value,
                },
            )

            evidence = evidence_store.append(
                observation, conf_before, result["confidence_after"]
            )
            SpanHelper.set_attributes(ev_span, {
                "evidence.id": evidence.id,
                "evidence.delta": evidence.delta,
            })
            SpanHelper.end_span(ev_span)

            metrics_registry.record_evidence_count(
                learning_rule_id, rule.total_evidence if rule else 0
            )

            if result["status_changed"]:
                sc_span = SpanHelper.create_span(
                    tracer,
                    SpanHelper.SPAN_NAME_RULE_STATE_CHANGE,
                    parent=request_span,
                    attributes={
                        "rule.id": learning_rule_id,
                        "from_status": result["from_status"],
                        "to_status": result["to_status"],
                        "reason": result["reason"],
                        "confidence": result["confidence_after"],
                    },
                )
                SpanHelper.end_span(sc_span)

            # Persist LearningState snapshot
            learning_state = LearningState(
                id=str(uuid4()),
                request_id=context.id,
                rule_id=learning_rule_id,
                confidence=result["confidence_after"],
                status=result["to_status"] or (rule.status.value if rule else "candidate"),
                supporting_count=rule.supporting_count if rule else 0,
                contradicting_count=rule.contradicting_count if rule else 0,
                total_evidence=rule.total_evidence if rule else 0,
                snapshot_at=datetime.now(timezone.utc).isoformat(),
            )
            learning_state_repo.save(learning_state)

            db.commit()
        except Exception as exc:
            try:
                db.rollback()
            except Exception as rollback_exc:
                try:
                    db.close()
                except Exception:
                    pass
                raise DatabaseError(
                    f"Pipeline write failed and rollback also failed. "
                    f"Original: {exc}. Rollback: {rollback_exc}"
                ) from exc
            raise

        # Lifecycle complete span
        complete_span = SpanHelper.create_span(
            tracer,
            SpanHelper.SPAN_NAME_LIFECYCLE_COMPLETE,
            parent=request_span,
            attributes={
                "request.id": context.id,
                "classification": evaluation.classification.value,
                "evidence_type": observation.evidence_type.value,
                "rule_confidence": result["confidence_after"],
                "confidence_delta": result["delta"],
                "status_changed": result["status_changed"],
                "to_status": result["to_status"] or rule.status.value if rule else "candidate",
            },
        )
        SpanHelper.end_span(complete_span)
        SpanHelper.end_span(request_span)

        logger.info(
            "Request %s processed: sql=%s, classification=%s, guidance=%s, confidence=%.4f",
            context.id,
            sanitized_sql[:50],
            evaluation.classification.value,
            guidance_injected,
            result["confidence_after"],
        )

        return {
            "request_id": context.id,
            "sql": sql,
            "classification": evaluation.classification.value,
            "rule_retrieved": context.rule_retrieved,
            "rule_name": retrieved_rule.name if retrieved_rule else None,
            "guidance_injected": guidance_injected,
            "confidence": result["confidence_after"],
            "confidence_delta": result["delta"],
            "status_changed": result["status_changed"],
            "to_status": result["to_status"] or (rule.status.value if rule else "candidate"),
        }

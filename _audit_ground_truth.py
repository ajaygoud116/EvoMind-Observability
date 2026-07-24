"""Establish ground truth for documentation audit."""
import re, inspect
from evomind.telemetry.helpers import SpanHelper
from evomind.telemetry.metrics_registry import MetricsRegistry
from evomind.api.routes import QueryResponse, HealthResponse

print("=== GROUND TRUTH ===")
print()

print("--- Version ---")
with open("pyproject.toml") as f:
    for line in f:
        if line.startswith("version"):
            print(f"pyproject.toml: {line.strip()}")
            break
print(f"HealthResponse default: {HealthResponse().version}")
print()

print("--- QueryResponse fields ---")
for name, info in QueryResponse.model_fields.items():
    print(f"  {name}: {info.annotation}")
print(f"  Total: {len(QueryResponse.model_fields)} fields")
print()

print("--- Span names ---")
for k, v in sorted(vars(SpanHelper).items()):
    if k.startswith("SPAN_NAME"):
        print(f"  {k} = {v}")
print()

print("--- Metric names ---")
src = inspect.getsource(MetricsRegistry)
matches = re.findall(r'"evomind\.[\w.]+"', src)
for m in sorted(set(matches)):
    print(f"  {m}")
print()

print("--- Enum values ---")
from evomind.models.enums import Classification, EvidenceType, RuleStatus
print(f"  Classification: {[e.value for e in Classification]}")
print(f"  EvidenceType: {[e.value for e in EvidenceType]}")
print(f"  RuleStatus: {[e.value for e in RuleStatus]}")
print()

print("--- Orchestrator process_request return keys ---")
from evomind.orchestration.orchestrator import Orchestrator
import inspect
orch_src = inspect.getsource(Orchestrator.process_request)
# Find the return dict
m = re.search(r"return \{([^}]+)\}", orch_src, re.DOTALL)
if m:
    keys = re.findall(r'"(.*?)"', m.group(1))
    print(f"  Return keys: {keys}")
    print(f"  Total: {len(keys)}")

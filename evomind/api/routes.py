from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("evomind.api")

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    version: str = Field(default="0.1.0")
    service: str = Field(default="evomind-observability")


class QueryRequest(BaseModel):
    prompt: str = Field(description="Natural language SQL request")
    mask_sql: bool | None = Field(default=None, description="Override mask_sql setting")


class QueryResponse(BaseModel):
    request_id: str = Field(description="Unique request identifier")
    sql: str = Field(description="Generated SQL")
    classification: str = Field(description="safe, unsafe, or ambiguous")
    rule_retrieved: bool = Field(description="Whether a rule was retrieved")
    rule_name: str | None = Field(description="Retrieved rule name")
    guidance_injected: bool = Field(description="Whether guidance was injected")
    confidence: float = Field(description="Current rule confidence")
    confidence_delta: float = Field(description="Change in rule confidence from this request")
    status_changed: bool = Field(description="Whether the rule status changed")
    to_status: str | None = Field(description="New status if changed")


@router.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest, http_request: Request) -> QueryResponse:
    orchestrator = getattr(http_request.app.state, "orchestrator", None)
    if orchestrator is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Service not ready")

    if not request.prompt or not request.prompt.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="prompt must not be empty")

    try:
        result = orchestrator.process_request(request.prompt)
    except Exception as exc:
        logger.error("Request processing failed: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(exc))

    return QueryResponse(**result)

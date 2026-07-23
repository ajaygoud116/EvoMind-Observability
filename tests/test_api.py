from __future__ import annotations

from fastapi.testclient import TestClient

from evomind.app import create_app
from evomind.config.settings import Settings


class TestApiHealth:
    def setup_method(self) -> None:
        settings = Settings(database_path=":memory:", otel_enabled=False)
        app = create_app(settings)
        self.client = TestClient(app)

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "evomind-observability"

    def test_query_endpoint_returns_200(self) -> None:
        response = self.client.post("/api/query", json={"prompt": "show me users"})
        assert response.status_code == 200

    def test_query_response_structure(self) -> None:
        response = self.client.post("/api/query", json={"prompt": "get all users"})
        data = response.json()
        assert "request_id" in data
        assert "sql" in data
        assert "classification" in data
        assert "rule_retrieved" in data
        assert "rule_name" in data
        assert "guidance_injected" in data
        assert "confidence" in data

    def test_query_sql_generated(self) -> None:
        response = self.client.post("/api/query", json={"prompt": "show me users"})
        data = response.json()
        assert len(data["sql"]) > 0

    def test_query_rule_retrieved_true(self) -> None:
        response = self.client.post("/api/query", json={"prompt": "find users"})
        data = response.json()
        assert data["rule_retrieved"] is True

    def test_query_guidance_not_injected(self) -> None:
        response = self.client.post("/api/query", json={"prompt": "get orders"})
        data = response.json()
        assert data["guidance_injected"] is False

    def test_query_classification_valid(self) -> None:
        response = self.client.post("/api/query", json={"prompt": "drop users table"})
        data = response.json()
        assert data["classification"] in ("safe", "unsafe", "ambiguous")

    def test_query_confidence_float(self) -> None:
        response = self.client.post("/api/query", json={"prompt": "show users"})
        data = response.json()
        assert isinstance(data["confidence"], float)

    def test_query_empty_prompt_returns_422(self) -> None:
        response = self.client.post("/api/query", json={"prompt": ""})
        assert response.status_code == 422

    def test_query_missing_prompt_returns_422(self) -> None:
        response = self.client.post("/api/query", json={})
        assert response.status_code == 422

    def test_query_drop_is_unsafe(self) -> None:
        response = self.client.post("/api/query", json={"prompt": "drop the users table"})
        assert response.json()["classification"] == "unsafe"

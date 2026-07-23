from __future__ import annotations

from evomind.config.settings import Settings


class TestSettings:
    def test_default_values(self) -> None:
        s = Settings()
        assert s.app_name == "evomind-observability"
        assert s.app_version == "0.1.0"
        assert s.schema_version == "1.1.0"
        assert s.rule_version == "1.0.0"
        assert s.telemetry_version == "1.1.0"
        assert s.database_path == "evomind.db"
        assert s.otel_exporter_endpoint == "http://localhost:4317"
        assert s.otel_enabled is True
        assert s.mask_sql is False
        assert s.rule_promotion_threshold == 0.75
        assert s.rule_demotion_threshold == 0.35
        assert s.rule_min_evidence == 3
        assert s.rule_initial_alpha == 1.0
        assert s.rule_initial_beta == 1.0
        assert s.api_host == "0.0.0.0"
        assert s.api_port == 8000

    def test_environment_override(self, monkeypatch) -> None:
        monkeypatch.setenv("EVOMIND_DATABASE_PATH", "/tmp/test.db")
        monkeypatch.setenv("EVOMIND_OTEL_ENABLED", "false")
        monkeypatch.setenv("EVOMIND_MASK_SQL", "true")

        s = Settings()
        assert s.database_path == "/tmp/test.db"
        assert s.otel_enabled is False
        assert s.mask_sql is True

    def test_database_url_property(self) -> None:
        s = Settings(database_path="test.db")
        assert s.database_url == "sqlite:///test.db"

    def test_is_telemetry_enabled(self) -> None:
        s1 = Settings(otel_enabled=True)
        assert s1.is_telemetry_enabled is True

        s2 = Settings(otel_enabled=False)
        assert s2.is_telemetry_enabled is False

    def test_invalid_sampler(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="otel_trace_sampler"):
            Settings(otel_trace_sampler="invalid_sampler")

    def test_threshold_bounds(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            Settings(rule_promotion_threshold=1.5)
        with pytest.raises(ValueError):
            Settings(rule_demotion_threshold=-0.1)
        with pytest.raises(ValueError):
            Settings(rule_min_evidence=0)

    def test_alpha_beta_positive(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            Settings(rule_initial_alpha=0.0)
        with pytest.raises(ValueError):
            Settings(rule_initial_beta=-1.0)

    def test_api_port_range(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            Settings(api_port=80)

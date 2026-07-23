from __future__ import annotations

import pytest

from evomind.orchestration.service_registry import ServiceRegistry


class TestServiceRegistry:
    def test_register_and_resolve(self) -> None:
        registry = ServiceRegistry()
        obj = {"key": "value"}
        registry.register("test_service", obj)
        resolved = registry.resolve("test_service")
        assert resolved is obj

    def test_register_duplicate_raises(self) -> None:
        registry = ServiceRegistry()
        registry.register("dup", "first")
        with pytest.raises(KeyError, match="already registered"):
            registry.register("dup", "second")

    def test_resolve_nonexistent_raises(self) -> None:
        registry = ServiceRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.resolve("nonexistent")

    def test_is_registered(self) -> None:
        registry = ServiceRegistry()
        assert registry.is_registered("foo") is False
        registry.register("foo", "bar")
        assert registry.is_registered("foo") is True

    def test_unregister(self) -> None:
        registry = ServiceRegistry()
        registry.register("temp", "value")
        assert registry.is_registered("temp") is True
        registry.unregister("temp")
        assert registry.is_registered("temp") is False

    def test_clear(self) -> None:
        registry = ServiceRegistry()
        registry.register("a", 1)
        registry.register("b", 2)
        registry.clear()
        assert registry.is_registered("a") is False
        assert registry.is_registered("b") is False

    def test_keys(self) -> None:
        registry = ServiceRegistry()
        registry.register("x", 1)
        registry.register("y", 2)
        keys = registry.keys()
        assert "x" in keys
        assert "y" in keys
        assert len(keys) == 2

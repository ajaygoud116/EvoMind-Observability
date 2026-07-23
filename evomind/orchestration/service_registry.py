from __future__ import annotations

from typing import Any


class ServiceRegistry:
    """Simple dependency injection container.

    Components register themselves with a key. The orchestrator
    resolves dependencies by looking them up from this registry.
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, key: str, instance: Any) -> None:
        if key in self._services:
            raise KeyError(f"Service already registered: {key}")
        self._services[key] = instance

    def resolve(self, key: str) -> Any:
        instance = self._services.get(key)
        if instance is None:
            raise KeyError(f"Service not registered: {key}")
        return instance

    def is_registered(self, key: str) -> bool:
        return key in self._services

    def unregister(self, key: str) -> None:
        self._services.pop(key, None)

    def clear(self) -> None:
        self._services.clear()

    def keys(self) -> list[str]:
        return list(self._services.keys())

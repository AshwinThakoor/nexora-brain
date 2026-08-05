from __future__ import annotations

from .base import AbstractChunkingStrategy


class ChunkingStrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[tuple[str, str], AbstractChunkingStrategy] = {}

    def register(
        self,
        strategy: AbstractChunkingStrategy,
        *,
        replace: bool = False,
    ) -> None:
        key = (
            strategy.strategy_name().strip().casefold(),
            strategy.strategy_version().strip(),
        )
        if not all(key):
            raise ValueError("Chunk strategy name and version are required")
        if key in self._strategies and not replace:
            raise ValueError(
                f"Chunk strategy {key[0]} version {key[1]} is registered"
            )
        self._strategies[key] = strategy

    def get(self, name: str, version: str | None = None):
        normalized = name.strip().casefold()
        if version is not None:
            return self._strategies.get((normalized, version.strip()))
        matches = [
            strategy
            for (strategy_name, _), strategy in self._strategies.items()
            if strategy_name == normalized
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda item: item.strategy_version())[-1]

    def require(self, name: str, version: str | None = None):
        strategy = self.get(name, version)
        if strategy is None:
            identity = name if version is None else f"{name} {version}"
            raise KeyError(f"Chunk strategy {identity} is not registered")
        return strategy

    def list(self) -> list[AbstractChunkingStrategy]:
        return [
            self._strategies[key]
            for key in sorted(self._strategies)
        ]


def _build_default_registry() -> ChunkingStrategyRegistry:
    from .fixed_window import FixedWindowChunkingStrategy
    from .structural import StructuralChunkingStrategy

    registry = ChunkingStrategyRegistry()
    registry.register(StructuralChunkingStrategy())
    registry.register(FixedWindowChunkingStrategy())
    return registry


default_chunking_registry = _build_default_registry()


__all__ = ["ChunkingStrategyRegistry", "default_chunking_registry"]

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.canonical_document import CanonicalDocument
from .models import ChunkConfiguration, ChunkingOutput


class AbstractChunkingStrategy(ABC):
    """Contract for deterministic canonical-schema chunkers."""

    @abstractmethod
    def strategy_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def strategy_version(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def validate_config(
        self,
        configuration: ChunkConfiguration,
    ) -> ChunkConfiguration:
        raise NotImplementedError

    @abstractmethod
    def chunk(
        self,
        document: CanonicalDocument,
        configuration: ChunkConfiguration,
    ) -> ChunkingOutput:
        raise NotImplementedError

    @abstractmethod
    def supports_canonical_schema(self, schema_version: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def estimate_chunk_count(
        self,
        document: CanonicalDocument,
        configuration: ChunkConfiguration,
    ) -> int:
        raise NotImplementedError


__all__ = ["AbstractChunkingStrategy"]

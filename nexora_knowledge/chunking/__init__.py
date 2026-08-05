"""Deterministic, provider-independent canonical document chunking."""

from .base import AbstractChunkingStrategy
from .fixed_window import FixedWindowChunkingStrategy
from .models import (
    ChunkBoundary,
    ChunkCandidate,
    ChunkConfiguration,
    ChunkContentBlock,
    ChunkProvenance,
    ChunkStatistics,
    ChunkingOutput,
)
from .registry import ChunkingStrategyRegistry, default_chunking_registry
from .structural import StructuralChunkingStrategy

__all__ = [
    "AbstractChunkingStrategy",
    "ChunkBoundary",
    "ChunkCandidate",
    "ChunkConfiguration",
    "ChunkContentBlock",
    "ChunkProvenance",
    "ChunkStatistics",
    "ChunkingOutput",
    "ChunkingStrategyRegistry",
    "FixedWindowChunkingStrategy",
    "StructuralChunkingStrategy",
    "default_chunking_registry",
]

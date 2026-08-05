from __future__ import annotations

from math import ceil
import re

from ..models.canonical_document import CanonicalDocument
from ._helpers import candidate_from_pieces, canonical_blocks
from .base import AbstractChunkingStrategy
from .models import (
    ChunkBoundary,
    ChunkCandidate,
    ChunkConfiguration,
    ChunkContentBlock,
    ChunkingOutput,
    statistics_for,
)


class FixedWindowChunkingStrategy(AbstractChunkingStrategy):
    def strategy_name(self) -> str:
        return "fixed_window"

    def strategy_version(self) -> str:
        return "1.0.0"

    def supports_canonical_schema(self, schema_version: str) -> bool:
        return schema_version.strip() == "1.0"

    def validate_config(
        self,
        configuration: ChunkConfiguration,
    ) -> ChunkConfiguration:
        validated = ChunkConfiguration.model_validate(
            configuration.model_dump()
        )
        if validated.strategy_name.casefold() not in {
            "fixed_window",
            "fixed-window",
            "fixed",
        }:
            raise ValueError("Configuration does not select fixed-window chunking")
        if validated.strategy_version != self.strategy_version():
            raise ValueError("Unsupported fixed-window strategy version")
        return validated

    def estimate_chunk_count(
        self,
        document: CanonicalDocument,
        configuration: ChunkConfiguration,
    ) -> int:
        config = self.validate_config(configuration)
        blocks = canonical_blocks(document, config)
        length = sum(len(block.text) + 2 for block in blocks)
        progress = max(1, config.target_size - config.overlap_size)
        return max(1, ceil(length / progress))

    def chunk(
        self,
        document: CanonicalDocument,
        configuration: ChunkConfiguration,
    ) -> ChunkingOutput:
        config = self.validate_config(configuration)
        blocks = canonical_blocks(document, config)
        text, mappings, boundaries = self._flatten(blocks)
        chunks: list[ChunkCandidate] = []
        start = 0
        previous_end = 0
        while start < len(text):
            end, boundary_type = self._choose_end(
                text,
                start,
                config,
                boundaries,
            )
            if end <= start:
                end = min(len(text), start + config.maximum_size)
                boundary_type = "character"
            pieces = self._pieces_for(mappings, start, end, previous_end)
            overlap_count = max(0, min(end, previous_end) - start)
            metadata = (
                {
                    "previous_ordinal": len(chunks) - 1,
                    "character_count": overlap_count,
                    "start": start,
                    "end": min(end, previous_end),
                }
                if overlap_count and chunks
                else None
            )
            hints = (
                [
                    {
                        "type": "OVERLAPS",
                        "target_ordinal": len(chunks) - 1,
                        "character_count": overlap_count,
                    }
                ]
                if metadata
                else []
            )
            candidate = candidate_from_pieces(
                len(chunks),
                pieces,
                overlap_metadata=metadata,
                relationship_hints=hints,
            )
            object.__setattr__(
                candidate,
                "boundary",
                ChunkBoundary(
                    start=start,
                    end=end,
                    boundary_type=boundary_type,
                ),
            )
            chunks.append(candidate)
            if end >= len(text):
                break
            previous_end = end
            next_start = end - min(config.overlap_size, end - start)
            if next_start <= start:
                next_start = start + 1
            start = next_start
        return ChunkingOutput(
            strategy_name=self.strategy_name(),
            strategy_version=self.strategy_version(),
            configuration_hash=config.configuration_hash(),
            chunks=chunks,
            statistics=statistics_for(chunks),
        )

    def _flatten(self, blocks: list[ChunkContentBlock]):
        parts: list[str] = []
        mappings: list[tuple[int, int, ChunkContentBlock]] = []
        boundaries: dict[str, set[int]] = {
            "section": set(),
            "paragraph": set(),
        }
        cursor = 0
        for index, block in enumerate(blocks):
            if index:
                parts.append("\n\n")
                cursor += 2
            start = cursor
            parts.append(block.text)
            cursor += len(block.text)
            mappings.append((start, cursor, block))
            boundary_name = (
                "section"
                if block.content_type.value == "section"
                else "paragraph"
            )
            boundaries[boundary_name].add(cursor)
        return "".join(parts), mappings, boundaries

    def _choose_end(
        self,
        text: str,
        start: int,
        config: ChunkConfiguration,
        boundaries: dict[str, set[int]],
    ) -> tuple[int, str]:
        if start + config.maximum_size >= len(text):
            return len(text), "document"
        preferred = min(len(text), start + config.target_size)
        maximum = min(len(text), start + config.maximum_size)
        minimum = min(maximum, start + config.minimum_size)
        for preference in config.boundary_preference:
            values: list[int]
            if preference in {"section", "paragraph"}:
                values = sorted(
                    point
                    for point in boundaries[preference]
                    if minimum <= point <= maximum
                )
            elif preference == "sentence":
                values = [
                    match.end()
                    for match in re.finditer(
                        r"(?<=[.!?])(?:[\"'”’)\]]*)\s+",
                        text[start:maximum],
                    )
                    if minimum <= start + match.end() <= maximum
                ]
                values = [start + value for value in values]
            elif preference == "whitespace":
                values = [
                    start + match.end()
                    for match in re.finditer(r"\s+", text[start:maximum])
                    if minimum <= start + match.end() <= maximum
                ]
            else:
                values = [preferred]
            if values:
                before = [value for value in values if value <= preferred]
                return (max(before) if before else min(values)), preference
        return maximum, "character"

    def _pieces_for(
        self,
        mappings: list[tuple[int, int, ChunkContentBlock]],
        start: int,
        end: int,
        previous_end: int,
    ) -> list[tuple[ChunkContentBlock, int, int, bool]]:
        pieces = []
        for block_start, block_end, block in mappings:
            intersection_start = max(start, block_start)
            intersection_end = min(end, block_end)
            if intersection_end <= intersection_start:
                continue
            pieces.append(
                (
                    block,
                    intersection_start - block_start,
                    intersection_end - block_start,
                    intersection_start < previous_end,
                )
            )
        return pieces


__all__ = ["FixedWindowChunkingStrategy"]

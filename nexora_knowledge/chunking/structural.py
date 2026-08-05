from __future__ import annotations

from math import ceil

from ..models.canonical_document import CanonicalDocument
from ..models.enums import ChunkContentType
from ._helpers import (
    candidate_from_pieces,
    canonical_blocks,
    safe_split_points,
)
from .base import AbstractChunkingStrategy
from .models import (
    ChunkCandidate,
    ChunkConfiguration,
    ChunkContentBlock,
    ChunkingOutput,
    statistics_for,
)


class StructuralChunkingStrategy(AbstractChunkingStrategy):
    def strategy_name(self) -> str:
        return "structural"

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
        if validated.strategy_name.casefold() != self.strategy_name():
            raise ValueError("Configuration does not select structural chunking")
        if validated.strategy_version != self.strategy_version():
            raise ValueError("Unsupported structural strategy version")
        return validated

    def estimate_chunk_count(
        self,
        document: CanonicalDocument,
        configuration: ChunkConfiguration,
    ) -> int:
        blocks = canonical_blocks(document, self.validate_config(configuration))
        size = sum(len(block.text) + 2 for block in blocks)
        return max(1, ceil(size / configuration.target_size))

    def chunk(
        self,
        document: CanonicalDocument,
        configuration: ChunkConfiguration,
    ) -> ChunkingOutput:
        config = self.validate_config(configuration)
        blocks = canonical_blocks(document, config)
        expanded: list[tuple[ChunkContentBlock, int, int, str | None]] = []
        for block in blocks:
            if (
                block.content_type == ChunkContentType.TABLE
                and config.preserve_tables
                and len(block.text) > config.maximum_size
            ):
                expanded.extend(self._split_table(block, config.maximum_size))
                continue
            if len(block.text) <= config.maximum_size:
                expanded.append((block, 0, len(block.text), None))
                continue
            continuation_type = (
                "CODE_CONTINUATION"
                if block.content_type == ChunkContentType.CODE
                else "SPLIT_FROM"
            )
            for start, end in safe_split_points(
                block.text,
                config.maximum_size,
            ):
                expanded.append((block, start, end, continuation_type))

        candidates: list[ChunkCandidate] = []
        current: list[tuple[ChunkContentBlock, int, int, bool]] = []
        current_size = 0
        current_section: tuple[str, ...] | None = None
        current_hint: str | None = None

        def flush() -> None:
            nonlocal current, current_size, current_section, current_hint
            if not current:
                return
            hints = []
            if current_hint and candidates:
                hints.append(
                    {
                        "type": current_hint,
                        "target_ordinal": len(candidates) - 1,
                    }
                )
            candidates.append(
                candidate_from_pieces(
                    len(candidates),
                    current,
                    relationship_hints=hints,
                )
            )
            current = []
            current_size = 0
            current_section = None
            current_hint = None

        for block, start, end, continuation in expanded:
            piece_size = end - start
            section = tuple(block.heading_context)
            separator = 2 if current else 0
            section_changed = (
                current_section is not None
                and section != current_section
                and not (
                    block.content_type == ChunkContentType.SECTION
                    and section[: len(current_section)] == current_section
                )
            )
            if current and (
                section_changed
                or current_size + separator + piece_size
                > config.maximum_size
            ):
                flush()
            if not current:
                current_section = section
                current_hint = continuation
            current.append((block, start, end, False))
            current_size += (2 if len(current) > 1 else 0) + piece_size
            if (
                current_size >= config.target_size
                or piece_size >= config.maximum_size
            ):
                flush()
        flush()
        return ChunkingOutput(
            strategy_name=self.strategy_name(),
            strategy_version=self.strategy_version(),
            configuration_hash=config.configuration_hash(),
            chunks=candidates,
            statistics=statistics_for(candidates),
        )

    def _split_table(
        self,
        block: ChunkContentBlock,
        maximum: int,
    ) -> list[tuple[ChunkContentBlock, int, int, str | None]]:
        headers = [str(value) for value in block.metadata.get("headers", [])]
        rows = [
            [str(value) for value in row]
            for row in block.metadata.get("rows", [])
        ]
        caption = block.metadata.get("caption")
        prefix_parts = []
        if caption:
            prefix_parts.append(str(caption))
        if headers:
            prefix_parts.append("\t".join(headers))
        prefix = "\n".join(prefix_parts)
        groups: list[ChunkContentBlock] = []
        current_rows: list[tuple[int, list[str]]] = []

        def render(values: list[tuple[int, list[str]]]) -> str:
            body = "\n".join("\t".join(row) for _, row in values)
            return "\n".join(item for item in (prefix, body) if item)

        def emit() -> None:
            nonlocal current_rows
            if not current_rows:
                return
            rendered = render(current_rows)
            start_row = current_rows[0][0]
            end_row = current_rows[-1][0]
            provenance = block.provenance.model_copy(
                update={
                    "table_row_start": start_row,
                    "table_row_end": end_row,
                    "source_text_start": 0,
                    "source_text_end": len(rendered),
                }
            )
            groups.append(
                block.model_copy(
                    update={
                        "text": rendered,
                        "metadata": {
                            **block.metadata,
                            "rows": [row for _, row in current_rows],
                        },
                        "provenance": provenance,
                    }
                )
            )
            current_rows = []

        for row_index, row in enumerate(rows):
            proposed = [*current_rows, (row_index, row)]
            if current_rows and len(render(proposed)) > maximum:
                emit()
            current_rows.append((row_index, row))
            if len(render(current_rows)) > maximum:
                oversized = current_rows.pop()
                emit()
                raw = render([oversized])
                for start, end in safe_split_points(raw, maximum):
                    split = block.model_copy(
                        update={
                            "text": raw[start:end],
                            "provenance": block.provenance.model_copy(
                                update={
                                    "table_row_start": row_index,
                                    "table_row_end": row_index,
                                    "source_text_start": start,
                                    "source_text_end": end,
                                }
                            ),
                        }
                    )
                    groups.append(split)
        emit()
        if not groups:
            return [(block, 0, len(block.text), None)]
        return [
            (
                group,
                0,
                len(group.text),
                "TABLE_CONTINUATION" if index else None,
            )
            for index, group in enumerate(groups)
        ]


__all__ = ["StructuralChunkingStrategy"]

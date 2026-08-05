from __future__ import annotations

from copy import deepcopy
import re
from typing import Iterable

from ..models.canonical_document import CanonicalDocument, Section
from ..models.enums import ChunkContentType
from .models import (
    ChunkCandidate,
    ChunkConfiguration,
    ChunkContentBlock,
    ChunkProvenance,
)


def _content_type(block_type: str) -> ChunkContentType:
    normalized = block_type.casefold()
    if "list" in normalized:
        return ChunkContentType.LIST
    if "blockquote" in normalized or normalized == "quote":
        return ChunkContentType.BLOCKQUOTE
    if "code" in normalized or normalized == "fence":
        return ChunkContentType.CODE
    if normalized == "table":
        return ChunkContentType.TABLE
    if normalized in {"heading", "section"}:
        return ChunkContentType.SECTION
    if normalized == "paragraph":
        return ChunkContentType.PARAGRAPH
    return ChunkContentType.TEXT


def canonical_blocks(
    document: CanonicalDocument,
    configuration: ChunkConfiguration,
) -> list[ChunkContentBlock]:
    """Project a canonical document into source-ordered faithful blocks."""

    pending: list[tuple[int, int, ChunkContentBlock]] = []
    sequence = 0
    section_index = 0
    paragraph_fallback = 0

    def add(
        block: ChunkContentBlock,
        raw_order: int | None,
        *,
        first: bool = False,
    ) -> None:
        nonlocal sequence
        if first:
            order = -1
        elif raw_order is None:
            order = 1_000_000_000 + sequence
        else:
            order = raw_order
        pending.append((order, sequence, block))
        sequence += 1

    if configuration.include_document_title and document.metadata.title:
        add(
            ChunkContentBlock(
                block_type="document_title",
                text=document.metadata.title,
                heading_context=[document.metadata.title],
                content_type=ChunkContentType.SECTION,
                provenance=ChunkProvenance(
                    source_order=0,
                    canonical_block_type="document_title",
                    source_text_end=len(document.metadata.title),
                ),
            ),
            None,
            first=True,
        )

    def visit(section: Section, inherited: list[str]) -> None:
        nonlocal section_index, paragraph_fallback
        current_index = section_index
        section_index += 1
        path = [*inherited]
        if section.title:
            path.append(section.title)
        section_source = section.provenance
        if configuration.include_headings and section.title:
            add(
                ChunkContentBlock(
                    block_type="heading",
                    block_index=current_index,
                    text=section.title,
                    heading_context=path,
                    content_type=ChunkContentType.SECTION,
                    provenance=ChunkProvenance(
                        source_order=0,
                        canonical_block_type="section",
                        canonical_block_index=current_index,
                        source_index=(
                            section_source.source_index
                            if section_source
                            else None
                        ),
                        page_number=(
                            section_source.page_number
                            if section_source
                            else section.page_start
                        ),
                        section_path=(
                            list(section_source.section_path)
                            if section_source
                            else path
                        ),
                        character_start=(
                            section_source.character_start
                            if section_source
                            else None
                        ),
                        character_end=(
                            section_source.character_end
                            if section_source
                            else None
                        ),
                        source_locator=(
                            section_source.source_locator
                            if section_source
                            else None
                        ),
                        source_text_end=len(section.title),
                    ),
                ),
                section_source.source_index if section_source else section.order,
            )
        for paragraph in section.paragraphs:
            provenance = paragraph.provenance
            block_type = str(
                paragraph.metadata.get("block_type", "paragraph")
            )
            paragraph_index = (
                provenance.paragraph_index
                if provenance and provenance.paragraph_index is not None
                else paragraph_fallback
            )
            paragraph_fallback += 1
            add(
                ChunkContentBlock(
                    block_type=block_type,
                    block_index=paragraph_index,
                    text=paragraph.text,
                    heading_context=path,
                    content_type=_content_type(block_type),
                    metadata=deepcopy(paragraph.metadata),
                    provenance=ChunkProvenance(
                        source_order=0,
                        canonical_block_type="paragraph",
                        canonical_block_index=paragraph_index,
                        source_index=(
                            provenance.source_index if provenance else None
                        ),
                        page_number=(
                            provenance.page_number
                            if provenance
                            else paragraph.page_number
                        ),
                        section_path=(
                            list(provenance.section_path)
                            if provenance
                            else path
                        ),
                        paragraph_index=paragraph_index,
                        character_start=(
                            provenance.character_start
                            if provenance
                            else None
                        ),
                        character_end=(
                            provenance.character_end
                            if provenance
                            else None
                        ),
                        source_locator=(
                            provenance.source_locator if provenance else None
                        ),
                        source_text_end=len(paragraph.text),
                    ),
                ),
                provenance.source_index if provenance else paragraph.order,
            )
        for subsection in section.subsections:
            visit(subsection, path)

    for root in document.sections:
        visit(root, [])

    for table_index, table in enumerate(document.tables):
        provenance = table.provenance
        rows = [table.headers, *table.rows] if table.headers else table.rows
        rendered = "\n".join("\t".join(row) for row in rows)
        if table.caption:
            rendered = (
                f"{table.caption}\n{rendered}" if rendered else table.caption
            )
        if not rendered:
            continue
        add(
            ChunkContentBlock(
                block_type="table",
                block_index=table_index,
                text=rendered,
                heading_context=(
                    list(provenance.section_path) if provenance else []
                ),
                content_type=ChunkContentType.TABLE,
                metadata={
                    "headers": list(table.headers),
                    "rows": deepcopy(table.rows),
                    "caption": table.caption,
                },
                provenance=ChunkProvenance(
                    source_order=0,
                    canonical_block_type="table",
                    canonical_block_index=table_index,
                    source_index=provenance.source_index if provenance else None,
                    page_number=(
                        provenance.page_number
                        if provenance
                        else table.page_number
                    ),
                    section_path=(
                        list(provenance.section_path) if provenance else []
                    ),
                    table_index=table_index,
                    table_row_start=0,
                    table_row_end=max(0, len(table.rows) - 1),
                    character_start=(
                        provenance.character_start if provenance else None
                    ),
                    character_end=(
                        provenance.character_end if provenance else None
                    ),
                    source_locator=(
                        provenance.source_locator if provenance else None
                    ),
                    source_text_end=len(rendered),
                ),
            ),
            provenance.source_index if provenance else None,
        )

    ordered = [item[2] for item in sorted(pending, key=lambda item: item[:2])]
    for source_order, block in enumerate(ordered):
        object.__setattr__(block.provenance, "source_order", source_order)
    return ordered


def safe_split_points(text: str, maximum: int) -> Iterable[tuple[int, int]]:
    """Yield deterministic non-empty slices no longer than maximum."""

    start = 0
    while start < len(text):
        hard_end = min(len(text), start + maximum)
        end = hard_end
        if hard_end < len(text):
            window = text[start:hard_end]
            candidates = [
                match.end()
                for pattern in (r"\n\n+", r"(?<=[.!?])\s+", r"\s+")
                for match in re.finditer(pattern, window)
                if match.end() > max(1, maximum // 3)
            ]
            if candidates:
                end = start + max(candidates)
        if end <= start:
            end = hard_end
        yield start, end
        start = end


def candidate_from_pieces(
    ordinal: int,
    pieces: list[tuple[ChunkContentBlock, int, int, bool]],
    *,
    overlap_metadata: dict | None = None,
    relationship_hints: list[dict] | None = None,
) -> ChunkCandidate:
    texts: list[str] = []
    spans: list[ChunkProvenance] = []
    source_blocks: list[ChunkContentBlock] = []
    chunk_offset = 0
    for block, source_start, source_end, is_overlap in pieces:
        value = block.text[source_start:source_end]
        if not value:
            continue
        if texts:
            texts.append("\n\n")
            chunk_offset += 2
        text_start = chunk_offset
        texts.append(value)
        chunk_offset += len(value)
        original = block.provenance
        character_start = original.character_start
        character_end = original.character_end
        if (
            character_start is not None
            and character_end is not None
            and character_end - character_start == len(block.text)
        ):
            character_end = character_start + source_end
            character_start += source_start
        span = original.model_copy(
            update={
                "text_start_in_chunk": text_start,
                "text_end_in_chunk": chunk_offset,
                "source_text_start": source_start,
                "source_text_end": source_end,
                "character_start": character_start,
                "character_end": character_end,
                "is_overlap": is_overlap,
            }
        )
        spans.append(span)
        source_blocks.append(
            block.model_copy(
                update={
                    "text": value,
                    "provenance": span,
                }
            )
        )
    content_types = {block.content_type for block in source_blocks}
    content_type = (
        next(iter(content_types))
        if len(content_types) == 1
        else ChunkContentType.MIXED
    )
    heading_context = next(
        (
            block.heading_context
            for block in reversed(source_blocks)
            if block.heading_context
        ),
        [],
    )
    return ChunkCandidate(
        ordinal=ordinal,
        text="".join(texts),
        content_type=content_type,
        heading_context=heading_context,
        source_blocks=source_blocks,
        provenance=spans,
        overlap_metadata=overlap_metadata,
        relationship_hints=relationship_hints or [],
    )


__all__ = [
    "candidate_from_pieces",
    "canonical_blocks",
    "safe_split_points",
]

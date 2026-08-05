from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from ..models.canonical_document import (
    CanonicalDocument,
    DocumentMetadata,
    ImageReference,
    Paragraph,
    Reference,
    Section,
    SourceProvenance,
    Table,
)
from .base import AbstractParser, InvalidParserInputError, normalize_mime_type


class MarkdownParser(AbstractParser):
    """CommonMark parser with deterministic structural projection."""

    extensions = frozenset({".md", ".markdown"})
    mime_types = frozenset(
        {"text/markdown", "text/plain", "text/x-markdown"}
    )

    def __init__(self) -> None:
        self._engine = MarkdownIt(
            "commonmark",
            {
                "html": False,
                "linkify": False,
                "typographer": False,
            },
        ).enable("table")

    def parser_name(self) -> str:
        return "markdown"

    def parser_version(self) -> str:
        return "2.0.0"

    def validate(self, content: bytes) -> bool:
        text = self._decode(content)
        if not text.strip():
            raise InvalidParserInputError(
                "Markdown document must contain non-whitespace text"
            )
        try:
            self._engine.parse(self._split_front_matter(text)[1], {})
        except (TypeError, ValueError, RuntimeError) as exc:
            raise InvalidParserInputError(
                "Markdown document is malformed or unreadable"
            ) from exc
        return True

    def extract_metadata(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> DocumentMetadata:
        self.validate(content)
        text = self._decode(content)
        front_matter, body, raw_front_matter, line_offset = (
            self._split_front_matter(text)
        )
        tokens = self._engine.parse(body, {})
        heading_title = self._first_heading(tokens)
        title_value = front_matter.get("title")
        title = (
            str(title_value).strip()
            if title_value is not None and str(title_value).strip()
            else heading_title
        )
        if title is None and filename:
            title = self._filename_title(filename)
        author_value = front_matter.get("author")
        author = (
            str(author_value).strip()
            if author_value is not None and str(author_value).strip()
            else None
        )
        language_value = front_matter.get("language") or front_matter.get("lang")
        language = (
            str(language_value).strip()
            if language_value is not None
            else None
        )
        return DocumentMetadata(
            title=title,
            author=author,
            authors=[author] if author else [],
            subject=self._front_matter_text(front_matter, "subject"),
            keywords=self._front_matter_list(front_matter.get("keywords")),
            created_at=self._front_matter_text(front_matter, "created"),
            modified_at=self._front_matter_text(front_matter, "modified"),
            language=language,
            source_filename=Path(filename).name if filename else None,
            extension=(
                Path(filename).suffix.lower()
                if filename
                and Path(filename).suffix.lower() in self.extensions
                else ".md"
            ),
            mime_type=normalize_mime_type(mime_type) or "text/markdown",
            page_count=1,
            properties={
                "front_matter": front_matter,
                "front_matter_raw": raw_front_matter,
                "front_matter_line_count": line_offset,
            },
        )

    def parse(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> CanonicalDocument:
        self.validate(content)
        text = self._decode(content)
        _, body, _, line_offset = self._split_front_matter(text)
        metadata = self.extract_metadata(
            content,
            filename=filename,
            mime_type=mime_type,
        )
        environment: dict[str, Any] = {}
        tokens = self._engine.parse(body, environment)
        sections: list[Section] = []
        section_stack: list[Section] = []
        tables: list[Table] = []
        images: list[ImageReference] = []
        references: list[Reference] = []
        content_blocks: list[str] = []
        list_stack: list[dict[str, Any]] = []
        blockquote_depth = 0
        paragraph_index = 0
        table_index = 0
        source_index = 0

        def section_path() -> list[str]:
            return [
                section.title
                for section in section_stack
                if section.title is not None
            ]

        def add_section(title: str, level: int, token: Token) -> None:
            nonlocal section_stack
            while section_stack and section_stack[-1].level >= level:
                section_stack.pop()
            line = self._line_number(token, line_offset)
            path = section_path() + [title]
            section = Section(
                title=title,
                level=level,
                order=source_index,
                page_start=1,
                page_end=1,
                provenance=SourceProvenance(
                    source_index=source_index,
                    page_number=1,
                    section_path=path,
                    source_locator=f"line:{line}" if line else None,
                ),
            )
            if section_stack:
                section_stack[-1].subsections.append(section)
            else:
                sections.append(section)
            section_stack.append(section)

        def ensure_section() -> Section:
            if not section_stack:
                title = metadata.title or "Document"
                section = Section(
                    title=title,
                    level=1,
                    order=0,
                    page_start=1,
                    page_end=1,
                    provenance=SourceProvenance(
                        source_index=0,
                        page_number=1,
                        section_path=[title],
                        source_locator="line:1",
                    ),
                )
                sections.append(section)
                section_stack.append(section)
            return section_stack[-1]

        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token.type == "heading_open":
                inline = self._next_inline(tokens, index)
                heading = (
                    self._inline_text(inline.children or [])
                    if inline is not None
                    else ""
                ).strip()
                if heading:
                    level = int(token.tag[1:])
                    add_section(heading, level, token)
                    content_blocks.append(heading)
                    source_index += 1
            elif token.type in {"bullet_list_open", "ordered_list_open"}:
                list_stack.append(
                    {
                        "list_type": (
                            "ordered"
                            if token.type == "ordered_list_open"
                            else "unordered"
                        ),
                        "list_level": len(list_stack),
                        "list_start": int(token.attrGet("start") or 1),
                    }
                )
            elif token.type in {"bullet_list_close", "ordered_list_close"}:
                if list_stack:
                    list_stack.pop()
            elif token.type == "blockquote_open":
                blockquote_depth += 1
            elif token.type == "blockquote_close":
                blockquote_depth = max(0, blockquote_depth - 1)
            elif token.type == "paragraph_open":
                inline = self._next_inline(tokens, index)
                if inline is not None:
                    visible_text = self._inline_text(
                        inline.children or []
                    ).strip()
                    if visible_text:
                        current = ensure_section()
                        path = section_path()
                        line = self._line_number(token, line_offset)
                        start = self._character_start(content_blocks)
                        inline_metadata, new_images, new_references = (
                            self._inline_metadata(
                                inline.children or [],
                                source_index=source_index,
                                paragraph_index=paragraph_index,
                                section_path=path,
                                line=line,
                            )
                        )
                        block_type = "paragraph"
                        if list_stack:
                            block_type = "list_item"
                        elif blockquote_depth:
                            block_type = "blockquote"
                        current.paragraphs.append(
                            Paragraph(
                                text=visible_text,
                                order=paragraph_index,
                                page_number=1,
                                provenance=SourceProvenance(
                                    source_index=source_index,
                                    page_number=1,
                                    section_path=path,
                                    paragraph_index=paragraph_index,
                                    character_start=start,
                                    character_end=(
                                        start + len(visible_text)
                                    ),
                                    source_locator=(
                                        f"line:{line}" if line else None
                                    ),
                                ),
                                metadata={
                                    "block_type": block_type,
                                    "blockquote_depth": blockquote_depth,
                                    **(list_stack[-1] if list_stack else {}),
                                    **inline_metadata,
                                },
                            )
                        )
                        images.extend(new_images)
                        references.extend(new_references)
                        content_blocks.append(visible_text)
                        paragraph_index += 1
                        source_index += 1
            elif token.type in {"fence", "code_block"}:
                code = token.content.rstrip("\n")
                if code.strip():
                    current = ensure_section()
                    path = section_path()
                    line = self._line_number(token, line_offset)
                    start = self._character_start(content_blocks)
                    language = (
                        token.info.strip().split()[0]
                        if token.info.strip()
                        else None
                    )
                    current.paragraphs.append(
                        Paragraph(
                            text=code,
                            order=paragraph_index,
                            page_number=1,
                            provenance=SourceProvenance(
                                source_index=source_index,
                                page_number=1,
                                section_path=path,
                                paragraph_index=paragraph_index,
                                character_start=start,
                                character_end=start + len(code),
                                source_locator=(
                                    f"line:{line}" if line else None
                                ),
                            ),
                            metadata={
                                "block_type": (
                                    "fenced_code"
                                    if token.type == "fence"
                                    else "code_block"
                                ),
                                "language": language,
                                "markup": token.markup or None,
                                "executed": False,
                            },
                        )
                    )
                    content_blocks.append(code)
                    paragraph_index += 1
                    source_index += 1
            elif token.type == "hr":
                current = ensure_section()
                path = section_path()
                line = self._line_number(token, line_offset)
                current.paragraphs.append(
                    Paragraph(
                        text="[HORIZONTAL_RULE]",
                        order=paragraph_index,
                        page_number=1,
                        provenance=SourceProvenance(
                            source_index=source_index,
                            page_number=1,
                            section_path=path,
                            paragraph_index=paragraph_index,
                            source_locator=(
                                f"line:{line}" if line else None
                            ),
                        ),
                        metadata={
                            "block_type": "horizontal_rule",
                            "markup": token.markup,
                        },
                    )
                )
                content_blocks.append("[HORIZONTAL_RULE]")
                paragraph_index += 1
                source_index += 1
            elif token.type == "table_open":
                end_index, table = self._table_from_tokens(
                    tokens,
                    index,
                    source_index=source_index,
                    table_index=table_index,
                    section_path=section_path(),
                    line_offset=line_offset,
                )
                if table is not None:
                    tables.append(table)
                    rendered_rows = [table.headers, *table.rows]
                    flattened = "\n".join(
                        "\t".join(row) for row in rendered_rows
                    ).strip()
                    if flattened:
                        content_blocks.append(flattened)
                    table_index += 1
                    source_index += 1
                index = end_index
            index += 1

        references.extend(
            self._reference_definitions(
                body,
                source_index_start=source_index,
                line_offset=line_offset,
            )
        )
        if not any(True for section in sections for _ in section.iter_paragraphs()):
            flattened = "\n\n".join(content_blocks).strip()
            if not flattened:
                raise InvalidParserInputError(
                    "Markdown document contains no extractable text"
                )
            root = ensure_section()
            root.paragraphs.append(
                Paragraph(
                    text=flattened,
                    order=0,
                    page_number=1,
                    provenance=SourceProvenance(
                        source_index=0,
                        page_number=1,
                        section_path=[root.title] if root.title else [],
                        paragraph_index=0,
                        character_start=0,
                        character_end=len(flattened),
                        source_locator="line:1",
                    ),
                    metadata={"block_type": "structural_fallback"},
                )
            )
        return CanonicalDocument.build(
            parser_name=self.parser_name(),
            parser_version=self.parser_version(),
            metadata=metadata,
            content="\n\n".join(content_blocks),
            sections=sections,
            tables=tables,
            images=images,
            references=references,
        )

    @staticmethod
    def _decode(content: bytes) -> str:
        if not content:
            raise InvalidParserInputError("Markdown document cannot be empty")
        try:
            return content.decode("utf-8-sig").replace(
                "\r\n",
                "\n",
            ).replace("\r", "\n")
        except UnicodeDecodeError as exc:
            raise InvalidParserInputError(
                "Markdown document must contain valid UTF-8 text"
            ) from exc

    @staticmethod
    def _split_front_matter(
        text: str,
    ) -> tuple[dict[str, Any], str, str | None, int]:
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return {}, text, None, 0
        closing = next(
            (
                index
                for index in range(1, len(lines))
                if lines[index].strip() in {"---", "..."}
            ),
            None,
        )
        if closing is None:
            return {}, text, None, 0
        raw_lines = lines[1:closing]
        values: dict[str, Any] = {}
        for line in raw_lines:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, separator, value = line.partition(":")
            normalized_key = key.strip()
            if not separator or not normalized_key:
                continue
            normalized_value = value.strip().strip("\"'")
            if (
                normalized_value.startswith("[")
                and normalized_value.endswith("]")
            ):
                values[normalized_key] = [
                    item.strip().strip("\"'")
                    for item in normalized_value[1:-1].split(",")
                    if item.strip()
                ]
            else:
                values[normalized_key] = normalized_value
        body = "\n".join(lines[closing + 1 :])
        return values, body, "\n".join(raw_lines), closing + 1

    @staticmethod
    def _first_heading(tokens: list[Token]) -> str | None:
        for index, token in enumerate(tokens):
            if token.type != "heading_open":
                continue
            inline = MarkdownParser._next_inline(tokens, index)
            if inline is not None:
                title = MarkdownParser._inline_text(
                    inline.children or []
                ).strip()
                if title:
                    return title
        return None

    @staticmethod
    def _next_inline(tokens: list[Token], index: int) -> Token | None:
        if index + 1 < len(tokens) and tokens[index + 1].type == "inline":
            return tokens[index + 1]
        return None

    @staticmethod
    def _inline_text(children: list[Token]) -> str:
        parts: list[str] = []
        for child in children:
            if child.type in {"text", "code_inline"}:
                parts.append(child.content)
            elif child.type in {"softbreak", "hardbreak"}:
                parts.append("\n")
            elif child.type == "image":
                parts.append(child.content)
            elif child.type == "html_inline":
                parts.append(child.content)
        return re.sub(r"[ \t]+", " ", "".join(parts)).strip()

    @staticmethod
    def _inline_metadata(
        children: list[Token],
        *,
        source_index: int,
        paragraph_index: int,
        section_path: list[str],
        line: int | None,
    ) -> tuple[dict[str, Any], list[ImageReference], list[Reference]]:
        inline_code: list[dict[str, Any]] = []
        images: list[ImageReference] = []
        references: list[Reference] = []
        link_stack: list[tuple[str | None, str | None, list[str]]] = []
        for child_index, child in enumerate(children):
            if child.type == "code_inline":
                inline_code.append(
                    {
                        "text": child.content,
                        "markup": child.markup,
                        "executed": False,
                    }
                )
            elif child.type == "link_open":
                link_stack.append(
                    (
                        child.attrGet("href"),
                        child.attrGet("title"),
                        [],
                    )
                )
            elif child.type == "link_close" and link_stack:
                target, title, text_parts = link_stack.pop()
                link_text = "".join(text_parts).strip() or target or "link"
                references.append(
                    Reference(
                        text=link_text,
                        target=target,
                        reference_type="link",
                        page_number=1,
                        provenance=SourceProvenance(
                            source_index=source_index,
                            page_number=1,
                            section_path=section_path,
                            paragraph_index=paragraph_index,
                            source_locator=(
                                f"line:{line}/inline:{child_index}"
                                if line
                                else f"inline:{child_index}"
                            ),
                        ),
                        metadata={"title": title},
                    )
                )
            elif child.type == "image":
                source = child.attrGet("src")
                images.append(
                    ImageReference(
                        identifier=source or f"image-{source_index}-{child_index}",
                        source=source,
                        alt_text=child.content or None,
                        page_number=1,
                        provenance=SourceProvenance(
                            source_index=source_index,
                            page_number=1,
                            section_path=section_path,
                            paragraph_index=paragraph_index,
                            source_locator=(
                                f"line:{line}/image:{child_index}"
                                if line
                                else f"image:{child_index}"
                            ),
                        ),
                        metadata={
                            "title": child.attrGet("title"),
                            "loaded": False,
                            "ocr_performed": False,
                        },
                    )
                )
            if link_stack and child.type in {
                "text",
                "code_inline",
                "image",
            }:
                link_stack[-1][2].append(child.content)
        return {"inline_code": inline_code}, images, references

    @staticmethod
    def _table_from_tokens(
        tokens: list[Token],
        start_index: int,
        *,
        source_index: int,
        table_index: int,
        section_path: list[str],
        line_offset: int,
    ) -> tuple[int, Table | None]:
        rows: list[list[str]] = []
        row: list[str] | None = None
        index = start_index + 1
        while index < len(tokens):
            token = tokens[index]
            if token.type == "table_close":
                break
            if token.type == "tr_open":
                row = []
            elif token.type == "tr_close" and row is not None:
                rows.append(row)
                row = None
            elif token.type == "inline" and row is not None:
                row.append(
                    MarkdownParser._inline_text(token.children or [])
                )
            index += 1
        if not rows:
            return index, None
        start_token = tokens[start_index]
        line = MarkdownParser._line_number(start_token, line_offset)
        alignments: list[str | None] = []
        for token in tokens[start_index:index]:
            if token.type == "th_open":
                alignments.append(token.attrGet("style"))
        table = Table(
            headers=rows[0],
            rows=rows[1:],
            page_number=1,
            provenance=SourceProvenance(
                source_index=source_index,
                page_number=1,
                section_path=section_path,
                table_index=table_index,
                source_locator=f"line:{line}" if line else None,
            ),
            metadata={
                "row_count": len(rows),
                "column_count": max(len(item) for item in rows),
                "alignments": alignments,
            },
        )
        return index, table

    @staticmethod
    def _reference_definitions(
        body: str,
        *,
        source_index_start: int,
        line_offset: int,
    ) -> list[Reference]:
        pattern = re.compile(
            r"^[ \t]{0,3}\[([^\]]+)\]:[ \t]*"
            r"(?:<([^>]+)>|(\S+))"
            r"(?:[ \t]+(?:\"([^\"]*)\"|'([^']*)'|\(([^)]*)\)))?"
            r"[ \t]*$",
            re.MULTILINE,
        )
        references: list[Reference] = []
        for offset, match in enumerate(pattern.finditer(body)):
            label = match.group(1).strip()
            target = (match.group(2) or match.group(3) or "").strip()
            title = match.group(4) or match.group(5) or match.group(6)
            line = body.count("\n", 0, match.start()) + 1 + line_offset
            references.append(
                Reference(
                    text=label,
                    target=target or None,
                    reference_type="reference_definition",
                    page_number=1,
                    provenance=SourceProvenance(
                        source_index=source_index_start + offset,
                        page_number=1,
                        source_locator=f"line:{line}",
                    ),
                    metadata={"title": title},
                )
            )
        return references

    @staticmethod
    def _line_number(token: Token, line_offset: int) -> int | None:
        return (
            token.map[0] + 1 + line_offset
            if token.map is not None
            else None
        )

    @staticmethod
    def _character_start(content_blocks: list[str]) -> int:
        return sum(len(block) for block in content_blocks) + 2 * len(
            content_blocks
        )

    @staticmethod
    def _filename_title(filename: str) -> str | None:
        title = Path(filename).stem.replace("_", " ").replace("-", " ")
        title = re.sub(r"\s+", " ", title).strip()
        return title or None

    @staticmethod
    def _front_matter_text(
        values: dict[str, Any],
        key: str,
    ) -> str | None:
        value = values.get(key)
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _front_matter_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value is None:
            return []
        return [
            item.strip()
            for item in re.split(r"[,;]", str(value))
            if item.strip()
        ]


__all__ = ["MarkdownParser"]

from __future__ import annotations

from pathlib import Path
import re

from ..models.canonical_document import (
    CanonicalDocument,
    DocumentMetadata,
    Paragraph,
    Section,
)
from .base import AbstractParser, InvalidParserInputError, normalize_mime_type


class TxtParser(AbstractParser):
    extensions = frozenset({".txt"})
    mime_types = frozenset({"text/plain"})

    def parser_name(self) -> str:
        return "txt"

    def parser_version(self) -> str:
        return "1.0.0"

    def validate(self, content: bytes) -> bool:
        if not content:
            raise InvalidParserInputError("TXT document cannot be empty")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidParserInputError(
                "TXT document must contain valid UTF-8 text"
            ) from exc
        if not text.strip():
            raise InvalidParserInputError(
                "TXT document must contain non-whitespace text"
            )
        return True

    def extract_metadata(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> DocumentMetadata:
        self.validate(content)
        text = content.decode("utf-8-sig")
        title = self._first_heading(text)
        if title is None and filename:
            stem = Path(filename).stem.replace("_", " ").replace("-", " ")
            title = re.sub(r"\s+", " ", stem).strip() or None
        return DocumentMetadata(
            title=title,
            source_filename=Path(filename).name if filename else None,
            extension=".txt",
            mime_type=normalize_mime_type(mime_type) or "text/plain",
            page_count=1,
            properties={"encoding": "utf-8"},
        )

    def parse(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> CanonicalDocument:
        self.validate(content)
        text = content.decode("utf-8-sig").replace("\r\n", "\n").replace(
            "\r", "\n"
        )
        metadata = self.extract_metadata(
            content,
            filename=filename,
            mime_type=mime_type,
        )
        sections = self._build_sections(text, metadata.title)
        return CanonicalDocument.build(
            parser_name=self.parser_name(),
            parser_version=self.parser_version(),
            metadata=metadata,
            content=text,
            sections=sections,
        )

    @classmethod
    def _first_heading(cls, text: str) -> str | None:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            heading = cls._heading_at(lines, index)
            return heading[0] if heading else None
        return None

    @classmethod
    def _heading_at(
        cls,
        lines: list[str],
        index: int,
    ) -> tuple[str, int, int] | None:
        stripped = lines[index].strip()
        if not stripped:
            return None
        markdown = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", stripped)
        if markdown:
            return markdown.group(2).strip(), len(markdown.group(1)), 1
        if (
            index + 1 < len(lines)
            and re.fullmatch(r"\s*(=+|-+)\s*", lines[index + 1])
            and len(lines[index + 1].strip()) >= 3
        ):
            level = 1 if lines[index + 1].strip().startswith("=") else 2
            return stripped, level, 2
        words = stripped.split()
        if (
            len(stripped) <= 120
            and 1 <= len(words) <= 12
            and any(character.isalpha() for character in stripped)
            and stripped.upper() == stripped
        ):
            return stripped, 1, 1
        return None

    @classmethod
    def _build_sections(
        cls,
        text: str,
        fallback_title: str | None,
    ) -> list[Section]:
        lines = text.splitlines()
        sections: list[Section] = []
        current_title = fallback_title
        current_level = 1
        paragraph_lines: list[str] = []
        paragraphs: list[Paragraph] = []

        def flush_paragraph() -> None:
            if not paragraph_lines:
                return
            paragraph_text = " ".join(
                line.strip() for line in paragraph_lines if line.strip()
            ).strip()
            paragraph_lines.clear()
            if paragraph_text:
                paragraphs.append(
                    Paragraph(text=paragraph_text, order=len(paragraphs))
                )

        def flush_section() -> None:
            nonlocal paragraphs
            flush_paragraph()
            if paragraphs:
                sections.append(
                    Section(
                        title=current_title,
                        level=current_level,
                        order=len(sections),
                        page_start=1,
                        page_end=1,
                        paragraphs=paragraphs,
                    )
                )
                paragraphs = []

        index = 0
        while index < len(lines):
            line = lines[index]
            heading = cls._heading_at(lines, index)
            if heading:
                flush_section()
                current_title, current_level, consumed = heading
                index += consumed
                continue
            if line.strip():
                paragraph_lines.append(line)
            else:
                flush_paragraph()
            index += 1
        flush_section()
        if not sections:
            raise InvalidParserInputError(
                "TXT document did not produce any paragraphs"
            )
        return sections


TXTParser = TxtParser


__all__ = ["TXTParser", "TxtParser"]

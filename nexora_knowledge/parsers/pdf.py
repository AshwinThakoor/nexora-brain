from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ..models.canonical_document import (
    CanonicalDocument,
    DocumentMetadata,
    Paragraph,
    Section,
)
from .base import AbstractParser, InvalidParserInputError, normalize_mime_type


class PdfParser(AbstractParser):
    extensions = frozenset({".pdf"})
    mime_types = frozenset({"application/pdf"})

    def parser_name(self) -> str:
        return "pdf"

    def parser_version(self) -> str:
        return "1.0.0"

    def validate(self, content: bytes) -> bool:
        if not content:
            raise InvalidParserInputError("PDF document cannot be empty")
        if not content.lstrip().startswith(b"%PDF-"):
            raise InvalidParserInputError(
                "PDF document does not have a valid PDF signature"
            )
        reader = self._reader(content)
        if len(reader.pages) < 1:
            raise InvalidParserInputError(
                "PDF document must contain at least one page"
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
        reader = self._reader(content)
        source = reader.metadata
        title = self._metadata_value(source, "/Title")
        if title is None and filename:
            title = Path(filename).stem.replace("_", " ").replace("-", " ")
        author = self._metadata_value(source, "/Author")
        keywords = self._metadata_value(source, "/Keywords")
        return DocumentMetadata(
            title=title,
            author=author,
            authors=[author] if author else [],
            subject=self._metadata_value(source, "/Subject"),
            keywords=[
                item.strip()
                for item in re.split(r"[,;]", keywords or "")
                if item.strip()
            ],
            creator=self._metadata_value(source, "/Creator"),
            producer=self._metadata_value(source, "/Producer"),
            created_at=self._metadata_value(source, "/CreationDate"),
            modified_at=self._metadata_value(source, "/ModDate"),
            source_filename=Path(filename).name if filename else None,
            extension=".pdf",
            mime_type=normalize_mime_type(mime_type) or "application/pdf",
            page_count=len(reader.pages),
            properties={"encrypted": bool(reader.is_encrypted)},
        )

    def parse(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> CanonicalDocument:
        self.validate(content)
        reader = self._reader(content)
        metadata = self.extract_metadata(
            content,
            filename=filename,
            mime_type=mime_type,
        )
        page_texts = [
            (page.extract_text() or "").strip()
            for page in reader.pages
        ]
        full_text = "\n\n".join(
            page_text for page_text in page_texts if page_text
        )
        if not full_text:
            raise InvalidParserInputError(
                "PDF contains no extractable text; OCR is not supported"
            )
        sections = self._build_sections(page_texts)
        return CanonicalDocument.build(
            parser_name=self.parser_name(),
            parser_version=self.parser_version(),
            metadata=metadata,
            content=full_text,
            sections=sections,
        )

    @staticmethod
    def _reader(content: bytes) -> PdfReader:
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if reader.is_encrypted and reader.decrypt("") == 0:
                raise InvalidParserInputError(
                    "Encrypted PDF requires a password and cannot be parsed"
                )
            return reader
        except InvalidParserInputError:
            raise
        except (PdfReadError, ValueError, TypeError, OSError) as exc:
            raise InvalidParserInputError(
                "PDF document is malformed or unreadable"
            ) from exc

    @staticmethod
    def _metadata_value(metadata: Any, key: str) -> str | None:
        if metadata is None:
            return None
        value = metadata.get(key)
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _looks_like_heading(line: str) -> tuple[str, int] | None:
        stripped = re.sub(r"\s+", " ", line).strip()
        if (
            not stripped
            or len(stripped) > 120
            or stripped.endswith((".", ";", ","))
        ):
            return None
        numbered = re.match(r"^(\d+(?:\.\d+)*)[.)]?\s+(.+)$", stripped)
        if numbered:
            level = min(numbered.group(1).count(".") + 1, 6)
            return stripped, level
        words = stripped.split()
        if (
            len(words) <= 12
            and any(character.isalpha() for character in stripped)
            and stripped.upper() == stripped
        ):
            return stripped, 1
        if (
            1 <= len(words) <= 8
            and all(
                not word[0].isalpha() or word[0].isupper()
                for word in words
            )
        ):
            return stripped, 2
        return None

    @classmethod
    def _build_sections(cls, page_texts: list[str]) -> list[Section]:
        sections: list[Section] = []
        for page_number, page_text in enumerate(page_texts, start=1):
            if not page_text:
                continue
            current_title = f"Page {page_number}"
            current_level = 1
            paragraphs: list[Paragraph] = []
            paragraph_lines: list[str] = []

            def flush_paragraph() -> None:
                if not paragraph_lines:
                    return
                paragraph_text = " ".join(paragraph_lines).strip()
                paragraph_lines.clear()
                if paragraph_text:
                    paragraphs.append(
                        Paragraph(
                            text=paragraph_text,
                            order=len(paragraphs),
                            page_number=page_number,
                        )
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
                            page_start=page_number,
                            page_end=page_number,
                            paragraphs=paragraphs,
                        )
                    )
                    paragraphs = []

            for raw_line in page_text.splitlines():
                line = re.sub(r"\s+", " ", raw_line).strip()
                if not line:
                    flush_paragraph()
                    continue
                heading = cls._looks_like_heading(line)
                if heading:
                    flush_section()
                    current_title, current_level = heading
                    continue
                paragraph_lines.append(line)
            flush_section()
        if not sections:
            raise InvalidParserInputError(
                "PDF text did not produce any paragraphs"
            )
        return sections


PDFParser = PdfParser


__all__ = ["PDFParser", "PdfParser"]

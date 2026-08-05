from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..models.canonical_document import (
    CanonicalDocument,
    DocumentMetadata,
)


def normalize_extension(extension: str | None) -> str | None:
    if extension is None:
        return None
    normalized = extension.strip().lower()
    if not normalized:
        return None
    if "/" in normalized or "\\" in normalized:
        normalized = Path(normalized).suffix.lower()
    if normalized and not normalized.startswith("."):
        normalized = f".{normalized}"
    return normalized or None


def normalize_mime_type(mime_type: str | None) -> str | None:
    if mime_type is None:
        return None
    normalized = mime_type.split(";", 1)[0].strip().lower()
    if normalized == "application/octet-stream":
        return None
    return normalized or None


class ParserError(ValueError):
    """Base error for parser selection, validation, and extraction failures."""


class UnsupportedDocumentFormatError(ParserError):
    """Raised when no registered parser matches the supplied format."""


class ParserNotImplementedError(ParserError, NotImplementedError):
    """Raised by a registered format whose extraction adapter is pending."""


class InvalidParserInputError(ParserError):
    """Raised when a parser cannot safely interpret the supplied bytes."""


@dataclass(frozen=True, slots=True)
class ParserCapability:
    name: str
    version: str
    extensions: tuple[str, ...]
    mime_types: tuple[str, ...]
    implemented: bool


class AbstractParser(ABC):
    extensions: frozenset[str] = frozenset()
    mime_types: frozenset[str] = frozenset()
    implemented: bool = True

    def supports(
        self,
        extension: str | None = None,
        mime_type: str | None = None,
    ) -> bool:
        normalized_extension = normalize_extension(extension)
        normalized_mime = normalize_mime_type(mime_type)
        if normalized_extension is None and normalized_mime is None:
            return False
        if (
            normalized_extension is not None
            and normalized_extension not in self.extensions
        ):
            return False
        if (
            normalized_mime is not None
            and normalized_mime not in self.mime_types
        ):
            return False
        return True

    def capability(self) -> ParserCapability:
        return ParserCapability(
            name=self.parser_name(),
            version=self.parser_version(),
            extensions=tuple(sorted(self.extensions)),
            mime_types=tuple(sorted(self.mime_types)),
            implemented=self.implemented,
        )

    @abstractmethod
    def parse(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> CanonicalDocument:
        """Convert validated bytes to the canonical document model."""

    @abstractmethod
    def extract_metadata(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> DocumentMetadata:
        """Extract portable metadata without persisting parser state."""

    @abstractmethod
    def validate(self, content: bytes) -> bool:
        """Return true for valid input, otherwise raise a parser error."""

    @abstractmethod
    def parser_name(self) -> str:
        """Return the stable registry name for this parser."""

    @abstractmethod
    def parser_version(self) -> str:
        """Return the implementation version for audit output."""


__all__ = [
    "AbstractParser",
    "InvalidParserInputError",
    "ParserCapability",
    "ParserError",
    "ParserNotImplementedError",
    "UnsupportedDocumentFormatError",
    "normalize_extension",
    "normalize_mime_type",
]

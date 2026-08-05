from __future__ import annotations

from collections.abc import Iterable

from .base import (
    AbstractParser,
    ParserCapability,
    ParserError,
    UnsupportedDocumentFormatError,
    normalize_extension,
    normalize_mime_type,
)


class ParserRegistry:
    """Deterministic registry for parser discovery and selection."""

    def __init__(
        self,
        parsers: Iterable[AbstractParser] | None = None,
    ) -> None:
        self._parsers: dict[str, AbstractParser] = {}
        for parser in parsers or ():
            self.register_parser(parser)

    def register_parser(
        self,
        parser: AbstractParser | type[AbstractParser],
    ) -> AbstractParser:
        instance = parser() if isinstance(parser, type) else parser
        if not isinstance(instance, AbstractParser):
            raise TypeError("Registered parsers must implement AbstractParser")
        name = instance.parser_name().strip().lower()
        if not name:
            raise ParserError("Parser name cannot be empty")
        if name in self._parsers:
            raise ParserError(f"Parser '{name}' is already registered")
        self._parsers[name] = instance
        return instance

    def get_parser(
        self,
        extension: str | None = None,
        mime_type: str | None = None,
    ) -> AbstractParser:
        normalized_extension = normalize_extension(extension)
        normalized_mime = normalize_mime_type(mime_type)
        if normalized_extension is None and normalized_mime is None:
            raise UnsupportedDocumentFormatError(
                "A file extension or MIME type is required for parser selection"
            )
        matches = [
            parser
            for parser in self._parsers.values()
            if parser.supports(normalized_extension, normalized_mime)
        ]
        if not matches:
            description = (
                f"extension={normalized_extension or 'unspecified'}, "
                f"mime_type={normalized_mime or 'unspecified'}"
            )
            raise UnsupportedDocumentFormatError(
                f"No parser supports {description}"
            )
        return matches[0]

    def list_parsers(self) -> list[ParserCapability]:
        return sorted(
            (parser.capability() for parser in self._parsers.values()),
            key=lambda capability: capability.name,
        )

    def supports_extension(self, extension: str) -> bool:
        normalized = normalize_extension(extension)
        return normalized is not None and any(
            normalized in parser.extensions
            for parser in self._parsers.values()
        )

    def supports_mime(self, mime_type: str) -> bool:
        normalized = normalize_mime_type(mime_type)
        return normalized is not None and any(
            normalized in parser.mime_types
            for parser in self._parsers.values()
        )


__all__ = ["ParserRegistry"]

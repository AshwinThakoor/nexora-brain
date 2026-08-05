from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import BinaryIO

from pydantic import ValidationError

from ..config import Settings, get_settings
from ..models.canonical_document import CanonicalDocument
from ..parsers import default_registry
from ..parsers.base import (
    AbstractParser,
    InvalidParserInputError,
    ParserCapability,
    normalize_extension,
    normalize_mime_type,
)
from ..parsers.registry import ParserRegistry


DocumentSource = bytes | bytearray | memoryview | BinaryIO | str | Path


def select_parser(
    filename: str | None = None,
    *,
    extension: str | None = None,
    mime_type: str | None = None,
    registry: ParserRegistry | None = None,
) -> AbstractParser:
    selected_registry = registry or default_registry
    selected_extension = normalize_extension(extension)
    if selected_extension is None and filename:
        selected_extension = normalize_extension(Path(filename).suffix)
    selected_mime = normalize_mime_type(mime_type)
    if selected_mime is None and filename:
        guessed_mime, _ = mimetypes.guess_type(filename)
        selected_mime = normalize_mime_type(guessed_mime)
    return selected_registry.get_parser(
        extension=selected_extension,
        mime_type=selected_mime,
    )


def parse_document(
    source: DocumentSource,
    *,
    filename: str | None = None,
    extension: str | None = None,
    mime_type: str | None = None,
    registry: ParserRegistry | None = None,
    settings: Settings | None = None,
) -> CanonicalDocument:
    content, resolved_filename = _read_source(
        source,
        filename=filename,
        settings=settings,
    )
    parser = select_parser(
        resolved_filename,
        extension=extension,
        mime_type=mime_type,
        registry=registry,
    )
    parser.validate(content)
    document = parser.parse(
        content,
        filename=resolved_filename,
        mime_type=mime_type,
    )
    validate_document(document)
    return document


def validate_document(
    document_or_source: CanonicalDocument | DocumentSource,
    *,
    filename: str | None = None,
    extension: str | None = None,
    mime_type: str | None = None,
    registry: ParserRegistry | None = None,
    settings: Settings | None = None,
) -> bool:
    if isinstance(document_or_source, CanonicalDocument):
        try:
            validated = CanonicalDocument.model_validate(
                document_or_source.model_dump()
            )
            validated.assert_valid()
        except (ValidationError, ValueError) as exc:
            raise InvalidParserInputError(str(exc)) from exc
        return True

    content, resolved_filename = _read_source(
        document_or_source,
        filename=filename,
        settings=settings,
    )
    parser = select_parser(
        resolved_filename,
        extension=extension,
        mime_type=mime_type,
        registry=registry,
    )
    return parser.validate(content)


def get_supported_formats(
    registry: ParserRegistry | None = None,
) -> list[ParserCapability]:
    return (registry or default_registry).list_parsers()


def _read_source(
    source: DocumentSource,
    *,
    filename: str | None,
    settings: Settings | None,
) -> tuple[bytes, str | None]:
    configured = settings or get_settings()
    maximum_size = configured.max_upload_size
    resolved_filename = filename

    if isinstance(source, (str, Path)):
        path = Path(source)
        resolved_filename = resolved_filename or path.name
        try:
            size = path.stat().st_size
            if size > maximum_size:
                raise InvalidParserInputError(
                    f"Document exceeds maximum parser size of "
                    f"{maximum_size} bytes"
                )
            content = path.read_bytes()
        except InvalidParserInputError:
            raise
        except OSError as exc:
            raise InvalidParserInputError(
                f"Document could not be read: {path}"
            ) from exc
    elif isinstance(source, (bytes, bytearray, memoryview)):
        content = bytes(source)
    elif hasattr(source, "read"):
        value = source.read(maximum_size + 1)
        if not isinstance(value, bytes):
            raise InvalidParserInputError(
                "Parser input streams must return bytes"
            )
        content = value
    else:
        raise TypeError(
            "Parser source must be bytes, a binary stream, or a file path"
        )

    if len(content) > maximum_size:
        raise InvalidParserInputError(
            f"Document exceeds maximum parser size of {maximum_size} bytes"
        )
    if not content:
        raise InvalidParserInputError("Document cannot be empty")
    return content, resolved_filename


__all__ = [
    "DocumentSource",
    "get_supported_formats",
    "parse_document",
    "select_parser",
    "validate_document",
]

# Pack 3A Sprint 5 — Universal Parser Framework

## Scope

Sprint 1E introduces a format-neutral conversion layer for PDF, TXT, DOCX,
Markdown, and HTML documents. PDF and TXT extraction are active. The other
three formats are registered adapters with explicit capability metadata and a
typed unavailable-parser exception.

The framework is intentionally limited to deterministic document parsing. It
does not include OCR, embeddings, vector databases, semantic search,
language-model functionality, or AI reasoning.

## Architecture

The parser boundary has four layers:

1. `AbstractParser` defines format support, source validation, metadata
   extraction, canonical parsing, and stable parser identity.
2. `ParserRegistry` registers parser instances and selects one by extension,
   MIME type, or a coherent pair of both.
3. `parser_service` applies bounded input reading, parser selection, raw
   validation, extraction, and canonical consistency validation.
4. The admin API exposes discovery, validation, and parsing without persisting
   either source bytes or canonical output.

The default registry is created in code and is deterministic. Duplicate parser
names are rejected. MIME parameters such as `charset=utf-8` are normalized,
extensions are case-insensitive, and a generic `application/octet-stream` MIME
does not override a recognized filename extension.

## Canonical representation

`models/canonical_document.py` defines strict Pydantic models:

- `CanonicalDocument`
- `DocumentMetadata`
- `Section`
- `Paragraph`
- `Table`
- `ImageReference`
- `Reference`
- `DocumentStatistics`

The root document carries `schema_version`, `parser_name`, `parser_version`,
metadata, source text, structural collections, and calculated statistics.
Unknown fields are rejected. Paragraph and reference text must be non-empty,
page numbers and hierarchy levels are positive, and the service verifies that
statistics exactly match the canonical content.

This model is a transfer object, not an ORM entity. It can be serialized
directly by FastAPI while remaining independent of SQLite and MySQL.

## Implemented parsers

### TXT

The TXT parser:

- accepts `.txt` and `text/plain`;
- decodes strict UTF-8 and accepts an optional UTF-8 BOM;
- normalizes line endings;
- separates paragraphs on blank lines;
- recognizes `#` headings, setext-style underlined headings, and conservative
  uppercase headings;
- extracts filename, title, encoding, extension, MIME, and page-count
  metadata; and
- returns a validated `CanonicalDocument`.

Invalid UTF-8, empty input, whitespace-only input, or content that cannot
produce a paragraph fails closed.

### PDF

The PDF parser uses maintained `pypdf` APIs. It:

- accepts `.pdf` and `application/pdf`;
- verifies the PDF signature and readable page tree;
- extracts standard title, author, subject, keyword, creator, producer, and
  date metadata;
- records page count;
- extracts page text without rendering or OCR; and
- recognizes conservative uppercase, numbered, and short title-style
  headings.

Malformed files and password-protected PDFs fail validation. A PDF with no
extractable text reports that OCR is unsupported.

## Registered scaffold parsers

DOCX, Markdown, and HTML adapters declare their extensions, MIME types, names,
versions, and unavailable capability state. They perform non-empty source
validation and basic filename metadata extraction. Parsing raises
`ParserNotImplementedError` with the affected format, making unavailable
behavior observable through both services and the API.

## Service contract

`services/parser_service.py` exposes:

- `select_parser(filename, extension, mime_type, registry)`
- `parse_document(source, filename, extension, mime_type, registry, settings)`
- `validate_document(document_or_source, filename, extension, mime_type, ...)`
- `get_supported_formats(registry)`

`source` may be bytes, a binary stream, or a filesystem path. Input is bounded
by `NEXORA_MAX_UPLOAD_SIZE`. Path sizes are checked before reading, streams are
read with a one-byte overflow sentinel, and oversized content is rejected.

## API contract

All parser routes require an authenticated `admin` principal:

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/v1/parsers` | Registered capability list |
| POST | `/api/v1/parsers/validate` | Raw format validation result |
| POST | `/api/v1/parsers/parse` | Canonical document |

POST operations accept multipart uploads and always close the temporary upload
handle. Parser selection, malformed input, unknown formats, format/MIME
mismatches, and unavailable scaffold parsing return HTTP 422.

## Extension procedure

To activate or add a format:

1. Implement an `AbstractParser` subclass with unique name and version.
2. Declare all supported extension and MIME aliases.
3. Validate signatures or encoding before extraction.
4. Extract metadata into `DocumentMetadata`.
5. Map content to `Section`, `Paragraph`, and other canonical components.
6. Return `CanonicalDocument.build(...)`.
7. Register the implementation in `build_default_registry()`.
8. Test valid extraction, malformed input, registry discovery, service
   selection, API authorization, and canonical statistics.

## Database compatibility

No parser capabilities or canonical output are persisted in this sprint.
Adding database tables would couple deterministic parsing to a storage policy
that has not been requested. Consequently there is no `3a_s5_001` revision;
the current head remains `3a_s4_001`.

Compatibility tests verify that:

- Alembic still upgrades SQLite to `3a_s4_001`;
- Alembic autogeneration reports no pending schema operations;
- canonical classes do not register SQLAlchemy tables; and
- the unchanged SQLAlchemy metadata compiles for both SQLite and MySQL.

# Pack 3A Sprint 6 — Complete Parsing and Persistent Results

## Scope

Sprint 1F completes deterministic DOCX, Markdown, and HTML extraction and
connects the universal parser framework to `StoredFile`, `DocumentVersion`, and
`IngestionJob`. Parsing is synchronous. Canonical output, attempts, safe
failures, and structured metadata artifacts are durable and auditable.

This sprint does not implement OCR, image recognition, semantic table
interpretation, chunking, embeddings, vector storage, semantic search, LLM
calls, AI reasoning, background workers, malware scanning, or remote storage
providers.

## Parser implementations

### DOCX

`DocxParser` uses `python-docx` and validates the Office Open XML package before
opening it. It reads core title, author, subject, keywords, creation and
modification dates, language, and other portable properties. Body XML is
walked in source order so headings, paragraphs, list items, tables, page-break
markers, hyperlinks, and image relationships receive stable provenance.

List metadata distinguishes ordered and unordered numbering and records nesting
and numbering format when available. Embedded images are represented by
relationship, target, content type, description, and source coordinates only.
No image bytes are persisted and no OCR is attempted.

### Markdown

`MarkdownParser` uses `markdown-it-py` with HTML execution, linkification, and
typographic rewriting disabled. It supports simple deterministic front matter,
heading hierarchy, paragraphs, ordered and unordered lists, blockquotes,
fenced/code blocks, inline-code metadata, tables, links, image references,
horizontal rules, and reference definitions.

Code tokens are stored as content with `executed: false`. The parser never
imports, evaluates, runs, or shells out to source code.

### HTML

`HtmlParser` uses Beautiful Soup with the explicit `lxml` backend. It extracts
title, relevant meta tags, language, headings, paragraphs, lists, blockquotes,
preformatted and code content, tables, links, and image references.

`script`, `style`, `noscript`, `template`, `iframe`, `object`, and `embed` nodes
are removed. No URL or external resource is opened. Validation enforces a
10 MiB HTML-specific byte limit, 200,000-node limit, and nesting depth of 100.
The outer parser service and stored-file pipeline also enforce
`NEXORA_MAX_UPLOAD_SIZE`.

## Canonical schema

The runtime `CanonicalDocument` remains a strict Pydantic model and is not a
database table. Existing TXT and PDF documents remain compatible.

The optional `SourceProvenance` model is available on sections, paragraphs,
tables, image references, and references:

- `source_index`;
- nullable `page_number`;
- `section_path`;
- nullable `paragraph_index`;
- nullable `table_index`;
- nullable `character_start` and `character_end`; and
- nullable `source_locator`.

This captures source coordinates without creating chunks or assigning semantic
meaning.

## Persistence model

### ParseResult

`ParseResult` owns the durable canonical output and current status. Its
idempotency identity is:

```text
stored_file_id + input_sha256 + parser_name + parser_version
```

`input_sha256` must equal the linked `StoredFile.sha256`. The database unique
constraint makes identity resolution portable under SQLite and MySQL
concurrency. On an insert race, the service rolls back and reloads the winning
row.

Canonical JSON is serialized with sorted keys, compact separators, UTF-8,
non-ASCII preservation, and non-finite-number rejection. `content_hash` is
SHA-256 over the exact deterministic serialization.

Successful results are immutable at the ORM boundary. They may only transition
to `invalidated`; their parser identity, input identity, canonical data,
metadata, statistics, hash, and timestamps cannot be replaced. Current lookup
returns only successful, non-invalidated output.

### ParseExecution

Every execution receives a monotonically increasing attempt number within its
result. It records status, start and finish time, duration, parser identity,
processing-node name, and sanitized error code/message. Stack traces and raw
internal paths are not returned through parse APIs.

Normal repeated parsing reuses a successful result without another attempt.
Explicit reparse records another attempt against the immutable result. The
recomputed canonical serialization and hash must be identical; any difference
fails closed and preserves the original successful output.

### ParseArtifact

Artifacts store JSON or text only. Supported types are canonical manifest,
metadata, statistics, warning, and validation report. Each artifact receives a
SHA-256 checksum over deterministic JSON or exact text. Arbitrary binary blobs
and extracted images are not stored.

## Stored-file parser pipeline

`parser_pipeline_service.parse_stored_file` performs:

1. `StoredFile` and current `DocumentVersion` validation.
2. Ingestion eligibility validation through `document_service`.
3. Parser selection from both MIME type and extension.
4. Reserved/running job, active reservation, unexpired lease, and active-node
   validation.
5. Legal `RESERVED -> RUNNING` transition through `ingestion_service`.
6. Provider object existence and registered/current size validation.
7. Bounded streamed read with SHA-256 verification.
8. Idempotent `ParseResult` resolution and `ParseExecution` creation.
9. Parser extraction and canonical-model validation.
10. Deterministic persistence and artifact creation.
11. Legal `RUNNING -> SUCCEEDED` transition.

After a job starts, a read, integrity, parser, or persistence failure is
recorded safely and transitions the job through `RUNNING -> FAILED`. Existing
ingestion attempts, reservations, and append-only audit events are preserved.
Retry uses the existing ingestion retry/reservation services and creates a new
parse execution for a failed result.

No status is mutated outside the existing ingestion service.

## Storage integration

`AbstractStorageProvider` exposes `store`, `delete`, `exists`, `open`, and
`size`. `LocalStorageProvider` resolves every relative key beneath its
configured root. `NullStorageProvider` validates the same relative-key rules
and exposes bounded in-memory read streams for tests.

The pipeline never returns `storage_path`. Size and digest validation operate
through the provider abstraction.

## API and authorization

Persistent routes:

- `POST /api/v1/files/{file_id}/parse`;
- `POST /api/v1/files/{file_id}/reparse`;
- `GET /api/v1/files/{file_id}/parse-readiness`;
- `GET /api/v1/files/{file_id}/parse-results`;
- `GET /api/v1/parse-results/{result_id}`;
- `GET /api/v1/parse-results/{result_id}/history`;
- `GET /api/v1/parse-results/{result_id}/artifacts`; and
- `POST /api/v1/parse-results/{result_id}/invalidate`.

Learners are denied. Instructors receive summaries and extracted metadata but
not canonical content or history. Reviewers also receive execution history.
Admins control parsing, reparse, invalidation, canonical inspection, and
artifact inspection.

The direct multipart routes under `/api/v1/parsers` remain available for
transient validation. They do not create parse-result records.

Result listing supports filters for stored file, document version, ingestion
job, parser identity, status, input hash, content hash, and creation range.
Pagination is capped at 200 and every sort uses result ID as a stable
tie-breaker.

## Migration and portability

Revision `3a_s5_001` has parent `3a_s4_001`. It creates `parse_results`,
`parse_executions`, and `parse_artifacts`. Indexed strings are short enough for
MySQL `utf8mb4`; canonical output uses MySQL `LONGTEXT` and portable text on
SQLite. JSON metadata uses SQLAlchemy JSON on both supported dialects.

Verification:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest
```

Expected head: `3a_s5_001`.

The test suite covers upgrade, downgrade, re-upgrade, drift detection, SQLite,
MySQL DDL compilation and key lengths, and the existing configured live-MySQL
convention.

## Adding a parser

1. Implement `AbstractParser` with stable name/version, extensions, MIME types,
   validation, metadata extraction, and `CanonicalDocument` output.
2. Make extraction deterministic and offline, and define explicit size or
   complexity limits needed by the format.
3. Add optional source provenance to emitted structures.
4. Register the parser in `build_default_registry`.
5. Add extension/MIME upload compatibility when the format is storable.
6. Test valid structure, malformed input, external-resource behavior,
   deterministic serialization, persistence, failure history, and both
   supported SQL dialects.
7. Increment the parser version whenever extraction behavior can change
   canonical output.

## Deferred work

The next sprint should implement the Chunking and Provenance Engine against
immutable successful `ParseResult.canonical_json`. It should preserve source
coordinates, define deterministic chunk identities, and remain separate from
embeddings and retrieval.

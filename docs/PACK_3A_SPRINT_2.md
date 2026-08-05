# Pack 3A Sprint 2: Document Registry

The Document Registry represents logical documents and their versioned physical
file metadata before content processing. Registration never uploads or reads
file bytes and does not invoke parsing, OCR, workers, embeddings, or language
models.

## Registry structure

- `documents` holds stable identity, source provenance, bibliographic metadata,
  lifecycle state, and archive state.
- `document_versions` holds immutable version labels, checksums, release
  metadata, and the current-version marker.
- `document_files` holds physical-file metadata only. `storage_key` remains
  nullable until a later storage workflow exists.
- `document_identifiers` stores generic identifier type/value pairs with a
  global composite uniqueness rule.
- `document_relationships` stores directed, typed edges between distinct
  documents.
- `document_tags` supports tag search using the existing tag taxonomy.
- `import_batches` reserves auditable batch metadata for a future ingestion
  workflow without implementing that workflow.

The legacy `knowledge_documents` and `knowledge_chunks` tables are unchanged.
They continue to support existing Pack 1 behavior.

## Lifecycle and authorization

Document states are `draft`, `registered`, `ready`, `processing`, `processed`,
`published`, and `archived`. Archive is non-destructive and reversible.
Learners, instructors, reviewers, and admins may read registry records. Only
admins may create, update, archive, add versions or identifiers, or create
relationships.

## Versioning contract

Version and checksum are each unique within a document. The first registered
version is always current. Later versions may become current atomically or be
registered as historical. A portable current-marker representation plus a
composite unique constraint prevents multiple current versions in SQLite and
MySQL. Version fields cannot be changed after insertion; only the current
marker can rotate.

## Eligibility gate

The eligibility service raises a validation error unless all of the following
are true:

1. The source is active and not archived.
2. The source has a license record that explicitly allows ingestion.
3. The document is active and not archived.
4. Exactly one current version exists.
5. The current version has a non-empty checksum.
6. The current version has at least one file metadata record.

Passing the gate returns `True`; it does not enqueue or perform ingestion.

## Relationship model

Relationships are directed and use `supersedes`, `replaces`, `translation`,
`companion`, `references`, or `derived_from`. A source document cannot target
itself, both endpoints must exist, and a source/target/type triple is unique.
Inbound and outbound relationships are available separately on detailed reads.

## API

| Method | Route | Permission |
|---|---|---|
| `POST` | `/api/v1/documents` | Admin |
| `GET` | `/api/v1/documents` | All roles |
| `GET` | `/api/v1/documents/search` | All roles |
| `GET` | `/api/v1/documents/{id}` | All roles |
| `PATCH` | `/api/v1/documents/{id}` | Admin |
| `DELETE` | `/api/v1/documents/{id}` | Admin |
| `POST` | `/api/v1/documents/{id}/versions` | Admin |
| `POST` | `/api/v1/documents/{id}/identifiers` | Admin |
| `POST` | `/api/v1/documents/{id}/relationships` | Admin |
| `GET` | `/api/v1/import-batches` | All roles |

List and search operations support offset/skip pagination, limits from 1 to 200,
stable sorting, and filters for title, subtitle, author, language, source,
status, type, publication year, identifier, tag, active state, and archive
state.

## Migration and compatibility

Revision `3a_s2_001` has parent `3a_s1_001`. It creates new normalized tables
without altering prior migrations or legacy document tables.

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest
```

Migration-cycle tests cover upgrade, downgrade to the parent, and re-upgrade on
SQLite. Model DDL is compiled with the MySQL dialect, including identifier
length validation, to preserve SQLite/MySQL compatibility.

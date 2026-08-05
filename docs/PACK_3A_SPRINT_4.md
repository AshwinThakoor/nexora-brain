# Pack 3A Sprint 4: Secure File Upload and Storage Abstraction

This sprint adds the controlled byte-ingress boundary for Document Registry
versions. Uploads are validated, hashed, stored through a provider-neutral
interface, and linked to `DocumentVersion`. No uploaded content is parsed,
OCR-processed, embedded, or submitted to a language model, and no background
process is started.

## Storage architecture

`AbstractStorageProvider` defines three operations: store a binary stream,
delete a relative object path, and check whether an object exists. Storage
services consume only this contract.

- `LocalStorageProvider` resolves all paths beneath one configured root,
  rejects absolute and parent-traversal paths, writes a temporary file in the
  destination directory, flushes it, and atomically replaces the final path.
- `NullStorageProvider` stores bytes in memory for deterministic tests.
- `s3`, `azure`, `gcs`, and `minio` are reserved provider types. Their adapters
  are deliberately not implemented in this sprint.

The `storage_providers` table records enabled provider identities. The migration
registers local and null identities. `stored_files.storage_provider` and the
randomized relative `storage_path` are sufficient for future adapter routing
without changing document models.

## Upload lifecycle

An admin creates an `UploadSession` with a bounded expiry. A successful upload
follows:

```text
CREATED -> RECEIVING -> VALIDATING -> COMPLETED
```

Validation, duplicate detection, provider failure, or database failure produces
`FAILED`. A non-terminal session can become `CANCELLED`; an overdue non-terminal
session can become `EXPIRED`. Completed, cancelled, and expired sessions cannot
be reused.

Each session owns at most one `StoredFile`. Provider storage succeeds before
file metadata commits. If the database commit then fails, the newly stored
object is deleted. Cancellation, expiration, and metadata deletion similarly
remove the provider object before committing metadata changes.

## Filename and path security

The original filename is retained for audit. The normalized filename:

1. discards any client-supplied directory path;
2. applies Unicode normalization and safe ASCII conversion;
3. removes control and unsafe punctuation;
4. normalizes whitespace and extension case;
5. protects Windows reserved device names; and
6. enforces the database length limit.

The normalized name is descriptive only. It is never used as the provider
object identity. Storage paths use UUID components and are validated again by
the provider.

## Validation configuration

All operational limits are settings:

```text
NEXORA_MAX_UPLOAD_SIZE=52428800
NEXORA_ALLOWED_EXTENSIONS=pdf,docx,txt,csv,md,json
NEXORA_ALLOWED_MIME_TYPES=application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/csv,text/markdown,application/json
NEXORA_DEFAULT_STORAGE_PROVIDER=local
NEXORA_LOCAL_STORAGE_ROOT=./storage/uploads
NEXORA_UPLOAD_SESSION_TTL_SECONDS=3600
```

Validation rejects zero bytes, oversize content, disallowed extensions,
disallowed MIME types, known extension/MIME mismatches, unsafe filenames, and
duplicate SHA-256 values.

## Hashing strategy

The service reads the input stream once into a size-bounded spooled stream while
calculating SHA-256, SHA-1, and MD5. The spool may move to temporary disk for
larger allowed uploads and is rewound before provider storage.

SHA-256 is globally unique on `stored_files` and is the canonical duplicate
identity. SHA-1 and MD5 support external catalog reconciliation and legacy
fingerprints. Normalized `FileHash` rows make algorithms extensible without
altering the stored-file table.

## Document Registry integration

Every `StoredFile` has a restrictive foreign key to `DocumentVersion`.
`DocumentVersion.stored_files` and `Document.stored_files` expose the
relationship. The Document Registry eligibility gate accepts either legacy
file metadata or a securely stored file on the current version.

## API and authorization

| Method | Route | Permission | Behavior |
|---|---|---|---|
| `POST` | `/api/v1/uploads/session` | Admin | Create a bounded upload session |
| `POST` | `/api/v1/uploads/{session_id}` | Admin | Validate and store multipart content |
| `GET` | `/api/v1/uploads/{session_id}` | Admin | Read session and stored-file metadata |
| `DELETE` | `/api/v1/uploads/{session_id}` | Admin | Cancel a non-terminal session |
| `GET` | `/api/v1/files/{id}` | Admin | Read stored-file and hash metadata |

Learners, instructors, and reviewers have no access to the upload or storage
metadata APIs. File bytes are not exposed by these routes.

## Migration and compatibility

Revision `3a_s4_001` has parent `3a_s3_001`. It creates `storage_providers`,
`upload_sessions`, `stored_files`, and `file_hashes`; previous migrations remain
unchanged.

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest
```

SQLite tests cover lifecycle, validation, provider behavior, multipart API,
upgrade, downgrade, and re-upgrade. MySQL compatibility is verified through
dialect DDL, UTF-8 index budgets, and live Alembic upgrade and schema-drift
checks.

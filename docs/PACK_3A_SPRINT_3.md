# Pack 3A Sprint 3: Ingestion Orchestration Engine

The Ingestion Orchestration Engine is a metadata-only control plane. It
coordinates eligible Document Registry records through durable jobs, attempts,
reservations, retries, node heartbeats, and audit history. It performs no file
upload, parsing, OCR, embedding, language-model operation, or background
execution.

## Data model

- `ingestion_jobs` stores one logical unit of ingestion work, its priority,
  lifecycle state, completion time, and last error.
- `ingestion_attempts` stores numbered execution attempts with start, finish,
  duration, status, and error metadata.
- `ingestion_audit_events` is the immutable lifecycle history.
- `processing_nodes` is the registry of orchestration-capable node identities
  and their latest heartbeat metadata.
- `job_reservations` records time-bounded claims on jobs. A portable nullable
  active slot and composite unique constraint permit at most one active
  reservation per job.

No model stores uploaded file bytes or parsed content.

## State machine

The legal primary path is:

```text
NEW -> QUEUED -> RESERVED -> RUNNING -> SUCCEEDED
                                  \-> FAILED -> RETRYING -> RESERVED
```

Cancellation is allowed from `new`, `queued`, `reserved`, `running`, `failed`,
and `retrying`. Terminal `succeeded` and `cancelled` jobs cannot transition.
Explicitly releasing an unstarted reservation returns `reserved` to `queued`.
An expired unstarted reservation follows the same path. Expiration while
running records a failed attempt and moves the job to `failed`.

All transitions are validated before mutation and are committed atomically with
their audit event and related attempt or reservation changes.

## Readiness and idempotency

Creating a service-level job records `new` state. Queuing calls the Document
Registry eligibility gate, which requires active source and document records,
an ingestion-permitting license, exactly one current version with a checksum,
and current-version file metadata.

The API creates and queues in one request. If readiness fails, the durable
`new` job can be retried after its metadata is corrected. A document with a
non-terminal job returns that existing job when creation is repeated. Parent
document row locking serializes service-level creation on databases that
support row locks.

## Retry policy

Starting a reserved job creates the next unique attempt number. Completing,
failing, or cancelling a running job closes the attempt and calculates
`duration_ms`. Retry requests are accepted only from `failed`.

The default limit is configured with:

```text
NEXORA_INGESTION_RETRY_LIMIT=3
```

Services and API retry requests may supply a bounded override. The count is
derived from immutable `retried` audit events, so it cannot be reset by
modifying attempt rows.

## Reservation and node model

Only active processing nodes can reserve work. Reservation creation locks the
job, checks for an existing active claim, and relies on a database uniqueness
constraint as the final concurrency boundary. Reservations remain active while
an attempt runs and are released on success, failure, or cancellation.

Node registration is idempotent by `node_name`: repeat registration refreshes
version, hostname, heartbeat, and active state. `heartbeat_node` updates the
heartbeat and reactivates the node. This sprint records node readiness only; it
does not launch or manage a node process.

## Audit model

Events use `created`, `queued`, `reserved`, `started`, `succeeded`, `failed`,
`retried`, `cancelled`, and `released`. Each event records the previous and new
job status, an optional reason, and creation time. ORM update and delete hooks
reject mutation, and no API exposes audit mutation.

## API and authorization

| Method | Route | Permission |
|---|---|---|
| `POST` | `/api/v1/ingestion/jobs` | Admin |
| `GET` | `/api/v1/ingestion/jobs` | Instructor, Reviewer, Admin |
| `GET` | `/api/v1/ingestion/jobs/{id}` | Instructor, Reviewer, Admin |
| `POST` | `/api/v1/ingestion/jobs/{id}/reserve` | Admin |
| `POST` | `/api/v1/ingestion/jobs/{id}/start` | Admin |
| `POST` | `/api/v1/ingestion/jobs/{id}/complete` | Admin |
| `POST` | `/api/v1/ingestion/jobs/{id}/fail` | Admin |
| `POST` | `/api/v1/ingestion/jobs/{id}/retry` | Admin |
| `POST` | `/api/v1/ingestion/jobs/{id}/cancel` | Admin |
| `GET` | `/api/v1/ingestion/jobs/{id}/audit` | Instructor, Reviewer, Admin |
| `GET` | `/api/v1/processing/nodes` | Instructor, Reviewer, Admin |
| `POST` | `/api/v1/processing/nodes` | Admin |

Learners have no access. Listings support deterministic sorting, filters,
search, and offset/skip pagination.

## Migration and compatibility

Revision `3a_s3_001` has parent `3a_s2_001` and creates only orchestration
tables. Prior migrations are unchanged.

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest
```

SQLite tests exercise schema creation, upgrade, downgrade, re-upgrade, state
transitions, retry limits, reservations, and audit immutability. MySQL
compatibility is checked through dialect DDL, UTF-8 key budgets, and live
Alembic schema verification.

# Pack 2A Sprint 2

## Architecture summary

The FastAPI application remains importable as `nexora_knowledge.api:app`.
`api/__init__.py` owns application construction, startup, exception handlers,
and router registration. Pack 1 routes live in `api/legacy.py` and retain their
original paths and responses. `api/dependencies.py` provides the shared
SQLAlchemy session dependency.

Each Knowledge Graph resource has three layers:

1. A Pydantic schema module for create, partial update, response, and
   pagination contracts.
2. A service module for validation, querying, transactions, and domain errors.
3. A thin API router that translates HTTP input and output.

SQLAlchemy models and table initialization remain unchanged from Sprint 1.
Importing `nexora_knowledge.models` registers all tables with `Base.metadata`.

## Endpoints

### Pack 1 compatibility

- `GET /health`
- `POST /ingest`
- `GET /search`
- `GET /stats`

### Categories

- `POST /categories`
- `GET /categories`
- `GET /categories/{category_id}`
- `PATCH /categories/{category_id}`
- `DELETE /categories/{category_id}`

Filters: `parent_id`, `name`, `skip`, and `limit`.

### Concepts

- `POST /concepts`
- `GET /concepts`
- `GET /concepts/{concept_id}`
- `PATCH /concepts/{concept_id}`
- `DELETE /concepts/{concept_id}`
- `POST /concepts/{concept_id}/tags/{tag_id}`
- `DELETE /concepts/{concept_id}/tags/{tag_id}`
- `GET /concepts/{concept_id}/claims`
- `GET /concepts/{concept_id}/relationships`

Filters: `category_id`, `difficulty`, `status`, `tag_id`, `q`, `skip`, and
`limit`. The text query checks title, slug, summary, and description. Attaching
an existing tag is idempotent. Removing a missing association returns 404.

### Sources

- `POST /sources`
- `GET /sources`
- `GET /sources/{source_id}`
- `PATCH /sources/{source_id}`
- `DELETE /sources/{source_id}`

Filters: `source_type`, `author`, `q`, `skip`, and `limit`.

### Claims

- `POST /claims`
- `GET /claims`
- `GET /claims/{claim_id}`
- `PATCH /claims/{claim_id}`
- `DELETE /claims/{claim_id}`

Filters: `concept_id`, `claim_type`, `status`, `min_confidence_score`, `q`,
`skip`, and `limit`. Detailed claim responses include evidence records.

### Evidence

- `POST /evidence`
- `GET /evidence`
- `GET /evidence/{evidence_id}`
- `PATCH /evidence/{evidence_id}`
- `DELETE /evidence/{evidence_id}`

Filters: `claim_id`, `source_id`, `evidence_type`, `strength`, `skip`, and
`limit`.

### Relationships

- `POST /relationships`
- `GET /relationships`
- `GET /relationships/{relationship_id}`
- `PATCH /relationships/{relationship_id}`
- `DELETE /relationships/{relationship_id}`

Filters: `source_concept_id`, `target_concept_id`, `relationship_type`,
`min_confidence_score`, `skip`, and `limit`.

### Tags

- `POST /tags`
- `GET /tags`
- `GET /tags/{tag_id}`
- `PATCH /tags/{tag_id}`
- `DELETE /tags/{tag_id}`

Filters: `q`, `skip`, and `limit`.

## Validation rules

- Required strings are stripped and must remain non-empty.
- Slugs use lowercase letters and numbers separated by single hyphens.
- Path, foreign-key, and filter IDs must be positive.
- Quality, trust, confidence, and strength scores range from 0.0 to 1.0.
- Publication years range from 1000 through the current UTC year.
- Category parents must exist. Self-parenting and parent cycles are rejected.
- Concept category, claim concept, and evidence claim/source references are
  checked before writes.
- Relationship endpoints must exist and must be different concepts.
- Relationship source/target/type triples are unique.
- Category and tag names/slugs and concept slugs return 409 on duplicates.
- Partial updates distinguish an omitted field from an explicit `null`.
  Nullable metadata can be cleared; required fields cannot.

Request-shape validation and invalid IDs return 422. Missing resources return
404. Uniqueness conflicts return 409. Database integrity details are never
included in API responses.

## Service layer

Resource services accept a SQLAlchemy `Session` and plain mappings. They own
reference validation, uniqueness checks, filtered counts, ordering,
pagination, mutation commits, and rollback after integrity failures.

The shared domain exceptions are:

- `ResourceNotFoundError`
- `ResourceConflictError`
- `ResourceValidationError`

FastAPI exception handlers map these to consistent `{"detail": "..."}` JSON
responses. Collection responses contain `items`, `total`, `skip`, and `limit`;
`total` is calculated with the same filters as the item query.

## Cascade behavior

- Deleting a parent category sets child `parent_id` values to null.
- Deleting a category sets linked concept `category_id` values to null.
- Deleting a concept deletes its claims, their evidence, its incoming and
  outgoing relationships, and its concept-tag association rows.
- Deleting a claim deletes its evidence records.
- Deleting a source preserves evidence and sets `source_id` to null.
- Deleting a tag removes association rows without deleting concepts.
- Pack 1 document deletion continues to delete its chunks.

Both ORM relationships and database foreign keys enforce the intended behavior.
SQLite tests enable foreign-key enforcement explicitly.

## Known limitations

- Schema migrations are not yet managed by Alembic.
- Authentication, authorization, audit history, and soft deletion are absent.
- Controlled vocabularies for statuses, difficulties, relationship types, and
  evidence types are not enforced yet.
- Text filtering uses database `LIKE` matching rather than full-text search.
- No embeddings, AI enrichment, or automated graph extraction are included.
- Concurrent writes are protected by database constraints, but no optimistic
  locking or ETag behavior is implemented.

## Next recommended sprint

Add Alembic migrations and migration tests first. Then introduce audit fields
and optimistic concurrency for graph edits, followed by authentication and
role-based authorization. Controlled vocabularies and bulk import/export can
follow once migration and access-control foundations are established.

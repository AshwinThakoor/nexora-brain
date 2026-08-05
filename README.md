# NEXORA Knowledge Engine

Pack 1 document ingestion and search plus the Pack 2A Knowledge Graph
management foundation.

## Included

- MySQL-ready SQLAlchemy database
- CLI: `init-db`, `ingest`, `search`, `stats`
- TXT, Markdown, PDF and EPUB ingestion
- Cleaning, chunking and rule-based classification
- Duplicate-file protection
- Source and licensing metadata
- FastAPI endpoints
- Knowledge Graph categories, concepts, claims, evidence, sources,
  relationships, and tags
- NEXORA Academy schools, degrees, courses, modules, lessons, objectives,
  prerequisites, and ordered curriculum paths
- Transaction-safe CRUD services and paginated management APIs
- Automated tests

## Quick start

Alembic is the official database schema-management mechanism. The default
development database is SQLite; set `DATABASE_URL` to select another database.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m pytest
```

### Linux and macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -m alembic upgrade head
python -m pytest
```

For MySQL, update `.env` with an appropriate SQLAlchemy URL:

```env
DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/nexora_brain?charset=utf8mb4
```

Do not commit `.venv`, `.env`, or generated databases. If an existing virtual
environment points to a removed Python installation, remove it manually and
recreate it. See
[Pack 2B Sprint 2 documentation](docs/PACK_2B_SPRINT_2.md) for migration
commands, environment details, CI, and troubleshooting.

Ingest the included test file:

```powershell
python -m nexora_knowledge.cli ingest ".\knowledge_sources\raw\test_trading.txt" --title "Trading Basics" --source-name "NEXORA Internal" --author "NEXORA" --license-status OWNED --commercial-use-allowed
```

Search:

```powershell
python -m nexora_knowledge.cli search "Bear Flag"
python -m nexora_knowledge.cli search "Bullish Engulfing"
python -m nexora_knowledge.cli search "risk management"
python -m nexora_knowledge.cli stats
```

Run the API:

```powershell
uvicorn nexora_knowledge.api:app --reload
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

## Knowledge Graph

- Categories organize concepts into optional parent-child hierarchies.
- Concepts are the primary knowledge topics and can have many tags.
- Claims are testable statements belonging to concepts.
- Evidence supports a claim and can optionally cite a source.
- Sources describe books, articles, websites, and other references.
- Relationships create typed, directed links between different concepts.
- Tags provide a flexible cross-category classification system.

### Endpoints

All collection endpoints support `skip` and `limit` pagination. The default
limit is 50 and the maximum is 200.

| Resource | Endpoints |
|---|---|
| Legacy | `GET /health`, `POST /ingest`, `GET /search`, `GET /stats` |
| Categories | `POST/GET /categories`, `GET/PATCH/DELETE /categories/{id}` |
| Concepts | `POST/GET /concepts`, `GET/PATCH/DELETE /concepts/{id}` |
| Concept tags | `POST/DELETE /concepts/{id}/tags/{tag_id}` |
| Concept graph | `GET /concepts/{id}/claims`, `GET /concepts/{id}/relationships` |
| Sources | `POST/GET /sources`, `GET/PATCH/DELETE /sources/{id}` |
| Claims | `POST/GET /claims`, `GET/PATCH/DELETE /claims/{id}` |
| Evidence | `POST/GET /evidence`, `GET/PATCH/DELETE /evidence/{id}` |
| Relationships | `POST/GET /relationships`, `GET/PATCH/DELETE /relationships/{id}` |
| Tags | `POST/GET /tags`, `GET/PATCH/DELETE /tags/{id}` |

### PowerShell examples

Create a category:

```powershell
$category = Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/categories" `
  -ContentType "application/json" `
  -Body '{"name":"Risk Management","slug":"risk-management"}'
```

Create a concept in that category:

```powershell
$body = @{
  title = "Position Sizing"
  slug = "position-sizing"
  summary = "Allocate position size from defined risk."
  category_id = $category.id
} | ConvertTo-Json

$concept = Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/concepts" `
  -ContentType "application/json" `
  -Body $body
```

Filter concepts:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/concepts?q=position&limit=20"
```

## Knowledge Builder

Pack 2B Sprint 1 converts parsed documents into categories, concepts, claims,
relationships, sources, and tags with deterministic rules. It reuses the
existing document parsers, cleaner, Knowledge Graph models, and CRUD services.

Import a document:

```powershell
python -m nexora_knowledge.knowledge_builder.importer knowledge_sources/raw/test_trading.txt
```

Or build from text:

```python
from nexora_knowledge.knowledge_builder import build_knowledge

result = build_knowledge(
    "Forex is part of Financial Markets. Position Sizing controls trade risk.",
    {"title": "Trading Notes", "source_type": "article"},
)
print(result.statistics)
```

The result includes created entities, duplicate counts, warnings, errors, and
processing time. See
[Pack 2B Sprint 1 documentation](docs/PACK_2B_SPRINT_1.md) for the pipeline
architecture and builder extension points.

## Rich Knowledge System

Pack 2C adds governed long-form articles, ordered sections, aliases, FAQs,
specialized financial entities, revisions, reviews, claim conflicts, and
source-quality assessments. Concepts remain the stable semantic identities;
rich records add editorial or machine-readable detail without changing the
existing graph, ingestion, search, builder, or API behavior.

The initial rich-knowledge migration is `2c_s1_001`:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m pytest
```

No rich seed data runs automatically. An optional, clearly labelled
demonstration seed is available for disposable development databases. See
[Pack 2C Sprint 1 documentation](docs/PACK_2C_SPRINT_1.md) for architecture,
governance rules, JSON examples, confidence limitations, and future
integration boundaries.

## NEXORA Academy

Pack 2D Sprint 1 adds the curriculum infrastructure that organizes governed
financial knowledge into this hierarchy:

```text
School
  Degree
    Course
      Module
        Lesson
          Learning Objectives
          Lesson Prerequisites
```

Curriculum paths provide a separate, explicitly ordered sequence of lessons
that can cross module or course boundaries. Services validate parent records,
unique slugs, non-negative ordering values, duplicate path positions, and
circular lesson prerequisites. Hierarchy deletion cascades through its
children while deleting a curriculum path never deletes its lessons.

Lessons may reference a Pack 2C `KnowledgeArticle` and `Concept`. Both links
are nullable so curriculum structure can be planned before editorial content
is ready. Deleting a linked article or concept clears the corresponding lesson
reference instead of deleting the lesson.

After applying migrations, seed the single Financial Markets Foundation
example:

```powershell
python -m alembic upgrade head
python -m nexora_knowledge.seeds.academy_seed
```

The seed creates one school, degree, course, module, three introductory
lessons, objectives, prerequisites, and an ordered path in one transaction.
For each lesson it links an existing Knowledge Article with the same canonical
slug or exact title when available; otherwise the article link remains null.
The seed is optional, never runs automatically, and refuses to duplicate an
existing Financial Markets Academy hierarchy.

## NEXORA Academy Learner Engine

Pack 2D Sprint 2 separates learner-owned records from the curriculum
definitions introduced in Sprint 1. Schools, degrees, courses, modules,
lessons, objectives, prerequisites, and curriculum paths describe what can be
learned. Learners, enrollments, progress rows, immutable completion events,
assessment attempts, and answers describe one learner's history. Curriculum
records should not be used to store user state.

The enrollment workflow creates one unique learner/course or learner/path
pair, then moves it from `enrolled` to `in_progress` and finally `completed`.
Starting and completing enrollments are idempotent with respect to their
timestamps. Course progress is the percentage of that course's lessons whose
current progress status is `completed`; path progress uses the explicitly
ordered path lessons. Empty courses and paths report `0.0%` and are not
auto-completed.

Lesson access and accumulated time are tracked independently from percentage
updates. Completing a lesson always records `100%`, creates one immutable
`LessonCompletion` event, and recalculates related course/path enrollments.
Repeating the normal completion call creates no duplicate event. An explicit
reset reopens the current progress row without deleting prior completion
events; completing after that reset creates a new historical event.

An assessment belongs to exactly one lesson, module, or course. An active
learner starts a numbered attempt, subject to the assessment's optional
attempt limit, and submits at most once. Multiple-choice and true/false
answers are graded immediately. Short answers remain ungraded, so a mixed
attempt can have a provisional score while pass/fail remains unset until all
grading is complete.

Apply the Sprint 2 migration and inspect the revision:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

After the Sprint 1 Academy seed exists, run the idempotent learner seed. It
creates one example learner, a Market Basics enrollment, three progress rows,
and one mixed-format lesson assessment without completing the course:

```powershell
python -m nexora_knowledge.seeds.learning_seed
python -m nexora_knowledge.seeds.learning_seed
```

The second command reuses all seeded learner records and assessment
definitions, making it safe for repeatable local development setup.

Run tests:

```powershell
python -m pytest
```

## NEXORA Academy API

Pack 2D Sprint 3 exposes the curriculum and learner engine at
`/api/v1/academy`. It adds authenticated learner workflows, staff grading and
review operations, admin lookup routes, immutable grading history, safe
pagination, and structured `400`, `401`, `403`, `404`, `409`, and `422`
responses.

### Authentication boundary

Academy routes depend on a provider-neutral `Principal` rather than passwords
or a NEXORA-specific token store. The default adapter reads identity claims
from `X-Nexora-Principal-Id` and `X-Nexora-Principal-Role`; an optional
`X-Nexora-Course-Ids` comma-separated claim restricts staff to assigned course
scope. Valid roles are `learner`, `instructor`, `reviewer`, and `admin`.

These headers are an integration boundary for a trusted identity-aware proxy,
not credentials. A production gateway must authenticate the caller, remove
untrusted inbound copies of these headers, and set verified claims. A future
OIDC or enterprise identity adapter can replace `get_current_principal`
through FastAPI dependency injection without changing Academy policies or
routes. NEXORA stores no passwords.

| Role | Academy permissions |
|---|---|
| Learner | Published catalog, own profile/dashboard, own enrollments/progress, own attempts/results |
| Instructor | Assigned-scope attempt inspection, short-answer grading, grade changes, review requests |
| Reviewer | Assigned-scope grading audit, review decisions, full regrades |
| Admin | Full Academy lookup, grading, review, and audit access |

Ownership and role checks live in
`nexora_knowledge.services.authorization`; routers do not make independent
authorization decisions. If an upstream provider supplies course IDs, those
claims are enforced for staff access. Without a course claim, staff assignment
scope remains the responsibility of the upstream provider until persistent
instructor-assignment records are introduced.

### Route inventory

All collection routes use deterministic ordering, `limit` and `offset`, and a
maximum page size of 100. Catalog routes also accept `skip` for compatibility
with the existing API convention.

| Area | Routes |
|---|---|
| Catalog | `GET /catalog/schools`, `/degrees`, `/courses`, `/modules`, `/lessons`, `/curriculum-paths`, plus each resource detail route |
| Learner | `GET /learners/me`, `GET /learners/me/dashboard` |
| Enrollment | `POST/GET /enrollments/courses`, `POST/GET /enrollments/paths`, and enrollment detail routes |
| Progress | `POST /progress/lessons/{id}/start`, `PATCH /progress/lessons/{id}`, `POST /progress/lessons/{id}/complete` |
| Assessment | `GET /assessments/{id}`, `POST /assessments/{id}/attempts`, `POST /assessments/attempts/{id}/submit`, own attempt list/detail/result routes |
| Grading | `GET /grading/attempts`, `GET /grading/attempts/{id}`, assigned-course learner progress, `POST /grading/answers/{id}`, `POST /grading/answers/{id}/changes`, answer/attempt history routes |
| Review | `POST /reviews/attempts/{id}/request`, `/approve`, `/changes`, `/regrade` |
| Admin | `GET /admin/learners`, learner detail/progress, assessment-attempt detail, and `/admin/audit-events` |

The full prefix for every route in the table is `/api/v1/academy`.

### Learner and assessment flow

1. Resolve the learner profile with `GET /learners/me`.
2. Enroll once in a course or curriculum path; duplicate enrollment returns
   `409`.
3. Start a lesson, report progress/time, and complete it.
4. Read the learner-safe assessment definition, start a numbered attempt, and
   submit it once.
5. Read the attempt result. Multiple-choice and true/false answers are scored
   immediately; short answers remain pending until staff grading.

Learner assessment definitions never serialize option correctness,
explanations, question metadata, or internal grading keys. Attempts are
ownership checked before retrieval or submission.

### Manual grading and review flow

A short-answer grade creates a new `ManualGrade`, makes it the answer's
current grade, appends audit events, and recalculates the attempt. A grade
change requires a non-empty reason and appends another record; prior grades
are never updated or deleted. Points cannot exceed the question maximum.

An instructor or reviewer may request review. Only a reviewer or admin may
approve it, request grading changes, or submit a full regrade. A full regrade
requires an explicit reason and a value for every short-answer response.
Review state has one current row per attempt, while every transition remains
in immutable `GradingAuditEvent` history.

`automatic_score_percent` and `automatic_points_earned` preserve the result
calculated at submission. `score_percent`, `points_earned`, and `passed`
represent the current provisional calculation. `final_score_percent` and
`final_passed` are set only after every question is fully graded. Review and
regrade status is tracked separately in `grading_status`.

### Example requests

The following values are fictional development claims. In production, a
trusted gateway supplies them after authentication.

```bash
curl -H "X-Nexora-Principal-Id: learner-demo-01" \
  -H "X-Nexora-Principal-Role: learner" \
  http://127.0.0.1:8000/api/v1/academy/learners/me

curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Nexora-Principal-Id: instructor-demo-01" \
  -H "X-Nexora-Principal-Role: instructor" \
  -d '{"points_awarded":2.5,"is_correct":true,"feedback":"Meets the rubric"}' \
  http://127.0.0.1:8000/api/v1/academy/grading/answers/42

curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Nexora-Principal-Id: reviewer-demo-01" \
  -H "X-Nexora-Principal-Role: reviewer" \
  -d '{"reason":"Rubric and feedback verified"}' \
  http://127.0.0.1:8000/api/v1/academy/reviews/attempts/17/approve
```

### Sprint 3 migration and verification

The Sprint 3 migration is `2d_s3_001`, with parent `2d_s2_001`.

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest

python -m alembic downgrade 2d_s2_001
python -m alembic upgrade head
```

Only ingest documents you own or are permitted to use.

See [Pack 2A Sprint 2 documentation](docs/PACK_2A_SPRINT_2.md) for the
architecture, validation, cascade behavior, and current limitations.

## Source Registry

Pack 3A Sprint 1 establishes the provenance registry that every future NEXORA
knowledge-ingestion path must use. It evolves the existing `sources` table in
place and adds normalized organizations, licenses, aliases, versions, and
source-tag associations. Document parsing, upload APIs, background workers,
language-model functionality, and MT5 changes are outside this sprint.

Every source has a stable UUID and unique slug. DOI and ISBN are unique when
present. Sources start active and can be archived without losing citations or
audit history; the service also supports restoring archived records. The trust
model is an explicit `low`, `medium`, `high`, or `official` provenance
classification and does not replace claim validation or evidence review.

Versions keep publisher release identity separate from exact-content identity:
both version and checksum are unique within a source. Licenses independently
record whether ingestion and distribution are allowed. A missing license is an
unknown permission state, not implicit permission.

The authenticated registry API is mounted at `/api/v1/sources`. Learners,
instructors, reviewers, and admins have read access; only admins can create,
update, or archive sources. Listings support pagination, deterministic sorting,
and filters for type, organization, language, trust, tag, active state, and
archive state. `/api/v1/sources/search` searches source metadata and aliases.
The older `/sources` routes remain available for Pack 2 Knowledge Graph
compatibility.

The Source Registry migration is `3a_s1_001`, with parent `2d_s3_001`:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest
```

See [Pack 3A Sprint 1 documentation](docs/PACK_3A_SPRINT_1.md) for the source
lifecycle, trust model, version semantics, license policy, authorization, and
migration-cycle details.

## Document Registry

Pack 3A Sprint 2 adds the production metadata boundary for every logical
document NEXORA may ingest. A registry `Document` belongs to a `Source`, owns
immutable versions, and can reference multiple physical-file metadata records,
generic external identifiers, tags, and typed relationships to other
documents. It is intentionally separate from the legacy
`knowledge_documents` table: registration does not upload, parse, OCR, embed,
or otherwise process document content.

### Lifecycle

Documents use the states `draft`, `registered`, `ready`, `processing`,
`processed`, `published`, and `archived`. Archive is a reversible soft-delete:
archiving sets `active=false`, `archived=true`, and status `archived`; restoring
returns the document to the active `registered` state. Source lifecycle remains
independent, so an active document cannot pass ingestion eligibility while its
source is inactive or archived.

### Eligibility Gate

`validate_ingestion_eligibility` permits a future ingestion workflow only when:

- the source is active and not archived;
- its normalized license explicitly allows ingestion;
- the document is active and not archived;
- exactly one current version exists and has a checksum; and
- the current version has at least one physical-file metadata record.

A missing license or missing file is a failed gate, never implicit permission.
The gate validates metadata only and starts no worker or parser.

### Versioning

Version labels and checksums are unique within each document. Version metadata
is immutable after creation. Registering a current version atomically demotes
the prior current version, while a portable database constraint prevents more
than one current version on both SQLite and MySQL. Historical versions and
their file metadata remain attached to the document.

### Relationship model

Directed relationships connect two distinct documents using `supersedes`,
`replaces`, `translation`, `companion`, `references`, or `derived_from`.
Duplicate source/target/type triples and self-relationships are rejected.
Identifiers such as ISBN, DOI, SEC accession, FRED release ID, CUSIP, and ticker
are stored generically and are globally unique by normalized type/value pair.

The authenticated API is mounted at `/api/v1/documents`, with future-batch
metadata listed at `/api/v1/import-batches`. Learners, instructors, reviewers,
and admins can read. Only admins can register, update, archive, version,
identify, or relate documents. Search supports title, subtitle, author,
language, source, status, document type, publication year, identifier, tag,
pagination, and deterministic sorting.

The Document Registry migration is `3a_s2_001`, with parent `3a_s1_001`:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest
```

See [Pack 3A Sprint 2 documentation](docs/PACK_3A_SPRINT_2.md) for the complete
data model, route inventory, eligibility contract, and compatibility notes.

## Ingestion Orchestration Engine

Pack 3A Sprint 3 adds the control plane for ingestion work without executing
content processing. It tracks jobs, attempts, reservations, processing-node
heartbeats, retries, and immutable audit events. It does not upload files,
parse documents, run OCR, generate embeddings, invoke language models, or
start background processes.

### Ingestion lifecycle and state machine

Jobs are created as `new`. Queuing applies the Document Registry eligibility
gate, and the orchestration API queues eligible jobs during creation. Legal
transitions are enforced centrally:

```text
new -> queued -> reserved -> running -> succeeded
                                  \-> failed -> retrying -> reserved
```

Active states may transition to `cancelled`. Explicit reservation release and
pre-start expiry return `reserved` jobs to `queued`. Invalid transitions raise
a service validation error and do not change job state.

### Retry policy

Each start creates a numbered attempt. Success or failure records its finish
time, duration, result, and optional error. Retries are counted from immutable
`retried` audit events and are limited by `NEXORA_INGESTION_RETRY_LIMIT`
(default `3`) or an explicit service/API override. Reaching the limit leaves
the job failed for operator review or cancellation.

### Reservation model

A database constraint permits only one unreleased reservation per job on both
SQLite and MySQL. Reservation operations also lock the job row to serialize
competing claims. Reservations have explicit expirations and releases.
`cleanup_expired_reservations` makes unstarted work queueable again and marks a
running attempt failed if its reservation expires.

### Audit model

Every lifecycle change writes an append-only audit event containing its event
type, previous state, new state, optional reason, and timestamp. Audit model
updates and deletes are rejected. Job creation is idempotent: while a document
has a non-terminal job, repeated creation returns that job instead of producing
duplicate work.

Instructors and reviewers can read jobs, nodes, attempts, reservations, and
audit history. Learners have no orchestration access. Admins have full control.
The APIs are mounted at `/api/v1/ingestion/jobs` and
`/api/v1/processing/nodes`.

The orchestration migration is `3a_s3_001`, with parent `3a_s2_001`:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest
```

See [Pack 3A Sprint 3 documentation](docs/PACK_3A_SPRINT_3.md) for the complete
state machine, retry, reservation, audit, API, and compatibility contracts.

## Secure File Upload and Storage

Pack 3A Sprint 4 introduces validated multipart uploads and backend-neutral
byte storage. It stores uploaded files, calculates cryptographic hashes, links
each file to a `DocumentVersion`, and makes the result eligible for ingestion
orchestration. It does not parse content, run OCR, create embeddings, invoke
language models, or start worker processes.

### Storage architecture

Application services depend on `AbstractStorageProvider`, never on filesystem
or cloud-specific APIs. `LocalStorageProvider` writes randomized relative paths
atomically beneath a configured root and rejects path traversal.
`NullStorageProvider` is an in-memory test provider. S3, Azure Blob, Google
Cloud Storage, and MinIO are represented by provider types for future adapters;
selecting one before its adapter exists fails closed.

Provider selection requires configuration only:

```text
NEXORA_DEFAULT_STORAGE_PROVIDER=local
NEXORA_LOCAL_STORAGE_ROOT=./storage/uploads
```

### Upload lifecycle

Sessions progress through `created`, `receiving`, `validating`, and `completed`.
Validation or storage failure produces `failed`; administrators can cancel
non-terminal sessions, and overdue sessions can be marked `expired`. Each
session accepts at most one stored file. Cancellation and expiry remove any
partial stored object and its database metadata.

### Validation rules

The service normalizes user filenames, discards supplied directory paths,
protects reserved filenames, and generates the actual storage path from a UUID.
Before provider storage it rejects:

- zero-byte content;
- content exceeding `NEXORA_MAX_UPLOAD_SIZE`;
- extensions outside `NEXORA_ALLOWED_EXTENSIONS`;
- MIME types outside `NEXORA_ALLOWED_MIME_TYPES`;
- known extension/MIME mismatches; and
- content whose SHA-256 already belongs to another stored file.

Upload bytes are processed through a bounded spooled stream rather than loaded
unbounded into application memory.

### Hashing strategy

SHA-256, SHA-1, and MD5 are computed in one streaming pass. SHA-256 is the
canonical duplicate-detection key and is uniquely constrained in the database.
All three values are preserved both on the stored-file record and in normalized
`file_hashes` rows for audit and future verification. SHA-1 and MD5 are
compatibility fingerprints, not security identity.

All upload and file-metadata routes require the admin role. The API is mounted
at `/api/v1/uploads` and `/api/v1/files`.

The secure-storage migration is `3a_s4_001`, with parent `3a_s3_001`:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest
```

See [Pack 3A Sprint 4 documentation](docs/PACK_3A_SPRINT_4.md) for provider,
validation, lifecycle, hashing, API, and compatibility details.

## Universal Parser Framework

Pack 3A Sprint 5 (Sprint 1E) adds a pluggable, in-memory parsing boundary
between stored source bytes and downstream content processing. Every parser
implements `AbstractParser`, publishes deterministic capability metadata, and
returns the same validated `CanonicalDocument` shape. Parsing does not write
database rows and does not perform OCR, embeddings, semantic search, vector
storage, language-model calls, or AI reasoning.

### Parser architecture

`ParserRegistry` owns parser registration and format selection. Selection can
use a normalized extension, MIME type, or both; when both are supplied they
must identify the same registered parser. This rejects disguised files instead
of silently choosing one hint. The default registry contains:

| Format | Extensions | MIME types | Extraction |
| --- | --- | --- | --- |
| PDF | `.pdf` | `application/pdf` | Available through `pypdf` |
| TXT | `.txt` | `text/plain` | Available, strict UTF-8 |
| DOCX | `.docx` | Office Open XML document | Available through `python-docx` |
| Markdown | `.md`, `.markdown` | Markdown text types | Available through `markdown-it-py` |
| HTML | `.html`, `.htm` | HTML/XHTML types | Available through Beautiful Soup and `lxml` |

DOCX, Markdown, and HTML are deterministic working parsers. Their former
scaffold import paths remain compatibility aliases, but no supported format
raises `ParserNotImplementedError`.

`parser_service` provides the application-facing operations:

- `select_parser()` resolves a parser from filename, extension, and MIME;
- `parse_document()` reads bounded bytes, validates the input, parses it, and
  verifies canonical statistics;
- `validate_document()` validates either raw parser input or canonical output;
  and
- `get_supported_formats()` returns registry capabilities.

The admin-only endpoints are `GET /api/v1/parsers`,
`POST /api/v1/parsers/validate`, and `POST /api/v1/parsers/parse`. The two POST
routes accept a multipart `file`. Parse responses are serialized
`CanonicalDocument` objects.

### Canonical document model

The portable Pydantic model is independent of SQLAlchemy. A
`CanonicalDocument` records its schema version, parser identity, metadata,
normalized text, sections, tables, image references, references, and computed
statistics. Sections contain ordered paragraphs and may contain nested
sections. `DocumentStatistics` verifies page, section, paragraph, table,
image, reference, word, and character counts before service output.

PDF extraction reads document metadata, page count, extractable text, and
conservative heading candidates. Image-only PDFs fail with a clear message
because OCR is outside this sprint. TXT extraction decodes UTF-8 (including an
optional BOM), separates blank-line paragraphs, and recognizes Markdown-style,
underlined, and uppercase headings.

### Adding a parser

1. Subclass `AbstractParser` and declare normalized `extensions` and
   `mime_types`.
2. Implement `supports()`, `validate()`, `extract_metadata()`, `parse()`,
   `parser_name()`, and `parser_version()` using the base contract.
3. Build the result with `CanonicalDocument.build()` so statistics are
   calculated consistently.
4. Register the parser in `build_default_registry()` and add registry,
   extraction, validation, service-selection, and API tests.

Direct multipart parsing remains an in-memory compatibility API. Stored-file
parsing persists canonical results through the Sprint 1F services described
below. The current Alembic head is `3a_s5_001`.

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest
```

See [Pack 3A Sprint 5 documentation](docs/PACK_3A_SPRINT_5.md) for the complete
parser, validation, API, extension, and compatibility contracts.

## Complete Format Parsing and Persistent Results

Pack 3A Sprint 6 (Sprint 1F) completes DOCX, Markdown, and HTML extraction and
adds an auditable synchronous pipeline from `StoredFile` to immutable canonical
output. The migration is `3a_s5_001`, with parent `3a_s4_001`.

### Supported structures

- DOCX extracts core properties, headings, paragraphs, ordered and unordered
  list items, tables, page-break markers, hyperlinks, and embedded-image
  references. Images remain metadata only and are never sent through OCR.
- Markdown extracts front matter, headings, paragraphs, lists, blockquotes,
  fenced and inline code metadata, tables, links, image references, horizontal
  rules, and reference definitions. Code is represented as text and is never
  executed.
- HTML extracts title, relevant meta tags, language, content blocks, lists,
  blockquotes, preformatted/code content, tables, links, and image references.
  Scripts, styles, templates, frames, objects, and embeds are removed. Parsing
  uses explicit byte, node-count, and nesting-depth limits and never loads an
  external resource.

Every canonical structure may carry `SourceProvenance`: a stable source index,
nullable page/paragraph/table coordinates, section path, character offsets,
and a source locator. TXT and PDF remain valid because provenance is optional.

### Persistent lifecycle and identity

`ParseResult` stores the current canonical result. `ParseExecution` preserves
every attempt, including failures, duration, safe error details, parser
identity, and processing node. `ParseArtifact` stores JSON or text manifests,
metadata summaries, statistics, validation reports, and warnings; binary
artifacts are not accepted.

The idempotency identity is:

```text
stored_file_id + input_sha256 + parser_name + parser_version
```

Repeated normal parsing returns the existing successful result. A parser
version change or changed stored-file hash forms a new identity. Successful
canonical content is immutable; explicit reparse records another execution and
must reproduce the same deterministic output. A differing result fails closed
instead of replacing the successful record. Invalidated results remain
auditable and are excluded from current-result lookup.

Canonical documents use sorted-key, compact UTF-8 JSON serialization.
`content_hash` is the SHA-256 of those exact deterministic bytes.

### Pipeline and ingestion

Stored-file parsing requires a current `DocumentVersion`, ingestion eligibility,
and a valid reservation owned by an active processing node. It then:

1. selects one parser from both extension and MIME type;
2. starts the reserved ingestion job through `ingestion_service`;
3. opens the configured provider through its read-only stream API;
4. enforces the configured size limit and verifies size and SHA-256;
5. creates or reuses the idempotent result and records an execution;
6. validates and persists canonical output and artifacts; and
7. completes or fails the ingestion job through legal state transitions.

Both `LocalStorageProvider` and `NullStorageProvider` implement `open`, `exists`,
and `size`. Storage paths are validated internally and are never exposed by
parse-result schemas or APIs.

### APIs and authorization

- `POST /api/v1/files/{file_id}/parse`
- `POST /api/v1/files/{file_id}/reparse`
- `GET /api/v1/files/{file_id}/parse-readiness`
- `GET /api/v1/files/{file_id}/parse-results`
- `GET /api/v1/parse-results/{result_id}`
- `GET /api/v1/parse-results/{result_id}/history`
- `GET /api/v1/parse-results/{result_id}/artifacts`
- `POST /api/v1/parse-results/{result_id}/invalidate`

Learners have no access. Instructors can read result summaries and metadata but
not canonical content or attempt history. Reviewers can also read execution
history. Admins can parse, reparse, invalidate, and inspect canonical content
and artifacts. The direct multipart parser API remains admin-only and clearly
separate from persistent stored-file parsing.

Filtering supports stored file, document version, ingestion job, parser name
and version, status, input hash, content hash, and creation range. Ordering is
stable and uses the result ID as a deterministic tie-breaker.

See [Pack 3A Sprint 6 documentation](docs/PACK_3A_SPRINT_6.md) and
[ADR-001](docs/adr/ADR-001-persistent-parser-results.md) for the detailed
contracts and rationale. Chunking, embeddings, semantic search, OCR, external
storage adapters, background workers, malware scanning, and LLM behavior remain
outside this sprint.

# Pack 3A Sprint 1: Source Registry

The Source Registry is the required provenance boundary for future NEXORA
knowledge ingestion. A `Source` identifies where knowledge originated; future
documents, extracted claims, and ingestion jobs must resolve or create that
source before storing knowledge. This sprint does not parse documents, upload
files, run workers, call language models, or alter MT5.

## Registry structure

`Source` stores a stable UUID and unique human-readable slug together with
title, type, language, trust, publication, identifier, ownership, and lifecycle
metadata. DOI and ISBN values are optional but unique when supplied. The
pre-existing `publication_year`, `license`, `quality_score`, and `trust_score`
columns remain available to Pack 2 callers; new registry operations use
`publication_date`, `license_id`, and `trust_level`.

The normalized entities are:

- `SourceOrganization`: publisher, institution, government body, company, or
  other organization responsible for a source.
- `SourceLicense`: ingestion and distribution permissions for a source.
- `SourceAlias`: alternate source names, unique within one source.
- `SourceVersion`: immutable version identity, with version and checksum each
  unique within one source.
- `SourceTag`: the many-to-many link between sources and the existing tag
  taxonomy.

Organizations and licenses are referenced with nullable foreign keys. Deleting
one detaches it from its sources. Aliases, versions, and tag links are removed
when their source is deleted. Normal registry deletion is archival, not a hard
delete.

## Source lifecycle

A new source is active and not archived. `DELETE /api/v1/sources/{id}` performs
a reversible archive transition:

```text
active=true, archived=false
          |
          | archive
          v
active=false, archived=true
          |
          | restore service operation
          v
active=true, archived=false
```

Archived sources remain queryable so citations and audit history do not lose
their provenance. The service-level `restore_source` operation reactivates a
source. Legacy `/sources` hard-delete behavior remains available only for
compatibility with the existing Pack 2 Knowledge Graph API.

## Trust model

Trust is a declared provenance classification, not a prediction:

| Level | Meaning |
|---|---|
| `low` | Unverified or weakly attributable material |
| `medium` | Identified source with ordinary editorial confidence |
| `high` | Strongly attributable, reputable, or independently controlled material |
| `official` | The authoritative issuing organization or official record |

Trust affects filtering and downstream policy decisions; it does not make a
claim true. Claim review, evidence strength, and source assessments remain
separate governance signals.

## Version model

Each version belongs to exactly one source. `version` identifies the publisher's
edition or release, while `checksum` identifies the exact content bytes that a
future ingestion pipeline will process. Both are unique within their source.
The same checksum may be used by a different source because source boundaries
represent distinct provenance records.

Checksums are normalized to lowercase by the service. A release date and notes
can record edition context without changing the stable source identity.

## License model

Licenses are reusable registry records. `allows_ingestion` answers whether
NEXORA may process the content; `allows_distribution` independently answers
whether NEXORA may redistribute it. A source without a license record is
unknown, not implicitly permitted. Future ingestion must refuse or quarantine
content unless its license policy permits the requested operation.

License notes can record attribution, jurisdiction, internal approvals, or
other restrictions. They are policy context, not a substitute for legal review.

## API and authorization

The authenticated registry is available at `/api/v1/sources`.

| Method | Route | Permission | Behavior |
|---|---|---|---|
| `POST` | `/api/v1/sources` | Admin | Create a source |
| `GET` | `/api/v1/sources` | All roles | Filtered, sorted, paginated listing |
| `GET` | `/api/v1/sources/search` | All roles | Full-text metadata and alias search |
| `GET` | `/api/v1/sources/{id}` | All roles | Detailed registry record |
| `PATCH` | `/api/v1/sources/{id}` | Admin | Update metadata |
| `DELETE` | `/api/v1/sources/{id}` | Admin | Archive the source |

Learners, instructors, reviewers, and admins may read. Only admins may mutate
registry records. Authentication uses the existing trusted principal headers
and authorization policies described by the Academy API documentation.

Listing supports `offset`, `limit`, `sort_by`, and `sort_order`, plus filters for
`type`, `organization`, `language`, `trust`, `tag`, `active`, and `archived`.
Organization and tag filters accept either numeric IDs or canonical
slugs/names. Search covers titles, descriptions, authors, publishers, URLs,
identifiers, DOI, ISBN, and aliases.

## Migration and verification

Revision `3a_s1_001` has parent `2d_s3_001` and evolves the existing `sources`
table in place. Existing rows receive a UUID, a deterministic `source-{id}`
slug, English language, medium trust, and active lifecycle state.

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest

python -m alembic downgrade 2d_s3_001
python -m alembic upgrade head
```

The models and migration are portable across SQLite and MySQL. The migration
cycle test verifies preservation of legacy source rows, and the DDL test
compiles every registry table for the MySQL dialect.

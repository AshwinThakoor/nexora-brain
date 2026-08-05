# ADR-001: Persist Canonical Parser Results

- Status: Accepted
- Date: 2026-07-28
- Decision owners: NEXORA Brain maintainers

## Context

The universal parser framework originally produced runtime-only
`CanonicalDocument` values. That was useful for format validation but
insufficient for downstream provenance: a later consumer could not prove which
stored bytes, parser implementation, execution attempt, or canonical schema
produced its input. Repeating extraction also consumed work and could silently
change output after a parser upgrade.

Chunking will require stable structural input and source coordinates, while
operational review requires durable success and failure history.

## Decision

Persist canonical parser output in `ParseResult`, preserve every attempt in
`ParseExecution`, and store non-binary metadata in `ParseArtifact`.

The idempotency identity is:

```text
stored_file_id + input_sha256 + parser_name + parser_version
```

Canonical output is serialized deterministically and hashed. A successful
result is immutable and can only be invalidated explicitly. Normal duplicate
requests return it. Explicit reparse may add an execution, but it must
reproduce the exact serialization and hash rather than overwrite the result.

## Rationale

### Why persist canonical output

Persistence creates a durable boundary between byte extraction and later
content processing. It makes parser output inspectable, reproducible, and
available to chunking without rereading source bytes. It also allows every
downstream record to cite one stable result and its source provenance.

### Why successful results are immutable

Silent replacement would destroy reproducibility. Existing chunks or audit
decisions could appear to reference the same result while its content had
changed. Immutability makes parser upgrades explicit, retains historical
evidence, and turns nondeterministic reparse output into a visible failure.

### Why input hash plus parser name/version forms identity

`stored_file_id` selects the registered object. `input_sha256` proves the
actual byte identity. `parser_name` distinguishes format adapters, and
`parser_version` makes extraction behavior part of provenance. A file or
parser change therefore produces a new identity, while identical work is
idempotent.

The schema uses a portable composite unique constraint rather than
dialect-specific partial indexes so SQLite and MySQL enforce the same rule.

### Why chunking is deferred

Extraction and chunking have different contracts. Parsing reconstructs
deterministic source structure; chunking makes downstream segmentation choices.
Combining them would make parser versions depend on chunk policy and would
prevent reuse of one canonical result across future chunking strategies.
Chunking is therefore the next sprint and will consume immutable successful
results.

## Consequences

Positive consequences:

- repeat parsing is idempotent;
- parser and input provenance is explicit;
- failures and retries remain auditable;
- downstream chunking receives stable, validated structure; and
- SQLite and MySQL share one concurrency and identity design.

Tradeoffs:

- canonical JSON consumes database storage;
- parser version discipline is mandatory;
- explicit reparse can expose nondeterminism as a failure; and
- invalidation is additive state, not deletion.

## Rejected alternatives

Runtime-only output was rejected because it cannot support durable provenance.
Overwriting a single row was rejected because it destroys auditability.
Storing only chunks was rejected because it couples extraction to one chunking
policy. A partial unique index on successful rows was rejected because portable
SQLite/MySQL behavior is more important than allowing duplicate failed result
rows; repeated failures are represented as executions instead.

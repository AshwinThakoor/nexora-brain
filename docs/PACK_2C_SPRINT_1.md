# Pack 2C Sprint 1: Rich Knowledge Foundation

Pack 2C extends the Knowledge Graph with structured explanations, financial
entity details, and governance records. It adds no live market connection,
embeddings, LLM workflow, MT5 integration, or claimed strategy performance.

## Architecture overview

The rich-knowledge foundation has four cooperating layers:

1. `Concept` is the stable semantic identity for a topic.
2. `KnowledgeArticle`, `KnowledgeSection`, `FAQ`, and `ConceptAlias` provide
   human-readable depth and discoverability.
3. Specialized financial entities hold machine-readable domain attributes for
   instruments, indicators, strategies, patterns, events, formulas, and case
   studies.
4. Governance entities record reviews, revisions, claim conflicts, and source
   assessments without rewriting the underlying knowledge object.

SQLAlchemy uses portable `String` columns for enum values and portable `JSON`
columns for structured data. This keeps the schema compatible with SQLite
development and migration tests while remaining usable with the existing
MySQL configuration.

## Concept remains the semantic identity

A Concept answers “what topic is this?” It owns the stable slug and graph
relationships that connect knowledge across categories, claims, tags, and
other Concepts. Rich records reference a Concept rather than replacing it.

This separation prevents article formatting, instrument metadata, or a
strategy revision from changing the identity of the underlying topic.
Concept-linked specialized entities use one-to-one relationships where their
`concept_id` is unique. Formulas, case studies, aliases, and articles can have
multiple records per Concept where the domain requires it.

Deleting an article does not delete its shared Concept. Article sections and
FAQs are article-owned and are deleted with the article. Aliases and
specialized entities are dependent on their Concept and are removed when that
Concept is deliberately deleted.

## Rich articles and flexible sections

`KnowledgeArticle` stores the curated long-form view: definition, explanation,
history, market context, trading applications, risk, strengths, limitations,
examples, mistakes, checklist, audience, lifecycle, review state, and explicit
confidence context.

`KnowledgeSection` adds ordered, typed sections without requiring a new column
for every future editorial structure. Its `section_type` distinguishes
definitions, formulas, examples, risks, limitations, case studies, checklists,
implementation notes, market behavior, and other supported content.
`metadata_json` can hold documented section-level structure such as variable
names or source references.

`FAQ` records are independently ordered. `ConceptAlias` stores both the
displayed alias and a Unicode-normalized, case-folded, whitespace-normalized
key. The database enforces uniqueness for a Concept, normalized alias, and
language.

## Specialized financial entities

- `AssetClass` describes market structure, participants, risk profile, and
  trading-hour considerations.
- `Instrument` stores canonical symbols, asset/quote components, venue and
  contract details, trading constraints, activity state, and broker- or
  venue-specific metadata.
- `Indicator` records calculation, parameters, required inputs,
  interpretation, signal context, regime suitability, strengths, and misuse.
- `Strategy` keeps governed lifecycle state and machine-readable entry, exit,
  invalidation, and risk rules. Eligibility, filters, parameters, and regime
  assumptions remain explicit JSON structures.
- `Pattern` separates detection, confirmation, invalidation, regime
  suitability, failure modes, and visual description.
- `EconomicEventType` describes recurring release types and their possible
  asset, volatility, interpretation, and risk-policy context. It does not
  contain live event data.
- `Formula` stores an expression, optional LaTeX, variable definitions,
  assumptions, interpretation, worked examples, and limitations.
- `CaseStudy` connects optional Concept, Instrument, and Strategy context to a
  time-bounded decision review. It separates information available at the time
  from decision, outcome, and lessons.

JSON fields must be objects or arrays. Their internal domain vocabulary should
be versioned and documented by future feature-specific sprints.

## Facts, rules, and empirical results

The `ClaimType` enum prevents fundamentally different assertions from being
presented as if they had the same evidence:

- `established_fact` and `definition` represent reviewed factual or semantic
  assertions.
- `interpretation` and `expert_opinion` require attribution and should not be
  mistaken for universal facts.
- `strategy_rule` is a prescriptive rule belonging to a governed strategy.
- `statistical_observation`, `backtest_result`, and `live_result` must identify
  their dataset, period, method, and limitations.
- `model_output` is produced by a defined model and is not automatically a
  fact.
- `hypothesis` remains unvalidated until evidence and review support a stronger
  lifecycle state.

The legacy `general`, `causal`, and `instruction` claim values remain readable
and writable so Pack 2B knowledge-builder behavior is not broken. New curated
content should prefer the richer enum vocabulary.

## Governance lifecycle

Knowledge lifecycle values are:

`draft → extracted → validated → reviewed → published`

`superseded`, `archived`, and `rejected` represent terminal or exceptional
states. Transitions are not automatically inferred. A review process should
record the decision in `KnowledgeReview`, then explicitly update the governed
entity.

`KnowledgeRevision` stores an immutable version number, change category,
summary, and JSON snapshot. The service prevents duplicate version numbers for
the same entity.

`ClaimConflict` stores a canonical ordered pair of different Claims. Reversed
pairs are normalized by the service and the database prevents duplicate pairs.
Resolution is explicit; creating a conflict does not silently rewrite either
Claim.

## Confidence limitations

A confidence score is bounded from 0 to 1, but the number is meaningless
without `confidence_method` and `confidence_reason`. Confidence is not a
probability unless the documented method establishes that interpretation. It
does not replace source review, uncertainty analysis, out-of-sample testing,
or operational risk controls.

Backtest confidence must not be transferred to live performance. Model output
confidence must not be presented as factual confidence. Null is preferable to
an invented score.

## Source-quality assessment

`SourceAssessment` records authority, accuracy, recency, transparency,
relevance, and overall scores, each bounded from 0 to 1. Scores are assessments
at a point in time, not permanent source properties. The method, notes, and
assessment time provide essential context.

Multiple assessments can be retained as a source changes or different review
methods are applied. Deleting an assessment never deletes the Source; deleting
a Source deletes its dependent assessment history.

## Worked structural examples

### Gold

A Gold Concept provides the semantic identity. A rich article can explain
market context, risks, and limitations. A separate Metals AssetClass and
XAUUSD Instrument hold machine-readable venue and contract attributes. Those
attributes must be verified for the actual broker or venue before use.

### RSI

An RSI Concept can link to an Indicator containing:

```json
{
  "default_parameters_json": {"period": 14},
  "input_requirements_json": {"series": ["close"]}
}
```

The calculation method must state smoothing and initialization behavior.
Interpretation belongs in reviewed text; an “overbought” label alone is not a
complete trading rule.

### Draft London-session strategy

A London-session Strategy can represent draft machine-readable rules:

```json
{
  "entry_rules_json": {"all": ["inside_reviewed_session_window"]},
  "exit_rules_json": {"any": ["time_exit", "invalidation"]},
  "invalidation_rules_json": {"any": ["required_data_missing"]},
  "risk_rules_json": {"policy": "governance_approved_limits"}
}
```

This structure demonstrates rule storage only. It makes no profitability,
backtest, or live-performance claim.

## Optional demonstration seed

`nexora_knowledge.seeds.rich_knowledge_examples` is import-only and never runs
at application startup or during migrations. It creates clearly labelled Gold,
XAUUSD, RSI, London-session, source, Claim, Evidence, and SourceAssessment
examples in one transaction.

After applying migrations to a disposable development database:

```python
from nexora_knowledge.database import SessionLocal
from nexora_knowledge.seeds import seed_rich_knowledge_examples

with SessionLocal() as session:
    result = seed_rich_knowledge_examples(session)
    print(result)
```

The seed uses `example.invalid`, labels all records as demonstration content,
and contains no invented numerical performance.

## Migrations and tests

Revision `2c_s1_001` follows `2b_s2_001`. It adds the rich tables and extends
Claims with lifecycle, confidence-method, confidence-reason, and review-time
fields. Existing Claim rows receive the migration-safe `draft` lifecycle
default.

Apply and verify:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest
```

The migration tests start at the Pack 2B revision, insert Pack 2B data, upgrade,
verify data preservation, downgrade to Pack 2B, and upgrade again.

## Future integration

### Semantic search

Future work can index Concept identity, aliases, article sections, formulas,
and governed Claim text. Embeddings should reference revision identifiers so
stale vectors can be invalidated. This sprint does not create embeddings.

### LLM workflows

Future extraction or drafting can target the Pydantic schemas, but generated
records should enter `extracted` or `draft`, preserve provenance, and require
review before publication. LLM output must not directly mark itself validated
or approved.

### MT5 TradeReview

A future TradeReview integration can reference Instrument, Strategy, Pattern,
CaseStudy, and Claim identifiers. It should capture the knowledge revision used
at decision time and must remain isolated from MT5 execution. This sprint does
not read, write, or connect to MT5.

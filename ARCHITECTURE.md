# NEXORA Brain — Architecture

NEXORA Brain is a modular document-intelligence and knowledge infrastructure service built with Python, FastAPI, SQLAlchemy, Alembic and Pydantic.

## 1. High-level architecture

```mermaid
flowchart TB
    CLIENT[Client / Internal Consumer] --> API[FastAPI API Layer]

    API --> INGEST[Ingestion Services]
    API --> KNOW[Knowledge Services]
    API --> ACADEMY[Academy Services]

    INGEST --> SOURCE[Source Registry]
    INGEST --> DOCUMENT[Document Registry]
    INGEST --> STORAGE[Storage Service]
    INGEST --> PARSER[Parser Pipeline]
    INGEST --> CHUNK[Chunking Pipeline]

    PARSER --> PARSERESULT[Persistent Parse Results]
    CHUNK --> CHUNKS[Persistent Chunks]

    KNOW --> CONCEPTS[Concepts / Claims / Evidence / Relationships]

    SOURCE --> DB[(SQLAlchemy Persistence)]
    DOCUMENT --> DB
    STORAGE --> DB
    PARSERESULT --> DB
    CHUNKS --> DB
    CONCEPTS --> DB
    ACADEMY --> DB

    MIG[Alembic Migrations] --> DB
```

## 2. Layer responsibilities

```mermaid
flowchart LR
    ROUTER[FastAPI Routers] --> SCHEMA[Pydantic Schemas]
    ROUTER --> SERVICE[Domain Services]
    SERVICE --> MODEL[SQLAlchemy Models]
    MODEL --> DATABASE[(Database)]
    SERVICE --> DOMAIN[Parser / Chunking / Storage Components]
```

**API routers** handle HTTP concerns. **Schemas** validate contracts. **Services** implement business behavior. **Models** represent persistence. Parser/chunking/storage packages isolate specialized infrastructure.

## 3. Ingestion lifecycle

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant I as Ingestion Service
    participant S as Source/Document Registry
    participant F as Storage
    participant P as Parser Pipeline
    participant K as Chunking Pipeline
    participant DB as Database

    C->>A: Submit ingestion request
    A->>I: Validated request
    I->>S: Resolve source + document identity
    I->>F: Resolve/persist storage metadata
    I->>P: Parse stored document
    P->>DB: Persist ParseResult
    I->>K: Chunk parsed content
    K->>DB: Persist chunk set + chunks
    I->>DB: Update processing state
    I-->>A: Ingestion result
    A-->>C: Typed response
```

## 4. Parser architecture

```mermaid
flowchart TD
    INPUT[Document] --> REGISTRY[Parser Registry]
    REGISTRY --> TYPE{Detected / Selected Format}
    TYPE --> TXT[TXT Parser]
    TYPE --> PDF[PDF Parser]
    TYPE --> DOCX[DOCX Parser]
    TYPE --> MD[Markdown Parser]
    TYPE --> HTML[HTML Parser]
    TXT --> RESULT[Structured Parse Result]
    PDF --> RESULT
    DOCX --> RESULT
    MD --> RESULT
    HTML --> RESULT
    RESULT --> PERSIST[Persistent ParseResult]
```

Parser implementations share common abstractions while retaining format-specific logic.

## 5. Deterministic chunking

```mermaid
flowchart LR
    PARSED[Parsed Content] --> STRATEGY{Chunk Strategy}
    STRATEGY --> FIXED[Fixed Window]
    STRATEGY --> STRUCT[Structural]
    FIXED --> NORMALIZE[Chunk Models + Metadata]
    STRUCT --> NORMALIZE
    NORMALIZE --> IDS[Stable / Deterministic Identity]
    IDS --> STORE[Persist Chunk Set + Chunks]
    STORE --> PROV[Provenance to Parse Result / Document]
```

Chunking is modeled as its own subsystem rather than embedded inside parser code, allowing strategies to evolve independently.

## 6. Knowledge model

```mermaid
flowchart TD
    SOURCE[Source] --> DOCUMENT[Document]
    DOCUMENT --> CHUNK[Chunk]
    SOURCE --> CONCEPT[Concept]
    CONCEPT --> CLAIM[Claim]
    CLAIM --> EVIDENCE[Evidence]
    CONCEPT --> REL[Relationship]
    CONCEPT --> TAG[Tag]
    DOCUMENT --> ARTICLE[Knowledge Article]
```

The goal is to retain both document-level provenance and richer semantic structures.

## 7. Persistence and migration architecture

```mermaid
flowchart LR
    MODELS[SQLAlchemy Models] --> SESSION[SQLAlchemy Session]
    SESSION --> DB[(SQLite / SQLAlchemy-compatible DB)]
    ALEMBIC[Alembic] --> MIGRATIONS[Versioned Migrations]
    MIGRATIONS --> DB
```

The repository contains multiple migrations representing actual schema evolution. Application startup does not rely on silently recreating the current schema; migrations are applied explicitly.

## 8. Authorization architecture

```mermaid
flowchart LR
    AUTH[Upstream Identity Provider] --> PRINCIPAL[Provider-neutral Principal]
    PRINCIPAL --> ROLE[Role Policy]
    PRINCIPAL --> SCOPE[Ownership / Course Scope]
    ROLE --> GATE{Authorized?}
    SCOPE --> GATE
    GATE -->|yes| SERVICE[Domain Operation]
    GATE -->|no| DENY[401 / 403]
```

The repository implements authorization policy and principal claims, not a full production authentication provider.

## 9. Academy domain

```mermaid
flowchart TD
    COURSE[Course / Curriculum] --> MODULE[Learning Structure]
    LEARNER[Learner] --> PROGRESS[Progress]
    MODULE --> PROGRESS
    MODULE --> ASSESS[Assessment]
    LEARNER --> SUBMISSION[Submission]
    ASSESS --> SUBMISSION
    SUBMISSION --> GRADE[Grading]
    GRADE --> REVIEW[Review Workflow]
```

The Academy subsystem demonstrates reuse of the same API/service/model/schema architecture for a larger application domain.

## 10. Testing architecture

```mermaid
flowchart LR
    CORE[Core / Services] --> PYTEST[pytest]
    API[FastAPI Routes] --> PYTEST
    PARSERS[Parsers] --> PYTEST
    CHUNK[Chunking] --> PYTEST
    STORAGE[Storage] --> PYTEST
    MIG[Alembic Migrations] --> PYTEST
    PYTEST --> ACTIONS[GitHub Actions]
```

Tests cover both functional behavior and migration/schema compatibility.

## 11. Future AI / retrieval integration

The current repository intentionally stops before claiming a complete RAG system.

```mermaid
flowchart LR
    BRAIN[NEXORA Brain Today] --> CONTENT[Validated Content + Chunks + Provenance]
    CONTENT -. future .-> EMBED[Embeddings]
    EMBED -. future .-> VECTOR[Vector / Hybrid Retrieval]
    VECTOR -. future .-> RERANK[Reranking]
    RERANK -. future .-> LLM[LLM Answer Generation]
```

This distinction is important: Brain already provides much of the data infrastructure a retrieval system would require, but embeddings/vector retrieval/LLM generation should only be presented as implemented once those components exist in code.

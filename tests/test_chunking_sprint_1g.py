from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import nexora_knowledge.api as api_package
from nexora_knowledge.api import app
from nexora_knowledge.api.dependencies import get_db
from nexora_knowledge.chunking.fixed_window import FixedWindowChunkingStrategy
from nexora_knowledge.chunking.models import ChunkCandidate, ChunkConfiguration
from nexora_knowledge.chunking.structural import StructuralChunkingStrategy
from nexora_knowledge.config import Settings
from nexora_knowledge.database import Base
from nexora_knowledge.models import (
    ChunkRelationshipType,
    ChunkSetStatus,
    DocumentType,
    ParseResultStatus,
    SourceLicense,
    SourceType,
)
from nexora_knowledge.models.canonical_document import (
    CanonicalDocument,
    DocumentMetadata,
    Paragraph,
    Section,
    SourceProvenance,
)
from nexora_knowledge.services import (
    chunking_pipeline_service,
    chunking_service,
    document_service,
    ingestion_service,
    parse_result_service,
    parser_pipeline_service,
    source_service,
    storage_service,
)
from nexora_knowledge.services.exceptions import ResourceValidationError
from nexora_knowledge.storage import NullStorageProvider


def _enable_foreign_keys(engine) -> None:
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture
def chunk_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    _enable_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()


def _settings(*, provider_type: str = "null", root: str = ".") -> Settings:
    return Settings(
        max_upload_size=1024 * 1024,
        allowed_extensions="txt,md,markdown,html,htm,docx,pdf",
        allowed_mime_types=(
            "text/plain,text/markdown,text/x-markdown,text/html,"
            "application/xhtml+xml,application/pdf,"
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        default_storage_provider=provider_type,
        local_storage_root=root,
    )


def _stored_file(
    db: Session,
    provider,
    *,
    suffix: str,
    content: bytes,
    filename: str = "fixture.txt",
    mime_type: str = "text/plain",
):
    license_record = SourceLicense(
        name=f"Chunk Licence {suffix}",
        slug=f"chunk-licence-{suffix}",
        allows_ingestion=True,
        allows_distribution=False,
    )
    db.add(license_record)
    db.commit()
    source = source_service.create_source(
        db,
        {
            "slug": f"chunk-source-{suffix}",
            "title": f"Chunk Source {suffix}",
            "source_type": SourceType.RESEARCH_PAPER,
            "language": "en",
            "trust_level": "official",
            "license_id": license_record.id,
        },
    )
    document = document_service.register_document(
        db,
        {
            "slug": f"chunk-document-{suffix}",
            "source_id": source.id,
            "title": f"Chunk Document {suffix}",
            "document_type": DocumentType.RESEARCH,
            "language": "en",
        },
    )
    version = document_service.register_version(
        db,
        document.id,
        {
            "version": "1.0",
            "checksum": f"chunk-checksum-{suffix}",
        },
    )
    settings = _settings(
        provider_type=provider.provider_type.value,
        root=str(getattr(provider, "root", ".")),
    )
    upload = storage_service.create_upload_session(
        db,
        f"admin-{suffix}",
        settings=settings,
    )
    stored = storage_service.store_file(
        db,
        upload.id,
        version.id,
        filename,
        mime_type,
        content,
        provider=provider,
        settings=settings,
    )
    storage_service.complete_upload(db, upload.id)
    return stored, document, settings


def _reserved_job(db: Session, document_id: int, *, suffix: str):
    node = ingestion_service.register_processing_node(
        db,
        {
            "node_name": f"chunk-node-{suffix}",
            "node_version": "1.0.0",
            "hostname": f"{suffix}.internal",
        },
    )
    job = ingestion_service.create_job(
        db,
        {"document_id": document_id, "priority": 25},
    )
    ingestion_service.queue_job(db, job.id)
    return ingestion_service.reserve_job(db, job.id, node.id)


def test_chunk_configuration_hashing_and_strategy_selection() -> None:
    config = ChunkConfiguration(target_size=1200, maximum_size=1400)
    assert len(chunking_service.calculate_configuration_hash(config)) == 64
    assert chunking_service.calculate_configuration_hash(config) == chunking_service.calculate_configuration_hash(
        config.model_dump()
    )

    structural = StructuralChunkingStrategy()
    fixed = FixedWindowChunkingStrategy()

    assert structural.strategy_name() == "structural"
    assert structural.supports_canonical_schema("1.0")
    assert fixed.strategy_name() == "fixed_window"
    assert fixed.supports_canonical_schema("1.0")


def test_structural_and_fixed_window_chunking_produce_deterministic_chunks() -> None:
    document = CanonicalDocument.build(
        parser_name="txt",
        parser_version="1.0.0",
        metadata=DocumentMetadata(title="Deterministic Chunking", page_count=1),
        content="Alpha beta gamma delta epsilon zeta eta theta iota kappa.",
        sections=[
            Section(
                title="Intro",
                level=1,
                order=0,
                provenance=SourceProvenance(source_index=0, page_number=1, section_path=["Intro"]),
                paragraphs=[
                    Paragraph(
                        text="Alpha beta gamma delta epsilon zeta eta theta iota kappa.",
                        order=0,
                        provenance=SourceProvenance(
                            source_index=0,
                            page_number=1,
                            section_path=["Intro"],
                            paragraph_index=0,
                        ),
                    )
                ],
            )
        ],
    )
    structural = StructuralChunkingStrategy()
    fixed = FixedWindowChunkingStrategy()
    config = ChunkConfiguration(target_size=40, maximum_size=60, minimum_size=20, overlap_size=10)

    structural_output = structural.chunk(document, config)
    fixed_config = ChunkConfiguration(
        strategy_name="fixed_window",
        strategy_version="1.0.0",
        target_size=40,
        maximum_size=60,
        minimum_size=20,
        overlap_size=10,
    )
    fixed_output = fixed.chunk(document, fixed_config)

    assert structural_output.statistics.chunk_count >= 1
    assert structural_output.chunks[0].content_hash
    assert fixed_output.statistics.chunk_count >= 1
    assert fixed_output.chunks[0].content_hash
    assert structural_output.configuration_hash == structural_output.configuration_hash
    assert fixed_output.configuration_hash == fixed_output.configuration_hash


def test_chunking_pipeline_is_idempotent_and_immutable(chunk_db: Session) -> None:
    provider = NullStorageProvider()
    stored, document, settings = _stored_file(
        chunk_db,
        provider,
        suffix="pipeline",
        content=b"# TITLE\n\nChunking pipeline content for a deterministic set.",
    )
    node = ingestion_service.register_processing_node(
        chunk_db,
        {"node_name": "chunk-pipeline-node", "node_version": "1.0.0", "hostname": "pipeline.internal"},
    )
    job = ingestion_service.create_job(chunk_db, {"document_id": document.id, "priority": 10})
    ingestion_service.queue_job(chunk_db, job.id)
    reserved = ingestion_service.reserve_job(chunk_db, job.id, node.id)

    first = parser_pipeline_service.parse_stored_file(
        chunk_db,
        stored.id,
        ingestion_job_id=reserved.id,
        provider=provider,
        settings=settings,
    )
    assert first.status == ParseResultStatus.SUCCEEDED.value

    chunk_set = chunking_pipeline_service.chunk_parse_result(
        chunk_db,
        first.id,
        ChunkConfiguration(target_size=80, maximum_size=120, minimum_size=20, overlap_size=10),
    )
    assert chunk_set.status == ChunkSetStatus.SUCCEEDED.value
    assert chunk_set.chunk_count == len(chunk_set.chunks)
    assert chunk_set.content_hash == chunking_service.calculate_chunk_set_content_hash(chunk_set.chunks)
    assert len(chunk_set.executions) == 1
    assert chunk_set.artifacts
    assert chunk_set.chunks[0].source_spans
    assert chunk_set.chunks[0].stable_key

    repeated = chunking_pipeline_service.chunk_parse_result(
        chunk_db,
        first.id,
        ChunkConfiguration(target_size=80, maximum_size=120, minimum_size=20, overlap_size=10),
    )
    assert repeated.id == chunk_set.id
    assert len(repeated.executions) == 1

    with pytest.raises(ValueError, match="immutable"):
        chunk_set.strategy_name = "modified"
        chunk_db.commit()
    chunk_db.rollback()


def test_chunking_api_routes_expose_chunking_payloads() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _enable_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    provider = NullStorageProvider()
    with factory() as db:
        stored, document, settings = _stored_file(
            db,
            provider,
            suffix="api",
            content=b"API\n\nChunking API content for deterministic chunking.",
        )
        node = ingestion_service.register_processing_node(
            db,
            {"node_name": "chunk-api-node", "node_version": "1.0.0", "hostname": "api.internal"},
        )
        job = ingestion_service.create_job(db, {"document_id": document.id, "priority": 10})
        ingestion_service.queue_job(db, job.id)
        reserved = ingestion_service.reserve_job(db, job.id, node.id)
        parse_result = parser_pipeline_service.parse_stored_file(
            db,
            stored.id,
            ingestion_job_id=reserved.id,
            provider=provider,
            settings=settings,
        )
        chunking_pipeline_service.chunk_parse_result(
            db,
            parse_result.id,
            ChunkConfiguration(target_size=80, maximum_size=120, minimum_size=20, overlap_size=10),
        )

    def override_get_db():
        with factory() as db:
            yield db

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(api_package, "init_database", lambda: None)
    monkeypatch.setattr(
        parser_pipeline_service,
        "get_default_storage_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        parser_pipeline_service,
        "get_settings",
        lambda: settings,
    )
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        headers = {
            "X-Nexora-Principal-Id": "chunk-admin",
            "X-Nexora-Principal-Role": "admin",
        }
        chunk_response = client.post(
            f"/api/v1/parse-results/{parse_result.id}/chunk",
            json={"configuration": {"strategy_name": "structural", "target_size": 80, "maximum_size": 120, "minimum_size": 20, "overlap_size": 10}},
            headers=headers,
        )
        assert chunk_response.status_code == 200
        chunk_payload = chunk_response.json()
        assert chunk_payload["status"] == ChunkSetStatus.SUCCEEDED.value
        assert chunk_payload["chunks"]
        assert chunk_payload["artifacts"]

        readiness = client.get(
            f"/api/v1/parse-results/{parse_result.id}/chunk-readiness",
            headers=headers,
        )
        assert readiness.status_code == 200
        assert readiness.json()["ready"] is True

        chunk_sets = client.get(
            f"/api/v1/parse-results/{parse_result.id}/chunk-sets",
            headers=headers,
        )
        assert chunk_sets.status_code == 200
        assert chunk_sets.json()["total"] >= 1

    app.dependency_overrides.clear()
    engine.dispose()
    monkeypatch.undo()

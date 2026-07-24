from pathlib import Path
import pytest
from nexora_knowledge.chunker import chunk_text
from nexora_knowledge.classifier import classify_text
from nexora_knowledge.cleaner import clean_text
from nexora_knowledge.ingest import ingest_document
from nexora_knowledge.schemas import IngestRequest
from nexora_knowledge.services import knowledge_stats, search_knowledge

def test_cleaner():
    assert clean_text("A  \r\n\r\n\r\nB\x00") == "A\n\nB"

def test_chunker():
    chunks = chunk_text("A"*500 + "\n\n" + "B"*500, chunk_size=600, overlap=50)
    assert len(chunks) >= 2
    assert all(chunks)

def test_classifier():
    assert classify_text("Use a stop loss and position size carefully") == "risk_management"
    assert classify_text("A bullish engulfing candlestick appears") == "candlesticks"
    assert classify_text("A bear flag chart setup") == "chart_patterns"

def test_ingest_search_and_stats(tmp_path: Path, db):
    source = tmp_path/"trading.txt"
    source.write_text(
        "Bullish Engulfing candlestick pattern near support.\n\n"
        "Bear Flag chart pattern may continue a bearish trend.\n\n"
        "Risk management uses a stop loss.", encoding="utf-8"
    )
    doc = ingest_document(db, IngestRequest(
        file_path=str(source), title="Trading Test",
        source_name="Unit Test", license_status="OWNED",
        commercial_use_allowed=True
    ))
    assert doc.id is not None
    assert len(doc.chunks) >= 1
    results = search_knowledge(db, "Bear Flag")
    assert results and results[0].document_title == "Trading Test"
    stats = knowledge_stats(db)
    assert stats["documents"] == 1
    assert stats["chunks"] >= 1

def test_duplicate_protection(tmp_path: Path, db):
    source = tmp_path/"duplicate.txt"
    source.write_text("A sufficiently long trading strategy document for duplicate testing.", encoding="utf-8")
    request = IngestRequest(file_path=str(source), license_status="OWNED")
    ingest_document(db, request)
    with pytest.raises(ValueError, match="already ingested"):
        ingest_document(db, request)

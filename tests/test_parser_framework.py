from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexora_knowledge.api import app
from nexora_knowledge.models.canonical_document import (
    CanonicalDocument,
    DocumentMetadata,
    Paragraph,
    Section,
)
from nexora_knowledge.parsers import (
    DocxParser,
    HtmlParser,
    MarkdownParser,
    ParserError,
    ParserRegistry,
    PdfParser,
    TxtParser,
    UnsupportedDocumentFormatError,
    build_default_registry,
)
from nexora_knowledge.services import parser_service


FIXTURES = Path(__file__).parent / "fixtures"


def _headers(role: str) -> dict[str, str]:
    return {
        "X-Nexora-Principal-Id": f"{role}-parser-test",
        "X-Nexora-Principal-Role": role,
    }


def test_txt_parser_builds_sections_paragraphs_metadata_and_statistics() -> None:
    content = (
        b"\xef\xbb\xbf# Market Brief\n\n"
        b"Liquidity conditions remain stable.\n\n"
        b"RISK CONTROLS\n\n"
        b"Exposure stays inside approved limits.\n"
    )
    document = TxtParser().parse(
        content,
        filename="market-brief.txt",
        mime_type="text/plain; charset=utf-8",
    )

    assert isinstance(document, CanonicalDocument)
    assert document.parser_name == "txt"
    assert document.metadata.title == "Market Brief"
    assert document.metadata.source_filename == "market-brief.txt"
    assert document.metadata.properties["encoding"] == "utf-8"
    assert [section.title for section in document.sections] == [
        "Market Brief",
        "RISK CONTROLS",
    ]
    assert [
        paragraph.text for paragraph in document.iter_paragraphs()
    ] == [
        "Liquidity conditions remain stable.",
        "Exposure stays inside approved limits.",
    ]
    assert document.statistics.page_count == 1
    assert document.statistics.section_count == 2
    assert document.statistics.paragraph_count == 2
    assert parser_service.validate_document(document)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "cannot be empty"),
        (b"\xff\xfeinvalid", "valid UTF-8"),
        (b" \n\t ", "non-whitespace"),
    ],
)
def test_txt_parser_rejects_invalid_input(
    content: bytes,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        TxtParser().parse(content, filename="invalid.txt")


def test_pdf_parser_extracts_metadata_pages_text_and_headings() -> None:
    content = (FIXTURES / "parser_sample.pdf").read_bytes()
    document = parser_service.parse_document(
        content,
        filename="parser_sample.pdf",
        mime_type="application/pdf",
    )

    assert document.parser_name == "pdf"
    assert document.metadata.title == "NEXORA Parser Sample"
    assert document.metadata.author == "NEXORA QA"
    assert document.metadata.page_count == 2
    assert "Revenue increased" in document.content
    assert "Liquidity remains" in document.content
    assert [section.title for section in document.sections] == [
        "QUARTERLY RESULTS",
        "RISK OUTLOOK",
    ]
    assert document.statistics.page_count == 2
    assert document.statistics.paragraph_count == 2
    assert parser_service.validate_document(document)


@pytest.mark.parametrize(
    "content",
    [
        b"not a PDF",
        b"%PDF-1.7\nmalformed",
    ],
)
def test_pdf_parser_rejects_malformed_documents(content: bytes) -> None:
    with pytest.raises(ValueError):
        PdfParser().parse(content, filename="invalid.pdf")


def test_registry_lists_all_capabilities_and_normalizes_formats() -> None:
    registry = build_default_registry()
    capabilities = {
        capability.name: capability
        for capability in registry.list_parsers()
    }

    assert set(capabilities) == {"docx", "html", "markdown", "pdf", "txt"}
    assert capabilities["pdf"].implemented is True
    assert capabilities["txt"].implemented is True
    assert capabilities["docx"].implemented is True
    assert capabilities["markdown"].implemented is True
    assert capabilities["html"].implemented is True
    assert registry.supports_extension("PDF")
    assert registry.supports_extension(".markdown")
    assert registry.supports_mime("text/plain; charset=utf-8")
    assert registry.supports_mime("text/html")
    assert not registry.supports_extension(".xlsx")
    assert not registry.supports_mime("application/zip")
    assert isinstance(registry.get_parser(".txt"), TxtParser)
    assert isinstance(
        registry.get_parser(mime_type="application/pdf"),
        PdfParser,
    )


def test_registry_rejects_duplicates_and_unknown_formats() -> None:
    registry = ParserRegistry([TxtParser()])
    with pytest.raises(ParserError, match="already registered"):
        registry.register_parser(TxtParser)
    with pytest.raises(UnsupportedDocumentFormatError, match="No parser"):
        registry.get_parser(".xlsx")
    with pytest.raises(
        UnsupportedDocumentFormatError,
        match="extension or MIME",
    ):
        registry.get_parser()


@pytest.mark.parametrize(
    ("parser", "filename", "mime_type", "content"),
    [
        (
            DocxParser(),
            "report.docx",
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document",
            b"not-a-docx",
        ),
        (
            MarkdownParser(),
            "notes.md",
            "text/markdown",
            b"# Notes\n\nA deterministic paragraph.",
        ),
        (
            HtmlParser(),
            "page.html",
            "text/html",
            b"<html><body><h1>Page</h1><p>Content.</p></body></html>",
        ),
    ],
)
def test_registered_structured_parsers_are_implemented(
    parser,
    filename: str,
    mime_type: str,
    content: bytes,
) -> None:
    capability = parser.capability()
    assert capability.implemented is True
    if isinstance(parser, DocxParser):
        with pytest.raises(ValueError):
            parser.parse(content, filename=filename, mime_type=mime_type)
        return
    assert parser.validate(content)
    metadata = parser.extract_metadata(
        content,
        filename=filename,
        mime_type=mime_type,
    )
    assert metadata.source_filename == filename
    document = parser.parse(
        content,
        filename=filename,
        mime_type=mime_type,
    )
    assert document.parser_name == parser.parser_name()


def test_service_selects_parser_and_rejects_unknown_or_mismatched_format() -> None:
    assert parser_service.select_parser("notes.TXT").parser_name() == "txt"
    assert (
        parser_service.select_parser(
            mime_type="application/pdf",
        ).parser_name()
        == "pdf"
    )
    with pytest.raises(UnsupportedDocumentFormatError):
        parser_service.select_parser("workbook.xlsx")
    with pytest.raises(UnsupportedDocumentFormatError):
        parser_service.select_parser(
            "disguised.pdf",
            mime_type="text/plain",
        )


def test_canonical_validation_detects_inconsistent_statistics() -> None:
    document = CanonicalDocument.build(
        parser_name="test",
        parser_version="1.0.0",
        metadata=DocumentMetadata(
            title="Validation",
            page_count=1,
        ),
        content="Canonical paragraph.",
        sections=[
            Section(
                title="Validation",
                paragraphs=[Paragraph(text="Canonical paragraph.")],
            )
        ],
    )
    assert parser_service.validate_document(document)
    document.statistics.word_count += 1
    with pytest.raises(ValueError, match="statistics"):
        parser_service.validate_document(document)


def test_legacy_path_parser_remains_compatible(tmp_path: Path) -> None:
    from nexora_knowledge.parsers import parse_document as legacy_parse

    path = tmp_path / "legacy.txt"
    path.write_text("legacy parser content", encoding="utf-8")
    assert legacy_parse(str(path)) == "legacy parser content"


def test_parser_api_is_admin_only_and_returns_canonical_output() -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/parsers").status_code == 401
        for role in ("learner", "instructor", "reviewer"):
            assert client.get(
                "/api/v1/parsers",
                headers=_headers(role),
            ).status_code == 403

        listing = client.get(
            "/api/v1/parsers",
            headers=_headers("admin"),
        )
        assert listing.status_code == 200
        capabilities = {
            item["name"]: item for item in listing.json()
        }
        assert capabilities["txt"]["implemented"] is True
        assert capabilities["docx"]["implemented"] is True

        validation = client.post(
            "/api/v1/parsers/validate",
            files={
                "file": (
                    "api.txt",
                    b"API validation paragraph.",
                    "text/plain",
                )
            },
            headers=_headers("admin"),
        )
        assert validation.status_code == 200, validation.text
        assert validation.json()["valid"] is True
        assert validation.json()["parser_name"] == "txt"

        parsed = client.post(
            "/api/v1/parsers/parse",
            files={
                "file": (
                    "api.txt",
                    b"API parsing paragraph.",
                    "text/plain",
                )
            },
            headers=_headers("admin"),
        )
        assert parsed.status_code == 200, parsed.text
        assert parsed.json()["parser_name"] == "txt"
        assert parsed.json()["statistics"]["paragraph_count"] == 1

        markdown = client.post(
            "/api/v1/parsers/parse",
            files={
                "file": (
                    "api.md",
                    b"# Registered scaffold",
                    "text/markdown",
                )
            },
            headers=_headers("admin"),
        )
        assert markdown.status_code == 200, markdown.text
        assert markdown.json()["parser_name"] == "markdown"

        unknown = client.post(
            "/api/v1/parsers/validate",
            files={
                "file": (
                    "api.xlsx",
                    b"unknown",
                    "application/vnd.ms-excel",
                )
            },
            headers=_headers("admin"),
        )
        assert unknown.status_code == 422

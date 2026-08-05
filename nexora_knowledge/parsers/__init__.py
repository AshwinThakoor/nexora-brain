from .base import (
    AbstractParser,
    InvalidParserInputError,
    ParserCapability,
    ParserError,
    ParserNotImplementedError,
    UnsupportedDocumentFormatError,
)
from .legacy import SUPPORTED_EXTENSIONS, parse_document
from .docx import DOCXParser, DocxParser
from .html import HTMLParser, HtmlParser
from .markdown import MarkdownParser
from .pdf import PDFParser, PdfParser
from .registry import ParserRegistry
from .txt import TXTParser, TxtParser


def build_default_registry() -> ParserRegistry:
    return ParserRegistry(
        [
            PdfParser(),
            TxtParser(),
            DocxParser(),
            MarkdownParser(),
            HtmlParser(),
        ]
    )


default_registry = build_default_registry()


__all__ = [
    "AbstractParser",
    "DOCXParser",
    "DocxParser",
    "HTMLParser",
    "HtmlParser",
    "InvalidParserInputError",
    "MarkdownParser",
    "ParserCapability",
    "ParserError",
    "ParserNotImplementedError",
    "ParserRegistry",
    "PDFParser",
    "PdfParser",
    "SUPPORTED_EXTENSIONS",
    "TXTParser",
    "TxtParser",
    "UnsupportedDocumentFormatError",
    "build_default_registry",
    "default_registry",
    "parse_document",
]

"""Compatibility exports for the former Sprint 1E scaffold module."""

from .docx import DOCXParser, DocxParser
from .html import HTMLParser, HtmlParser
from .markdown import MarkdownParser


__all__ = [
    "DOCXParser",
    "DocxParser",
    "HTMLParser",
    "HtmlParser",
    "MarkdownParser",
]

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.builder import ParserRejectedMarkup

from ..models.canonical_document import (
    CanonicalDocument,
    DocumentMetadata,
    ImageReference,
    Paragraph,
    Reference,
    Section,
    SourceProvenance,
    Table,
)
from .base import AbstractParser, InvalidParserInputError, normalize_mime_type


class HtmlParser(AbstractParser):
    """Offline HTML extractor with explicit resource and complexity limits."""

    extensions = frozenset({".htm", ".html"})
    mime_types = frozenset({"application/xhtml+xml", "text/html"})
    max_document_bytes = 10 * 1024 * 1024
    max_nodes = 200_000
    max_nesting_depth = 100
    ignored_tags = frozenset(
        {
            "script",
            "style",
            "noscript",
            "template",
            "iframe",
            "object",
            "embed",
        }
    )

    def parser_name(self) -> str:
        return "html"

    def parser_version(self) -> str:
        return "2.0.0"

    def validate(self, content: bytes) -> bool:
        if not content:
            raise InvalidParserInputError("HTML document cannot be empty")
        if len(content) > self.max_document_bytes:
            raise InvalidParserInputError(
                "HTML document exceeds the safe parser size limit"
            )
        text = self._decode(content)
        if not text.strip():
            raise InvalidParserInputError(
                "HTML document must contain non-whitespace text"
            )
        soup = self._soup(text)
        self._validate_complexity(soup)
        return True

    def extract_metadata(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> DocumentMetadata:
        self.validate(content)
        soup = self._soup(self._decode(content))
        meta_tags = self._meta_tags(soup)
        meta_values: dict[str, Any] = {}
        for item in meta_tags:
            key = item["key"]
            value = item["content"]
            if key not in meta_values:
                meta_values[key] = value
            elif isinstance(meta_values[key], list):
                meta_values[key].append(value)
            else:
                meta_values[key] = [meta_values[key], value]
        title = (
            soup.title.get_text(" ", strip=True)
            if soup.title is not None
            else None
        )
        if not title:
            title = self._meta_text(meta_values, "og:title")
        if not title and filename:
            title = self._filename_title(filename)
        author = self._meta_text(meta_values, "author")
        language = None
        html_tag = soup.find("html")
        if isinstance(html_tag, Tag):
            language = self._clean(html_tag.get("lang"))
            if language is None:
                language = self._clean(html_tag.get("xml:lang"))
        if language is None:
            language = self._meta_text(meta_values, "content-language")
        keywords = self._meta_text(meta_values, "keywords")
        return DocumentMetadata(
            title=title,
            author=author,
            authors=[author] if author else [],
            subject=(
                self._meta_text(meta_values, "description")
                or self._meta_text(meta_values, "og:description")
            ),
            keywords=[
                item.strip()
                for item in re.split(r"[,;]", keywords or "")
                if item.strip()
            ],
            created_at=(
                self._meta_text(meta_values, "article:published_time")
                or self._meta_text(meta_values, "date")
            ),
            modified_at=self._meta_text(
                meta_values,
                "article:modified_time",
            ),
            language=language,
            source_filename=Path(filename).name if filename else None,
            extension=(
                Path(filename).suffix.lower()
                if filename
                and Path(filename).suffix.lower() in self.extensions
                else ".html"
            ),
            mime_type=normalize_mime_type(mime_type) or "text/html",
            page_count=1,
            properties={
                "meta": meta_values,
                "meta_tags": meta_tags,
                "external_resources_loaded": False,
                "ignored_tags": sorted(self.ignored_tags),
                "parser_backend": "lxml",
            },
        )

    def parse(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> CanonicalDocument:
        self.validate(content)
        soup = self._soup(self._decode(content))
        metadata = self.extract_metadata(
            content,
            filename=filename,
            mime_type=mime_type,
        )
        for ignored in soup.find_all(self.ignored_tags):
            ignored.decompose()
        root = soup.body or soup
        tags = [node for node in root.descendants if isinstance(node, Tag)]
        tag_order = {id(tag): index for index, tag in enumerate(tags)}
        sections: list[Section] = []
        section_stack: list[Section] = []
        tables: list[Table] = []
        content_blocks: list[str] = []
        paragraph_index = 0
        table_index = 0

        def section_path() -> list[str]:
            return [
                section.title
                for section in section_stack
                if section.title is not None
            ]

        def locator(tag: Tag) -> str:
            if tag.get("id"):
                return f"#{tag.get('id')}"
            return self._css_locator(tag)

        def add_section(tag: Tag, title: str, level: int) -> None:
            nonlocal section_stack
            while section_stack and section_stack[-1].level >= level:
                section_stack.pop()
            path = section_path() + [title]
            source_index = tag_order[id(tag)]
            section = Section(
                title=title,
                level=level,
                order=source_index,
                page_start=1,
                page_end=1,
                provenance=SourceProvenance(
                    source_index=source_index,
                    page_number=1,
                    section_path=path,
                    source_locator=locator(tag),
                ),
            )
            if section_stack:
                section_stack[-1].subsections.append(section)
            else:
                sections.append(section)
            section_stack.append(section)

        def ensure_section() -> Section:
            if not section_stack:
                title = metadata.title or "Document"
                section = Section(
                    title=title,
                    level=1,
                    order=0,
                    page_start=1,
                    page_end=1,
                    provenance=SourceProvenance(
                        source_index=0,
                        page_number=1,
                        section_path=[title],
                        source_locator="html/body",
                    ),
                )
                sections.append(section)
                section_stack.append(section)
            return section_stack[-1]

        for tag in tags:
            name = tag.name.casefold()
            if re.fullmatch(r"h[1-6]", name):
                title = self._normalize_text(tag.get_text(" ", strip=True))
                if title:
                    add_section(tag, title, int(name[1]))
                    content_blocks.append(title)
                continue
            if name == "table":
                parsed_table = self._table(
                    tag,
                    source_index=tag_order[id(tag)],
                    table_index=table_index,
                    section_path=section_path(),
                    source_locator=locator(tag),
                )
                if parsed_table is not None:
                    tables.append(parsed_table)
                    rows = [parsed_table.headers, *parsed_table.rows]
                    flattened = "\n".join(
                        "\t".join(row) for row in rows
                    ).strip()
                    if flattened:
                        content_blocks.append(flattened)
                    table_index += 1
                continue
            if not self._is_content_block(tag):
                continue
            block_text = self._block_text(tag)
            if not block_text:
                continue
            current = ensure_section()
            path = section_path()
            source_index = tag_order[id(tag)]
            block_type = self._block_type(tag)
            start = self._character_start(content_blocks)
            list_parent = tag.find_parent(["ol", "ul"]) if name == "li" else None
            list_level = (
                len(tag.find_parents(["ol", "ul"])) - 1
                if name == "li"
                else None
            )
            inline_code = [
                self._normalize_text(code.get_text(" ", strip=False))
                for code in tag.find_all("code")
                if code.find_parent("pre") is None
            ]
            current.paragraphs.append(
                Paragraph(
                    text=block_text,
                    order=paragraph_index,
                    page_number=1,
                    provenance=SourceProvenance(
                        source_index=source_index,
                        page_number=1,
                        section_path=path,
                        paragraph_index=paragraph_index,
                        character_start=start,
                        character_end=start + len(block_text),
                        source_locator=locator(tag),
                    ),
                    metadata={
                        "block_type": block_type,
                        "tag": name,
                        "blockquote_depth": len(
                            tag.find_parents("blockquote")
                        ),
                        "list_type": (
                            "ordered"
                            if isinstance(list_parent, Tag)
                            and list_parent.name == "ol"
                            else (
                                "unordered"
                                if isinstance(list_parent, Tag)
                                else None
                            )
                        ),
                        "list_level": list_level,
                        "inline_code": [
                            value for value in inline_code if value
                        ],
                        "code_executed": False,
                    },
                )
            )
            content_blocks.append(block_text)
            paragraph_index += 1

        references = [
            Reference(
                text=(
                    self._normalize_text(link.get_text(" ", strip=True))
                    or self._clean(link.get("href"))
                    or "link"
                ),
                target=self._clean(link.get("href")),
                reference_type="link",
                page_number=1,
                provenance=SourceProvenance(
                    source_index=tag_order[id(link)],
                    page_number=1,
                    section_path=self._heading_path_for_tag(link),
                    source_locator=locator(link),
                ),
                metadata={
                    "title": self._clean(link.get("title")),
                    "rel": list(link.get("rel") or []),
                    "loaded": False,
                },
            )
            for link in root.find_all("a")
            if self._clean(link.get("href"))
            and id(link) in tag_order
        ]
        images = [
            ImageReference(
                identifier=(
                    self._clean(image.get("id"))
                    or self._clean(image.get("src"))
                    or f"image-{tag_order[id(image)]}"
                ),
                source=self._clean(image.get("src")),
                alt_text=self._clean(image.get("alt")),
                caption=self._image_caption(image),
                page_number=1,
                provenance=SourceProvenance(
                    source_index=tag_order[id(image)],
                    page_number=1,
                    section_path=self._heading_path_for_tag(image),
                    source_locator=locator(image),
                ),
                metadata={
                    "title": self._clean(image.get("title")),
                    "width": self._clean(image.get("width")),
                    "height": self._clean(image.get("height")),
                    "loaded": False,
                    "ocr_performed": False,
                },
            )
            for image in root.find_all("img")
            if id(image) in tag_order
        ]
        if not any(True for section in sections for _ in section.iter_paragraphs()):
            flattened = "\n\n".join(content_blocks).strip()
            if not flattened:
                raise InvalidParserInputError(
                    "HTML document contains no extractable text"
                )
            canonical_root = ensure_section()
            canonical_root.paragraphs.append(
                Paragraph(
                    text=flattened,
                    order=0,
                    page_number=1,
                    provenance=SourceProvenance(
                        source_index=0,
                        page_number=1,
                        section_path=(
                            [canonical_root.title]
                            if canonical_root.title
                            else []
                        ),
                        paragraph_index=0,
                        character_start=0,
                        character_end=len(flattened),
                        source_locator="html/body",
                    ),
                    metadata={"block_type": "structural_fallback"},
                )
            )
        return CanonicalDocument.build(
            parser_name=self.parser_name(),
            parser_version=self.parser_version(),
            metadata=metadata,
            content="\n\n".join(content_blocks),
            sections=sections,
            tables=tables,
            images=images,
            references=references,
        )

    @staticmethod
    def _decode(content: bytes) -> str:
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidParserInputError(
                "HTML document must contain valid UTF-8 text"
            ) from exc

    @staticmethod
    def _soup(text: str) -> BeautifulSoup:
        try:
            return BeautifulSoup(text, "lxml")
        except (ParserRejectedMarkup, ValueError, TypeError) as exc:
            raise InvalidParserInputError(
                "HTML document is malformed or unreadable"
            ) from exc

    def _validate_complexity(self, soup: BeautifulSoup) -> None:
        node_count = 0
        for node in soup.descendants:
            node_count += 1
            if node_count > self.max_nodes:
                raise InvalidParserInputError(
                    "HTML document exceeds the safe node-count limit"
                )
            if isinstance(node, Tag):
                depth = 0
                parent = node.parent
                while parent is not None:
                    depth += 1
                    if depth > self.max_nesting_depth:
                        raise InvalidParserInputError(
                            "HTML document exceeds the safe nesting-depth limit"
                        )
                    parent = parent.parent

    @staticmethod
    def _meta_tags(soup: BeautifulSoup) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for meta in soup.find_all("meta"):
            key = (
                meta.get("name")
                or meta.get("property")
                or meta.get("http-equiv")
            )
            content = meta.get("content")
            if key and content:
                result.append(
                    {
                        "key": str(key).strip().casefold(),
                        "content": str(content).strip(),
                    }
                )
        return result

    @staticmethod
    def _meta_text(values: dict[str, Any], key: str) -> str | None:
        value = values.get(key)
        if isinstance(value, list):
            value = value[0] if value else None
        return HtmlParser._clean(value)

    @staticmethod
    def _clean(value: object | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _filename_title(filename: str) -> str | None:
        value = Path(filename).stem.replace("_", " ").replace("-", " ")
        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    @staticmethod
    def _normalize_text(value: str) -> str:
        lines = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in value.replace("\r", "\n").splitlines()
        ]
        return "\n".join(line for line in lines if line).strip()

    @staticmethod
    def _is_content_block(tag: Tag) -> bool:
        name = tag.name.casefold()
        if name not in {"p", "li", "blockquote", "pre"}:
            return False
        if name == "p" and tag.find_parent("li"):
            return False
        if name == "blockquote" and tag.find(["p", "li", "pre"]):
            return False
        if name == "li" and tag.find_parent("li") is not None:
            return True
        return tag.find_parent("table") is None

    @staticmethod
    def _block_text(tag: Tag) -> str:
        if tag.name == "pre":
            return HtmlParser._normalize_text(tag.get_text("", strip=False))
        parts: list[str] = []
        for descendant in tag.descendants:
            if not isinstance(descendant, NavigableString):
                continue
            parent = descendant.parent
            if parent is None:
                continue
            if parent.find_parent(["script", "style", "table"]):
                continue
            if tag.name == "li":
                owner_li = (
                    parent
                    if parent.name == "li"
                    else parent.find_parent("li")
                )
                if owner_li is not tag:
                    continue
            parts.append(str(descendant))
        return HtmlParser._normalize_text(" ".join(parts))

    @staticmethod
    def _block_type(tag: Tag) -> str:
        if tag.name == "li":
            return "list_item"
        if tag.name == "blockquote" or tag.find_parent("blockquote"):
            return "blockquote"
        if tag.name == "pre":
            return "preformatted_code" if tag.find("code") else "preformatted"
        return "paragraph"

    @staticmethod
    def _table(
        tag: Tag,
        *,
        source_index: int,
        table_index: int,
        section_path: list[str],
        source_locator: str,
    ) -> Table | None:
        rows: list[list[str]] = []
        for row in tag.find_all("tr"):
            if row.find_parent("table") is not tag:
                continue
            cells = [
                HtmlParser._normalize_text(cell.get_text(" ", strip=True))
                for cell in row.find_all(["th", "td"], recursive=False)
            ]
            if cells:
                rows.append(cells)
        if not rows:
            return None
        caption_tag = tag.find("caption", recursive=False)
        caption = (
            HtmlParser._normalize_text(
                caption_tag.get_text(" ", strip=True)
            )
            if caption_tag is not None
            else None
        )
        return Table(
            headers=rows[0],
            rows=rows[1:],
            caption=caption,
            page_number=1,
            provenance=SourceProvenance(
                source_index=source_index,
                page_number=1,
                section_path=section_path,
                table_index=table_index,
                source_locator=source_locator,
            ),
            metadata={
                "row_count": len(rows),
                "column_count": max(len(row) for row in rows),
            },
        )

    @staticmethod
    def _image_caption(image: Tag) -> str | None:
        figure = image.find_parent("figure")
        if figure is None:
            return None
        caption = figure.find("figcaption")
        if caption is None:
            return None
        return HtmlParser._normalize_text(caption.get_text(" ", strip=True))

    @staticmethod
    def _heading_path_for_tag(tag: Tag) -> list[str]:
        hierarchy: list[tuple[int, str]] = []
        headings = tag.find_all_previous(
            ["h1", "h2", "h3", "h4", "h5", "h6"]
        )
        for heading in reversed(headings):
            level = int(heading.name[1])
            title = HtmlParser._normalize_text(
                heading.get_text(" ", strip=True)
            )
            if not title:
                continue
            while hierarchy and hierarchy[-1][0] >= level:
                hierarchy.pop()
            hierarchy.append((level, title))
        return [title for _, title in hierarchy]

    @staticmethod
    def _css_locator(tag: Tag) -> str:
        parts: list[str] = []
        current: Tag | None = tag
        while current is not None and current.name != "[document]":
            name = current.name
            if current.get("id"):
                parts.append(f"{name}#{current.get('id')}")
                break
            position = 1
            sibling = current.previous_sibling
            while sibling is not None:
                if isinstance(sibling, Tag) and sibling.name == name:
                    position += 1
                sibling = sibling.previous_sibling
            parts.append(f"{name}:nth-of-type({position})")
            parent = current.parent
            current = parent if isinstance(parent, Tag) else None
        return " > ".join(reversed(parts))

    @staticmethod
    def _character_start(content_blocks: list[str]) -> int:
        return sum(len(block) for block in content_blocks) + 2 * len(
            content_blocks
        )


HTMLParser = HtmlParser


__all__ = ["HTMLParser", "HtmlParser"]

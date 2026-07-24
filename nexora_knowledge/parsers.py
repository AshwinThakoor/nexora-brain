from pathlib import Path

SUPPORTED_EXTENSIONS = {".txt",".md",".pdf",".epub"}

def parse_document(file_path: str) -> str:
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")
    if ext in {".txt",".md"}:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF support requires pypdf. Run: pip install -r requirements.txt") from exc
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    try:
        from bs4 import BeautifulSoup
        from ebooklib import epub, ITEM_DOCUMENT
    except ImportError as exc:
        raise RuntimeError("EPUB support requires EbookLib and beautifulsoup4. Run: pip install -r requirements.txt") from exc
    book = epub.read_epub(str(path))
    parts = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        parts.append(BeautifulSoup(item.get_content(), "html.parser").get_text(" ", strip=True))
    return "\n\n".join(parts)

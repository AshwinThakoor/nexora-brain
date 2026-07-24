def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 180) -> list[str]:
    if chunk_size < 100:
        raise ValueError("chunk_size must be at least 100")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []
    chunks, current = [], ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else current + "\n\n" + paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current.strip())
            tail = current[-overlap:] if overlap else ""
            current = (tail + "\n\n" + paragraph).strip()
        else:
            step = chunk_size - overlap
            for start in range(0, len(paragraph), step):
                piece = paragraph[start:start+chunk_size].strip()
                if piece:
                    chunks.append(piece)
            current = ""
    if current:
        chunks.append(current.strip())
    return chunks

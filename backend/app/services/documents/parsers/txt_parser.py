from app.services.documents.chunking_service import TextChunk


def parse_txt(data: bytes) -> list[TextChunk]:
    text = data.decode("utf-8", errors="replace")
    if not text.strip():
        return []
    return [TextChunk(text=text)]

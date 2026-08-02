import io

from pypdf import PdfReader

from app.services.documents.chunking_service import TextChunk


def parse_pdf(data: bytes) -> tuple[list[TextChunk], int]:
    reader = PdfReader(io.BytesIO(data))
    segments: list[TextChunk] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            segments.append(TextChunk(text=text, page_number=page_number))
    return segments, len(reader.pages)

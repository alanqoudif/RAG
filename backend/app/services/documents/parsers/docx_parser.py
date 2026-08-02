import io

from docx import Document

from app.services.documents.chunking_service import TextChunk


def parse_docx(data: bytes) -> list[TextChunk]:
    document = Document(io.BytesIO(data))
    segments: list[TextChunk] = []
    current_heading: str | None = None
    current_paragraphs: list[str] = []

    def flush() -> None:
        if current_paragraphs:
            segments.append(TextChunk(text="\n".join(current_paragraphs), section_title=current_heading))

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style_name = (paragraph.style.name if paragraph.style else "") or ""
        if style_name.lower().startswith("heading"):
            flush()
            current_heading = text
            current_paragraphs = []
        else:
            current_paragraphs.append(text)
    flush()

    if not segments:
        return []
    return segments

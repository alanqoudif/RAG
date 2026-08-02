"""Format dispatch. Docling is wired in behind `USE_DOCLING` (default off) as the
higher-quality, layout-aware parser the assignment recommends; the format-specific parsers
below (pypdf/python-docx/openpyxl/csv) are the default, always-available fallback and the path
actually exercised in this project's tests — Docling's first run downloads its own layout/OCR
models (several hundred MB), which is out of scope to exercise automatically here.
"""

from app.config import get_settings
from app.exceptions import ValidationAppError
from app.logging_config import get_logger
from app.services.documents.chunking_service import TextChunk
from app.services.documents.parsers.csv_parser import parse_csv
from app.services.documents.parsers.docx_parser import parse_docx
from app.services.documents.parsers.pdf_parser import parse_pdf
from app.services.documents.parsers.txt_parser import parse_txt
from app.services.documents.parsers.xlsx_parser import parse_xlsx

logger = get_logger(__name__)


def _try_docling(extension: str, data: bytes) -> list[TextChunk] | None:
    if extension not in {".pdf", ".docx"}:
        return None
    try:
        import tempfile

        from docling.document_converter import DocumentConverter

        with tempfile.NamedTemporaryFile(suffix=extension, delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            converter = DocumentConverter()
            result = converter.convert(tmp.name)
            text = result.document.export_to_markdown()
        return [TextChunk(text=text)] if text.strip() else None
    except Exception:  # noqa: BLE001 -- Docling is best-effort; any failure falls back
        logger.warning("docling_parse_failed_falling_back", extension=extension)
        return None


def parse_document(extension: str, data: bytes) -> tuple[list[TextChunk], int | None]:
    settings = get_settings()
    extension = extension.lower()

    if settings.use_docling:
        docling_segments = _try_docling(extension, data)
        if docling_segments:
            return docling_segments, None

    if extension == ".pdf":
        return parse_pdf(data)
    if extension == ".docx":
        return parse_docx(data), None
    if extension == ".xlsx":
        return parse_xlsx(data), None
    if extension == ".csv":
        return parse_csv(data), None
    if extension == ".txt":
        return parse_txt(data), None

    raise ValidationAppError(f"Unsupported file extension '{extension}'.")

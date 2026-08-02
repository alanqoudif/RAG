import csv
import io

from app.services.documents.chunking_service import TextChunk

_ROWS_PER_CHUNK = 50


def parse_csv(data: bytes) -> list[TextChunk]:
    text = data.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []

    header = rows[0]
    data_rows = rows[1:] or rows
    segments: list[TextChunk] = []

    for start in range(0, len(data_rows), _ROWS_PER_CHUNK):
        batch = data_rows[start : start + _ROWS_PER_CHUNK]
        lines = []
        for row in batch:
            pairs = [
                f"{header[i] if i < len(header) else f'col{i}'}={value}"
                for i, value in enumerate(row)
                if value
            ]
            if pairs:
                lines.append(", ".join(pairs))
        if not lines:
            continue
        end = start + len(batch)
        segments.append(TextChunk(text="\n".join(lines), section_title=f"rows {start + 1}-{end}"))
    return segments

"""Word-count-based chunking (no tokenizer dependency — a reasonable approximation for the
assignment's scope). Each format's parser hands this pre-segmented text (already split by page /
heading / sheet+row-range) so a single long document never becomes one giant chunk, and short
segments are still split further if they exceed the configured chunk size.
"""

from dataclasses import dataclass


@dataclass
class TextChunk:
    text: str
    page_number: int | None = None
    section_title: str | None = None


def _split_words(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= chunk_size:
        return [" ".join(words)]

    chunks = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(words), step):
        window = words[start : start + chunk_size]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + chunk_size >= len(words):
            break
    return chunks


def chunk_segments(
    segments: list[TextChunk], *, chunk_size_tokens: int, chunk_overlap_tokens: int
) -> list[TextChunk]:
    """Splits each (page/section-scoped) segment into word-count-bounded chunks, preserving the
    segment's page_number/section_title on every resulting chunk.
    """
    result: list[TextChunk] = []
    for segment in segments:
        if not segment.text or not segment.text.strip():
            continue
        pieces = _split_words(segment.text, chunk_size_tokens, chunk_overlap_tokens)
        for piece in pieces:
            result.append(
                TextChunk(text=piece, page_number=segment.page_number, section_title=segment.section_title)
            )
    return result

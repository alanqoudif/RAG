from app.services.documents.chunking_service import TextChunk, chunk_segments


def test_short_segment_stays_one_chunk():
    segments = [TextChunk(text="hello world", page_number=1)]
    chunks = chunk_segments(segments, chunk_size_tokens=400, chunk_overlap_tokens=60)
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"
    assert chunks[0].page_number == 1


def test_long_segment_split_into_multiple_chunks():
    words = " ".join(f"word{i}" for i in range(1000))
    segments = [TextChunk(text=words, page_number=3, section_title="Intro")]
    chunks = chunk_segments(segments, chunk_size_tokens=100, chunk_overlap_tokens=10)
    assert len(chunks) > 1
    assert all(c.page_number == 3 for c in chunks)
    assert all(c.section_title == "Intro" for c in chunks)


def test_overlap_shares_words_between_adjacent_chunks():
    words = " ".join(f"w{i}" for i in range(300))
    segments = [TextChunk(text=words)]
    chunks = chunk_segments(segments, chunk_size_tokens=100, chunk_overlap_tokens=20)
    first_tail = chunks[0].text.split()[-20:]
    second_head = chunks[1].text.split()[:20]
    assert first_tail == second_head


def test_empty_segments_produce_no_chunks():
    segments = [TextChunk(text=""), TextChunk(text="   ")]
    chunks = chunk_segments(segments, chunk_size_tokens=400, chunk_overlap_tokens=60)
    assert chunks == []


def test_multiple_segments_never_merged_into_one_chunk():
    """A whole workbook must not become a single giant chunk — each pre-segmented input
    (one per page/sheet-range/section) stays chunked independently."""
    segments = [
        TextChunk(text="short segment one", page_number=1),
        TextChunk(text="short segment two", page_number=2),
    ]
    chunks = chunk_segments(segments, chunk_size_tokens=400, chunk_overlap_tokens=60)
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2

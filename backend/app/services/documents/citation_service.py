from app.core.constants import CITATION_TYPE_DOCUMENT
from app.services.documents.retrieval_service import RetrievedChunk


def format_document_citation(chunk: RetrievedChunk) -> dict:
    """Matches the assignment's citation contract example: {"type": "document", "file_name": ...,
    "page": ...}, extended with section/chunk_id/score for the fuller citation detail the PDF
    also asks for ("File name, Page number, Section, Chunk ID, Relevance score").
    """
    return {
        "type": CITATION_TYPE_DOCUMENT,
        "file_name": chunk.file_name,
        "page": chunk.page_number,
        "section": chunk.section_title,
        "chunk_id": str(chunk.chunk_id),
        "relevance_score": round(chunk.score, 6),
    }


def has_sufficient_evidence(chunks: list[RetrievedChunk], *, min_score: float = 0.2) -> bool:
    """A very small guard against answering confidently from noise: if every retrieved chunk
    scores below this floor, the caller should return an insufficient-evidence response instead
    of asking the LLM to synthesize an answer from weak matches.
    """
    return any(c.score >= min_score for c in chunks)

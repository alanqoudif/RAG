import uuid

from app.services.documents.citation_service import format_document_citation, has_sufficient_evidence
from app.services.documents.retrieval_service import RetrievedChunk


def _chunk(score=0.5, page=14, file_name="contract.pdf"):
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        file_name=file_name,
        content="Approved contract value is 60000 EGP.",
        page_number=page,
        section_title="Approved Contract Value",
        score=score,
    )


def test_format_document_citation_matches_pdf_contract_shape():
    citation = format_document_citation(_chunk())
    assert citation["type"] == "document"
    assert citation["file_name"] == "contract.pdf"
    assert citation["page"] == 14


def test_format_document_citation_includes_extended_fields():
    citation = format_document_citation(_chunk())
    assert "section" in citation
    assert "chunk_id" in citation
    assert "relevance_score" in citation


def test_has_sufficient_evidence_true_when_any_chunk_scores_above_floor():
    chunks = [_chunk(score=0.05), _chunk(score=0.4)]
    assert has_sufficient_evidence(chunks) is True


def test_has_sufficient_evidence_false_when_all_chunks_below_floor():
    chunks = [_chunk(score=0.01), _chunk(score=0.05)]
    assert has_sufficient_evidence(chunks) is False


def test_has_sufficient_evidence_false_for_no_chunks():
    assert has_sufficient_evidence([]) is False

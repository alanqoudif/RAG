from app.core.constants import INTENT_CLARIFICATION, INTENT_DATABASE, INTENT_DOCUMENT, INTENT_HYBRID
from app.services.chat.intent_classifier import classify


def test_database_only_when_only_db_sources_selected():
    assert (
        classify(question="total sales?", has_database_sources=True, has_document_sources=False)
        == INTENT_DATABASE
    )


def test_document_only_when_only_kb_sources_selected():
    assert (
        classify(question="what does the contract say?", has_database_sources=False, has_document_sources=True)
        == INTENT_DOCUMENT
    )


def test_hybrid_when_both_selected():
    assert (
        classify(question="compare invoices to contract", has_database_sources=True, has_document_sources=True)
        == INTENT_HYBRID
    )


def test_clarification_when_no_sources_selected():
    assert classify(question="hello", has_database_sources=False, has_document_sources=False) == INTENT_CLARIFICATION


def test_clarification_for_empty_question():
    assert classify(question="", has_database_sources=True, has_document_sources=True) == INTENT_CLARIFICATION
    assert classify(question="   ", has_database_sources=True, has_document_sources=False) == INTENT_CLARIFICATION

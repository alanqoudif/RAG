"""Deterministic-first intent classification. Which sources the user selected for the
conversation (database connections, knowledge bases) is the primary, reliable signal — it comes
from the API request, not from parsing free text — so no LLM call is needed for the common cases.
An LLM classifier is not used at all in this implementation: the deterministic rule covers every
case the assignment's contract actually needs (source selection is always explicit).
"""

from app.core.constants import INTENT_CLARIFICATION, INTENT_DATABASE, INTENT_DOCUMENT, INTENT_HYBRID


def classify(*, question: str, has_database_sources: bool, has_document_sources: bool) -> str:
    if not question or not question.strip():
        return INTENT_CLARIFICATION

    if has_database_sources and has_document_sources:
        return INTENT_HYBRID
    if has_database_sources:
        return INTENT_DATABASE
    if has_document_sources:
        return INTENT_DOCUMENT
    return INTENT_CLARIFICATION

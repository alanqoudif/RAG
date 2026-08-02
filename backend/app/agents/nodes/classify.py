from app.agents.state import ChatState
from app.services.chat.intent_classifier import classify


def classify_request(state: ChatState) -> ChatState:
    state.intent = classify(
        question=state.question,
        has_database_sources=bool(state.database_connection_ids),
        has_document_sources=bool(state.knowledge_base_ids),
    )
    return state

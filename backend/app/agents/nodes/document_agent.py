from app.agents.state import ChatState
from app.services.documents.retrieval_service import retrieve


async def run_document_agent(state: ChatState) -> ChatState:
    if not state.knowledge_base_ids:
        return state
    results = retrieve(
        state.db,
        tenant_id=state.current_user.tenant_id,
        knowledge_base_ids=state.knowledge_base_ids,
        query=state.question,
    )
    state.doc_results.extend(results)
    return state

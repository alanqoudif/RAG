import asyncio

from app.agents.state import ChatState
from app.services.documents.retrieval_service import retrieve


async def run_document_agent(state: ChatState) -> ChatState:
    if not state.knowledge_base_ids:
        return state
    # `retrieve` is synchronous and can block for a while (embedding model load/inference on
    # first use). Run it in a worker thread so it never blocks the event loop — critical for
    # the hybrid path, where this runs concurrently (asyncio.gather) with the database agent's
    # async Ollama HTTP call; without this, the blocking call starves that request of the loop
    # time it needs and it can time out even though Ollama itself is healthy.
    results = await asyncio.to_thread(
        retrieve,
        state.db,
        tenant_id=state.current_user.tenant_id,
        knowledge_base_ids=state.knowledge_base_ids,
        query=state.question,
    )
    state.doc_results.extend(results)
    return state

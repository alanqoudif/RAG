import asyncio

from app.agents.nodes.database_agent import run_database_agent
from app.agents.nodes.document_agent import run_document_agent
from app.agents.state import ChatState
from app.core.constants import INTENT_DATABASE, INTENT_DOCUMENT, INTENT_HYBRID


async def run_sources(state: ChatState) -> ChatState:
    """Dispatches to the database agent, the document agent, or both — concurrently for hybrid
    requests via asyncio.gather, satisfying "run database and document retrieval in parallel
    where possible" without the two branches racing on shared state (they only ever append to
    their own disjoint list: sql_outcomes vs. doc_results).
    """
    if state.intent == INTENT_DATABASE:
        await run_database_agent(state)
    elif state.intent == INTENT_DOCUMENT:
        await run_document_agent(state)
    elif state.intent == INTENT_HYBRID:
        await asyncio.gather(run_database_agent(state), run_document_agent(state))
    return state

"""One generic database agent node — not one agent per table or per connection type. It is
handed whichever connections the request selected and always re-derives a fresh,
permission-filtered schema per connection through text_to_sql_service.ask_database.
"""

from app.agents.state import ChatState
from app.repositories import database_connection_repository
from app.services.database import text_to_sql_service


async def run_database_agent(state: ChatState) -> ChatState:
    for connection_id in state.database_connection_ids:
        connection = database_connection_repository.get_by_id(
            state.db, state.current_user.tenant_id, connection_id
        )
        if connection is None:
            continue
        outcome = await text_to_sql_service.ask_database(
            state.db,
            connection=connection,
            question=state.question,
            current_user=state.current_user,
            ollama_client=state.ollama_client,
            conversation_id=state.conversation_id,
            message_id=state.message_id,
            ip_address=state.ip_address,
            request_id=state.request_id,
        )
        state.sql_outcomes.append(outcome)
    return state

from app.agents.state import ChatState


async def ask_for_clarification(state: ChatState) -> ChatState:
    if not state.question or not state.question.strip():
        state.answer = "Please ask a question."
    else:
        state.answer = (
            "Please select at least one database connection or knowledge base for me to answer "
            "from, or ask a general question that doesn't require either."
        )
    return state

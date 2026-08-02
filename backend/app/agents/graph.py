"""One generic chat orchestration graph, shared by every tenant/connection/knowledge-base
combination — never a per-table or per-tenant graph, per the assignment's agent design rule.

classify -> (clarification -> END) | (run_sources -> merge_and_generate -> END)

`run_sources` internally fans out to the database and/or document agent (concurrently for
hybrid requests); see app.agents.nodes.run_sources for why that concurrency lives inside one
node rather than as parallel LangGraph branches.
"""

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.clarification import ask_for_clarification
from app.agents.nodes.classify import classify_request
from app.agents.nodes.merge_and_generate import merge_and_generate
from app.agents.nodes.run_sources import run_sources
from app.agents.state import ChatState
from app.core.constants import INTENT_CLARIFICATION


def _route_after_classify(state: ChatState) -> str:
    return "clarification" if state.intent == INTENT_CLARIFICATION else "run_sources"


def build_chat_graph():
    graph = StateGraph(ChatState)

    graph.add_node("classify", classify_request)
    graph.add_node("run_sources", run_sources)
    graph.add_node("merge_and_generate", merge_and_generate)
    graph.add_node("clarification", ask_for_clarification)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify", _route_after_classify, {"run_sources": "run_sources", "clarification": "clarification"}
    )
    graph.add_edge("run_sources", "merge_and_generate")
    graph.add_edge("merge_and_generate", END)
    graph.add_edge("clarification", END)

    return graph.compile()


_compiled_graph = None


def get_chat_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_chat_graph()
    return _compiled_graph

"""LangGraph graph definition for the Country Information Agent.

Graph structure:
    START → parse_intent → (route) → fetch_country → synthesize_answer → END
                                  ↘ (error) → END
"""

from langgraph.graph import END, START, StateGraph

from .nodes import fetch_country, parse_intent, synthesize_answer
from .state import AgentState


def _route_after_parse(state: AgentState) -> str:
    """Conditional edge: skip fetch if intent parsing found an error."""
    if state.get("error"):
        return END
    return "fetch_country"


def build_graph() -> StateGraph:
    """Build and compile the Country Information Agent graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("fetch_country", fetch_country)
    graph.add_node("synthesize_answer", synthesize_answer)

    # Add edges
    graph.add_edge(START, "parse_intent")
    graph.add_conditional_edges("parse_intent", _route_after_parse, ["fetch_country", END])

    # After fetch: if API error, go to END; otherwise synthesize
    graph.add_conditional_edges(
        "fetch_country",
        lambda state: END if state.get("error") else "synthesize_answer",
        ["synthesize_answer", END],
    )

    graph.add_edge("synthesize_answer", END)

    return graph.compile()


# Pre-compiled graph instance for reuse
agent = build_graph()

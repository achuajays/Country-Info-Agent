"""LangGraph agent state definition."""

from typing import TypedDict


class AgentState(TypedDict):
    """State schema for the Country Information Agent graph.

    This state flows through all nodes in the pipeline:
      parse_intent → fetch_country → synthesize_answer
    """

    # Input
    question: str

    # After parse_intent
    country: str
    fields: list[str]

    # After fetch_country
    api_data: dict | None
    flag_url: str

    # Error tracking
    error: str | None

    # Final output
    answer: str

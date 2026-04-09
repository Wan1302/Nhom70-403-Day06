from __future__ import annotations

from typing import Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    metrics: list[dict[str, Any]]
    intent: str | None
    active_flow: str | None
    route_reason: str | None
    final_response: str
    next_action: str | None

    faq_query: dict[str, Any]
    retrieved_docs: list[dict[str, Any]]
    faq_status: str
    faq_agent_answer: str
    faq_step_count: int
    faq_clarify_count: int
    faq_web_searched: bool

    ticket_draft: dict[str, Any]
    ticket_missing_fields: list[str]
    ticket_status: str
    ticket_confirmation: str
    ticket_result: dict[str, Any]

    trip_constraints: dict[str, Any]
    trip_missing_fields: list[str]
    trip_status: str
    trip_context: dict[str, Any]
    itinerary: dict[str, Any]
    trip_tool_name: str | None
    trip_tool_args: dict[str, Any]
    trip_tool_result: dict[str, Any]
    trip_agent_answer: str
    trip_step_count: int
    trip_scratchpad: list[dict[str, Any]]
    last_trace: list[dict[str, Any]]
    last_latest_metrics: list[dict[str, Any]]

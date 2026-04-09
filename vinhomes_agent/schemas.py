from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    intent: Literal["faq_policy", "ticket_issue", "trip_plan", "unknown"]
    reason: str


class FAQExtraction(BaseModel):
    query: str = Field(description="Normalized query for FAQ search.")
    category: str | None = Field(default=None, description="FAQ category hint.")
    needs_clarification: bool = False
    clarification_question: str | None = None


class FAQAgentAction(BaseModel):
    action: Literal["ask_user", "call_tool", "finish"]
    thought: str = Field(description="Short reasoning for debugging.")
    tool_name: Literal["search_faq_kb"] | None = None
    user_question: str | None = None
    final_answer: str | None = None


class TicketUpdate(BaseModel):
    issue_type: str | None = None
    urgency: str | None = None
    location: str | None = None
    description: str | None = None
    incident_time: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    confirmation: Literal["none", "confirmed", "needs_edit"] = "none"


class TripUpdate(BaseModel):
    trip_date: str | None = None
    party_size: int | None = None
    audience: str | None = None
    origin: str | None = None
    budget_level: str | None = None
    budget_amount_vnd: int | None = None
    interests: list[str] = Field(default_factory=list)
    notes: str | None = None


class TripAgentAction(BaseModel):
    action: Literal["ask_user", "call_tool", "finish"]
    thought: str = Field(description="Short reasoning for debugging.")
    tool_name: Literal["get_trip_requirements_helper", "get_trip_context", "build_itinerary"] | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    user_question: str | None = None
    final_answer: str | None = None


class FAQRecord(BaseModel):
    id: str
    title: str
    category_title: str | None = None
    detail_url: str
    content_text: str
    publish_time_iso: str | None = None
    updated_time_iso: str | None = None
    score: float = 0.0


from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from vinhomes_agent.config import OPENAI_MODEL
from vinhomes_agent.observability import append_metric, build_metric, now
from vinhomes_agent.prompts import (
    build_faq_extract_prompt,
    build_faq_respond_prompt,
    build_route_intent_prompt,
    build_ticket_ask_prompt,
    build_ticket_extract_prompt,
    build_trip_extract_prompt,
    build_trip_plan_prompt,
)
from vinhomes_agent.schemas import FAQExtraction, RouteDecision, TicketUpdate, TripUpdate
from vinhomes_agent.state import AgentState
from vinhomes_agent.tools import (
    TRIP_TOOL_REGISTRY,
    build_itinerary,
    create_ticket,
    get_ticket_schema,
    get_trip_context,
    get_trip_requirements_helper,
    search_faq_kb,
    search_faq_web,
    summarize_ticket_draft,
    validate_ticket_input,
)


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=OPENAI_MODEL, temperature=0)


def latest_user_message(state: AgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return message.content
    return ""


def normalized_text(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def is_generic_acceptance(text: str) -> bool:
    normalized = normalized_text(text)
    generic_answers = {
        "gi cung duoc",
        "gi cũng được",
        "bat ky",
        "bất kỳ",
        "tong quat",
        "tổng quát",
        "cu the nao cung duoc",
        "cụ thể nào cũng được",
        "ok",
        "oke",
    }
    return normalized in generic_answers


def is_trip_revision_request(text: str) -> bool:
    normalized = normalized_text(text)
    revision_phrases = (
        "qua chi phi",
        "vuot ngan sach",
        "re hon",
        "tiet kiem",
        "giam chi phi",
        "chinh lai",
        "sua lai",
        "doi lich",
        "doi ke hoach",
        "toi uu lai",
        "qua dat",
    )
    return any(phrase in normalized for phrase in revision_phrases)


def wants_cheaper_trip_plan(text: str) -> bool:
    normalized = normalized_text(text)
    cheaper_phrases = (
        "qua chi phi",
        "vuot ngan sach",
        "re hon",
        "tiet kiem",
        "giam chi phi",
        "qua dat",
    )
    return any(phrase in normalized for phrase in cheaper_phrases)


def merge_dict(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def merge_faq_query(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    if update.get("query"):
        merged["query"] = update["query"]
    if update.get("category"):
        merged["category"] = update["category"]

    merged["needs_clarification"] = bool(update.get("needs_clarification", False))
    merged["clarification_question"] = update.get("clarification_question")

    if not merged["needs_clarification"]:
        merged["clarification_question"] = None

    return merged


def fallback_trip_action(state: AgentState) -> None:
    """Kept for reference only — trip_agent_decide is now deterministic."""
    raise NotImplementedError


def route_intent(state: AgentState) -> AgentState:
    llm = get_llm().with_structured_output(
        RouteDecision,
        include_raw=True,
        method="function_calling",
    )
    prompt = build_route_intent_prompt(state, latest_user_message(state))
    started_at = now()
    result = llm.invoke(prompt)
    decision = result["parsed"]
    current_active_flow = state.get("active_flow")
    resolved_intent = decision.intent
    latest_text = latest_user_message(state)
    has_trip_context = bool(state.get("trip_constraints") or state.get("trip_context") or state.get("itinerary"))
    route_reason = decision.reason

    if has_trip_context and is_trip_revision_request(latest_text):
        resolved_intent = "trip_plan"
        route_reason = "Detected trip revision follow-up from existing trip context."

    if decision.intent == "unknown" and current_active_flow in {"faq_policy", "ticket_issue", "trip_plan"}:
        resolved_intent = current_active_flow
    metric = build_metric("route_intent", started_at, result["raw"])
    return {
        "metrics": append_metric(state.get("metrics"), metric),
        "intent": resolved_intent,
        "active_flow": resolved_intent if resolved_intent != "unknown" else current_active_flow,
        "route_reason": route_reason,
    }


def clarify_intent(_: AgentState) -> AgentState:
    response = "Mình có thể hỗ trợ 3 việc: hỏi FAQ/quy định, tạo ticket sự cố, hoặc lên kế hoạch đi chơi ở Ocean Park. Bạn muốn làm việc nào?"
    return {"final_response": response, "messages": [AIMessage(content=response)]}


def faq_extract(state: AgentState) -> AgentState:
    llm = get_llm().with_structured_output(
        FAQExtraction,
        include_raw=True,
        method="function_calling",
    )
    prompt = build_faq_extract_prompt(state, latest_user_message(state))
    started_at = now()
    result = llm.invoke(prompt)
    parsed = result["parsed"]
    metric = build_metric("faq_extract", started_at, result["raw"])
    existing_faq_query = state.get("faq_query", {}) if state.get("active_flow") == "faq_policy" else {}
    merged_faq_query = merge_faq_query(existing_faq_query, parsed.model_dump())
    latest_text = latest_user_message(state)

    if not merged_faq_query.get("query") and not merged_faq_query.get("needs_clarification"):
        merged_faq_query["needs_clarification"] = True
        merged_faq_query["clarification_question"] = "Ban co the noi ro hon quy dinh hoac loai phi ban muon hoi khong?"

    if is_generic_acceptance(latest_text) and existing_faq_query.get("query"):
        merged_faq_query["query"] = existing_faq_query["query"]
        if existing_faq_query.get("category"):
            merged_faq_query["category"] = existing_faq_query["category"]
        merged_faq_query["needs_clarification"] = False
        merged_faq_query["clarification_question"] = None

    if merged_faq_query.get("needs_clarification"):
        response = parsed.clarification_question or "Bạn có thể nói rõ hơn loại phí/quy định mà bạn muốn hỏi không?"
        response = merged_faq_query.get("clarification_question") or response
        response = state.get("faq_agent_answer") or response
        return {
            "metrics": append_metric(state.get("metrics"), metric),
            "faq_query": merged_faq_query,
            "retrieved_docs": [],
            "faq_status": "collecting",
            "faq_agent_answer": "",
            "faq_step_count": 0,
            "faq_web_searched": False,
            "faq_clarify_count": state.get("faq_clarify_count", 0) + 1,
            "active_flow": "faq_policy",
        }

    return {
        "metrics": append_metric(state.get("metrics"), metric),
        "faq_query": merged_faq_query,
        "retrieved_docs": [],
        "faq_status": "ready",
        "faq_agent_answer": "",
        "faq_step_count": 0,
        "faq_web_searched": False,
        "faq_clarify_count": 0,
        "active_flow": "faq_policy",
    }


def fallback_faq_action(state: AgentState) -> None:
    """Kept for reference only — faq_agent_decide is now deterministic."""
    raise NotImplementedError



def faq_agent_decide(state: AgentState) -> AgentState:
    """Quyết định bước tiếp theo của FAQ hoàn toàn theo state machine — không gọi LLM."""
    faq_query  = state.get("faq_query", {})
    docs       = state.get("retrieved_docs", [])
    web_searched = state.get("faq_web_searched", False)

    # 1. Đã search cả KB lẫn web mà vẫn không có kết quả → kết thúc lịch sự
    if web_searched and not docs:
        return {
            "next_action": "finish",
            "faq_agent_answer": "Hiện tại dữ liệu của chúng tôi chưa cập nhật phần đấy, bạn có thể hỏi câu hỏi khác tôi sẽ trả lời cho bạn.",
            "faq_status": "no_result",
        }

    # 2. Cần làm rõ câu hỏi → hỏi user
    if faq_query.get("needs_clarification"):
        question = (
            faq_query.get("clarification_question")
            or "Bạn có thể nói rõ hơn về loại phí hoặc quy định muốn hỏi không?"
        )
        return {
            "next_action": "ask_user",
            "faq_agent_answer": question,
            "faq_status": "collecting",
        }

    # 3. Đã có docs → trả lời
    if docs:
        return {
            "next_action": "finish",
            "faq_agent_answer": "",
            "faq_status": "planning",
        }

    # 4. Có query, chưa search → search
    if faq_query.get("query"):
        return {
            "next_action": "call_tool",
            "faq_agent_answer": "",
            "faq_status": "planning",
        }

    # 5. Không có gì → hỏi lại
    return {
        "next_action": "ask_user",
        "faq_agent_answer": "Bạn có thể nói rõ hơn câu hỏi FAQ không?",
        "faq_status": "collecting",
    }



def faq_next(state: AgentState) -> str:
    return state.get("next_action", "ask_user")


def faq_ask(state: AgentState) -> AgentState:
    response = state.get("faq_agent_answer") or state.get("faq_query", {}).get("clarification_question") or "Ban co the noi ro hon cau hoi FAQ nay khong?"
    return {
        "final_response": response,
        "messages": [AIMessage(content=response)],
        "active_flow": "faq_policy",
        "faq_status": "collecting",
        "faq_clarify_count": state.get("faq_clarify_count", 0),
    }


def faq_search(state: AgentState) -> AgentState:
    """
    Bước 1: Tìm kiếm tài liệu nội bộ (CSV local).
    Bước 2: Nếu không có, fallback search web. Flag faq_web_searched ngăn
            gọi web lần 2, tránh vòng lặp.
    """
    query    = state["faq_query"]["query"]
    category = state["faq_query"].get("category")
    web_searched = state.get("faq_web_searched", False)

    # Bước 1: local KB
    docs = search_faq_kb.invoke({"query": query, "category": category, "top_k": 3})

    # Bước 2: fallback web (chỉ 1 lần duy nhất)
    if not docs and not web_searched:
        docs = search_faq_web.invoke({"query": query, "top_k": 3})
        web_searched = True

    return {
        "retrieved_docs": docs,
        "faq_step_count": state.get("faq_step_count", 0) + 1,
        "faq_web_searched": web_searched,
        "faq_status": "searched" if docs else "no_result",
    }


def faq_respond(state: AgentState) -> AgentState:
    docs = state.get("retrieved_docs", [])
    # Ưu tiên dùng câu trả lời đã được agent_decide đặt sẵn (no_result path)
    pre_built_answer = state.get("faq_agent_answer", "")
    if not docs:
        no_result_msg = pre_built_answer or "Hiện tại dữ liệu của chúng tôi chưa cập nhật phần đấy, bạn có thể hỏi câu hỏi khác tôi sẽ trả lời cho bạn."
        return {
            "final_response": no_result_msg,
            "messages": [AIMessage(content=no_result_msg)],
            "faq_query": {},
            "retrieved_docs": [],
            "faq_status": "completed",
            "faq_agent_answer": "",
            "faq_step_count": 0,
            "faq_web_searched": False,
            "faq_clarify_count": 0,
            "active_flow": None,
        }

    doc_context = "\n\n".join(
        f"Tiêu đề: {doc['title']}\nDanh mục: {doc.get('category_title')}\nNội dung: {doc['content_text']}\nNguồn: {doc['detail_url']}"
        for doc in docs
    )
    llm = get_llm()
    faq_question = state.get("faq_query", {}).get("query", latest_user_message(state))
    prompt = build_faq_respond_prompt(doc_context, faq_question)
    started_at = now()
    message = llm.invoke(prompt)
    metric = build_metric("faq_respond", started_at, message)
    response = message.content
    return {
        "metrics": append_metric(state.get("metrics"), metric),
        "final_response": response,
        "messages": [AIMessage(content=response)],
        "faq_query": {},
        "retrieved_docs": [],
        "faq_status": "completed",
        "faq_agent_answer": "",
        "faq_step_count": 0,
        "faq_clarify_count": 0,
        "active_flow": None,
    }


def ticket_extract(state: AgentState) -> AgentState:
    llm = get_llm().with_structured_output(
        TicketUpdate,
        include_raw=True,
        method="function_calling",
    )
    prompt = build_ticket_extract_prompt(state, latest_user_message(state))
    started_at = now()
    result = llm.invoke(prompt)
    metric = build_metric("ticket_extract", started_at, result["raw"])
    update = result["parsed"].model_dump()
    confirmation = update.pop("confirmation", "none")
    merged = merge_dict(state.get("ticket_draft", {}), update)
    return {
        "metrics": append_metric(state.get("metrics"), metric),
        "ticket_draft": merged,
        "ticket_confirmation": confirmation,
        "active_flow": "ticket_issue",
    }


def ticket_validate(state: AgentState) -> AgentState:
    _ = get_ticket_schema.invoke({})
    result = validate_ticket_input.invoke({"ticket_draft": state.get("ticket_draft", {})})
    if result["missing_fields"] or result["errors"]:
        return {
            "ticket_missing_fields": result["missing_fields"],
            "next_action": "ticket_ask",
            "ticket_status": "collecting",
        }
    if state.get("ticket_confirmation") == "confirmed":
        return {"next_action": "ticket_create", "ticket_status": "confirmed"}
    return {"next_action": "ticket_confirm", "ticket_status": "awaiting_confirmation"}


def ticket_next(state: AgentState) -> str:
    return state.get("next_action", "ticket_ask")


def ticket_ask(state: AgentState) -> AgentState:
    # build_ticket_ask_prompt trả về câu hỏi tĩnh từ question_map → không cần LLM
    response = build_ticket_ask_prompt(state)
    return {
        "final_response": response,
        "messages": [AIMessage(content=response)],
    }


def ticket_confirm(state: AgentState) -> AgentState:
    summary = summarize_ticket_draft.invoke({"ticket_draft": state.get("ticket_draft", {})})
    response = f"{summary}\n\nNếu đúng rồi, bạn chỉ cần trả lời 'đúng'. Nếu cần sửa, bạn nói lại phần cần đổi."
    return {"final_response": response, "messages": [AIMessage(content=response)]}


def ticket_create_node(state: AgentState) -> AgentState:
    result = create_ticket.invoke({"ticket_draft": state.get("ticket_draft", {})})
    response = f"Ticket đã được tạo thành công.\n- Mã ticket: {result['ticket_id']}\n- Thời gian tạo: {result['created_at']}"
    return {
        "ticket_result": result,
        "ticket_status": "completed",
        "active_flow": None,
        "final_response": response,
        "messages": [AIMessage(content=response)],
    }


def trip_extract(state: AgentState) -> AgentState:
    llm = get_llm().with_structured_output(
        TripUpdate,
        include_raw=True,
        method="function_calling",
    )
    prompt = build_trip_extract_prompt(state, latest_user_message(state))
    started_at = now()
    result = llm.invoke(prompt)
    metric = build_metric("trip_extract", started_at, result["raw"])
    update = result["parsed"].model_dump()
    latest_text = latest_user_message(state)
    has_new_info = any(value not in (None, "", [], {}) for key, value in update.items() if key != "notes")
    revision_requested = is_trip_revision_request(latest_text)
    merged = merge_dict(state.get("trip_constraints", {}), update)
    if wants_cheaper_trip_plan(latest_text) and not merged.get("budget_amount_vnd"):
        merged["budget_level"] = "thấp"
    return {
        "metrics": append_metric(state.get("metrics"), metric),
        "trip_constraints": merged,
        "trip_context": {} if (has_new_info or revision_requested) else state.get("trip_context", {}),
        "itinerary": {} if (has_new_info or revision_requested) else state.get("itinerary", {}),
        "trip_tool_result": {} if (has_new_info or revision_requested) else state.get("trip_tool_result", {}),
        "trip_tool_name": None,
        "trip_tool_args": {},
        "trip_agent_answer": "",
        "trip_step_count": 0 if (has_new_info or revision_requested) else state.get("trip_step_count", 0),
        "trip_scratchpad": [] if (has_new_info or revision_requested) else state.get("trip_scratchpad", []),
        "active_flow": "trip_plan",
    }


def trip_agent_decide(state: AgentState) -> AgentState:
    """Quyết định bước tiếp theo của trip hoàn toàn theo state machine — không gọi LLM."""
    tool_name_last = state.get("trip_tool_name")   # tool vừa hoàn thành (do trip_tool_executor ghi)
    tool_result    = state.get("trip_tool_result", {})
    trip_context   = state.get("trip_context", {})
    itinerary      = state.get("itinerary", {})
    step_count     = state.get("trip_step_count", 0)

    # Guard: quá nhiều bước → hỏi user
    if step_count >= 5:
        return {
            "next_action": "ask_user",
            "trip_tool_name": None,
            "trip_tool_args": {},
            "trip_agent_answer": "Mình cần thêm thông tin để lên kế hoạch chính xác hơn. Bạn cho mình biết ngày đi và số người tham gia nhé?",
        }

    # 1. Đã có itinerary → finish
    if itinerary:
        return {
            "next_action": "finish",
            "trip_tool_name": None,
            "trip_tool_args": {},
            "trip_agent_answer": "",
        }

    # 2. Đã có context → dựng itinerary
    if trip_context:
        return {
            "next_action": "call_tool",
            "trip_tool_name": "build_itinerary",
            "trip_tool_args": {},
            "trip_agent_answer": "",
        }

    # 3. Vừa kiểm tra requirements xong
    if tool_name_last == "get_trip_requirements_helper" and tool_result:
        missing = tool_result.get("missing_fields", [])
        if missing:
            next_q = tool_result.get("next_question") or "Bạn cho mình thêm thông tin về chuyến đi nhé?"
            return {
                "next_action": "ask_user",
                "trip_tool_name": None,
                "trip_tool_args": {},
                "trip_agent_answer": next_q,
            }
        # Đủ dữ kiến → lấy context
        return {
            "next_action": "call_tool",
            "trip_tool_name": "get_trip_context",
            "trip_tool_args": {},
            "trip_agent_answer": "",
        }

    # 4. Mặc định: kiểm tra requirements trước
    return {
        "next_action": "call_tool",
        "trip_tool_name": "get_trip_requirements_helper",
        "trip_tool_args": {},
        "trip_agent_answer": "",
    }



def trip_next(state: AgentState) -> str:
    return state.get("next_action", "ask_user")


def trip_tool_executor(state: AgentState) -> AgentState:
    tool_name = state.get("trip_tool_name")
    tool = TRIP_TOOL_REGISTRY[tool_name]

    if tool_name == "get_trip_requirements_helper":
        tool_args = {"trip_constraints": state.get("trip_constraints", {})}
    elif tool_name == "get_trip_context":
        tool_args = {"trip_constraints": state.get("trip_constraints", {})}
    elif tool_name == "build_itinerary":
        tool_args = {
            "trip_constraints": state.get("trip_constraints", {}),
            "trip_context": state.get("trip_context", {}),
        }
    else:
        tool_args = state.get("trip_tool_args", {})

    started_at = now()
    result = tool.invoke(tool_args)
    metric = {
        "node": f"tool:{tool_name}",
        "elapsed_ms": round((now() - started_at) * 1000, 2),
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    scratchpad_entry = {"tool": tool_name, "result": result}

    updates: AgentState = {
        "metrics": append_metric(state.get("metrics"), metric),
        "trip_tool_args": tool_args,
        "trip_tool_result": result,
        "trip_step_count": state.get("trip_step_count", 0) + 1,
        "trip_scratchpad": [*state.get("trip_scratchpad", []), scratchpad_entry],
        "trip_status": "planning",
    }

    if tool_name == "get_trip_requirements_helper":
        updates["trip_missing_fields"] = result.get("missing_fields", [])
        updates["trip_status"] = "collecting" if result.get("missing_fields") else "ready"
    elif tool_name == "get_trip_context":
        updates["trip_context"] = result
    elif tool_name == "build_itinerary":
        updates["itinerary"] = result
        updates["trip_status"] = "awaiting_revision"

    return updates


def trip_ask(state: AgentState) -> AgentState:
    response = state.get("trip_agent_answer") or "Bạn muốn mình lên kế hoạch theo tiêu chí nào?"
    return {
        "final_response": response,
        "messages": [AIMessage(content=response)],
    }


def trip_finalize(state: AgentState) -> AgentState:
    response = state.get("trip_agent_answer")
    if not response:
        llm = get_llm()
        prompt = build_trip_plan_prompt(
            state.get("trip_constraints", {}),
            state.get("trip_context", {}),
            state.get("itinerary", {}),
        )
        started_at = now()
        message = llm.invoke(prompt)
        metric = build_metric("trip_finalize", started_at, message)
        response = message.content
        return {
            "metrics": append_metric(state.get("metrics"), metric),
            "trip_status": "completed",
            "active_flow": "trip_plan",
            "final_response": response,
            "messages": [AIMessage(content=response)],
        }

    return {
        "trip_status": "completed",
        "active_flow": "trip_plan",
        "final_response": response,
        "messages": [AIMessage(content=response)],
    }


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("route_intent", route_intent)
    graph.add_node("clarify_intent", clarify_intent)

    graph.add_node("faq_extract", faq_extract)
    graph.add_node("faq_agent_decide", faq_agent_decide)
    graph.add_node("faq_search", faq_search)
    graph.add_node("faq_ask", faq_ask)
    graph.add_node("faq_respond", faq_respond)

    graph.add_node("ticket_extract", ticket_extract)
    graph.add_node("ticket_validate", ticket_validate)
    graph.add_node("ticket_ask", ticket_ask)
    graph.add_node("ticket_confirm", ticket_confirm)
    graph.add_node("ticket_create", ticket_create_node)

    graph.add_node("trip_extract", trip_extract)
    graph.add_node("trip_agent_decide", trip_agent_decide)
    graph.add_node("trip_tool_executor", trip_tool_executor)
    graph.add_node("trip_ask", trip_ask)
    graph.add_node("trip_finalize", trip_finalize)

    graph.add_edge(START, "route_intent")

    graph.add_conditional_edges(
        "route_intent",
        lambda state: state["intent"],
        {
            "faq_policy": "faq_extract",
            "ticket_issue": "ticket_extract",
            "trip_plan": "trip_extract",
            "unknown": "clarify_intent",
        },
    )

    graph.add_edge("faq_extract", "faq_agent_decide")
    graph.add_conditional_edges(
        "faq_agent_decide",
        faq_next,
        {
            "ask_user": "faq_ask",
            "call_tool": "faq_search",
            "finish": "faq_respond",
        },
    )
    graph.add_edge("faq_search", "faq_agent_decide")
    graph.add_edge("faq_ask", END)
    graph.add_edge("faq_respond", END)
    graph.add_edge("clarify_intent", END)

    graph.add_edge("ticket_extract", "ticket_validate")
    graph.add_conditional_edges(
        "ticket_validate",
        ticket_next,
        {
            "ticket_ask": "ticket_ask",
            "ticket_confirm": "ticket_confirm",
            "ticket_create": "ticket_create",
        },
    )
    graph.add_edge("ticket_ask", END)
    graph.add_edge("ticket_confirm", END)
    graph.add_edge("ticket_create", END)

    graph.add_edge("trip_extract", "trip_agent_decide")
    graph.add_conditional_edges(
        "trip_agent_decide",
        trip_next,
        {
            "ask_user": "trip_ask",
            "call_tool": "trip_tool_executor",
            "finish": "trip_finalize",
        },
    )
    graph.add_edge("trip_tool_executor", "trip_agent_decide")
    graph.add_edge("trip_ask", END)
    graph.add_edge("trip_finalize", END)

    return graph.compile()

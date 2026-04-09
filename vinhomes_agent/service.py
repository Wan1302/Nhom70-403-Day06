from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from threading import Lock
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from vinhomes_agent.config import FEEDBACK_STORE_PATH, SESSION_STORE_PATH
from vinhomes_agent.graph import build_graph
from vinhomes_agent.state import AgentState


def create_initial_state() -> AgentState:
    return {
        "messages": [],
        "metrics": [],
        "last_trace": [],
        "last_latest_metrics": [],
        "faq_query": {},
        "retrieved_docs": [],
        "faq_status": "idle",
        "faq_agent_answer": "",
        "faq_step_count": 0,
        "faq_clarify_count": 0,
        "ticket_draft": {},
        "trip_constraints": {},
        "trip_context": {},
        "trip_tool_result": {},
        "trip_tool_args": {},
        "trip_scratchpad": [],
        "itinerary": {},
        "ticket_missing_fields": [],
        "trip_missing_fields": [],
        "trip_step_count": 0,
        "trip_status": "idle",
        "ticket_status": "idle",
        "final_response": "",
    }


def summarize_tool_entry(entry: dict) -> str:
    tool_name = entry.get("tool")
    result = entry.get("result", {})

    if tool_name == "get_trip_requirements_helper":
        missing = result.get("missing_fields", [])
        return f"Con thieu: {', '.join(missing)}" if missing else "Da du du kien co ban."
    if tool_name == "get_trip_context":
        places = result.get("places", [])
        return f"Lay context voi {len(places)} dia diem va goi y di chuyen."
    if tool_name == "build_itinerary":
        slots = len(result.get("itinerary", []))
        cost = result.get("estimated_cost_vnd", 0)
        return f"Dung lich trinh {slots} buoi, chi phi du kien {cost:,} VND."
    return "Da thuc thi tool."


class AgentService:
    def __init__(self) -> None:
        load_dotenv()
        self.graph = build_graph()
        self.sessions: dict[str, AgentState] = {}
        self.session_meta: dict[str, dict] = {}
        self.lock = Lock()
        self._load_sessions()

    def _load_sessions(self) -> None:
        if not SESSION_STORE_PATH.exists():
            return
        try:
            payload = json.loads(
                SESSION_STORE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return

        for item in payload.get("sessions", []):
            session_id = item["session_id"]
            self.sessions[session_id] = self.deserialize_state(
                item.get("state", {}))
            self.session_meta[session_id] = {
                "session_id": session_id,
                "title": item.get("title", "Cuộc trò chuyện mới"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "pinned": item.get("pinned", False),
            }

    def _persist_sessions(self) -> None:
        SESSION_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sessions": [
                {
                    "session_id": session_id,
                    "title": self.session_meta.get(session_id, {}).get("title", "Cuộc trò chuyện mới"),
                    "created_at": self.session_meta.get(session_id, {}).get("created_at"),
                    "updated_at": self.session_meta.get(session_id, {}).get("updated_at"),
                    "pinned": self.session_meta.get(session_id, {}).get("pinned", False),
                    "state": self.serialize_state(state),
                }
                for session_id, state in self.sessions.items()
            ]
        }
        SESSION_STORE_PATH.write_text(json.dumps(
            payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def serialize_state(self, state: AgentState) -> dict:
        data = dict(state)
        data["messages"] = self.serialize_messages(state.get("messages", []))
        return data

    def deserialize_state(self, data: dict) -> AgentState:
        state = create_initial_state()
        state.update({k: v for k, v in data.items() if k != "messages"})
        restored_messages = []
        for item in data.get("messages", []):
            if item.get("role") == "assistant":
                restored_messages.append(
                    AIMessage(content=item.get("content", "")))
            else:
                restored_messages.append(HumanMessage(
                    content=item.get("content", "")))
        state["messages"] = restored_messages
        return state

    def _touch_session_meta(self, session_id: str, user_text: str | None = None) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        current = self.session_meta.get(session_id)
        if not current:
            current = {
                "session_id": session_id,
                "title": "Cuộc trò chuyện mới",
                "created_at": now,
                "updated_at": now,
                "pinned": False,
            }
        current["updated_at"] = now
        if user_text and current["title"] == "Cuộc trò chuyện mới":
            current["title"] = user_text.strip()[:52]
        self.session_meta[session_id] = current

    def create_session(self) -> dict:
        session_id = str(uuid4())
        with self.lock:
            self.sessions[session_id] = create_initial_state()
            self._touch_session_meta(session_id)
            self._persist_sessions()
        return {
            "session_id": session_id,
            "session": self.session_meta[session_id],
            "snapshot": self.snapshot(self.sessions[session_id]),
            "summary": self.summary(self.sessions[session_id]),
        }

    def get_state(self, session_id: str) -> AgentState:
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = create_initial_state()
                self._touch_session_meta(session_id)
                self._persist_sessions()
            return self.sessions[session_id]

    def list_sessions(self) -> list[dict]:
        with self.lock:
            items = []
            for session_id, meta in self.session_meta.items():
                state = self.sessions.get(session_id, create_initial_state())
                items.append(
                    {
                        **meta,
                        "intent": state.get("intent"),
                        "active_flow": state.get("active_flow"),
                        "last_reply": state.get("final_response", "")[:42],
                    }
                )
            items.sort(
                key=lambda item: (
                    not item.get("pinned", False),
                    item.get("updated_at") or "",
                ),
                reverse=False,
            )
            items.sort(key=lambda item: item.get(
                "updated_at") or "", reverse=True)
            items.sort(key=lambda item: not item.get("pinned", False))
            return items

    def get_session(self, session_id: str) -> dict:
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = create_initial_state()
                self._touch_session_meta(session_id)
                self._persist_sessions()
            state = self.sessions[session_id]
            meta = self.session_meta[session_id]

        return {
            "session": meta,
            "messages": self.serialize_messages(state.get("messages", [])),
            "summary": self.summary(state),
            "snapshot": self.snapshot(state),
            "trace": state.get("last_trace", []),
            "latest_metrics": state.get("last_latest_metrics", []),
        }

    def delete_session(self, session_id: str) -> dict:
        with self.lock:
            self.sessions.pop(session_id, None)
            self.session_meta.pop(session_id, None)
            self._persist_sessions()
        return {"ok": True, "session_id": session_id}

    def clear_session_history(self, session_id: str) -> dict:
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = create_initial_state()
                self._touch_session_meta(session_id)
            else:
                current_meta = self.session_meta.get(session_id, {})
                title = current_meta.get("title", "Cuoc tro chuyen moi")
                self.sessions[session_id] = create_initial_state()
                self.session_meta[session_id] = {
                    "session_id": session_id,
                    "title": title,
                    "created_at": current_meta.get("created_at") or datetime.now().isoformat(timespec="seconds"),
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "pinned": current_meta.get("pinned", False),
                }
            self._persist_sessions()

        return {
            "ok": True,
            "session_id": session_id,
            "session": self.session_meta[session_id],
            "summary": self.summary(self.sessions[session_id]),
            "snapshot": self.snapshot(self.sessions[session_id]),
            "messages": [],
        }

    def update_session_meta(self, session_id: str, *, title: str | None = None, pinned: bool | None = None) -> dict:
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = create_initial_state()
                self._touch_session_meta(session_id)

            meta = dict(self.session_meta.get(session_id, {}))
            if not meta:
                self._touch_session_meta(session_id)
                meta = dict(self.session_meta[session_id])

            if title is not None:
                cleaned_title = title.strip()[:80]
                if cleaned_title:
                    meta["title"] = cleaned_title

            if pinned is not None:
                meta["pinned"] = pinned

            meta["updated_at"] = datetime.now().isoformat(timespec="seconds")
            self.session_meta[session_id] = meta
            self._persist_sessions()

        return {
            "ok": True,
            "session_id": session_id,
            "session": self.session_meta[session_id],
        }

    def chat(self, session_id: str, user_text: str) -> dict:
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = create_initial_state()
                self._touch_session_meta(session_id)
            state = deepcopy(self.sessions[session_id])

        old_metric_count = len(state.get("metrics", []))
        old_trip_scratchpad_count = len(state.get("trip_scratchpad", []))
        old_message_count = len(state.get("messages", []))

        state["messages"] = [
            *state.get("messages", []), HumanMessage(content=user_text)]
        state = self.graph.invoke(state)

        latest_metrics = state.get("metrics", [])[old_metric_count:]
        latest_trip_steps = state.get("trip_scratchpad", [])[
            old_trip_scratchpad_count:]
        latest_messages = state.get("messages", [])[old_message_count:]
        trace = self.build_trace(state, latest_metrics, latest_trip_steps)

        state["last_trace"] = trace
        state["last_latest_metrics"] = latest_metrics

        with self.lock:
            self.sessions[session_id] = state
            self._touch_session_meta(session_id, user_text)
            self._persist_sessions()
            session = self.session_meta[session_id]

        return {
            "session_id": session_id,
            "session": session,
            "user_message": user_text,
            "reply": state.get("final_response", ""),
            "route": {
                "intent": state.get("intent"),
                "reason": state.get("route_reason"),
                "active_flow": state.get("active_flow"),
            },
            "latest_metrics": latest_metrics,
            "trace": trace,
            "summary": self.summary(state),
            "snapshot": self.snapshot(state),
            "messages": self.serialize_messages(latest_messages),
        }

    def submit_feedback(self, session_id: str, question: str, answer: str, feedback: str) -> dict:
        if feedback not in {"like", "dislike"}:
            raise ValueError("feedback must be 'like' or 'dislike'")

        with self.lock:
            state = self.sessions.get(session_id, create_initial_state())
            meta = self.session_meta.get(session_id, {})
            payload = {
                "feedback_id": str(uuid4()),
                "session_id": session_id,
                "session_title": meta.get("title", "Cuộc trò chuyện mới"),
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "feedback": feedback,
                "question": question.strip(),
                "answer": answer.strip(),
                "intent": state.get("intent"),
                "active_flow": state.get("active_flow"),
                "route_reason": state.get("route_reason"),
            }
            FEEDBACK_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with FEEDBACK_STORE_PATH.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")

        return {"ok": True, "feedback": payload}

    def serialize_messages(self, messages: list) -> list[dict]:
        items = []
        for message in messages:
            role = "assistant" if isinstance(message, AIMessage) else "user"
            items.append({"role": role, "content": message.content})
        return items

    def build_trace(self, state: AgentState, latest_metrics: list[dict], latest_trip_steps: list[dict]) -> list[dict]:
        trace = []
        if state.get("intent"):
            trace.append(
                {
                    "step": len(trace) + 1,
                    "title": f"Router -> {state.get('intent')}",
                    "detail": state.get("route_reason") or "Khong co ly do.",
                    "kind": "route",
                }
            )

        for metric in latest_metrics:
            title = metric["node"]
            detail = (
                f"{metric['elapsed_ms']} ms | in={metric['input_tokens']} | "
                f"out={metric['output_tokens']} | total={metric['total_tokens']}"
            )
            trace.append(
                {
                    "step": len(trace) + 1,
                    "title": title,
                    "detail": detail,
                    "kind": "metric",
                }
            )

        for entry in latest_trip_steps:
            trace.append(
                {
                    "step": len(trace) + 1,
                    "title": f"Tool {entry.get('tool')}",
                    "detail": summarize_tool_entry(entry),
                    "kind": "tool",
                }
            )

        if state.get("ticket_status") == "awaiting_confirmation":
            trace.append(
                {
                    "step": len(trace) + 1,
                    "title": "Ticket dang cho xac nhan",
                    "detail": "Bot da tong hop ban nhap va dang doi user xac nhan.",
                    "kind": "state",
                }
            )
        elif state.get("ticket_status") == "completed":
            trace.append(
                {
                    "step": len(trace) + 1,
                    "title": "Ticket da duoc tao",
                    "detail": state.get("ticket_result", {}).get("ticket_id", ""),
                    "kind": "state",
                }
            )

        if state.get("trip_status") in {"collecting", "planning", "awaiting_revision", "completed"}:
            trace.append(
                {
                    "step": len(trace) + 1,
                    "title": "Trang thai trip",
                    "detail": (
                        f"status={state.get('trip_status')} | "
                        f"vong_lap_tool={state.get('trip_step_count', 0)}"
                    ),
                    "kind": "state",
                }
            )

        return trace

    def summary(self, state: AgentState) -> dict:
        metrics = state.get("metrics", [])
        total_elapsed_ms = round(sum(item.get("elapsed_ms", 0)
                                 for item in metrics), 2)
        total_tokens = sum(item.get("total_tokens", 0) for item in metrics)
        total_input_tokens = sum(item.get("input_tokens", 0)
                                 for item in metrics)
        total_output_tokens = sum(item.get("output_tokens", 0)
                                  for item in metrics)

        return {
            "intent": state.get("intent"),
            "active_flow": state.get("active_flow"),
            "ticket_status": state.get("ticket_status"),
            "trip_status": state.get("trip_status"),
            "trip_step_count": state.get("trip_step_count", 0),
            "total_steps": len(metrics),
            "total_elapsed_ms": total_elapsed_ms,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
        }

    def snapshot(self, state: AgentState) -> dict:
        return {
            "ticket_draft": state.get("ticket_draft", {}),
            "ticket_missing_fields": state.get("ticket_missing_fields", []),
            "ticket_result": state.get("ticket_result", {}),
            "trip_constraints": state.get("trip_constraints", {}),
            "trip_missing_fields": state.get("trip_missing_fields", []),
            "trip_context": state.get("trip_context", {}),
            "trip_tool_name": state.get("trip_tool_name"),
            "trip_tool_result": state.get("trip_tool_result", {}),
            "itinerary": state.get("itinerary", {}),
        }

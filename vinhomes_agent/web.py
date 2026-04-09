from __future__ import annotations

from pathlib import Path

import asyncio
import json
import queue
import threading

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vinhomes_agent.service import AgentService

ROOT_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT_DIR / "webapp"
STATIC_DIR = WEB_DIR / "static"

app = FastAPI(title="Vinhomes Resident Agent")
service = AgentService()


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)


class SessionMetaUpdateRequest(BaseModel):
    title: str | None = None
    pinned: bool | None = None


class FeedbackRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    feedback: str = Field(pattern="^(like|dislike)$")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/chat")
def chat_page() -> FileResponse:
    return FileResponse(WEB_DIR / "chat.html")


@app.get("/sessions")
def sessions_page() -> FileResponse:
    return FileResponse(WEB_DIR / "sessions.html")


@app.post("/api/session")
def create_session() -> dict:
    return service.create_session()


@app.get("/api/sessions")
def list_sessions() -> dict:
    return {"sessions": service.list_sessions()}


@app.get("/api/session/{session_id}")
def get_session(session_id: str) -> dict:
    return service.get_session(session_id)


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str) -> dict:
    return service.delete_session(session_id)


@app.post("/api/session/{session_id}/clear")
def clear_session_history(session_id: str) -> dict:
    return service.clear_session_history(session_id)


@app.patch("/api/session/{session_id}")
def update_session_meta(session_id: str, payload: SessionMetaUpdateRequest) -> dict:
    return service.update_session_meta(session_id, title=payload.title, pinned=payload.pinned)


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict:
    return service.chat(payload.session_id, payload.message)


@app.post("/api/feedback")
def submit_feedback(payload: FeedbackRequest) -> dict:
    return service.submit_feedback(
        payload.session_id,
        payload.question,
        payload.answer,
        payload.feedback,
    )


@app.post("/api/chat/stream")
def chat_stream(payload: ChatRequest):
    """SSE endpoint: trả về từng chunk của reply rồi gửi event 'done' kèm metadata."""
    q: queue.Queue = queue.Queue()

    def run():
        result = service.chat(payload.session_id, payload.message)
        q.put(("result", result))

    threading.Thread(target=run, daemon=True).start()

    def event_gen():
        # Chờ kết quả từ graph (blocking)
        _, result = q.get()
        reply: str = result.get("reply", "")

        # Phân tách chủ ký tự thành các chunk nhỏ (mô phỏng streaming)
        words = reply.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            data = json.dumps({"chunk": chunk}, ensure_ascii=False)
            yield f"data: {data}\n\n"

        # Gửi metadata ở event cuối
        meta = json.dumps({
            "done": True,
            "summary": result.get("summary", {}),
            "session": result.get("session", {}),
            "trace": result.get("trace", []),
        }, ensure_ascii=False)
        yield f"event: done\ndata: {meta}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/ping")
def ping() -> dict:
    return {"ok": True, "message": "pong"}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

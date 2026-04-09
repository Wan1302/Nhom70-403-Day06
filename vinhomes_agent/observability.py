from __future__ import annotations

from time import perf_counter
from typing import Any


def now() -> float:
    return perf_counter()


def extract_token_usage(message: Any) -> dict[str, int]:
    usage = getattr(message, "usage_metadata", None) or {}
    if usage:
        return {
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        }

    response_metadata = getattr(message, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage", {})
    return {
        "input_tokens": int(token_usage.get("prompt_tokens", 0)),
        "output_tokens": int(token_usage.get("completion_tokens", 0)),
        "total_tokens": int(token_usage.get("total_tokens", 0)),
    }


def build_metric(node_name: str, started_at: float, message: Any) -> dict[str, Any]:
    usage = extract_token_usage(message)
    return {
        "node": node_name,
        "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
        **usage,
    }


def append_metric(state_metrics: list[dict[str, Any]] | None, metric: dict[str, Any]) -> list[dict[str, Any]]:
    return [*(state_metrics or []), metric]

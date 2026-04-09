from __future__ import annotations

from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

from vinhomes_agent.graph import build_graph


def main() -> None:
    load_dotenv()
    graph = build_graph()
    state = {
        "messages": [],
        "metrics": [],
        "ticket_draft": {},
        "trip_constraints": {},
    }

    print("Resident assistant demo. Gõ 'exit' để thoát.")

    while True:
        user_text = input("\nBạn: ").strip()
        if user_text.lower() in {"exit", "quit"}:
            break
        if not user_text:
            continue

        old_metric_count = len(state.get("metrics", []))
        state["messages"] = [*state.get("messages", []), HumanMessage(content=user_text)]
        state = graph.invoke(state)
        print(f"\nBot: {state.get('final_response', '')}")

        new_metrics = state.get("metrics", [])[old_metric_count:]
        if new_metrics:
            print("\nMetrics:")
            for item in new_metrics:
                print(
                    f"- {item['node']}: {item['elapsed_ms']} ms | "
                    f"in={item['input_tokens']} | out={item['output_tokens']} | total={item['total_tokens']}"
                )


if __name__ == "__main__":
    main()

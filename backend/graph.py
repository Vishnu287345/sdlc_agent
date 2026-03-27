from langgraph.graph import StateGraph, END
from state import SDLCState
from agents.planner import planner_agent
from agents.architect import architect_agent
from agents.coder import coder_agent
from agents.executor import execution_agent
from agents.debugger import debug_agent
from agents.evaluator import evaluator_agent

MAX_RETRIES = 3


def should_retry(state: SDLCState) -> str:
    # Fix #10: use .get() to avoid KeyError if errors key is missing
    errors = state.get("errors", [])
    retries = state.get("retries", 0)

    if errors and retries < MAX_RETRIES:
        return "debugger"

    # Fix #11: only route to evaluator when execution actually succeeded
    if not errors:
        return "evaluator"

    # Retries exhausted with errors still present — skip evaluation, end cleanly
    return END


def build_graph():
    # Fix #1 & #2: deferred compilation — never runs at import time
    graph = StateGraph(SDLCState)

    graph.add_node("planner", planner_agent)
    graph.add_node("architect", architect_agent)
    graph.add_node("coder", coder_agent)
    graph.add_node("executor", execution_agent)
    graph.add_node("debugger", debug_agent)
    graph.add_node("evaluator", evaluator_agent)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "architect")
    graph.add_edge("architect", "coder")
    graph.add_edge("coder", "executor")
    graph.add_conditional_edges("executor", should_retry)
    graph.add_edge("debugger", "executor")
    graph.add_edge("evaluator", END)

    return graph.compile()

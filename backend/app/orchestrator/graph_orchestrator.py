"""
LangGraph state machine that wires the Planner, RAG/Graph/SQL agents, and the
Report Agent together. This is the single entry point the API layer calls.

Flow:
    plan -> (rag | graph | sql, run in parallel as needed) -> synthesize
"""
from __future__ import annotations

import logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents import graph_agent, planner, rag_agent, report_agent, sql_agent
from app.models.schemas import AgentTrace, GraphFact, SourceChunk

logger = logging.getLogger(__name__)


def _merge_trace(existing: list[AgentTrace], new: list[AgentTrace]) -> list[AgentTrace]:
    return existing + new


class OrchestratorState(TypedDict):
    question: str
    agents_to_run: list[str]
    chunks: list[SourceChunk]
    facts: list[GraphFact]
    sql_rows: list[dict[str, Any]]
    trace: Annotated[list[AgentTrace], _merge_trace]
    answer: str


async def plan_node(state: OrchestratorState) -> dict:
    result = await planner.plan(state["question"])
    return {
        "agents_to_run": result["agents"],
        "trace": [AgentTrace(agent="planner", action="route", detail=result["reasoning"])],
    }


async def rag_node(state: OrchestratorState) -> dict:
    chunks = await rag_agent.retrieve(state["question"])
    return {
        "chunks": chunks,
        "trace": [AgentTrace(agent="rag", action="retrieve", detail=f"{len(chunks)} chunks retrieved")],
    }


async def graph_node(state: OrchestratorState) -> dict:
    facts = await graph_agent.query(state["question"])
    return {
        "facts": facts,
        "trace": [AgentTrace(agent="graph", action="query", detail=f"{len(facts)} facts retrieved")],
    }


async def sql_node(state: OrchestratorState) -> dict:
    rows = await sql_agent.query(state["question"])
    return {
        "sql_rows": rows,
        "trace": [AgentTrace(agent="sql", action="query", detail=f"{len(rows)} rows retrieved")],
    }


async def synthesize_node(state: OrchestratorState) -> dict:
    answer = await report_agent.synthesize(
        question=state["question"],
        chunks=state.get("chunks", []),
        facts=state.get("facts", []),
        sql_rows=state.get("sql_rows", []),
    )
    return {
        "answer": answer,
        "trace": [AgentTrace(agent="report", action="synthesize", detail="final answer generated")],
    }


def _route_after_plan(state: OrchestratorState) -> list[str]:
    """Fan out to whichever retrieval agents the planner selected."""
    agents = state["agents_to_run"]
    targets = []
    if "rag" in agents:
        targets.append("rag")
    if "graph" in agents:
        targets.append("graph")
    if "sql" in agents:
        targets.append("sql")
    return targets or ["rag"]


def build_graph() -> StateGraph:
    graph = StateGraph(OrchestratorState)

    graph.add_node("plan", plan_node)
    graph.add_node("rag", rag_node)
    graph.add_node("graph", graph_node)
    graph.add_node("sql", sql_node)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("plan")
    graph.add_conditional_edges("plan", _route_after_plan, {
        "rag": "rag", "graph": "graph", "sql": "sql",
    })

    # Each retrieval agent flows into synthesis; LangGraph waits for all
    # active branches before running a shared downstream node.
    graph.add_edge("rag", "synthesize")
    graph.add_edge("graph", "synthesize")
    graph.add_edge("sql", "synthesize")
    graph.add_edge("synthesize", END)

    return graph


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


async def run(question: str) -> OrchestratorState:
    app = get_compiled_graph()
    initial_state: OrchestratorState = {
        "question": question,
        "agents_to_run": [],
        "chunks": [],
        "facts": [],
        "sql_rows": [],
        "trace": [],
        "answer": "",
    }
    final_state = await app.ainvoke(initial_state)
    return final_state

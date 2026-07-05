"""
Planner Agent: classifies the incoming question and decides which downstream
agent(s) should handle it. Uses Gemini with a constrained JSON output so the
LangGraph orchestrator can route deterministically.
"""
from __future__ import annotations

import json
import logging

from langchain_google_vertexai import ChatVertexAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

PLANNER_SYSTEM_PROMPT = """You are a routing planner for a GraphRAG assistant.
Given a user question, decide which specialized agents are needed to answer it.

Available agents:
- rag: retrieves semantically relevant document passages (summaries, "what does X say", definitions)
- graph: queries a Neo4j knowledge graph for relationships, connections, multi-hop reasoning
- sql: queries structured relational data (counts, aggregates, "how many", "when did")
- web: searches the public web for information not in the internal knowledge base

Respond ONLY with JSON in this exact shape, no prose, no markdown fences:
{"agents": ["rag", "graph"], "reasoning": "short justification"}

Pick the minimal set of agents required. Combine agents only when the question
genuinely needs evidence from more than one source (e.g. "explain how X influenced Y using evidence"
needs both graph and rag).

Always include "rag" for questions about people, roles, biographies, definitions,
or anything that might be answered from uploaded documents (e.g. "who is X", "what does X do").
"""


def get_llm() -> ChatVertexAI:
    return ChatVertexAI(
        model_name=settings.gemini_model,
        project=settings.project_id,
        location=settings.vertex_location,
        temperature=0,
    )


async def plan(question: str) -> dict:
    llm = get_llm()
    messages = [
        ("system", PLANNER_SYSTEM_PROMPT),
        ("human", question),
    ]
    response = await llm.ainvoke(messages)
    raw = response.content.strip().removeprefix("```json").removesuffix("```").strip()

    try:
        parsed = json.loads(raw)
        agents = [a for a in parsed.get("agents", []) if a in {"rag", "graph", "sql", "web"}]
        if not agents:
            agents = ["rag"]
        return {"agents": agents, "reasoning": parsed.get("reasoning", "")}
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.warning("Planner JSON parse failed (%s); defaulting to rag agent", exc)
        return {"agents": ["rag"], "reasoning": "fallback: planner output was not valid JSON"}

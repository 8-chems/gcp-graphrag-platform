"""
Report Agent: synthesizes the final natural-language answer from whatever
evidence the other agents gathered (document chunks, graph facts, SQL rows).
"""
from __future__ import annotations

from langchain_google_vertexai import ChatVertexAI

from app.core.config import get_settings
from app.models.schemas import GraphFact, SourceChunk

settings = get_settings()

SYNTHESIS_PROMPT = """You are answering a user's question using the evidence below. Cite evidence
naturally in prose (e.g. "according to the document..." or "the graph shows a connection through...").
If evidence is insufficient, say so plainly rather than guessing.

Question: {question}

Document passages:
{chunks}

Knowledge graph facts:
{facts}

SQL query results:
{sql_rows}

Write a clear, direct answer in 2-4 short paragraphs.
"""


def get_llm() -> ChatVertexAI:
    return ChatVertexAI(
        model_name=settings.gemini_model,
        project=settings.project_id,
        location=settings.vertex_location,
        temperature=0.2,
    )


def _format_chunks(chunks: list[SourceChunk]) -> str:
    if not chunks:
        return "(none retrieved)"
    return "\n".join(f"- [{c.source}] {c.content[:500]}" for c in chunks)


def _format_facts(facts: list[GraphFact]) -> str:
    if not facts:
        return "(none retrieved)"
    return "\n".join(f"- {f.subject} --[{f.relation}]--> {f.object}" for f in facts)


def _format_sql(rows: list[dict]) -> str:
    if not rows:
        return "(none retrieved)"
    return "\n".join(str(row) for row in rows[:20])


async def synthesize(
    question: str,
    chunks: list[SourceChunk],
    facts: list[GraphFact],
    sql_rows: list[dict],
) -> str:
    llm = get_llm()
    prompt = SYNTHESIS_PROMPT.format(
        question=question,
        chunks=_format_chunks(chunks),
        facts=_format_facts(facts),
        sql_rows=_format_sql(sql_rows),
    )
    response = await llm.ainvoke(prompt)
    return response.content.strip()

"""
Graph Agent: extracts entities mentioned in the question, then queries Neo4j
either for direct neighbors or for connecting paths between two entities.
Falls back to an LLM-generated Cypher query for open-ended relationship
questions that don't map cleanly to the built-in templates.
"""
from __future__ import annotations

import json
import logging

from langchain_google_vertexai import ChatVertexAI

from app.core.config import get_settings
from app.models.schemas import GraphFact
from app.tools import neo4j_tool

logger = logging.getLogger(__name__)
settings = get_settings()

ENTITY_EXTRACTION_PROMPT = """Extract the named entities (people, organizations, products, concepts)
mentioned in this question. Respond ONLY with JSON: {"entities": ["Alice", "Project X"]}

Question: {question}
"""

CYPHER_GENERATION_PROMPT = """You write read-only Cypher queries for a Neo4j graph made of
(:Entity {{name}}) nodes connected by [:RELATES {{type}}] relationships.

Given the question and the extracted entities, write ONE Cypher query (read-only, no
CREATE/MERGE/DELETE/SET) that would help answer it. Respond with ONLY the Cypher query,
no prose, no markdown fences.

Entities: {entities}
Question: {question}
"""


def get_llm() -> ChatVertexAI:
    return ChatVertexAI(
        model_name=settings.gemini_model,
        project=settings.project_id,
        location=settings.vertex_location,
        temperature=0,
    )


async def extract_entities(question: str) -> list[str]:
    llm = get_llm()
    response = await llm.ainvoke(ENTITY_EXTRACTION_PROMPT.format(question=question))
    raw = response.content.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(raw).get("entities", [])
    except json.JSONDecodeError:
        return []


def _is_read_only(cypher: str) -> bool:
    forbidden = ("CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP", "CALL {")
    upper = cypher.upper()
    return not any(kw in upper for kw in forbidden)


async def query(question: str) -> list[GraphFact]:
    entities = await extract_entities(question)

    facts: list[GraphFact] = []

    if len(entities) >= 2:
        paths = await neo4j_tool.find_connections(entities[0], entities[1])
        for path in paths:
            nodes = path.get("path_nodes", [])
            relations = path.get("path_relations", [])
            for i, rel in enumerate(relations):
                if i + 1 < len(nodes):
                    facts.append(GraphFact(subject=nodes[i], relation=rel, object=nodes[i + 1]))
        if facts:
            return facts

    if len(entities) == 1:
        neighbors = await neo4j_tool.neighbors_of(entities[0])
        for row in neighbors:
            facts.append(GraphFact(subject=entities[0], relation=row["relation"], object=row["neighbor"]))
        if facts:
            return facts

    # Fallback: let the LLM draft a Cypher query for open-ended graph questions
    llm = get_llm()
    response = await llm.ainvoke(
        CYPHER_GENERATION_PROMPT.format(entities=json.dumps(entities), question=question)
    )
    cypher = response.content.strip().removeprefix("```cypher").removeprefix("```").removesuffix("```").strip()

    if not cypher or not _is_read_only(cypher):
        logger.warning("Rejected generated Cypher (not read-only or empty): %s", cypher)
        return facts

    try:
        rows = await neo4j_tool.run_cypher(cypher)
    except Exception as exc:  # noqa: BLE001
        logger.error("Generated Cypher failed: %s | query=%s", exc, cypher)
        return facts

    for row in rows[:20]:
        values = list(row.values())
        if len(values) >= 3:
            facts.append(GraphFact(subject=str(values[0]), relation=str(values[1]), object=str(values[2])))

    return facts

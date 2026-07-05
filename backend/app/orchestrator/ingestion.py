"""
Ingestion pipeline triggered when a user uploads a document:

    PDF bytes -> text extraction -> semantic chunking
        -> [embeddings -> BigQuery]  (parallel)
        -> [entity/relationship extraction -> Neo4j]  (parallel)
"""
from __future__ import annotations

import json
import logging
import re
import uuid

from langchain_google_vertexai import ChatVertexAI
from pypdf import PdfReader
from io import BytesIO

from app.core.config import get_settings
from app.tools import neo4j_tool, sql_tool, vector_tool
from app.tools.vector_tool import Chunk

logger = logging.getLogger(__name__)
settings = get_settings()

ENTITY_RELATION_PROMPT = """Extract factual (subject, relation, object) triples from this text.
Keep relation labels short and UPPER_SNAKE_CASE (e.g. WORKS_AT, TREATS, LOCATED_IN).
Respond ONLY with JSON: {{"triples": [["Alice", "WORKS_AT", "Acme Corp"], ...]}}
Return at most 15 triples. If none are found, return {{"triples": []}}.

Text:
{text}
"""


def extract_text_from_pdf(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def semantic_chunk(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """Simple sliding-window chunker on sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) > chunk_size and current:
            chunks.append(current.strip())
            current = current[-overlap:] + " " + sentence
        else:
            current += " " + sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks


def get_llm() -> ChatVertexAI:
    return ChatVertexAI(
        model_name=settings.gemini_model,
        project=settings.project_id,
        location=settings.vertex_location,
        temperature=0,
    )


async def extract_triples(text: str) -> list[tuple[str, str, str]]:
    llm = get_llm()
    response = await llm.ainvoke(ENTITY_RELATION_PROMPT.format(text=text[:3000]))
    raw = response.content.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        parsed = json.loads(raw)
        return [tuple(t) for t in parsed.get("triples", []) if len(t) == 3]
    except json.JSONDecodeError:
        logger.warning("Failed to parse entity extraction response")
        return []


async def ingest_document(data: bytes, filename: str, gcs_path: str) -> dict:
    document_id = await sql_tool.record_document(filename=filename, gcs_path=gcs_path)
    chunks_created = 0
    entities: set[str] = set()
    relationships_created = 0

    try:
        text = extract_text_from_pdf(data)
        if not text.strip():
            raise ValueError("PDF contains no extractable text")

        chunk_texts = semantic_chunk(text)
        chunks = [
            Chunk(chunk_id=str(uuid.uuid4()), document_id=document_id, content=c, source=filename)
            for c in chunk_texts
        ]

        chunks_created = vector_tool.upsert_chunks(chunks) if chunks else 0

        all_triples: list[tuple[str, str, str]] = []
        for chunk_text in chunk_texts:
            triples = await extract_triples(chunk_text)
            all_triples.extend(triples)

        if all_triples:
            try:
                await neo4j_tool.ensure_constraints()
                relationships_created = await neo4j_tool.upsert_triples(all_triples, document_id)
                for s, _, o in all_triples:
                    entities.update([s, o])
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Neo4j graph ingestion skipped for %s (%s): %s",
                    filename,
                    document_id,
                    exc,
                )

        await sql_tool.update_document_stats(
            document_id=document_id,
            chunks=chunks_created,
            entities=len(entities),
            relationships=relationships_created,
            status="completed",
        )

        return {
            "document_id": document_id,
            "filename": filename,
            "chunks_created": chunks_created,
            "entities_extracted": len(entities),
            "relationships_extracted": relationships_created,
            "status": "completed",
        }
    except Exception:
        await sql_tool.update_document_stats(
            document_id=document_id,
            chunks=chunks_created,
            entities=len(entities),
            relationships=relationships_created,
            status="failed",
        )
        raise

"""RAG Agent: retrieves the most semantically relevant document chunks for a question."""
from __future__ import annotations

import logging

from app.models.schemas import SourceChunk
from app.tools import vector_tool

logger = logging.getLogger(__name__)


async def retrieve(question: str, top_k: int = 5) -> list[SourceChunk]:
    try:
        rows = vector_tool.semantic_search(question, top_k=top_k)
    except Exception as exc:  # noqa: BLE001
        logger.error("Vector search failed: %s", exc)
        return []

    if not rows:
        logger.warning("Vector search returned no chunks for question: %s", question[:120])

    return [
        SourceChunk(
            content=row["content"],
            source=row.get("source", row.get("document_id", "unknown")),
            score=1 - float(row.get("distance", 0.0)),  # convert distance -> similarity
        )
        for row in rows
    ]

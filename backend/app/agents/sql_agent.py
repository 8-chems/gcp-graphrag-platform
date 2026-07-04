"""
SQL Agent: translates a natural-language question into a read-only SQL query
against the application's Cloud SQL schema, executes it, and returns rows.
"""
from __future__ import annotations

import logging
import re

from langchain_google_vertexai import ChatVertexAI

from app.core.config import get_settings
from app.tools import sql_tool

logger = logging.getLogger(__name__)
settings = get_settings()

SCHEMA_DESCRIPTION = """
Tables available:

documents(id UUID, filename TEXT, gcs_path TEXT, status TEXT,
          chunks_created INT, entities_extracted INT, relationships_extracted INT,
          created_at TIMESTAMPTZ)

chat_sessions(id UUID, user_id TEXT, created_at TIMESTAMPTZ)

chat_messages(id UUID, session_id UUID, role TEXT, content TEXT,
              used_agents TEXT[], created_at TIMESTAMPTZ)
"""

SQL_GENERATION_PROMPT = f"""You write a single read-only PostgreSQL SELECT query to answer the
user's question, given this schema:

{SCHEMA_DESCRIPTION}

Rules:
- Only SELECT statements. Never write/modify data.
- Use explicit column lists, avoid SELECT *.
- Respond with ONLY the SQL query, no prose, no markdown fences.

Question: {{question}}
"""

FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|CREATE|MERGE)\b", re.IGNORECASE
)


def get_llm() -> ChatVertexAI:
    return ChatVertexAI(
        model_name=settings.gemini_model,
        project=settings.project_id,
        location=settings.vertex_location,
        temperature=0,
    )


def _is_safe_select(sql: str) -> bool:
    stripped = sql.strip().rstrip(";")
    return stripped.upper().startswith("SELECT") and not FORBIDDEN_PATTERN.search(stripped)


async def query(question: str) -> list[dict]:
    llm = get_llm()
    response = await llm.ainvoke(SQL_GENERATION_PROMPT.format(question=question))
    sql = response.content.strip().removeprefix("```sql").removeprefix("```").removesuffix("```").strip()

    if not _is_safe_select(sql):
        logger.warning("Rejected unsafe / non-SELECT SQL from agent: %s", sql)
        return []

    try:
        return await sql_tool.run_readonly_query(sql)
    except Exception as exc:  # noqa: BLE001
        logger.error("SQL agent query failed: %s | sql=%s", exc, sql)
        return []

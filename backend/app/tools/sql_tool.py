"""
Async SQLAlchemy engine for Cloud SQL (PostgreSQL). Used by the SQL Agent to
answer structured questions (counts, aggregates, lookups over relational data)
and to persist chat session / ingestion metadata.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.sql_url, pool_size=5, max_overflow=5, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def session_scope():
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS documents (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        filename TEXT NOT NULL,
        gcs_path TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',
        chunks_created INT DEFAULT 0,
        entities_extracted INT DEFAULT 0,
        relationships_extracted INT DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id UUID REFERENCES chat_sessions(id),
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        used_agents TEXT[],
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
]


async def run_migrations() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        for ddl in DDL_STATEMENTS:
            await conn.execute(text(ddl))


async def run_readonly_query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """
    Execute a read-only SQL query for the SQL Agent. Callers are responsible
    for ensuring `sql` only contains SELECT statements (enforced upstream by
    the agent's prompt + a regex guard before this function is invoked).
    """
    async with session_scope() as session:
        result = await session.execute(text(sql), params or {})
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]


async def record_document(filename: str, gcs_path: str) -> str:
    async with session_scope() as session:
        result = await session.execute(
            text(
                "INSERT INTO documents (filename, gcs_path) VALUES (:filename, :gcs_path) "
                "RETURNING id"
            ),
            {"filename": filename, "gcs_path": gcs_path},
        )
        return str(result.scalar_one())


async def list_documents(limit: int = 200) -> list[dict[str, Any]]:
    async with session_scope() as session:
        result = await session.execute(
            text(
                """
                SELECT id, filename, gcs_path, status, chunks_created,
                       entities_extracted, relationships_extracted, created_at
                FROM documents
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        columns = result.keys()
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        for row in rows:
            row["id"] = str(row["id"])
        return rows


async def get_document(document_id: str) -> dict[str, Any] | None:
    async with session_scope() as session:
        result = await session.execute(
            text(
                """
                SELECT id, filename, gcs_path, status, chunks_created,
                       entities_extracted, relationships_extracted, created_at
                FROM documents WHERE id = :id
                """
            ),
            {"id": document_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        record = dict(zip(result.keys(), row))
        record["id"] = str(record["id"])
        return record


async def delete_document_record(document_id: str) -> None:
    async with session_scope() as session:
        await session.execute(text("DELETE FROM documents WHERE id = :id"), {"id": document_id})


async def update_document_stats(
    document_id: str, chunks: int, entities: int, relationships: int, status: str
) -> None:
    async with session_scope() as session:
        await session.execute(
            text(
                """
                UPDATE documents
                SET chunks_created = :chunks,
                    entities_extracted = :entities,
                    relationships_extracted = :relationships,
                    status = :status
                WHERE id = :id
                """
            ),
            {
                "chunks": chunks,
                "entities": entities,
                "relationships": relationships,
                "status": status,
                "id": document_id,
            },
        )

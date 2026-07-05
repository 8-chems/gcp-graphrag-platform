"""
Embedding + semantic retrieval tool.

Embeddings are generated with Vertex AI's text-embedding model and stored in
BigQuery, which supports native vector search (VECTOR_SEARCH / ML.PREDICT)
without needing a separate vector database for moderate-scale corpora.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from google.cloud import bigquery
from langchain_google_vertexai import VertexAIEmbeddings

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_embeddings_client: VertexAIEmbeddings | None = None
_bq_client: bigquery.Client | None = None


def get_embeddings_client() -> VertexAIEmbeddings:
    global _embeddings_client
    if _embeddings_client is None:
        _embeddings_client = VertexAIEmbeddings(
            model_name=settings.embedding_model,
            project=settings.project_id,
            location=settings.vertex_location,
        )
    return _embeddings_client


def get_bq_client() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=settings.project_id)
    return _bq_client


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    content: str
    source: str


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = get_embeddings_client()
    return client.embed_documents(texts)


def embed_query(text: str) -> list[float]:
    client = get_embeddings_client()
    return client.embed_query(text)


def full_table_id() -> str:
    return f"{settings.project_id}.{settings.bq_dataset}.{settings.bq_vector_table}"


def ensure_table() -> None:
    client = get_bq_client()
    schema = [
        bigquery.SchemaField("chunk_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("document_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source", "STRING"),
        bigquery.SchemaField("content", "STRING"),
        bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
    ]
    table_ref = bigquery.Table(full_table_id(), schema=schema)
    client.create_table(table_ref, exists_ok=True)


def upsert_chunks(chunks: list[Chunk]) -> int:
    """Embed and insert chunks into BigQuery."""
    ensure_table()
    client = get_bq_client()
    vectors = embed_texts([c.content for c in chunks])

    rows = [
        {
            "chunk_id": c.chunk_id or str(uuid.uuid4()),
            "document_id": c.document_id,
            "source": c.source,
            "content": c.content,
            "embedding": vec,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        for c, vec in zip(chunks, vectors)
    ]
    errors = client.insert_rows_json(full_table_id(), rows)
    if errors:
        logger.error("BigQuery insert errors: %s", errors)
        raise RuntimeError(f"BigQuery insert failed: {errors}")
    return len(rows)


def semantic_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Run a cosine-similarity vector search over stored chunk embeddings using
    BigQuery's VECTOR_SEARCH table function.
    """
    client = get_bq_client()
    query_vector = embed_query(query)

    sql = f"""
    SELECT
      base.chunk_id,
      base.document_id,
      base.source,
      base.content,
      distance
    FROM VECTOR_SEARCH(
      TABLE `{full_table_id()}`,
      'embedding',
      (SELECT @query_vector AS embedding),
      top_k => @top_k,
      distance_type => 'COSINE'
    ) AS base
    ORDER BY distance ASC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("query_vector", "FLOAT64", query_vector),
            bigquery.ScalarQueryParameter("top_k", "INT64", top_k),
        ]
    )
    results = client.query(sql, job_config=job_config).result()
    return [dict(row) for row in results]


def delete_by_document(document_id: str) -> None:
    """Remove all stored chunk embeddings belonging to a document (admin delete)."""
    client = get_bq_client()
    sql = f"DELETE FROM `{full_table_id()}` WHERE document_id = @document_id"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("document_id", "STRING", document_id)]
    )
    client.query(sql, job_config=job_config).result()

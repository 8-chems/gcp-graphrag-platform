from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import get_current_admin, get_current_user
from app.core.config import get_settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    DocumentSummary,
    HealthResponse,
    IngestResponse,
)
from app.orchestrator import graph_orchestrator, ingestion
from app.tools import neo4j_tool, sql_tool, storage_tool, vector_tool

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    neo4j_ok = await neo4j_tool.verify_connectivity()
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
        dependencies={"neo4j": neo4j_ok},
    )


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict:
    """Lets the frontend decide which UI (user chat vs admin dashboard) to render."""
    is_admin = user.get("admin") is True or (
        (user.get("email") or "").lower() in settings.admin_email_list and user.get("email_verified")
    )
    return {
        "uid": user.get("uid"),
        "email": user.get("email"),
        "is_admin": is_admin,
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())

    try:
        result = await graph_orchestrator.run(request.question)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Orchestrator run failed")
        raise HTTPException(status_code=500, detail="Failed to process question") from exc

    return ChatResponse(
        answer=result["answer"],
        used_agents=result["agents_to_run"],
        sources=result.get("chunks", []),
        graph_facts=result.get("facts", []),
        trace=result.get("trace", []),
        session_id=session_id,
    )


# --- Document management: admin-only, enforced server-side via get_current_admin ---


@router.post("/admin/documents/upload", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    admin: dict = Depends(get_current_admin),
) -> IngestResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    data = await file.read()
    gcs_path = storage_tool.upload_bytes(data, filename=file.filename, content_type=file.content_type)

    try:
        result = await ingestion.ingest_document(data, filename=file.filename, gcs_path=gcs_path)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ingestion failed for %s", file.filename)
        raise HTTPException(status_code=500, detail="Document ingestion failed") from exc

    return IngestResponse(**result)


@router.get("/admin/documents", response_model=list[DocumentSummary])
async def list_documents(admin: dict = Depends(get_current_admin)) -> list[DocumentSummary]:
    rows = await sql_tool.list_documents()
    return [DocumentSummary(**row) for row in rows]


@router.delete("/admin/documents/{document_id}")
async def delete_document(document_id: str, admin: dict = Depends(get_current_admin)) -> dict:
    doc = await sql_tool.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    errors: list[str] = []

    try:
        storage_tool.delete_blob(doc["gcs_path"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("GCS delete failed for %s: %s", document_id, exc)
        errors.append("storage")

    try:
        vector_tool.delete_by_document(document_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("BigQuery delete failed for %s: %s", document_id, exc)
        errors.append("vector_store")

    try:
        await neo4j_tool.delete_by_document(document_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Neo4j delete failed for %s: %s", document_id, exc)
        errors.append("graph")

    await sql_tool.delete_document_record(document_id)

    return {"document_id": document_id, "deleted": True, "partial_failures": errors}

